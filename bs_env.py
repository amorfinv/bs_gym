import gym
from gym import spaces
import bluesky as bs
from bluesky.simulation import ScreenIO
import numpy as np

class BS_Gym(gym.Env):
    """Custom Environment that follows gym interface"""
    metadata = {'render.modes': []}

    def __init__(self):
        super(BS_Gym, self).__init__()

        bs.stack.stack('DT 1;FF')
        # initialize bluesky as non-networked simulation node
        bs.init(mode='sim', detached=True)
        # initialize dummy screen
        bs.scr = ScreenDummy()

        # Define action and observation space
        # They must be gym.spaces objects
        # Example when using discrete actions:
        self.action_space = spaces.Box(low=np.array([-1.0]), high=np.array([1.0]), dtype=np.float32)
        # Example for using image as input:
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(1, 3), dtype=np.float32)
    
    def step(self, action):
        self.do_action(action)
        bs.sim.step()
        observation, reward, done = self.get_update()
        info = {}

        return observation, reward, done, info

    def reset(self):
        for acid in bs.traf.id:
            idx = bs.traf.id2idx(acid)
            bs.traf.delete(idx)

        bs.traf.cre('KL001',actype="A320",acalt=3000,acspd=150)
        observation = self.get_state()
        return observation  # reward, done, info can't be included

    def render(self, mode='human'):
        pass

    def close (self):
        bs.sim.quit()

    def get_state(self):
        # get current altitude, vertical speed and distance to the runway (set at 200km from origin)
        alt = bs.traf.alt[0]
        vs = bs.traf.vs[0]
        dis =(200 - bs.tools.geo.kwikdist(52,4,bs.traf.lat[0],bs.traf.lon[0])*1.852)

        # (roughly) normalize the state values to a mean of zero and variance 1
        # (for more complex environments its better to calculate the mean and std over 
        # a series of interactions with the environment)
        alt = (alt - 1500)/3000
        vs = vs / 5
        dis = (dis - 100)/200

        state = [alt,vs,dis]

        return state

    def get_reward(self,state):
        # denormalize the relevant state variables
        alt = (state[0]*3000)+1500
        dis = (state[2]*200)+100

        # reward part of the function
        if dis > 0 and alt> 0:
            return abs(3000-alt)*-5/3000, 0
        elif alt <= 0:
            return -100, 1
        elif dis <= 0:
            return abs(100-alt)*-50/3000, 1
    
    def get_update(self):
        state_ = self.get_state()
        reward, done = self.get_reward(state_)
        return state_, reward, done
    
    def do_action(self,action):
        """
        do_action(action) takes the output of the RL model and translates it to an action intepretable 
        by Blueksy. As the output of the RL model is -1 < action < 1, we first map it to sensible values.
        Then the action is executed through stack commands in the Bluesky simulator.
        """
        # Transform action to the feet per minute domain
        action = action * 2500

        # Get aircraft ID of the controlled aircraft
        acid = bs.traf.id[0]

        # Bluesky interpretes vertical velocity command through altitude commands 
        # with a vertical speed (magnitude). So check sign of action and give arbitrary 
        # altitude command

        # The actions are then executed through stack commands;
        if -250<action<250:
            bs.stack.stack(f'ALT {acid},{bs.traf.alt[0]},{250}')
        if action > 0:
            bs.stack.stack(f'ALT {acid},45000,{action}')
        if action < 0:
            bs.stack.stack(f'ALT {acid},0,{-action}')

class ScreenDummy(ScreenIO):
    """
    Dummy class for the screen. Inherits from ScreenIO to make sure all the
    necessary methods are there. This class is there to reimplement the echo
    method so that console messages are printed.
    """
    def echo(self, text='', flags=0):
        """Just print echo messages"""
        print("BlueSky console:", text)