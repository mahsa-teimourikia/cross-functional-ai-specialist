"""Type-check each standalone course lab without module-name collisions."""

from __future__ import annotations

from pathlib import Path

from mypy import api

ROOT = Path(__file__).parents[1]
LABS = sorted((ROOT / "curriculum" / "advanced").glob("*/lab.py"))


def main() -> None:
    failures = 0
    for path in LABS:
        stdout, stderr, status = api.run([str(path)])
        print(stdout, end="")
        print(stderr, end="")
        failures += int(status != 0)
    if failures:
        raise SystemExit(f"mypy failed for {failures} course lab(s)")
    print(f"mypy passed for {len(LABS)} course labs")


if __name__ == "__main__":
    main()
