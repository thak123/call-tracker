# Call Tracker — plan (updated 24 Nov 2026)

One page where I see open research funding calls, third-party calls, competitions and datathons from real sources, with countdowns, keywords and a summary, so I don't miss a fitting one.

## IN

**Page (`index.html`)**
- Opens with a double-click and shows the newest results by itself (from `live_calls.js`). Only I use it.
- Each call shows: title, funder, type, deadline, link, amount, who can apply, keywords, my status.
- My status per call: interesting · applying · skipped. Saved in the browser.
- **Coloured cards:** funder, type, amount, deadline and each group who can apply (staff, PhD, students) have their own soft background colour; the card's left edge follows the type; the status box is coloured by my status. Words stay on every label, so colour is never the only clue; text contrast is checked (at least 4.5:1).
- Countdown on every open call; open calls sorted by deadline.
- Separate section "Check in the future (already closed)" for calls closed in the last year.
- **Search box** (any word in title, funder, keywords, source; every word must match). **Dismiss** a call to hide it for good ("Show N dismissed" and "Restore" bring it back). **NEW** badge and "Only new (N)" for calls that appeared since my last visit (only for the newest search results; the very first visit marks nothing).
- **Share:** "Share" on each card and "Share list…" at the top open a message with the details (title, funder, deadline, who can apply, amount, topics, link). Send it as an e-mail draft in my own mail program, copy it for a chat, or use the system share sheet where the browser offers it. Nothing is sent by the tool; only public call details are included. Long lists are shortened in the e-mail draft (with a warning) but copy in full.
- Sort: best fit first (default) or by deadline. Filters: type, who can apply, **funder** (incl. "EU-funded only" / "Not EU-funded"), status, keyword (click a tag or a bar in the keyword chart).
- Each card shows the funder (read from the call text), an **EU** badge for EU programmes, and where the call was found.
- Keyword panel closes with "← Back to calls", Esc, the browser's Back button, or "My keywords".
- Summary: four numbers (open, closing within 30 days, applying, closed) and two charts (deadlines per month by type, open calls per keyword). They follow the filters.
- Keyword editor ("My keywords"): add, edit, delete "Search for" keywords and "Not my topics". Not-my-topics hide matching calls right away.
- "Load calls.csv…" for my own spreadsheet (comma or semicolon, dates like 2027-01-15 or 15.1.2027).

**Search (`fetch_calls.py`)** writes `live_calls.csv` and `live_calls.js`
- EU Funding & Tenders Portal: exact-phrase search per keyword; open/closed decided by the real deadline.
- HRZZ: project calls and call news; deadline read from the Croatian text; job ads left out.
- eufondovi.gov.hr (incl. HAMAG-BICRO): research/innovation calls only; results, amendments, school calls and notices left out.
- AMPEU: Erasmus+, CEEPUS, bilateral mobility and scholarships.
- UNIZG: open research funding calls page.
- MZOM: science & international calls (no job ads, procurement, notices).
- UNIRI: news about calls, scholarships and competitions (no job ads or event reports).
- **EU browse:** all open/upcoming EU grant calls (about 520), each with a **fit score** (my keywords in the title +3 each, field words in the title +2, an EU programme close to my field +1). Calls with fit 1 or more show by default; the rest sit behind "Also show N other EU calls". A call with several cut-off dates shows the next one.
- **Devpost:** open AI/data hackathons for students.
- **My list (`my_calls.csv`):** events with no data feed, kept by hand in Excel (title, type, deadline, link, funder, who, keywords, amount). Today: SemEval-2027 shared tasks (join until 31 Jan 2027), SemEval-2027 call for task proposals (13 Apr 2026, for organizers), WMT 2026 (7 Aug 2026). Every date was read from the event's own page. Edit the file, then click Refresh.
- Keywords hold only my topics; the funder is read from the call text (e.g. ERC, HRZZ, Fulbright); the same call from two sites becomes one.
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

1. Run the search automatically every Monday.
2. More sources: CLARIN, EOSC, COST. Watch for a date (not in my list yet because no date is published): CLEF 2027 labs (conference 14-17 Sep 2027; check clef2027.clef-initiative.eu). Update `my_calls.csv` each spring: SemEval-2028 call, WMT 2027, ACL/EMNLP shared tasks.
3. Team use: share status and notes (today they stay in my browser).
4. Left out on purpose: Kaggle (no public feed), fondovieu.gov.hr (terms forbid automated use), Zaklada Adris (not reachable), UNIST (few research calls).

## Done when

1. Double-clicking the page shows the newest real calls with countdowns, keywords and the summary.
2. Filters, status and the keyword editor work, and my choices stay after closing and reopening the page.
3. Closed calls show up only in "Check in the future (already closed)".
4. `python3 fetch_calls.py` finishes without "PROBLEM" lines and reports a count for every source.
5. With `serve.py` running, "Refresh calls" updates the page by itself within a few minutes.

6. `python3 run_tests.py` shows PASS for Parts A, B and C (72 tests); `--live` also checks the real websites.
