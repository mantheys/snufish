"""Reference solver for B3: three-flavour evolution through a piecewise
constant Earth, exact for that model (one matrix exponential per shell
crossing, no stepping).

In the flavour basis H = U diag(0, dm21, dm31) U^dagger / 2E + diag(V, 0, 0),
V = sqrt(2) G_F N_e. A mass eigenstate nu_i arriving at the Earth is the
column U[:, i]; after the chord its nu_e amplitude is (S U)[e, i] with
S the ordered product of the shell propagators.
"""

import numpy as np

# Constants as in the B3 spec (PDG 2024, CODATA 2018): G_F in eV^-2,
# hbar*c in eV*cm, Avogadro in 1/mol.
G_F = 1.1663788e-23
HBARC_EV_CM = 1.973269804e-5
N_A = 6.02214076e23

KM_TO_INV_EV = 1e5 / HBARC_EV_CM


def matter_potential(density, ye):
    """V in eV for a density in g/cm^3 and Ye electrons per nucleon."""
    electrons_per_inv_ev3 = density * ye * N_A * HBARC_EV_CM**3
    return np.sqrt(2) * G_F * electrons_per_inv_ev3


def chord_segments(cos_nadir, radius, shells):
    """Ordered (length_km, density, ye) segments of the chord to a surface
    detector at nadir angle eta. ``shells`` are dicts with outer_radius_km,
    density and ye, innermost first."""
    if cos_nadir <= 0:
        return []
    sin2 = 1 - cos_nadir**2
    half = radius * cos_nadir
    # Distance from the chord midpoint to where it crosses each shell edge.
    edges = []
    for shell in shells:
        r = shell["outer_radius_km"]
        reach = r**2 - radius**2 * sin2
        edges.append(np.sqrt(reach) if reach > 0 else 0.0)
    # Walk from the far side to the detector: outermost shell inwards, then out.
    inward = []
    for k in range(len(shells) - 1, -1, -1):
        inner = edges[k - 1] if k > 0 else 0.0
        length = edges[k] - inner
        if length > 0:
            inward.append((length, shells[k]["density"], shells[k]["ye"]))
    # The innermost crossed segment is the middle one: traversed once, at full length.
    segments = inward[:-1] + [(2 * inward[-1][0], *inward[-1][1:])] + inward[-2::-1]
    assert np.isclose(sum(s[0] for s in segments), 2 * half)
    return segments


def _propagator(hamiltonian, length_inv_ev):
    values, vectors = np.linalg.eigh(hamiltonian)
    return (vectors * np.exp(-1j * values * length_inv_ev)) @ vectors.conj().T


def probabilities_ie(energy_mev, cos_nadir, U, dm2_21, dm2_31, radius, shells):
    """Array [P1e, P2e, P3e] for one energy (MeV) and nadir cosine."""
    energy_ev = energy_mev * 1e6
    vacuum = (U * np.array([0.0, dm2_21, dm2_31])) @ U.conj().T / (2 * energy_ev)
    S = np.eye(3, dtype=complex)
    for length, density, ye in chord_segments(cos_nadir, radius, shells):
        H = vacuum.copy()
        H[0, 0] += matter_potential(density, ye)
        S = _propagator(H, length * KM_TO_INV_EV) @ S
    return np.abs((S @ U)[0]) ** 2


# Variants with constant-shell Earth models, the ones this solver is exact for.
def exact_variants(spec):
    return [name for name, variant in spec.variants.items()
            if variant["earth_model"] and "shells" in spec["earth_models"][variant["earth_model"]]]


def solve_b3(spec, variant="prem_prob3", grid="map"):
    """Long-format records (grid, variant, quantity, energy, cos_nadir, value)
    for one grid of ``spec``."""
    from ..spec import pmns

    if variant not in exact_variants(spec):
        raise ValueError(f"the reference solver is exact only for constant shells: {exact_variants(spec)}")
    osc, earth = spec["oscillation"], spec["earth"]
    shells = spec["earth_models"][spec.variants[variant]["earth_model"]]["shells"]
    U = pmns(osc)
    records = []
    for cos_nadir in spec.axis("cos_nadir", grid):
        for energy in spec.axis("energy", grid):
            probs = probabilities_ie(energy, cos_nadir, U, osc["dm2_21_eV2"], osc["dm2_31_eV2"],
                                     earth["radius_km"], shells)
            for i, p in enumerate(probs, start=1):
                records.append((grid, variant, f"P{i}e", energy, cos_nadir, p))
    return records
