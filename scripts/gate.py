import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"gate failed: {' '.join(cmd)}")


def tests_for(stage: int) -> list[str]:
    files = []
    for n in range(stage + 1):
        files.extend(sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob(f"test_s{n}_*.py")))
    return files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", nargs="?", default="L")
    args = parser.parse_args()
    run([sys.executable, "-m", "ruff", "check", "src", "scripts", "tests", "app.py"])
    files = tests_for(int(args.stage)) if args.stage.isdigit() else []
    run([sys.executable, "-m", "pytest", "-q", *files] if files else [sys.executable, "-m", "pytest", "-q"])
    print(f"gate {args.stage} passed")


if __name__ == "__main__":
    main()
