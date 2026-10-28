"""Reference solver for B2: phase-averaged mass-eigenstate fractions in the
adiabatic limit, F_i(E, r0) = |V_ei(r0)|^2, with V the eigenvectors of the
three-flavour Hamiltonian at the production point ordered by eigenvalue
(normal ordering: no level crossing, so the k-th matter state becomes nu_k
at the surface).

For the B2 parameters the propagation is deeply adiabatic (gamma ~ 1e3 at
the MSW resonance, crossing probability ~ exp(-pi gamma / 2)). Corrections
of order 1/gamma oscillate with the phase accumulated across the Sun and
average out over any energy resolution; what remains is O(1/gamma^2) ~ 1e-6.
A staircase-density solver was tried and rejected: its step-boundary kicks
converge only like sqrt(step) and were larger than the effect.
"""

import numpy as np

from ..solar import electron_density
from .earth import matter_potential


def adiabatic_fractions(spec, model_name, energies_mev, radius_grid):
    """Array [radius, energy, i] of F_i = |V_ei(r0)|^2."""
    from ..spec import pmns

    osc = spec["oscillation"]
    U = pmns(osc)
    E = np.asarray(energies_mev, dtype=float) * 1e6
    vacuum = (U * np.array([0.0, osc["dm2_21_eV2"], osc["dm2_31_eV2"]])) @ U.conj().T
    out = np.empty((len(radius_grid), len(E), 3))
    for k, r in enumerate(radius_grid):
        H = vacuum[None] / (2 * E[:, None, None])
        H[:, 0, 0] += matter_potential(electron_density(model_name, r, spec), 1.0)
        _, vectors = np.linalg.eigh(H)  # eigenvalues ascending
        out[k] = np.abs(vectors[:, 0, :]) ** 2
    return out


def solve_b2(spec, variant="b16_gs98", grid="map"):
    model = spec.variants[variant]["solar_model"]
    energies, radii = spec.axis("energy", grid), spec.axis("radius", grid)
    F = adiabatic_fractions(spec, model, energies, radii)
    return [(grid, variant, f"F{i + 1}", e, r, F[k, j, i])
            for k, r in enumerate(radii) for j, e in enumerate(energies) for i in range(3)]
