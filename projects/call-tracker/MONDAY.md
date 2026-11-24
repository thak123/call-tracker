# Automatic search every Monday: a plan, not built yet

Goal: every Monday morning, the Call Tracker shows fresh real calls without me searching by hand.

## How it would work

1. **Sources list.** A short file of the places I check today, for example:
   - EU Funding & Tenders Portal (grants, has a public search)
   - my national research agency or science foundation
   - my university's research office (newsletter or web page)
   - competition and datathon sites (for example Kaggle, Devpost)
   - foundations and companies that fund third-party research
2. **Monday script.** A small Python script visits each source, picks out the title, funder, deadline, link, amount and who can apply, and writes them into `calls.csv`.
3. **Keywords.** The script adds keywords from the call text, using my own list of interests (for example "NLP", "education", "open data").
4. **Page.** The Call Tracker reads `calls.csv` instead of the made-up list. My status choices stay as they are.
5. **Scheduling.** The script runs on its own every Monday (a scheduled task on my laptop, or a scheduled agent).

## What it needs before we build it

- My list of real sources and interest keywords (no personal data needed).
- OK from my organisation to run a script that reads public websites.
- ~~The page must be able to read a CSV file.~~ Done: "Load calls.csv…" button, tested with made-up calls.

## Watch out for

- Websites change their layout, so a source can silently stop working. The script should report "0 calls found" loudly.
- Some sites forbid automatic reading. Check their terms first.
- Always confirm the deadline on the official call page before applying.

## My choices

- **First source:** the European Commission's public search API (Funding & Tenders Portal):
  `https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA&text=YOUR_KEYWORD`
  (`SEDIA` is the public key the portal itself uses, not a personal password.)
- **My keywords:** artificial intelligence · natural language processing · language acquisition (more to add later).

## Smallest first step

Run the EU search once per keyword, keep only open calls, and save the results into `calls.csv`. Then let the page read that file. Only after that works, schedule it for every Monday.

## Status (24 Nov 2026)

- Built: `fetch_eu_calls.py` searches the EU portal for each keyword (exact phrase) and writes `eu_calls.csv`. Run it with `python3 fetch_eu_calls.py`, then load `eu_calls.csv` in the page.
- First run: 15 calls for "artificial intelligence" (7 open, 8 closed in the last year), 0 for the other two keywords.
- Learned: the EU "open/forthcoming" label is unreliable, so the script decides by deadline date. The search also returns FAQ pages, so it keeps only records with a call number and a deadline.
- Not filled in yet: amount (says "see call page") and who can apply (set to staff;PhD for all EU calls).
- Not done yet: running automatically every Monday.

## Update (24 Nov 2026): two sources, keywords on the page

- `fetch_calls.py` replaces `fetch_eu_calls.py`. It searches the EU portal and HRZZ (hrzz.hr, project calls and call news; job ads left out) and writes `live_calls.csv`.
- HRZZ deadlines are read from the Croatian text ("rok prijave 25. veljače 2027."). Posts without a clear date are listed under "Check by hand".
- Keywords and "not my topics" now live in `keywords.js`. Edit them on the page (My keywords → Save to keywords.js). The script reads the same file.
- HRZZ titles are Croatian, so add Croatian words to "not my topics" too (for example "klimat").

## Update: Refresh button (24 Nov 2026)

- `python3 serve.py` starts a small helper on this laptop only (http://127.0.0.1:8765) and opens the tracker.
- "Refresh calls" runs `fetch_calls.py` in the background (about 35 seconds). The cards update by themselves when it's done and show how many new open calls arrived.
- "Save to keywords.js" writes the file directly when the page runs through the helper.
- Without the helper, double-clicking index.html still shows the newest results (from `live_calls.js`).

## Update: three Croatian sources (24 Nov 2026)

- Added eufondovi.gov.hr (research/innovation calls only; includes HAMAG-BICRO), AMPEU (/natjecaji list) and UNIZG (open research calls page).
- First run: 31 calls, 13 open. AMPEU deadlines matched the website; one eufondovi deadline checked against its page.
- UNIZG's open-calls page hasn't been updated since 2023, so it gives 0 calls for now.
- Still to add: MZOM, UNIRI, fondovieu.gov.hr. Not possible right now: Zaklada Adris (site not reachable), UNIST (few research calls).
