import time

import numpy as np

from env_wrappers.husk_environment import env_makers
from final_experiments.runners.bimodal import train_vision_and_sound
from final_experiments.wrappers.avoid_damage import AvoidDamageWrapper
from final_experiments.wrappers.bimodal import BimodalWrapper
from final_experiments.wrappers.simple_navigation import SimpleNavigationWrapper
from models.dueling_bimodal_dqn import DuelingBiModalDQNAgent


def solved_criterion(avg_score, test_score, avg_test_score, episode):
    if episode < 500:
        return False
    if avg_score < 195.0:
        return False
    if test_score < 198.0:
        return False
    if avg_test_score is None:
        return True
    if avg_test_score < 195.0:
        return False
    return True


def run_experiment():
    seed = int(time.time())
    np.random.seed(seed)

    verbose = False
    env_path = None
    port = 8003
    inner_env, sound_list = env_makers["husk-random-forest"](
        verbose, env_path, port, hud_hidden=True
    )
    env = AvoidDamageWrapper(
        BimodalWrapper(
            SimpleNavigationWrapper(
                inner_env, num_actions=SimpleNavigationWrapper.JUMP + 1
            ),
            x_dim=114,
            y_dim=64,
            sound_list=sound_list,
            sound_coord_dim=3,
        )
    )

    train_vision_and_sound(
        group="forest_bimodal",
        env=env,
        agent_class=DuelingBiModalDQNAgent,
        # env_name="husk-random-terrain",
        batch_size=256,
        gamma=0.99,
        learning_rate=0.00001,
        update_freq=1000,
        hidden_dim=128,
        kernel_size=5,
        stride=2,
        weight_decay=0.00001,
        buffer_size=1000000,
        epsilon_init=1.0,
        epsilon_decay=0.99,
        epsilon_min=0.01,
        max_steps_per_episode=400,
        num_episodes=3000,
        warmup_episodes=10,
        solved_criterion=solved_criterion,
    )


if __name__ == "__main__":
    run_experiment()
