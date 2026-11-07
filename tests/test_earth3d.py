"""prem_crust1_3d (snufish.earth3d): the CRUST1.0 crust along each night chord."""

import subprocess

import numpy as np
import pytest

from snufish import crust, earth3d
from snufish.exposure import cell_weights
from snufish.reference.earth import KM_TO_INV_EV, _propagator, matter_potential
from snufish.scan import _nufast_driver, oscillation
from snufish.spec import pmns

OSC = oscillation("juno_2025")


def _driver():
    try:
        return _nufast_driver()
    except FileNotFoundError:
        pytest.skip("NuFast-Earth driver not built")


def _run(chords, energies=(5.0, 10.0, 15.0)):
    path = earth3d.write_trajectories(chords, "test")
    e = list(energies)
    argv = [f"trajectories:{path}", *(str(OSC[k]) for k in ("sin2_theta12", "sin2_theta13", "sin2_theta23",
                                                            "delta_cp_deg", "dm2_21_eV2", "dm2_31_eV2")),
            "0", str(e[0]), str(e[-1]), str(e[1] - e[0]), "0", "1", "1"]
    out = subprocess.run([str(_driver()), *argv], capture_output=True, text=True, check=True).stdout
    table = np.loadtxt(out.splitlines())
    return table[:, [2, 5, 8]].reshape(len(e), len(chords), 3)


def test_crust_at_each_site_is_its_column():
    # the global grid gives the column of crust1_sites.yaml under every site
    for column in crust.columns().values():
        top = 0.0
        for layer in column["layers"]:
            middle = top + 0.5 * layer["thickness_km"]
            assert earth3d.crust_density(column["latitude_deg"], column["longitude_deg"], middle) == pytest.approx(
                layer["density"])
            top += layer["thickness_km"]
        assert np.isnan(earth3d.crust_density(column["latitude_deg"], column["longitude_deg"], top + 0.1))


def test_mantle_under_the_crust_is_prem():
    # PREM's regions below its lid, the lid continued to the surface (as prem_crust1 under the local Moho)
    regions = crust.regions("prem_crust1", "Kamioka")
    for r in (500.0, 3000.0, 5000.0, 6300.0):
        region = next(x for x in regions if r <= x["outer_radius_km"])
        rho = sum(c * (r / 6371.0) ** k for k, c in enumerate(region["coefficients"]))
        assert earth3d.mantle_rhoye(r) == pytest.approx(region["ye"] * rho)
    assert earth3d.mantle_rhoye(6360.0) == pytest.approx(0.494 * (2.691 + 0.6924 * 6360 / 6371))


def test_driver_chords_run_from_the_entry_point():
    # an asymmetric chord: the driver's order is the neutrino's, against the B3 reference propagator
    U, pieces = pmns(OSC), [(3000.0, 12 * 0.466), (2000.0, 2.7 * 0.494), (500.0, 4.0 * 0.494)]
    P = _run([(0.5, *map(np.array, zip(*pieces))), (0.6, *map(np.array, zip(*pieces[::-1])))])
    for k, chord in enumerate((pieces, pieces[::-1])):
        for i, energy in enumerate((5.0, 10.0, 15.0)):
            vacuum = (U * np.array([0, OSC["dm2_21_eV2"], OSC["dm2_31_eV2"]])) @ U.conj().T / (2e6 * energy)
            S = np.eye(3, dtype=complex)
            for length, rhoye in chord:
                H = vacuum.copy()
                H[0, 0] += matter_potential(rhoye, 1.0)
                S = _propagator(H, length * KM_TO_INV_EV) @ S
            assert np.allclose(P[i, k], np.abs((S @ U)[0]) ** 2, atol=1e-7)


def test_night_directions_follow_the_b3_exposure():
    # the time sampling of the Sun gives W(eta) of Lisi & Montanino, which keeps the nadir weights
    for site in ("Kamioka", "Jiangmen"):
        _, c = earth3d.night_directions(site, step_minutes=10)
        edges = np.linspace(0, 1, 11)
        sampled = np.histogram(c, edges)[0] / len(c)
        grid = earth3d.cos_grid()
        w = cell_weights(grid, np.radians(crust.columns()[site]["latitude_deg"]))
        expected = np.histogram(grid, edges, weights=w)[0]
        assert np.abs(sampled - expected).max() < 0.01


def test_pieces_keep_length_and_column():
    lengths = np.full(1000, 1.0)
    rhoye = np.where(np.arange(1000) < 300, 1.3, 1.6 + 1e-4 * np.arange(1000))
    total, mean = earth3d.pieces(lengths, rhoye)
    assert total.sum() == pytest.approx(1000.0) and np.sum(total * mean) == pytest.approx(np.sum(rhoye))
    assert 300.0 in np.cumsum(total)  # a layer border ends a piece


def test_radial_crust_gives_prem_crust1(monkeypatch):
    # with the detector's column everywhere, the chords of the 3D model are prem_crust1's: same night P
    site = "Kamioka"
    column = crust.columns()[site]
    bottoms = np.cumsum([layer["thickness_km"] for layer in column["layers"]])
    densities = np.array([layer["density"] for layer in column["layers"]])

    def site_column(lat, lon, depth):
        k = np.searchsorted(bottoms, np.asarray(depth), side="right")
        return np.where(k < len(densities), densities[np.minimum(k, len(densities) - 1)], np.nan)

    monkeypatch.setattr(earth3d, "crust_density", site_column)
    near, far, counts = earth3d.averaged_crust.__wrapped__(site, step_minutes=60)
    near, far = earth3d._fill_empty(near, far, counts)
    grid = earth3d.cos_grid()
    picks = [100, 300, 500, 700, 900]
    chords = [(grid[k], *earth3d.pieces(*earth3d.chord_profile(grid[k], near[k], far[k]))) for k in picks]
    regions = crust.split(crust.regions("prem_crust1", site), 10.0)
    from snufish.reference.earth import probabilities_ie_regions

    P = _run(chords)
    for j, k in enumerate(picks):
        exact = probabilities_ie_regions([5.0, 10.0, 15.0], grid[k], pmns(OSC), OSC["dm2_21_eV2"], OSC["dm2_31_eV2"],
                                         6371.0, regions)
        assert np.allclose(P[:, j], exact, atol=2e-4)
