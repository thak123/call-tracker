# Call Tracker — test plan

Goal: one command checks every click path of the page and every part of the search script, so a change can't silently break something. Each test describes a real workflow: "I click X, I expect Y".

## How it runs

- **One command:** `python3 run_tests.py` in the `call-tracker` folder. Prints a PASS/FAIL list and saves screenshots to `tests/screenshots/` for a human look.
- **No installs:** page tests drive the Chrome that is already on this laptop (hidden window, same method used today). Script tests use Python's built-in `unittest`.
- **Offline and repeatable:** tests use saved copies of the websites (`tests/fixtures/`) and a fixed "today" (24 Nov 2026), so results don't change when the real sites or the date change.
- **One optional online check:** `python3 run_tests.py --live` asks each real source once and reports which ones still work (for Mondays).
- Test files live in `tests/` inside this folder; nothing outside it is touched. `keywords.js` and `live_calls.*` are backed up before tests and restored after.

## Part A — page workflows (click → expect)

| # | Workflow | Checks |
|---|---|---|
| A1 | Open the page by double-click | newest results load by themselves; counts in tiles = cards; no JavaScript errors |
| A2 | Filters | type, who can apply, status each narrow the cards; "All" brings them back; combined filters work |
| A3 | Keyword filter | click a tag on a card → only those calls; click a bar in the keyword chart → same; "show all" clears it |
| A4 | My status | set "applying" → tile "I'm applying" goes up; reload → still set; status filter finds it |
| A5 | **Keyword panel navigation** (the bug) | open with "My keywords"; **close with a Close button, the Esc key, and "My keywords" again**; page scrolls back to the calls; button shows open/closed state |
| A6 | Keyword editing | add, empty word, too short, duplicate, word in other list, edit + save, edit + cancel, edit with Enter/Esc, delete; counts update |
| A7 | Not my topics | adding a word hides matching cards right away and the header says how many are hidden; deleting it brings them back |
| A8 | Unsaved changes | change survives reload; "Undo changes" returns to the file; message says "unsaved" |
| A9 | Save keywords | with helper: file on disk changes; without helper: download fallback with clear instructions |
| A10 | Load a CSV | good file; bad dates and missing title skip rows with a message; wrong columns refused; European Excel format (`;`, 15.1.2027); "Back to sample" |
| A11 | Which data shows on open | own CSV loaded after the last search wins; otherwise newest results; otherwise sample |
| A12 | Summary | 4 numbers match the cards; month chart total = open calls in the next 12 months; tooltip on hover names the right calls |
| A13 | Refresh without helper | shows how to start `serve.py`, nothing breaks |
| A14 | Refresh with helper | button disabled while running; progress message; cards update by themselves; "N new open" correct; failing search shows the error and keeps old data |
| A15 | Layout | screenshots at 1440, 1000, 820 and 375 px wide: content centred, no sideways scrolling, keyword panel and charts readable |

## Part B — search script (`fetch_calls.py`)

| # | What | Checks |
|---|---|---|
| B1 | Croatian deadline reader | "25. veljače 2027.", "do 17. studenoga", "27. 4. 2026.", missing year, impossible date (31.2.), old dates ignored, next upcoming deadline chosen |
| B2 | Each source on saved pages | EU, HRZZ, eufondovi, AMPEU, UNIZG, MZOM, UNIRI: expected number of calls and titles; job ads, results, notices, school calls left out |
| B3 | Not my topics | matching titles left out and listed in the report |
| B4 | Duplicates | same call from two sources becomes one (incl. "RAMP" vs "RAMP-a", currently missed) |
| B5 | Output files | `live_calls.csv` and `live_calls.js` hold the same calls; page can read both |
| B6 | Problems | a source that fails is reported as PROBLEM, the other sources still work |

## Part C — helper (`serve.py`)

| # | What | Checks |
|---|---|---|
| C1 | Start | page served at 127.0.0.1:8765; port busy → friendly message |
| C2 | Safety | requests from other websites or wrong host → "forbidden" |
| C3 | Keywords API | bad data refused; good data written to `keywords.js` |
| C4 | Refresh API | second click while running doesn't start a second search |

## Order of work

1. Build the test runner and test A5 first. It must **fail** on today's page (proves the bug).
2. Fix the keyword panel navigation (Close button, Esc, scroll back). A5 must pass.
3. Add the rest of Part A, then B and C. Fix anything they find, one at a time, and tell you each time.
4. Fix the RAMP duplicate (B4).

## Done when

- `python3 run_tests.py` shows all tests PASS, with zero JavaScript errors.
- Screenshots at 4 widths look right (I describe what I see; you take a final look).
- The keyword panel can be closed in three ways and returns you to the calls.

## Status (24 Nov 2026)

- Built: 16 page workflows (A1–A16, incl. the funder filter), 26 script tests, 7 helper tests, plus `--live`. All PASS.
- Bugs the tests found and that are fixed: keyword panel could not be closed; button row too wide on phones; Refresh message counted hidden calls; "found on" label was overwritten; RAMP duplicate not merged.
- Saved website copies: `tests/fixtures/web/` (refresh them with `python3 tests/web_replay.py record`, then update the expected counts in `tests/test_fetch.py`).
- Added with EU browse + Devpost: A17 (other EU calls toggle, fit badge, sorting), 9 more script tests (fit score, Devpost dates, browse, one card per call). Found by the tests: EU lists a call with several cut-off dates as separate records, so the script now keeps one card per call with the next cut-off. 59 tests, all PASS.
- Added A18 (search box), A19 (dismiss, show, restore, kept after reload) and A20 (NEW badge, "Only new", not tracked for my own CSV). Written first and seen failing, then built. 62 tests, all PASS.
- Added A21–A23 (share one call: details, e-mail draft, copy, system share, Esc/Close; share a list: marked or shown; long list shortened in the e-mail but complete when copied) and 6 tests for `my_calls.csv` (good rows, European Excel format, bad rows reported, old entries dropped, my real file has no typos). All written first, seen failing, then built. 71 tests, all PASS.
- Added A24 (card colours): each kind of data has its own background, words stay, text contrast at least 4.5:1, 4 types = 4 colours, urgency colours, status colours. 72 tests, all PASS.
