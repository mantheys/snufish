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
    from .build import build

    for benchmark in args.benchmark or available_benchmarks():
        build(benchmark, extra_roots=args.extra, out_dir=args.out, strict=not args.skip_invalid)
    return 0


def cmd_reference(args):
    from .reference import earth

    spec = load_spec(args.benchmark)
    records = [r for variant in earth.exact_variants(spec) for grid in spec.grids
               for r in earth.solve_b3(spec, variant, grid)]
    meta = {
        "tool": "snufish-reference",
        "tool_version": __version__,
        "tool_commit": None,
        "benchmark": spec.id,
        "benchmark_version": spec.version,
        "contributor": "SNUfish maintainers",
        "date": datetime.date.today().isoformat(),
        "command": f"snufish reference {spec.id}",
        "settings": {"method": "exact matrix exponential per constant-density segment",
                     "variants": earth.exact_variants(spec)},
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
    p.add_argument("benchmark", choices=["B3_earth"])
    p.set_defaults(func=cmd_reference)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
