import gym, gym.spaces, gym.utils, gym.utils.seeding
import numpy as np
import pybullet as p
import os


class PybulletMujocoXmlEnv(gym.Env):
	"""
	Base class for MuJoCo .xml actors in a Scene.
	These environments create single-player scenes and behave like normal Gym environments, if
	you don't use multiplayer.
	"""

	metadata = {
		'render.modes': ['human', 'rgb_array'],
		'video.frames_per_second': 60
		}

	self_collision = False

	def __init__(self, model_xml, robot_name, action_dim, obs_dim):
		self.scene = None

		self.parts = None
		self.jdict = None
		self.ordered_joints = None
		self.robot_body = None

		high = np.ones([action_dim])
		self.action_space = gym.spaces.Box(-high, high)
		high = np.inf*np.ones([obs_dim])
		self.observation_space = gym.spaces.Box(-high, high)
		self._seed()

		self.model_xml = model_xml
		self.robot_name = robot_name

		self.camera = Camera()

	def _seed(self, seed=None):
		self.np_random, seed = gym.utils.seeding.np_random(seed)
		return [seed]

	def addToScene(self, bodies):
		if self.parts is not None:
			parts = self.parts
		else:
			parts = {}

		if self.jdict is not None:
			joints = self.jdict
		else:
			joints = {}

		if self.ordered_joints is not None:
			ordered_joints = self.ordered_joints
		else:
			ordered_joints = []

		dump = 0
		for i in range(len(bodies)):
			if p.getNumJoints(bodies[i]) == 0:
				part_name, robot_name = p.getBodyInfo(bodies[i], 0)
				robot_name = robot_name.decode("utf8")
				part_name = part_name.decode("utf8")
				parts[part_name] = BodyPart(part_name, bodies, i, -1)
			for j in range(p.getNumJoints(bodies[i])):
				_,joint_name,_,_,_,_,_,_,_,_,_,_,part_name = p.getJointInfo(bodies[i], j)

				joint_name = joint_name.decode("utf8")
				part_name = part_name.decode("utf8")

				if dump: print("ROBOT PART '%s'" % part_name)
				if dump: print("ROBOT JOINT '%s'" % joint_name) # limits = %+0.2f..%+0.2f effort=%0.3f speed=%0.3f" % ((joint_name,) + j.limits()) )

				parts[part_name] = BodyPart(part_name, bodies, i, j)

				if part_name == self.robot_name:
					self.robot_body = parts[part_name]

				if i == 0 and j == 0 and self.robot_body is None:  # if nothing else works, we take this as robot_body
					parts[self.robot_name] = BodyPart(self.robot_name, bodies, 0, -1)
					self.robot_body = parts[self.robot_name]

				if joint_name[:8] != "jointfix":
					joints[joint_name] = Joint(joint_name, bodies, i, j)
					ordered_joints.append(joints[joint_name])

					if joint_name[:6] == "ignore":
						joints[joint_name].disable_motor()
						continue

					joints[joint_name].power_coef = 100.0

		return parts, joints, ordered_joints, self.robot_body

	def _reset(self):
		if self.scene is None:
			self.scene = self.create_single_player_scene()
		if not self.scene.multiplayer:
			self.scene.episode_restart()

		self.ordered_joints = []
		self.frame = 0
		self.done = 0
		self.reward = 0
		dump = 0

		if self.self_collision:
			self.parts, self.jdict, self.ordered_joints, self.robot_body = self.addToScene(p.loadMJCF(os.path.join(os.path.dirname(__file__), "mujoco_assets", self.model_xml), flags = p.URDF_USE_SELF_COLLISION_EXCLUDE_ALL_PARENTS))
		else:
			self.parts, self.jdict, self.ordered_joints, self.robot_body = self.addToScene(p.loadMJCF(os.path.join(os.path.dirname(__file__), "mujoco_assets", self.model_xml)))

		self.robot_specific_reset()
		s = self.calc_state()	# optimization: calc_state() can calculate something in self.* for calc_potential() to use
		self.potential = self.calc_potential()
		return s

	def _render(self, mode, close):
		pass

	def calc_potential(self):
		return 0

	def HUD(self, state, a, done):
		pass

class Camera:
	def __init__(self):
		pass

	def move_and_look_at(self,i,j,k,x,y,z):
		lookat = [x,y,z]
		distance = 10
		yaw = 10
		p.resetDebugVisualizerCamera(distance, yaw, -20, lookat)

