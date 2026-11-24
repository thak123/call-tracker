"""Fake search used only by the tests: waits 2 seconds, then adds one new call (or fails if FAIL exists)."""
import json, pathlib, sys, time
here = pathlib.Path(__file__).parent
time.sleep(2)
if (here / "FAIL").exists():
    print("PROBLEM: pretend the EU portal is down")
    sys.exit(1)
csv = (here / "live_calls.csv").read_text(encoding="utf-8")
if "t11," not in csv:
    csv += "t11,Brand New Call,Test Fund E,,MZOM,grant,2027-04-01,https://example.com/t11,€1,staff,multilingual\n"
(here / "live_calls.csv").write_text(csv, encoding="utf-8")
(here / "live_calls.js").write_text("window.LIVE_CALLS = " + json.dumps({"generated": "2026-11-24T10:05:00+01:00", "csv": csv}) + ";\n", encoding="utf-8")
print("Saved 11 calls (fake search)")
