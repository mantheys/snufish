"""Solar neutrino fluxes of a B5 spec: continuum shapes (normalised to unit
area on their own energy grids) and lines."""

import numpy as np

from .paths import repo_root


def components(spec, solar_model=None):
    """{name: (flux in cm^-2 s^-1, energies MeV, shape per MeV) or
    (flux, [(line energy, branching)])}; fluxes of the B1 ``solar_model``
    (default: the spec's reference model)."""
    from .solar import fluxes

    normalisation = fluxes(solar_model or spec["reference_solar_model"])
    out = {}
    for name, info in spec["fluxes"].items():
        if "lines" in info:
            out[name] = (normalisation[name], [tuple(line) for line in info["lines"]])
            continue
        table = np.loadtxt(repo_root() / info["shape"], comments="#", delimiter=",", ndmin=2)
        energy, shape = table[:, 0], np.clip(table[:, 1], 0, None)
        order = np.argsort(energy)
        energy, shape = energy[order], shape[order]
        out[name] = (normalisation[name], energy, shape / np.trapezoid(shape, energy))
    return out
