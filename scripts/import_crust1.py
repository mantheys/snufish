"""Extract the CRUST1.0 column under every B3 site: reference/earth/crust1_sites.yaml.

    curl -LO https://igppweb.ucsd.edu/~gabi/crust1/crust1.0.tar.gz && mkdir crust1 && tar -xzf crust1.0.tar.gz -C crust1
    python scripts/import_crust1.py crust1 crust1.0.tar.gz

CRUST1.0 (Laske, Masters, Ma & Pasyanos 2013) gives eight layers (water, ice, three sediment layers, upper,
middle and lower crystalline crust) on 1 x 1 degree cells, and the density under the Moho. Each site takes the
cell its coordinates fall in (cells are centred on half degrees).
"""

import argparse
import datetime
import hashlib
from pathlib import Path

import numpy as np
import yaml

LAYERS = ["water", "ice", "upper sediments", "middle sediments", "lower sediments", "upper crust", "middle crust",
          "lower crust"]
# Site coordinates (degrees north, east): the B3 latitudes; longitudes of the laboratories, to the 0.01 degree.
# Only the 1 x 1 degree cell matters.
LONGITUDES = {"Kamioka": 137.31, "LNGS": 13.57, "SURF": -103.75, "SNOLAB": -81.20, "Jiangmen": 112.52}


def read(directory, name):
    return np.loadtxt(Path(directory) / f"crust1.{name}").reshape(180, 360, 9)  # 89.5 N .. 89.5 S, 179.5 W .. 179.5 E


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("directory", help="the unpacked crust1.0.tar.gz")
    parser.add_argument("archive", help="crust1.0.tar.gz itself, for its checksum")
    parser.add_argument("--out", default=Path(__file__).resolve().parents[1] / "reference" / "earth" / "crust1_sites.yaml")
    args = parser.parse_args()
    bounds, density = read(args.directory, "bnds"), read(args.directory, "rho")
    with (Path(__file__).resolve().parents[1] / "benchmarks" / "B3_earth" / "spec.yaml").open() as handle:
        sites = yaml.safe_load(handle)["sites"]
    out = {}
    for site, info in sites.items():
        lat, lon = info["latitude_deg"], LONGITUDES[site]
        i, j = int(np.floor(90 - lat)), int(np.floor(lon + 180))
        top, bnd, rho = bounds[i, j, 0], bounds[i, j], density[i, j]
        layers = [dict(layer=LAYERS[k], thickness_km=round(float(bnd[k] - bnd[k + 1]), 3), density=float(rho[k]))
                  for k in range(8) if bnd[k] - bnd[k + 1] > 0]
        out[site] = dict(latitude_deg=lat, longitude_deg=lon, cell_centre=[89.5 - i, -179.5 + j],
                         surface_elevation_km=float(top), moho_depth_km=round(float(top - bnd[8]), 3),
                         mantle_density=float(rho[8]), layers=layers)
    digest = hashlib.sha256(Path(args.archive).read_bytes()).hexdigest()
    header = {
        "source": "CRUST1.0, G. Laske, G. Masters, Z. Ma and M. Pasyanos, EGU General Assembly 2013, EGU2013-2658; "
                  "https://igppweb.ucsd.edu/~gabi/crust1.html",
        "archive": f"crust1.0.tar.gz, sha256 {digest}",
        "retrieved": datetime.date.today().isoformat(),
        "method": "table (the 1 x 1 degree cell of each site; layers top down, thickness in km, density in g/cm^3)",
        "longitudes": "laboratory longitudes to 0.01 degree (scripts/import_crust1.py); only the cell matters",
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.out).open("w") as handle:
        yaml.safe_dump({**header, "sites": out}, handle, sort_keys=False, allow_unicode=True)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