class Pose_Helper: # dummy class to comply to original interface
	def __init__(self, body_part):
		self.body_part = body_part

	def xyz(self):
		return self.body_part.current_position()

	def rpy(self):
		return p.getEulerFromQuaternion(self.body_part.current_orientation())

	def orientation(self):
		return self.body_part.current_orientation()

class BodyPart:
	def __init__(self, body_name, bodies, bodyIndex, bodyPartIndex):
		self.bodies = bodies
		self.bodyIndex = bodyIndex
		self.bodyPartIndex = bodyPartIndex
		self.initialPosition = self.current_position()
		self.initialOrientation = self.current_orientation()
		self.bp_pose = Pose_Helper(self)

	def state_fields_of_pose_of(self, body_id, link_id=-1):  # a method you will most probably need a lot to get pose and orientation
		if link_id == -1:
			(x, y, z), (a, b, c, d) = p.getBasePositionAndOrientation(body_id)
		else:
			(x, y, z), (a, b, c, d), _, _, _, _ = p.getLinkState(body_id, link_id)
		return np.array([x, y, z, a, b, c, d])

	def get_pose(self):
		return self.state_fields_of_pose_of(self.bodies[self.bodyIndex], self.bodyPartIndex)

	def speed(self):
		if self.bodyPartIndex == -1:
			(vx, vy, vz), _ = p.getBaseVelocity(self.bodies[self.bodyIndex])
		else:
			(x,y,z), (a,b,c,d), _,_,_,_, (vx, vy, vz), (vr,vp,vy) = p.getLinkState(self.bodies[self.bodyIndex], self.bodyPartIndex, computeLinkVelocity=1)
		return np.array([vx, vy, vz])

	def current_position(self):
		return self.get_pose()[:3]

	def current_orientation(self):
		return self.get_pose()[3:]

	def reset_position(self, position):
		p.resetBasePositionAndOrientation(self.bodies[self.bodyIndex], position, self.get_orientation())

	def reset_orientation(self, orientation):
		p.resetBasePositionAndOrientation(self.bodies[self.bodyIndex], self.get_position(), orientation)

	def reset_pose(self, position, orientation):
		p.resetBasePositionAndOrientation(self.bodies[self.bodyIndex], position, orientation)

	def pose(self):
		return self.bp_pose

	def contact_list(self):
		return p.getContactPoints(self.bodies[self.bodyIndex], -1, self.bodyPartIndex, -1)


class Joint:
	def __init__(self, joint_name, bodies, bodyIndex, jointIndex):
		self.bodies = bodies
		self.bodyIndex = bodyIndex
		self.jointIndex = jointIndex
		self.joint_name = joint_name
		_,_,_,_,_,_,_,_,self.lowerLimit, self.upperLimit,_,_,_ = p.getJointInfo(self.bodies[self.bodyIndex], self.jointIndex)
		self.power_coeff = 0

	def set_state(self, x, vx):
		p.resetJointState(self.bodies[self.bodyIndex], self.jointIndex, x, vx)

	def current_position(self): # just some synonyme method
		return self.get_state()

	def current_relative_position(self):
		pos, vel = self.get_state()
		pos_mid = 0.5 * (self.lowerLimit + self.upperLimit);
		return (
			2 * (pos - pos_mid) / (self.upperLimit - self.lowerLimit),
			0.1 * vel
		)

	def get_state(self):
		x, vx,_,_ = p.getJointState(self.bodies[self.bodyIndex],self.jointIndex)
		return x, vx

	def set_position(self, position):
		p.setJointMotorControl2(self.bodies[self.bodyIndex],self.jointIndex,p.POSITION_CONTROL, targetPosition=position)

	def set_velocity(self, velocity):
		p.setJointMotorControl2(self.bodies[self.bodyIndex],self.jointIndex,p.VELOCITY_CONTROL, targetVelocity=velocity)

	def set_motor_torque(self, torque): # just some synonyme method
		self.set_torque(torque)

	def set_torque(self, torque):
		p.setJointMotorControl2(bodyIndex=self.bodies[self.bodyIndex], jointIndex=self.jointIndex, controlMode=p.TORQUE_CONTROL, force=torque) #, positionGain=0.1, velocityGain=0.1)

	def reset_current_position(self, position, velocity): # just some synonyme method
		self.reset_position(position, velocity)

	def reset_position(self, position, velocity):
		p.resetJointState(self.bodies[self.bodyIndex],self.jointIndex,targetValue=position, targetVelocity=velocity)
		self.disable_motor()

	def disable_motor(self):
		p.setJointMotorControl2(self.bodies[self.bodyIndex],self.jointIndex,controlMode=p.VELOCITY_CONTROL, force=0)
