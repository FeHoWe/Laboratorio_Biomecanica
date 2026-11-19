"""Adaptador MuJoCo (OPCIONAL) para SpatialChain: gera MJCF, calcula M, bias, FK e integra, para COMPARAR com o motor interno.

Mapeamento: cada corpo móvel → <body> com pos/quat = origem da junta (q=0); cada DOF → <joint type=hinge|slide axis=...> na ordem
do SpatialJoint (MuJoCo compõe juntas de um mesmo corpo em sequência, eixos no referencial já girado — mesma convenção do motor
interno, verificada em teste). Inércia: <inertial pos=CM fullinertia=tensor em torno do CM>. Limites articulares NÃO são
enviados (o motor interno também não os impõe), para a comparação ser justa. Sem MuJoCo instalado, `available()` é False e nada é simulado.
"""
from __future__ import annotations

import numpy as np

from biomechanics.spatial import quaternions as Q
from biomechanics.spatial.spatial_chain import SpatialChain
from core.exceptions import NexusError

try:  # dependência opcional
    import mujoco
    _IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - depende do ambiente
    mujoco = None
    _IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


class MujocoUnavailable(NexusError):
    pass


def available() -> bool:
    return mujoco is not None


def version() -> str:
    return getattr(mujoco, "__version__", "") if mujoco is not None else ""


def _f(v) -> str:
    return " ".join(f"{float(x):.17g}" for x in np.ravel(v))


def build_mjcf(chain: SpatialChain, gravity=(0.0, -9.80665, 0.0), timestep: float = 0.001, integrator: str = "RK4") -> str:
    """MJCF (XML) equivalente à cadeia. Corpos fixos (sem DOF) viram corpos sem junta."""
    children: dict[str, list] = {}
    for j in chain.joints:
        children.setdefault(j.parent, []).append(j)

    def body_xml(bid: str, pos, quat, joint, depth: int) -> str:
        b = chain.bodies[bid]
        ind = "  " * depth
        s = f'{ind}<body name="{bid}" pos="{_f(pos)}" quat="{_f(quat)}">\n'
        if joint is not None:
            for d in joint.dofs:
                typ = "hinge" if d.kind == "revolute" else "slide"
                s += f'{ind}  <joint name="{d.name}" type="{typ}" pos="0 0 0" axis="{_f(d.axis)}" limited="false" damping="0" armature="0"/>\n'
        I = b.inertia
        s += (f'{ind}  <inertial pos="{_f(b.com)}" mass="{b.mass_kg:.17g}" '
              f'fullinertia="{_f([I[0, 0], I[1, 1], I[2, 2], I[0, 1], I[0, 2], I[1, 2]])}"/>\n')
        for cj in children.get(bid, []):
            T0 = cj.origin_T()
            s += body_xml(cj.child, T0[:3, 3], Q.from_matrix(T0[:3, :3]), cj, depth + 1)
        return s + f"{ind}</body>\n"

    T = chain.base_T
    xml = (f'<mujoco model="nexus_spatial"><compiler angle="radian"/>'
           f'<option gravity="{_f(gravity)}" timestep="{timestep:.17g}" integrator="{integrator}"/>\n<worldbody>\n'
           + body_xml(chain.base, T[:3, 3], Q.from_matrix(T[:3, :3]), None, 1) + "</worldbody>\n</mujoco>\n")
    return xml


class MujocoModel:
    def __init__(self, chain: SpatialChain, gravity=(0.0, -9.80665, 0.0), timestep: float = 0.001, integrator: str = "RK4") -> None:
        if not available():
            raise MujocoUnavailable(f"MuJoCo não está instalado ({_IMPORT_ERROR or 'pip install mujoco'}). Nenhum resultado MuJoCo é inventado.")
        self.chain = chain
        self.xml = build_mjcf(chain, gravity, timestep, integrator)
        try:
            self.m = mujoco.MjModel.from_xml_string(self.xml)
        except Exception as exc:
            raise MujocoUnavailable(f"MuJoCo rejeitou o modelo gerado: {exc}") from exc
        self.d = mujoco.MjData(self.m)
        if self.m.nv != chain.n_dof:
            raise MujocoUnavailable(f"nv={self.m.nv} ≠ n_dof={chain.n_dof}")

    def _set(self, q, qd=None) -> None:
        self.d.qpos[:] = q
        self.d.qvel[:] = 0.0 if qd is None else qd

    def mass_matrix(self, q) -> np.ndarray:
        self._set(q)
        mujoco.mj_forward(self.m, self.d)
        M = np.zeros((self.m.nv, self.m.nv))
        try:                                   # MuJoCo ≥ 4: mj_fullM(m, d, dst)
            mujoco.mj_fullM(self.m, self.d, M)
        except TypeError:                      # MuJoCo 3.x: mj_fullM(m, dst, qM)
            mujoco.mj_fullM(self.m, M, self.d.qM)
        return M

    def bias(self, q, qd) -> np.ndarray:
        """qfrc_bias = C(q,q̇)q̇ + G(q)  (equivale a coriolis_vector + gravity_vector do motor interno)."""
        self._set(q, qd)
        mujoco.mj_forward(self.m, self.d)
        return self.d.qfrc_bias.copy()

    def body_positions(self, q) -> dict:
        self._set(q)
        mujoco.mj_kinematics(self.m, self.d)
        return {mujoco.mj_id2name(self.m, mujoco.mjtObj.mjOBJ_BODY, i): self.d.xpos[i].copy() for i in range(1, self.m.nbody)}

    def com_positions(self, q) -> dict:
        self._set(q)
        mujoco.mj_forward(self.m, self.d)
        return {mujoco.mj_id2name(self.m, mujoco.mjtObj.mjOBJ_BODY, i): self.d.xipos[i].copy() for i in range(1, self.m.nbody)}

    def inverse_dynamics(self, q, qd, qdd) -> np.ndarray:
        self._set(q, qd)
        self.d.qacc[:] = qdd
        mujoco.mj_inverse(self.m, self.d)
        return self.d.qfrc_inverse.copy()

    def energy(self, q, qd) -> tuple[float, float]:
        self._set(q, qd)
        self.m.opt.enableflags |= int(mujoco.mjtEnableBit.mjENBL_ENERGY)
        mujoco.mj_forward(self.m, self.d)
        return float(self.d.energy[0]), float(self.d.energy[1])   # (potencial, cinética)

    def simulate(self, q0, qd0, duration_s: float, tau_fn=None):
        """Integra com o integrador do MJCF; retorna (t, q, qd) nas amostras de cada passo."""
        self._set(q0, qd0)
        self.d.time = 0.0
        n = int(round(duration_s / self.m.opt.timestep))
        t, Q_, QD = np.zeros(n + 1), np.zeros((n + 1, self.m.nv)), np.zeros((n + 1, self.m.nv))
        Q_[0], QD[0] = q0, qd0
        for i in range(n):
            self.d.ctrl[:] = 0.0
            self.d.qfrc_applied[:] = 0.0 if tau_fn is None else tau_fn(self.d.time, self.d.qpos.copy(), self.d.qvel.copy())
            mujoco.mj_step(self.m, self.d)
            t[i + 1], Q_[i + 1], QD[i + 1] = self.d.time, self.d.qpos, self.d.qvel
        return t, Q_, QD
