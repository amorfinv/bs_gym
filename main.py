# copied from https://squadrick.dev/journal/efficient-multi-gym-environments.html

import gym
import pickle
import cloudpickle
import numpy as np

from multiprocessing import Pipe, Process

def main():
    make_mp_envs()


def make_mp_envs(env_id, num_env, seed, start_idx = 0):
	def make_env(rank):
		def fn():
			env = gym.make(env_id)
			env.seed(seed + rank)
			return env
		return fn
	return SubprocVecEnv([make_env(i + start_idx) for i in range(num_env)])

class SubprocVecEnv():
	def __init__(self, env_fns):
		self.waiting = False
		self.closed = False
		no_of_envs = len(env_fns)
		self.remotes, self.work_remotes = \
			zip(*[Pipe() for _ in range(no_of_envs)])
		self.ps = []
		
		for wrk, rem, fn in zip(self.work_remotes, self.remotes, env_fns):
			proc = Process(target = worker, 
				args = (wrk, rem, CloudpickleWrapper(fn)))
			self.ps.append(proc)

		for p in self.ps:
			p.daemon = True
			p.start()

		for remote in self.work_remotes:
			remote.close()
    
	def step_async(self, actions):
		if self.waiting:
			raise AlreadySteppingError
		self.waiting = True

		for remote, action in zip(self.remotes, actions):
			remote.send(('step', action))
    
	
	def step_wait(self):
		if not self.waiting:
			raise NotSteppingError
		self.waiting = False

		results = [remote.recv() for remote in self.remotes]
		obs, rews, dones, infos = zip(*results)
		return np.stack(obs), np.stack(rews), np.stack(dones), info
	
	def step(self, actions):
		self.step_async(actions)
		return self.step_wait()
	
	def reset(self):
		for remote in self.remotes:
			remote.send(('reset', None))

		return np.stack([remote.recv() for remote in self.remotes])
	
	def close(self):
		if self.closed:
			return
		if self.waiting:
			for remote in self.remotes:
				remote.recv()
		for remote in self.remotes:
			remote.send(('close', None))
		for p in self.ps:
			p.join()
		self.closed = True

class CloudpickleWrapper(object):
	def __init__(self, x):
		self.x = x

	def __getstate__(self):
		return cloudpickle.dumps(self.x)

	def __setstate__(self, ob):
		self.x = pickle.loads(ob)
	
	def __call__(self):
		return self.x()

def worker(remote, parent_remote, env_fn):
	parent_remote.close()
	env = env_fn()
	while True:
		cmd, data = remote.recv()
		
		if cmd == 'step':
			ob, reward, done, info = env.step(data)
			if done:
				ob = env.reset()
			remote.send((ob, reward, done, info))

		elif cmd == 'render':
			remote.send(env.render())

		elif cmd == 'close':
			remote.close()
			break

		else:
			raise NotImplentedError