# Call Tracker — plan (updated 24 Nov 2026)

One page where I see open research funding calls, third-party calls, competitions and datathons from real sources, with countdowns, keywords and a summary, so I don't miss a fitting one.

## IN

**Page (`index.html`)**
- Opens with a double-click and shows the newest results by itself (from `live_calls.js`). Only I use it.
- Each call shows: title, funder, type, deadline, link, amount, who can apply, keywords, my status.
- My status per call: interesting · applying · skipped. Saved in the browser.
- Countdown on every open call; open calls sorted by deadline.
- Separate section "Check in the future (already closed)" for calls closed in the last year.
- Filters: type, who can apply, status, keyword (click a tag or a bar in the keyword chart).
- Summary: four numbers (open, closing within 30 days, applying, closed) and two charts (deadlines per month by type, open calls per keyword). They follow the filters.
- Keyword editor ("My keywords"): add, edit, delete "Search for" keywords and "Not my topics". Not-my-topics hide matching calls right away.
- "Load calls.csv…" for my own spreadsheet (comma or semicolon, dates like 2027-01-15 or 15.1.2027).

**Search (`fetch_calls.py`)** writes `live_calls.csv` and `live_calls.js`
- EU Funding & Tenders Portal: exact-phrase search per keyword; open/closed decided by the real deadline.
- HRZZ: project calls and call news; deadline read from the Croatian text; job ads left out.
- eufondovi.gov.hr (incl. HAMAG-BICRO): research/innovation calls only; results, amendments, school calls and notices left out.
- AMPEU: Erasmus+, CEEPUS, bilateral mobility and scholarships.
- UNIZG: open research funding calls page.
- Calls whose title contains a "Not my topics" word are left out and listed in the report.
- Posts without a clear deadline are listed under "Check by hand".

**Helper (`serve.py`)**, optional, on this laptop only (127.0.0.1)
- "Refresh calls" runs the search in the background; the page updates by itself and shows how many new open calls arrived.
- "Save to keywords.js" writes the keyword file directly.
- Refuses requests from other websites.

**Settings:** `keywords.js`, read by both the page and the script.

## OUT

- No help writing applications.
- No reminders by e-mail or calendar.
- No personal data sent anywhere: only my keywords go to the EU search; the other sites are only read.
- Nothing published online; the helper is not reachable from other computers.
- Amount and "who can apply" are not read from the sources yet ("see call page", default staff/PhD).

## Data

- Real public calls from the sources above.
- `calls.csv` and the built-in sample stay as made-up test data.

## Next

1. Add MZOM, UNIRI and fondovieu.gov.hr.
2. Run the search automatically every Monday.
3. Not possible right now: Zaklada Adris (site not reachable), UNIST (few research calls).

## Done when

1. Double-clicking the page shows the newest real calls with countdowns, keywords and the summary.
2. Filters, status and the keyword editor work, and my choices stay after closing and reopening the page.
3. Closed calls show up only in "Check in the future (already closed)".
4. `python3 fetch_calls.py` finishes without "PROBLEM" lines and reports a count for every source.
5. With `serve.py` running, "Refresh calls" updates the page by itself within a few minutes.
