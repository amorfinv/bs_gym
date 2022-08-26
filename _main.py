import bs_env
from stable_baselines3.common.env_checker import check_env

env = bs_env.BS_Gym()

check_env(env)