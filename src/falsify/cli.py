import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="falsify")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="run checks against a trade CSV")
    check.add_argument("csv_path")
    check.add_argument("--params", type=int, required=True)
    check.add_argument("--trials", type=int, default=1)
    check.add_argument("--json", action="store_true")

    args = parser.parse_args()
    # ponytail: checks not implemented yet, see .fapony/plan/PLAN-engine-v1.md
    raise SystemExit("falsify check: not implemented yet")


if __name__ == "__main__":
    main()
