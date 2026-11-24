# What I learned

The agent adds two short sentences after each step.

- Step 1: We wrote down your job (teacher and researcher), your weekly files and your AI level (2). Worth remembering: the agent only needs made-up data, so you never have to share real student or research data.
- Step 4: We wrote a plan for the Call Tracker in `projects/call-tracker/PLAN.md`. Worth remembering: the OUT list matters as much as the IN list, because it keeps the first version small.
- Step 5: We built the first Call Tracker page in `projects/call-tracker/index.html`, with 12 made-up calls. Worth remembering: deadlines are counted from today, so the sample stays useful on any day.
- Step 6: We checked the page against the three "done when" points by opening it in a hidden browser, and all three passed. Worth remembering: "checked" means we saw the result, not that we expect it to work.
- Step 7: We wrote `projects/call-tracker/MONDAY.md`, a plan for gathering real calls automatically every Monday. Worth remembering: start by hand with one source, then automate it.
- Step 7 (second round): The page can now load calls from a `calls.csv` file and remembers them, and we tested good, bad and wrong files. Worth remembering: a clear error message for a bad row saves time once real data arrives on Monday.
- Step 7 (third round): The page now also reads CSV files from European Excel (";" separator, dates like 15.1.2027), and we tested it. Worth remembering: test with a file shaped exactly like the one you will really use.
- EU search: We wrote `fetch_eu_calls.py`, which collects real EU calls for your keywords into `eu_calls.csv` for the page. Worth remembering: don't trust a "status" label blindly; we checked the deadlines and found it was wrong.
- More keywords: We added six keywords; only "multilingual" and "benchmarking" found extra EU calls. Worth remembering: exact phrases are precise but narrow, so a keyword can also match an off-topic call (e.g. "environmental benchmarking").
- Dashboard: We added a "not my topics" list to the EU script, plus a summary with four numbers and two charts (deadlines per month, calls per keyword). Worth remembering: a screenshot found a layout problem and a wrong sentence that our click tests had missed.
- Second source and keyword editor: `fetch_calls.py` now reads the EU portal and HRZZ together, and you can add, edit and delete keywords on the page, saved in `keywords.js`. Worth remembering: one shared settings file means the page and the script can never disagree about your keywords.
- Refresh button: A small local helper (`serve.py`) lets the page start the search in the background and update itself, and the page opens the newest results without a Load click. Worth remembering: a web page can't start programs by itself, so a helper that only listens on your own laptop bridges the gap safely.
- Three more sources: eufondovi, AMPEU and UNIZG now feed the tracker (31 calls, 13 open). Worth remembering: every new source needs a filter for what is NOT a call (results, notices, job ads), and a spot check against the real website.
- Plan updated: `PLAN.md` now describes the tool as it really is (5 sources, dashboard, keyword editor, Refresh). Worth remembering: a plan is only useful while it matches the tool, so update it after big changes.
- Test suite: `python3 run_tests.py` now checks 49 click paths and script parts, and it found 5 real bugs that are now fixed. Worth remembering: write the test for a bug first, see it fail, then fix it, so you know the fix really works.
