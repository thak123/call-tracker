"""Run all Call Tracker tests:  python3 run_tests.py   (add --live to also check the real websites)

Part A  page workflows      tests/ui.test.mjs     (Chrome in a hidden window, via Node)
Part B  search script       tests/test_fetch.py   (saved website copies, no internet)
Part C  helper (serve.py)   tests/test_serve.py
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
TESTS = HERE / "tests"


def run(title, cmd, env=None):
    print(f"\n=== {title} ===", flush=True)
    return subprocess.run(cmd, cwd=HERE, env=env).returncode == 0


def main():
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    results = {}
    parts = {
        "A": ("Part A - page workflows", ["node", "--test", "--test-reporter=spec", str(TESTS / "ui.test.mjs")]),
        "B": ("Part B - search script", [sys.executable, "-m", "unittest", "-v", "tests.test_fetch"]),
        "C": ("Part C - helper", [sys.executable, "-m", "unittest", "-v", "tests.test_serve"]),
    }
    for key, (title, cmd) in parts.items():
        if only and key not in only:
            continue
        test_file = TESTS / (Path(cmd[-1]).name if key == "A" else cmd[-1].split(".")[-1] + ".py")
        if not test_file.exists():
            print(f"\n=== {title} === (not written yet)")
            continue
        results[title] = run(title, cmd)
    if "--live" in sys.argv:
        results["Live check of real websites"] = run("Live check of real websites",
                                                     [sys.executable, str(TESTS / "live_check.py")])
    print("\n=== Summary ===")
    for title, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {title}")
    print(f"  Screenshots: {TESTS / 'screenshots'}")
    sys.exit(0 if results and all(results.values()) else 1)


if __name__ == "__main__":
    main()
