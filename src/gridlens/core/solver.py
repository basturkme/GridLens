"""VA (Backward-Forward Sweep) power-flow solver for radial distribution networks.

Sprint 0: signature only. Sprint 2 will fill in the BFS algorithm.

Outline of the iteration to be implemented:

  1. Order buses by depth from the slack root (BFS traversal of the radial tree).
  2. **Backward sweep** — from leaves toward root, accumulate branch currents
     I_branch = Σ_downstream [conj((P_load - P_gen + j(Q_load - Q_gen)) / V_to)]
              − jB_cap · V_to    (capacitors entered as shunt susceptance)
  3. **Forward sweep** — from root toward leaves, update voltages
     V_to = V_from − Z_branch · I_branch
  4. Repeat until max|V_k − V_{k-1}| < tol or iter > max_iter.

PV bus handling (generators with regulated |V|):
  Plain BFS only converges with PQ buses + a single slack. A generator that
  fixes |V| (PV bus) needs an outer Q-compensation loop:
    a) Treat the PV bus as PQ with an initial Q guess.
    b) After each inner BFS converges, read the resulting |V| at the PV bus
       and compute ΔV = V_set − |V|.
    c) Update Q_gen via sensitivity ΔQ ≈ ΔV / X_th (or Jacobian-style update).
    d) Clamp to [Qmin, Qmax]; if hit, the bus reverts to PQ at its limit.
  Same idea applies to the operator-pinned leaf-bus voltage in this project.

Capacitor banks are modeled as shunt susceptances toggled by `in_service`.
"""
from __future__ import annotations

from gridlens.core.models import Network, SolutionResult
from gridlens.utils.constants import DEFAULT_MAX_ITER, DEFAULT_TOLERANCE_PU


def solve(
    network: Network,
    *,
    tol: float = DEFAULT_TOLERANCE_PU,
    max_iter: int = DEFAULT_MAX_ITER,
) -> SolutionResult:
    """Run BFS power flow on a radial network. Returns voltage magnitude/angle per bus."""
    raise NotImplementedError("Solver implementation deferred to Sprint 2.")
