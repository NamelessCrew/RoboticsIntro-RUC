"""控制层：阻尼最小二乘 IK + 原生 Panda 关节位置 PD；仅控制机器人执行器。"""
import mujoco
import numpy as np


def orientation_error(current, target):
    """世界坐标旋转向量；用 quaternion log 避免 180° 时叉积误差退化为零。"""
    quaternion = np.empty(4)
    mujoco.mju_mat2Quat(quaternion, (target @ current.T).ravel())
    if quaternion[0] < 0:
        quaternion *= -1
    length = np.linalg.norm(quaternion[1:])
    if length < 1e-12:
        return np.zeros(3)
    return 2*np.arctan2(length, quaternion[0])*quaternion[1:]/length


class CartesianController:
    def __init__(self, env, on_step=None):
        if env.robot != "panda":
            raise ValueError("Week07 controller requires Panda")
        self.env = env
        self.on_step = on_step
        self.ik_data = mujoco.MjData(env.model)  # IK 的虚拟状态，不写实际物理状态。
        self.rotation = env.data.site("tcp").xmat.reshape(3, 3).copy()
        self.site_id = env.model.site("tcp").id
        self.qadr, self.dadr = env.qadr[:7], env.dadr[:7]
        self.qtarget = env.qpos[:7].copy()
        self.limits = env.model.jnt_range[env.joint_ids[:7]]

    def inverse_kinematics(self, target):
        model, data = self.env.model, self.ik_data
        data.qpos[:] = self.env.data.qpos
        data.qpos[self.qadr] = self.qtarget
        jp, jr = np.zeros((3, model.nv)), np.zeros((3, model.nv))
        for _ in range(80):
            mujoco.mj_forward(model, data)
            current_R = data.site("tcp").xmat.reshape(3, 3)
            position_error = np.asarray(target)-data.site("tcp").xpos
            rotation_error = orientation_error(current_R, self.rotation)
            error = np.r_[position_error, rotation_error]
            if np.linalg.norm(position_error) < .0001 and np.linalg.norm(rotation_error) < .001:
                break
            mujoco.mj_jacSite(model, data, jp, jr, self.site_id)
            J = np.vstack([jp[:, self.dadr], jr[:, self.dadr]])
            dq = J.T @ np.linalg.solve(J@J.T + .0001*np.eye(6), error)
            data.qpos[self.qadr] = np.clip(data.qpos[self.qadr]+np.clip(dq, -.12, .12), self.limits[:, 0]+.001, self.limits[:, 1]-.001)
        mujoco.mj_forward(model, data)
        residual = float(np.linalg.norm(np.asarray(target)-data.site("tcp").xpos))
        current_R = data.site("tcp").xmat.reshape(3, 3)
        rotation_residual = float(np.linalg.norm(orientation_error(current_R, self.rotation)))
        if residual > .005 or rotation_residual > .01:
            raise ValueError(f"IK target unreachable or failed: position={residual:.4f} m, orientation={rotation_residual:.4f} rad")
        self.qtarget = data.qpos[self.qadr].copy()
        return self.qtarget

    def move_to(self, xyz, gripper_open):
        q = self.inverse_kinematics(xyz)
        # 位置PD执行器会通过力矩驱动关节，物体始终只由接触力/重力驱动。
        self._step(np.r_[q, 255. if gripper_open else 0.])

    def hold(self, gripper_open):
        self._step(np.r_[self.qtarget, 255. if gripper_open else 0.])

    def _step(self, action):
        self.env.step(action)
        if self.on_step is not None:
            self.on_step()


def bilateral_contacts(env, min_force=.01):
    cube = env.model.body("cube").id
    fingers = {env.model.body(name).id: name for name in ("left_finger", "right_finger")}
    forces = {name: 0. for name in fingers.values()}
    wrench = np.zeros(6)
    for i in range(env.data.ncon):
        contact = env.data.contact[i]
        a, b = [int(env.model.geom_bodyid[x]) for x in (contact.geom1, contact.geom2)]
        other = b if a == cube else a if b == cube else -1
        if other in fingers:
            mujoco.mj_contactForce(env.model, env.data, i, wrench)
            forces[fingers[other]] += float(max(0, wrench[0]))
    return all(x > min_force for x in forces.values()), forces
