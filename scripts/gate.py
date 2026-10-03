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


def check_no_comments() -> None:
    offenders = []
    for path in (
        list((ROOT / "src").rglob("*.py"))
        + list((ROOT / "scripts").rglob("*.py"))
        + list((ROOT / "tests").rglob("*.py"))
    ):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    if offenders:
        raise SystemExit("comment lines found: " + ", ".join(offenders[:20]))


def tests_for(stage: int) -> list[str]:
    files = []
    for n in range(stage + 1):
        files.extend(sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob(f"test_s{n}_*.py")))
    return files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", type=int)
    args = parser.parse_args()
    run([sys.executable, "-m", "ruff", "check", "src", "scripts", "tests", "app.py"])
    check_no_comments()
    files = tests_for(args.stage)
    run(
        [sys.executable, "-m", "pytest", "-q", *files]
        if files
        else [sys.executable, "-m", "pytest", "-q", "--co"]
    )
    print(f"gate {args.stage} passed")


if __name__ == "__main__":
    main()
