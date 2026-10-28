"""``snufish`` command line: validate, build, reference."""

import argparse
import datetime
import sys

from . import __version__
from .contribution import find_contributions, load_contribution, validate, write_contribution
from .paths import contributions_dir
from .spec import available_benchmarks, load_spec


def cmd_validate(args):
    paths = args.paths or find_contributions(args.benchmark, args.extra)
    failed = 0
    for path in paths:
        problems = validate(load_contribution(path))
        print(f"{'ok     ' if not problems else 'INVALID'} {path}")
        for problem in problems:
            print(f"  - {problem}")
        failed += bool(problems)
    return 1 if failed else 0


def cmd_build(args):
    from .build import BUILDERS, build, combine_day_night, combine_rates, combine_ssm

    combine_ssm(args.out)
    for benchmark in args.benchmark or available_benchmarks():
        if benchmark in BUILDERS:
            build(benchmark, extra_roots=args.extra, out_dir=args.out, strict=not args.skip_invalid)
    combine_day_night(args.out)
    combine_rates(args.out)
    return 0


def _reference_records(spec):
    if spec.id == "B3_earth":
        from .reference import earth

        variants = earth.exact_variants(spec)
        return variants, "exact matrix exponential per constant-density segment", [
            r for variant in variants for grid in spec.grids for r in earth.solve_b3(spec, variant, grid)]
    if spec.id == "B4_xsec":
        from .reference import xsec

        return ["default"], "tree-level SM nu-e elastic scattering, all recoil energies (no radiative corrections)", [
            r for grid in spec.grids for r in xsec.solve_b4(spec, grid)]
    from .reference import sun

    variants = list(spec.variants)
    return variants, "adiabatic: |V_ei(r0)|^2 from the eigenvectors at the production point", [
        r for variant in variants for grid in spec.grids for r in sun.solve_b2(spec, variant, grid)]


def cmd_reference(args):
    spec = load_spec(args.benchmark)
    variants, method, records = _reference_records(spec)
    meta = {
        "tool": "snufish-reference",
        "tool_version": __version__,
        "tool_commit": None,
        "benchmark": spec.id,
        "benchmark_version": spec.version,
        "contributor": "SNUfish maintainers",
        "date": datetime.date.today().isoformat(),
        "command": f"snufish reference {spec.id}",
        "settings": {"method": method, "variants": variants},
        "license": "CC-BY-4.0",
    }
    path = contributions_dir() / meta["tool"] / spec.id / meta["tool_version"]
    write_contribution(path, meta, records, spec)
    print(f"wrote {path} ({len(records)} rows)")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="snufish", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="check contributions against their benchmark spec")
    p.add_argument("paths", nargs="*", help="contribution directories (default: all)")
    p.add_argument("--benchmark")
    p.add_argument("--extra", nargs="*", default=[], help="extra contribution roots (private overlays)")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("build", help="validate and write plotipus frames to build/data")
    p.add_argument("--benchmark", nargs="*")
    p.add_argument("--extra", nargs="*", default=[], help="extra contribution roots (private overlays)")
    p.add_argument("--out", help="output directory (default build/data)")
    p.add_argument("--skip_invalid", action="store_true", help="skip invalid contributions instead of stopping")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("reference", help="(re)compute the SNUfish reference contribution")
    p.add_argument("benchmark", choices=["B2_sun", "B3_earth", "B4_xsec"])
    p.set_defaults(func=cmd_reference)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
