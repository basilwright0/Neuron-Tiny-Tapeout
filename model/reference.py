"""Numerical reference models for the TT analog-neuron test chip.

Every SPICE testbench result is compared against these equations in *hardware*
units: farads, siemens, amps, volts, seconds.  Biological parameters map to
hardware through the acceleration factor S (tau_hw = tau_bio / S).

Models
------
lif_step       : current-based LIF with reset + refractory (CS/NH reference cell)
adex           : adaptive exponential IF (Brette & Gerstner 2005)
compartments   : N passive compartments + optional plateau nonlinearity, with an
                 arbitrary coupling graph (star = NH depth-1 subunit topology)

Pure numpy; exact-exponential (LIF) or RK4 (others) integration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np


# ----------------------------------------------------------------- mapping --
def hw_from_bio(tau_bio: float, C: float, S: float) -> float:
    """Leak conductance needed for capacitance C to give tau_bio at acceleration S."""
    return C * S / tau_bio


# --------------------------------------------------------------------- LIF --
@dataclass
class LIF:
    C: float = 200e-15      # membrane capacitance [F] (use C_total incl. parasitics)
    gL: float = 2e-9        # leak conductance [S]   (200 fF, tau=100 us -> S=100)
    EL: float = 0.30        # rest [V] (hardware rails, not -65 mV)
    Vth: float = 0.60       # threshold [V]
    Vreset: float = 0.30    # reset [V]
    t_ref: float = 20e-6    # refractory [s] (2 ms bio at S=100)

    @property
    def tau(self) -> float:
        return self.C / self.gL

    def simulate(self, I: np.ndarray, dt: float, V0: float | None = None):
        """Exact-exponential integration for piecewise-constant input I[k] [A]."""
        n = len(I)
        V = np.empty(n)
        v = self.EL if V0 is None else V0
        a = np.exp(-dt / self.tau)
        ref_left = 0.0
        spikes = []
        for k in range(n):
            if ref_left > 0:
                ref_left -= dt
                v = self.Vreset
            else:
                vinf = self.EL + I[k] / self.gL
                v = vinf + (v - vinf) * a
                if v >= self.Vth:
                    spikes.append(k * dt)
                    v = self.Vreset
                    ref_left = self.t_ref
            V[k] = v
        return V, np.array(spikes)

    def rate(self, I: float) -> float:
        """Analytic f-I curve (steady-state firing rate) for constant input."""
        vinf = self.EL + I / self.gL
        if vinf <= self.Vth:
            return 0.0
        T = self.t_ref + self.tau * np.log((vinf - self.Vreset) / (vinf - self.Vth))
        return 1.0 / T


# -------------------------------------------------------------------- AdEx --
@dataclass
class AdEx:
    C: float = 200e-15
    gL: float = 2e-9
    EL: float = 0.30
    VT: float = 0.50        # exponential threshold
    DT: float = 0.02        # slope factor [V]
    Vpeak: float = 0.80
    Vreset: float = 0.32
    a: float = 0.5e-9       # subthreshold adaptation [S]
    b: float = 20e-12       # spike-triggered adaptation increment [A]
    tau_w: float = 1e-3     # adaptation time constant [s]

    def simulate(self, I: np.ndarray, dt: float):
        n = len(I)
        V = np.empty(n); W = np.empty(n)
        v, w = self.EL, 0.0
        spikes = []

        def f(v, w, i):
            dv = (-self.gL * (v - self.EL)
                  + self.gL * self.DT * np.exp(min((v - self.VT) / self.DT, 50.0))
                  - w + i) / self.C
            dw = (self.a * (v - self.EL) - w) / self.tau_w
            return dv, dw

        for k in range(n):
            i = I[k]
            k1 = f(v, w, i)
            k2 = f(v + dt / 2 * k1[0], w + dt / 2 * k1[1], i)
            k3 = f(v + dt / 2 * k2[0], w + dt / 2 * k2[1], i)
            k4 = f(v + dt * k3[0], w + dt * k3[1], i)
            v += dt / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
            w += dt / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
            if v >= self.Vpeak:
                spikes.append(k * dt)
                v = self.Vreset
                w += self.b
            V[k], W[k] = v, w
        return V, W, np.array(spikes)


# ------------------------------------------------------------ compartments --
@dataclass
class Compartments:
    """C_i dV_i/dt = -gL_i (V_i - EL) + sum_j g_ij (V_j - V_i) + I_i + I_plateau,i

    Plateau (NMDA-like caricature, active only where plateau_g[i] > 0):
        I_plateau = g_p * sigmoid((V - V_p)/w_p) * (E_p - V)
    Compartment 0 is the soma by convention.
    """
    C: np.ndarray
    gL: np.ndarray
    G: np.ndarray                       # symmetric axial conductance matrix [S]
    EL: float = 0.30
    plateau_g: np.ndarray = field(default=None)
    Vp: float = 0.45
    wp: float = 0.02
    Ep: float = 0.90

    @classmethod
    def star(cls, n_sub: int, C=200e-15, gL=2e-9, g_ax=4e-9, **kw):
        n = n_sub + 1
        G = np.zeros((n, n))
        for j in range(1, n):
            G[0, j] = G[j, 0] = g_ax
        return cls(C=np.full(n, C), gL=np.full(n, gL), G=G, **kw)

    @classmethod
    def chain(cls, n: int, C=200e-15, gL=2e-9, g_ax=4e-9, **kw):
        G = np.zeros((n, n))
        for j in range(n - 1):
            G[j, j + 1] = G[j + 1, j] = g_ax
        return cls(C=np.full(n, C), gL=np.full(n, gL), G=G, **kw)

    def _deriv(self, V, I):
        axial = self.G @ V - self.G.sum(axis=1) * V
        dV = -self.gL * (V - self.EL) + axial + I
        if self.plateau_g is not None:
            s = 1.0 / (1.0 + np.exp(-(V - self.Vp) / self.wp))
            dV = dV + self.plateau_g * s * (self.Ep - V)
        return dV / self.C

    def simulate(self, I: np.ndarray, dt: float):
        """I: shape (steps, n) injected currents [A]. RK4."""
        steps, n = I.shape
        V = np.full(n, self.EL)
        out = np.empty((steps, n))
        for k in range(steps):
            i = I[k]
            k1 = self._deriv(V, i)
            k2 = self._deriv(V + dt / 2 * k1, i)
            k3 = self._deriv(V + dt / 2 * k2, i)
            k4 = self._deriv(V + dt * k3, i)
            V = V + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            out[k] = V
        return out

    def steady_state_transfer(self) -> np.ndarray:
        """Passive transfer-resistance matrix R[i, j] = dV_i / dI_j (no plateau)."""
        L = np.diag(self.gL + self.G.sum(axis=1)) - self.G
        return np.linalg.inv(L)


# --------------------------------------------------------------- self-test --
if __name__ == "__main__":
    S = 100.0
    lif = LIF(C=200e-15, gL=hw_from_bio(10e-3, 200e-15, S))
    print(f"LIF tau_hw = {lif.tau*1e6:.1f} us (S={S:g}); gL = {lif.gL*1e9:.2f} nS")
    dt = 0.1e-6
    I = np.full(int(5e-3 / dt), 1.0e-9)
    _, sp = lif.simulate(I, dt)
    print(f"  1 nA step: {len(sp)} spikes in 5 ms -> {len(sp)/5e-3:.0f} Hz "
          f"(analytic {lif.rate(1e-9):.0f} Hz)")

    for C in (50e-15, 200e-15, 800e-15):
        for s in (1, 10, 100, 1000):
            g = hw_from_bio(10e-3, C, s)
            print(f"  C={C*1e15:4.0f} fF S={s:5d}: gL={g:9.3e} S, I_leak@100mV={g*0.1:9.3e} A")

    d = Compartments.star(3)
    R = d.steady_state_transfer()
    print("star(3) soma transfer R[0,j] (MOhm):", np.round(R[0] / 1e6, 1))
    print("  attenuation subunit->soma:", np.round(R[0, 1] / R[1, 1], 3))
