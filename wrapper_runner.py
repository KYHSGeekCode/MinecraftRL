import glob
import os
import time
from collections import deque

import matplotlib.pyplot as plt
import numpy as np

import wandb
from models.dqn import DQNAgent
from mydojo.MyEnv import print_with_time
from gymnasium.wrappers.monitoring.video_recorder import VideoRecorder


class WrapperRunner:
    def __init__(
        self,
        env,
        env_name,
        agent,
        max_steps_per_episode,
        num_episodes,
        warmup_episodes,
        update_frequency,
        epsilon_init,
        epsilon_min,
        epsilon_decay,
        solved_criterion,
        test_frequency,
        max_saved_models=2,
    ):
        config = {
            "environment": env_name,
            "architecture": "DQNAgent",
            "max_steps_per_episode": max_steps_per_episode,
            "num_episodes": num_episodes,
            "warmup_episodes": warmup_episodes,
            "update_frequency": update_frequency,
            "test_frequency": test_frequency,
            "epsilon_init": epsilon_init,
            "epsilon_min": epsilon_min,
            "epsilon_decay": epsilon_decay,
        }
        config.update(agent.config)
        wandb.init(
            # set the wandb project where this run will be logged
            project="mydojo",
            entity="jourhyang123",
            # track hyperparameters and run metadata
            config=config,
            resume=False,
        )
        # define our custom x axis metric
        wandb.define_metric("test/step")
        # define which metrics will be plotted against it
        wandb.define_metric("test/*", step_metric="test/step")
        import models.dqn

        models.dqn.after_wandb_init()
        self.env = env
        self.agent = agent
        self.max_steps_per_episode = max_steps_per_episode
        self.num_episodes = num_episodes
        self.warmup_episodes = warmup_episodes
        self.update_frequency = update_frequency
        self.test_frequency = test_frequency
        self.epsilon_init = epsilon_init
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.solved_criterion = solved_criterion
        self.model_dir = os.path.join(wandb.run.dir, env_name)
        self.local_plot_filename = os.path.join(self.model_dir, f"{env_name}.png")
        self.max_saved_models = max_saved_models
        if not os.path.exists(self.model_dir):
            os.makedirs(self.model_dir)

    def save_score_plot(self, scores, avg_scores):
        # Remove the file if it already exists
        if os.path.isfile(self.local_plot_filename):
            os.remove(self.local_plot_filename)

        # Create the plot
        x = np.arange(len(scores))
        fig, ax = plt.subplots()
        ax.plot(x, scores, label="Score")
        ax.plot(x, avg_scores, label="Avg Score")
        ax.set_xlabel("Episode")
        ax.set_ylabel("Score")
        ax.legend()

        # Save the plot to a file
        plt.savefig(self.local_plot_filename)
        plt.close(fig)

    def load_latest_model(self, agent):
        # Find the latest saved model file
        list_of_files = glob.glob(os.path.join(self.model_dir, "*.pt"))
        if len(list_of_files) == 0:
            return 0, 1.0  # No saved models

        latest_file = max(list_of_files, key=os.path.getctime)

        episode_number = int(latest_file.split("episode_")[1].split(".")[0])
        # Load the model from the file
        epsilon_ = agent.load(latest_file)
        return episode_number, epsilon_

    def save_model(self, episode: int, agent: DQNAgent, epsilon: float):
        model_path = os.path.join(self.model_dir, f"model_episode_{episode}.pt")
        agent.save(model_path, epsilon)
        # Delete oldest saved model if there are more than max_saved_models
        saved_models = sorted(
            os.listdir(self.model_dir),
            key=lambda x: os.path.getctime(os.path.join(self.model_dir, x)),
        )
        while len(saved_models) > self.max_saved_models:
            oldest_model_path = os.path.join(self.model_dir, saved_models[0])
            os.remove(oldest_model_path)
            saved_models.pop(0)

    def run_wrapper(self, record_video=False):
        if record_video:
            wandb.gym.monitor()
        initial_episode = 0
        epsilon = self.epsilon_init

        if wandb.run.resumed:
            initial_episode, epsilon = self.load_latest_model(self.agent)

        recent_scores = deque(maxlen=30)
        scores = []
        avg_scores = []
        for episode in range(initial_episode, self.num_episodes):
            testing = False
            if episode % self.test_frequency == 0:
                testing = True
                if record_video:
                    video_recorder = VideoRecorder(self.env, f"video{episode}.mp4")

            state = self.env.reset(fast_reset=True)
            print_with_time("Finished resetting the environment")
            episode_reward = 0

            sum_time = 0
            num_steps = 0
            for step in range(self.max_steps_per_episode):
                start_time = time.time()
                if testing and record_video:
                    video_recorder.capture_frame()

                if episode < self.warmup_episodes:
                    action = self.env.action_space.sample()
                else:
                    action = self.agent.select_action(state, epsilon, testing)
                next_state, reward, terminated, truncated, info = self.env.step(action)
                episode_reward += reward

                self.agent.add_experience(state, action, next_state, reward, terminated)
                self.agent.update_model()

                if step % self.update_frequency == 0:
                    self.agent.update_target_model()

                if terminated:
                    break

                state = next_state
                elapsed_time = time.time() - start_time
                # print(f"Step {step} took {elapsed_time:.5f} seconds")
                sum_time += elapsed_time
                num_steps += 1

            if num_steps == 0:
                num_steps = 1
            print(
                f"Seconds per episode{episode}: {sum_time}/{num_steps}={sum_time / num_steps:.5f} seconds"
            )
            # Save the agent's model
            self.save_model(episode, self.agent, epsilon)

            scores.append(episode_reward)
            recent_scores.append(episode_reward)
            avg_score = np.mean(recent_scores)
            avg_scores.append(avg_score)
            print(
                f"Episode {episode}: score={episode_reward:.2f}, avg_score={avg_score:.2f}, eps={epsilon:.2f}"
            )
            if testing:
                video_recorder.close()

            if testing:
                wandb.log({"test/score": episode_reward, "test/step": episode})
            else:
                wandb.log(
                    {
                        "episode": episode,
                        "score": episode_reward,
                        "avg_score": avg_score,
                        "epsilon": epsilon,
                    }
                )

            self.save_score_plot(scores, avg_scores)
            if episode >= self.warmup_episodes:
                epsilon = max(self.epsilon_min, self.epsilon_decay * epsilon)

            if self.solved_criterion(avg_score, episode):
                print(f"Solved in {episode} episodes!")
                break

        self.env.close()
        wandb.finish()
