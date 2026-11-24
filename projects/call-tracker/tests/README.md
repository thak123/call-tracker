# Tests

Run everything from the `call-tracker` folder:

```
python3 run_tests.py          # parts A, B, C
python3 run_tests.py A        # only one part (A page, B search script, C helper)
python3 run_tests.py --live   # also ask the real websites once
```

| File | What it tests |
|---|---|
| `ui.test.mjs` + `cdp.mjs` | A: page click paths, in the Chrome installed on this laptop (hidden window) |
| `test_fetch.py` + `web_replay.py` | B: search script, on saved website copies |
| `test_serve.py` | C: the helper `serve.py` |
| `live_check.py` | `--live`: do the real websites still answer? |
| `fixtures/` | made-up test data, plus the saved website copies |

## Saved website copies (not in Git)

`fixtures/web/*.gz` are compressed copies of what the real websites answered once. They are in
`.gitignore`. `run_tests.py` re-creates them automatically when they are missing. To refresh them by hand:

```
python3 tests/web_replay.py record
```

Needs internet. The real websites change, so after re-recording, the expected call counts in
`test_fetch.py` (for example "27 UNIRI calls") may need a new number.

## Other things the tests need

- Chrome or Chromium, and Node.js 22 or newer (for part A). Nothing else to install.
- Test screenshots land in `tests/screenshots/` (also not in Git).
