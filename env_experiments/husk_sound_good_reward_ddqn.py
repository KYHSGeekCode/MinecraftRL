from collections import deque
from typing import Tuple

from env_experiments.train_sound import train_sound

health_deque = deque(maxlen=2)


def reward_function(obs) -> Tuple[float, bool]:
    if obs.is_dead:
        health_deque.append(20)
        return -1, True
    health_deque.append(obs.health)
    if health_deque[0] < health_deque[1]:
        return -0.1, False
    return 0.5, False


if __name__ == "__main__":
    health_deque.append(20)
    train_sound(
        verbose=False,
        env_path=None,
        port=8004,
        agent="DDQNAgent",
        env_name="husk",
        batch_size=256,
        gamma=0.99,
        learning_rate=0.00001,
        update_freq=1000,
        hidden_dim=128,
        weight_decay=0.00001,
        buffer_size=1000000,
        epsilon_init=1.0,
        epsilon_decay=0.99,
        epsilon_min=0.01,
        max_steps_per_episode=400,
        num_episodes=2000,
        warmup_episodes=0,
        reward_function=reward_function,
    )