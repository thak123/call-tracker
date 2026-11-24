// Part A: page workflows. "I click X, I expect Y."
// Runs on a copy of index.html with fixed test data (tests/fixtures/site) and a fixed date (24 Nov 2026).
import { test, before, after, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, copyFileSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, sleep } from "./cdp.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = join(HERE, "..");
const FIX = join(HERE, "fixtures", "site");
export const SITE = join(HERE, ".tmp", "site");
const SHOTS = join(HERE, "screenshots");
const URL = "file://" + join(SITE, "index.html");

export function buildSite(dir = SITE) {
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  copyFileSync(join(APP, "index.html"), join(dir, "index.html"));
  copyFileSync(join(FIX, "keywords.js"), join(dir, "keywords.js"));
  const csv = readFileSync(join(FIX, "live_calls.csv"), "utf8");
  copyFileSync(join(FIX, "live_calls.csv"), join(dir, "live_calls.csv"));
  writeFileSync(join(dir, "live_calls.js"),
    "window.LIVE_CALLS = " + JSON.stringify({ generated: "2026-11-24T08:00:00+01:00", csv }) + ";\n");
}

let browser, page;
before(async () => { buildSite(); mkdirSync(SHOTS, { recursive: true }); browser = await launchBrowser(); });
after(async () => { await browser?.close(); });
beforeEach(async () => {
  page = await browser.newPage();
  await page.goto(URL); await page.eval("localStorage.clear()"); await page.goto(URL);
});
afterEach(async () => {
  assert.deepEqual(page.errors, [], "JavaScript errors on the page");
  await page.close();
});

const openCount = () => page.text("#openCount");
const closedCount = () => page.text("#closedCount");
const panelOpen = () => page.visible("#kwPanel .kwcols");

// ---------------------------------------------------------------- A5
test("A5 keyword panel: open and close in every way, and get back to the calls", async () => {
  await page.click("#kwToggle");
  assert.equal(await panelOpen(), true, "panel opens with 'My keywords'");
  assert.equal(await page.eval(`document.getElementById("kwToggle").getAttribute("aria-expanded")`), "true");

  // 1. a Close button inside the panel
  assert.equal(await page.visible("#kwClose"), true, "panel has a visible Close button");
  await page.click("#kwClose");
  assert.equal(await panelOpen(), false, "Close button closes the panel");
  assert.equal(await page.eval(`document.getElementById("kwToggle").getAttribute("aria-expanded")`), "false");
  assert.ok(await page.eval(`document.querySelector(".summary").getBoundingClientRect().top < innerHeight`),
            "after closing, the calls summary is in view");

  // 2. the Esc key
  await page.click("#kwToggle");
  await page.key("Escape");
  assert.equal(await panelOpen(), false, "Esc closes the panel");

  // 3. the browser Back button
  await page.click("#kwToggle");
  await page.eval("history.back()"); await sleep(300);
  assert.equal(await panelOpen(), false, "browser Back closes the panel");

  // 4. 'My keywords' again
  await page.click("#kwToggle");
  await page.click("#kwToggle");
  assert.equal(await panelOpen(), false, "'My keywords' toggles it closed");

  // Esc while editing a keyword cancels the edit, not the whole panel
  await page.click("#kwToggle");
  await page.click("[data-list=keywords] li .edit");
  await page.key("Escape");
  assert.equal(await panelOpen(), true, "Esc inside an edit only cancels the edit");
  assert.equal(await page.eval(`!!document.querySelector("[data-list=keywords] li input")`), false, "edit box is gone");
});

// ---------------------------------------------------------------- helpers for the tests below
const select = async (id, value) => { await page.eval(`(() => { const s = document.getElementById("${id}"); s.value = ${JSON.stringify(value)}; s.dispatchEvent(new Event("change")); })()`); await sleep(80); };
const tile = id => page.text("#" + id);
const addWord = async (list, word) => {
  await page.type(`[data-list=${list}] .kwadd input`, word);
  await page.click(`[data-list=${list}] .kwadd button`);
};
const words = list => page.eval(`[...document.querySelectorAll("[data-list=${list}] .word")].map(w => w.textContent)`);
const kwError = list => page.eval(`(e => e.hidden ? "" : e.textContent)(document.querySelector("[data-list=${list}] .kwerr"))`);
const CSV = name => join(HERE, "fixtures", "csv", name);

// ---------------------------------------------------------------- A1
test("A1 open the page: newest results load by themselves and the numbers agree", async () => {
  assert.match(await page.text("#sourceInfo"), /newest results \(24 Nov, 08:00\) \(10 calls, 1 hidden as not my topics\)/);
  assert.equal(await openCount(), "(7)");
  assert.equal(await closedCount(), "(2)");
  assert.equal(await page.eval(`document.querySelectorAll("#openList .card").length`), 7);
  assert.equal(await tile("tOpen"), "7");
  assert.equal(await tile("tSoon"), "3", "closing within 30 days: 3, 10 and 26 days");
  assert.equal(await tile("tClosed"), "2");
  assert.equal(await page.text("#openList .card .countdown"), "3 days left", "soonest deadline first");
  assert.equal(await page.visible("#sampleNote"), false, "no 'made-up' note for real results");
});

// ---------------------------------------------------------------- A2
test("A2 filters narrow the cards and 'All' brings them back", async () => {
  await select("fType", "datathon");
  assert.equal(await openCount(), "(1)"); assert.equal(await closedCount(), "(1)");
  await select("fType", ""); await select("fWho", "students");
  assert.equal(await openCount(), "(2)"); assert.equal(await closedCount(), "(1)");
  await select("fWho", "staff"); await select("fType", "grant");
  assert.equal(await openCount(), "(4)", "grant + staff combined");
  assert.equal(await tile("tOpen"), "4", "summary follows the filters");
  await select("fType", ""); await select("fWho", "");
  assert.equal(await openCount(), "(7)");
  await select("fType", "competition"); await select("fWho", "PhD");
  assert.equal(await page.text("#openList .empty"), "No calls match the filters.");
});

// ---------------------------------------------------------------- A3
test("A3 keyword filter: card tag, keyword chart and 'show all'", async () => {
  await page.click('#openList .tag[title="Show only calls with this keyword"]:not([data-x])');
  const first = await page.text("#kwName");
  assert.ok(first, "a keyword filter is active");
  await page.click("#kwClear");
  assert.equal(await openCount(), "(7)");
  await page.eval(`[...document.querySelectorAll("#openList .tag")].find(t => t.textContent === "artificial intelligence").setAttribute("data-pick", "1")`);
  await page.click('#openList .tag[data-pick="1"]');
  assert.equal(await page.text("#kwName"), "artificial intelligence");
  assert.equal(await openCount(), "(3)"); assert.equal(await closedCount(), "(0)");
  await page.click("#kwClear");
  await page.eval(`[...document.querySelectorAll("#kwChart button")].find(b => b.textContent === "speech recognition").setAttribute("data-pick", "1")`);
  await page.click('#kwChart button[data-pick="1"]');
  assert.equal(await page.text("#kwName"), "speech recognition");
  assert.equal(await openCount(), "(1)");
});

// ---------------------------------------------------------------- A4
test("A4 my status: set, counted, kept after reload, filterable", async () => {
  await page.eval(`(() => { const s = document.querySelector("#openList .card select"); s.value = "applying"; s.dispatchEvent(new Event("change")); })()`);
  assert.equal(await tile("tApply"), "1");
  await page.reload();
  assert.equal(await page.eval(`document.querySelector("#openList .card select").value`), "applying", "kept after reload");
  await select("fStatus", "applying");
  assert.equal(await openCount(), "(1)");
  await select("fStatus", "none");
  assert.equal(await openCount(), "(6)");
});

// ---------------------------------------------------------------- A6
test("A6 keyword editing: add, mistakes, edit, cancel, delete", async () => {
  await page.click("#kwToggle");
  await addWord("keywords", "dialogue systems");
  assert.ok((await words("keywords")).includes("dialogue systems"), "added");
  assert.equal(await page.text("[data-list=keywords] .kwcount"), "(5)");
  await page.click("[data-list=keywords] .kwadd button");
  assert.equal(await kwError("keywords"), "Please type a word first.");
  await addWord("keywords", "a");
  assert.equal(await kwError("keywords"), "Too short: use at least 2 letters.");
  await page.eval(`document.querySelector("[data-list=keywords] .kwadd input").value = ""`);
  await addWord("keywords", "Multilingual");
  assert.equal(await kwError("keywords"), '"Multilingual" is already in this list.');
  await page.eval(`document.querySelector("[data-list=keywords] .kwadd input").value = ""`);
  await addWord("keywords", "climate");
  assert.match(await kwError("keywords"), /already in the other list/);
  await page.eval(`document.querySelector("[data-list=keywords] .kwadd input").value = ""`);
  // edit + save
  await page.click("[data-list=keywords] li .edit");
  await page.eval(`document.querySelector("[data-list=keywords] li input").value = "NLP"`);
  await page.click("[data-list=keywords] li .ok");
  assert.equal((await words("keywords"))[0], "NLP", "edited");
  // edit + Enter
  await page.click("[data-list=keywords] li .edit");
  await page.eval(`document.querySelector("[data-list=keywords] li input").value = "nlp research"`);
  await page.key("Enter");
  assert.equal((await words("keywords"))[0], "nlp research", "Enter saves the edit");
  // edit + cancel
  await page.click("[data-list=keywords] li .edit");
  await page.eval(`document.querySelector("[data-list=keywords] li input").value = "should not stay"`);
  await page.click("[data-list=keywords] li .cancel");
  assert.equal((await words("keywords"))[0], "nlp research", "Cancel keeps the old word");
  // delete
  await page.click("[data-list=keywords] li .del");
  assert.ok(!(await words("keywords")).includes("nlp research"), "deleted");
  assert.equal(await page.text("[data-list=keywords] .kwcount"), "(4)");
});

// ---------------------------------------------------------------- A7
test("A7 not my topics: hides matching cards right away and brings them back", async () => {
  await page.click("#kwToggle");
  await addWord("exclude", "Datathon");
  assert.match(await page.text("#sourceInfo"), /2 hidden as not my topics/);
  assert.equal(await openCount(), "(6)");
  assert.match(await page.eval(`[...document.querySelectorAll("[data-list=exclude] li")].find(l => l.querySelector(".word").textContent === "Datathon").querySelector(".uses").textContent`), /1 hidden/);
  await page.eval(`[...document.querySelectorAll("[data-list=exclude] li")].find(l => l.querySelector(".word").textContent === "Datathon").querySelector(".del").setAttribute("data-pick", "1")`);
  await page.click('[data-list=exclude] .del[data-pick="1"]');
  assert.equal(await openCount(), "(7)");
});

// ---------------------------------------------------------------- A8
test("A8 unsaved changes survive a reload and 'Undo changes' goes back to the file", async () => {
  await page.click("#kwToggle");
  assert.equal(await page.eval(`document.getElementById("kwUndo").disabled`), true, "nothing to undo yet");
  await addWord("keywords", "corpus linguistics");
  assert.match(await page.text("#kwState"), /Unsaved changes/);
  await page.reload();
  assert.equal(await panelOpen(), true, "panel is still open after reload (#keywords in the address)");
  assert.ok((await words("keywords")).includes("corpus linguistics"), "draft kept after reload");
  await page.click("#kwUndo");
  assert.ok(!(await words("keywords")).includes("corpus linguistics"), "undo removes it");
  assert.equal(await page.text("#kwState"), "Saved in keywords.js");
});

// ---------------------------------------------------------------- A9 (without helper)
test("A9 save keywords without the helper: download with clear instructions", async () => {
  const dl = join(HERE, ".tmp", "downloads"); rmSync(dl, { recursive: true, force: true }); mkdirSync(dl, { recursive: true });
  const p2 = await browser.newPage({ downloads: dl });
  await p2.goto(URL); await p2.eval("localStorage.clear(); window.showSaveFilePicker = undefined");
  await p2.click("#kwToggle");
  await p2.type("[data-list=keywords] .kwadd input", "text mining");
  await p2.click("[data-list=keywords] .kwadd button");
  await p2.click("#kwSave"); await sleep(800);
  assert.match(await p2.text("#kwState"), /Downloaded keywords.js: move it into the call-tracker folder/);
  const file = readFileSync(join(dl, "keywords.js"), "utf8");
  assert.match(file, /"text mining"/);
  assert.match(file, /window\.CALL_TRACKER_SETTINGS = /);
  assert.deepEqual(p2.errors, []); await p2.close();
});

// ---------------------------------------------------------------- A10
test("A10 load CSV files: good, bad rows, wrong file, European Excel, back to sample", async () => {
  await page.setFile("#csvFile", join(APP, "calls.csv"));
  assert.match(await page.text("#sourceInfo"), /calls\.csv \(6 calls\)/);
  await page.setFile("#csvFile", CSV("bad.csv"));
  assert.match(await page.text("#sourceInfo"), /bad\.csv \(1 calls\)/);
  assert.match(await page.text("#loadMsg"), /Row 3 \("Bad Date Call"\).*skipped\. Row 4: no title, skipped\./);
  await page.setFile("#csvFile", CSV("wrong.csv"));
  assert.match(await page.text("#loadMsg"), /Could not load wrong\.csv: Missing column\(s\): title, type, deadline/);
  assert.match(await page.text("#sourceInfo"), /bad\.csv/, "old data stays after a refused file");
  await page.setFile("#csvFile", CSV("euro.csv"));
  assert.match(await page.text("#sourceInfo"), /euro\.csv \(2 calls\)/);
  assert.match(await page.text("#loadMsg"), /31\.2\.2027/);
  await page.click("#sampleBtn");
  assert.match(await page.text("#sourceInfo"), /made-up sample \(12 calls/);
  assert.equal(await page.visible("#sampleNote"), true);
});

// ---------------------------------------------------------------- A11
test("A11 on open: my own CSV wins if loaded after the last search, otherwise newest results", async () => {
  await page.setFile("#csvFile", join(APP, "calls.csv"));
  await page.reload();
  assert.match(await page.text("#sourceInfo"), /calls\.csv/, "own file loaded after the search stays");
  await page.eval(`(() => { const m = JSON.parse(localStorage.getItem("callTracker.csv")); m.loadedAt = "2026-11-23T09:00:00Z"; localStorage.setItem("callTracker.csv", JSON.stringify(m)); })()`);
  await page.reload();
  assert.match(await page.text("#sourceInfo"), /newest results/, "newer search results win over an older file");
});

// ---------------------------------------------------------------- A12
test("A12 summary: chart totals and hover tooltip match the cards", async () => {
  const bars = await page.eval(`[...document.querySelectorAll("#monthsChart text.val")].reduce((a, t) => a + +t.textContent, 0)`);
  assert.equal(bars, 6, "6 open calls close in the next 12 months");
  assert.match(await page.text("#monthsHint"), /1 call close later/);
  const kw = await page.eval(`Object.fromEntries([...document.querySelectorAll("#kwChart button")].map(b => [b.textContent, +b.nextSibling.nextSibling.textContent]))`);
  assert.equal(kw["artificial intelligence"], 3);
  const box = await page.eval(`(r => ({ x: r.x + r.width / 2, y: r.y + r.height - 4 }))(document.querySelector('#monthsChart .hit[data-i="1"]').getBoundingClientRect())`);
  await page.hover(box.x, box.y);
  const tip = await page.eval(`document.getElementById("tip").innerText`);
  assert.match(tip, /December 2026: 2 calls/);
  assert.match(tip, /NLP Research Grant/);
});

// ---------------------------------------------------------------- A13
test("A13 Refresh without the helper explains how to start it", async () => {
  await page.click("#refreshBtn");
  assert.match(await page.text("#refreshMsg"), /python3 serve\.py/);
  assert.equal(await openCount(), "(7)", "nothing else changes");
});

// ---------------------------------------------------------------- A14 (with helper)
test("A14 Refresh and Save with the helper: background run, cards update, errors shown", async () => {
  const { spawn } = await import("node:child_process");
  const dir = join(HERE, ".tmp", "helper");
  buildSite(dir);
  copyFileSync(join(APP, "serve.py"), join(dir, "serve.py"));
  copyFileSync(join(HERE, "fixtures", "helper", "fetch_calls.py"), join(dir, "fetch_calls.py"));
  const port = String(18000 + Math.floor(Math.random() * 1000));
  const proc = spawn("python3", [join(dir, "serve.py"), "--no-browser"], { env: { ...process.env, CT_PORT: port }, stdio: "ignore" });
  try {
    for (let i = 0; i < 40; i++) { try { await fetch(`http://127.0.0.1:${port}/`); break; } catch { await sleep(150); } }
    const p = await browser.newPage();
    await p.goto(`http://127.0.0.1:${port}/`); await p.eval("localStorage.clear()"); await p.reload();
    assert.equal(await p.text("#openCount"), "(7)");
    await p.click("#refreshBtn"); await sleep(400);
    assert.equal(await p.eval(`document.getElementById("refreshBtn").disabled`), true, "button disabled while running");
    assert.match(await p.text("#refreshMsg"), /Searching the EU portal and HRZZ/);
    for (let i = 0; i < 40 && await p.eval(`document.getElementById("refreshBtn").disabled`); i++) await sleep(250);
    await sleep(500);
    assert.match(await p.text("#refreshMsg"), /Updated .*11 calls, 8 open, 1 new open since before/);
    assert.equal(await p.text("#openCount"), "(8)", "cards updated by themselves");
    // failing search keeps the old data and shows the problem
    writeFileSync(join(dir, "FAIL"), "");
    await p.click("#refreshBtn");
    for (let i = 0; i < 40 && await p.eval(`document.getElementById("refreshBtn").disabled !== false || !document.getElementById("refreshMsg").classList.contains("bad")`); i++) await sleep(250);
    assert.match(await p.text("#refreshMsg"), /Refresh had a problem \(code 1\).*pretend the EU portal is down/s);
    assert.equal(await p.text("#openCount"), "(8)", "old data kept");
    // save keywords straight into the folder
    await p.click("#kwToggle");
    await p.type("[data-list=keywords] .kwadd input", "question answering");
    await p.click("[data-list=keywords] .kwadd button");
    await p.click("#kwSave"); await sleep(500);
    assert.equal(await p.text("#kwState"), "Saved in keywords.js");
    assert.match(readFileSync(join(dir, "keywords.js"), "utf8"), /"question answering"/);
    assert.deepEqual(p.errors, []); await p.close();
  } finally { proc.kill(); }
});

// ---------------------------------------------------------------- A15
test("A15 layout at 4 screen widths: centred, no sideways scrolling (screenshots saved)", async () => {
  for (const width of [1440, 1000, 820, 375]) {
    const p = await browser.newPage({ width, height: 1000 });
    await p.goto(URL);
    assert.ok(await p.eval(`document.documentElement.scrollWidth <= innerWidth + 1`), `no sideways scrolling at ${width}px`);
    if (width >= 1300) {
      const gaps = await p.eval(`(r => [r.left, innerWidth - r.right])(document.querySelector(".summary").getBoundingClientRect())`);
      assert.ok(Math.abs(gaps[0] - gaps[1]) < 30, `content centred at ${width}px (${gaps})`);
    }
    await p.screenshot(join(SHOTS, `page-${width}.png`));
    await p.click("#kwToggle");
    assert.ok(await p.eval(`document.documentElement.scrollWidth <= innerWidth + 1`), `keyword panel fits at ${width}px`);
    await p.screenshot(join(SHOTS, `keywords-${width}.png`));
    assert.deepEqual(p.errors, []); await p.close();
  }
});

// ---------------------------------------------------------------- A16
test("A16 funder filter and EU tag; sources are not keywords", async () => {
  const options = await page.eval(`[...document.getElementById("fFunder").options].map(o => o.textContent)`);
  assert.deepEqual(options.slice(0, 3), ["All", "EU-funded only (2)", "Not EU-funded (7)"]);
  assert.ok(options.includes("Test Fund A (2)"), "each funder listed with its count");
  await select("fFunder", "__eu");
  assert.equal(await openCount(), "(2)");
  assert.equal(await page.eval(`[...document.querySelectorAll("#openList .card")].every(c => c.querySelector(".eu"))`), true, "EU badge on every EU card");
  await select("fFunder", "__noneu");
  assert.equal(await openCount(), "(5)");
  assert.equal(await page.eval(`document.querySelectorAll("#openList .card .eu").length`), 0);
  await select("fFunder", "Test Fund A");
  assert.equal(await openCount(), "(1)"); assert.equal(await closedCount(), "(1)");
  await select("fFunder", "");
  const tags = await page.eval(`[...document.querySelectorAll(".card .tag")].map(t => t.textContent)`);
  for (const source of ["HRZZ", "UNIRI", "MZOM", "AMPEU", "EU portal"]) assert.ok(!tags.includes(source), `${source} is not shown as a keyword`);
  assert.match(await page.eval(`[...document.querySelectorAll(".card")].find(c => c.textContent.includes("Machine Translation")).textContent`), /found on MZOM, UNIRI/);
});

// ---------------------------------------------------------------- A17
test("A17 other EU calls: hidden by default, 'Also show' reveals them, fit badge and sorting", async () => {
  await page.setFile("#csvFile", CSV("browse.csv"));
  assert.match(await page.text("#sourceInfo"), /browse\.csv \(6 calls, 1 hidden as not my topics, 2 other EU calls hidden\)/);
  assert.equal(await openCount(), "(3)", "keyword match + two browse calls with fit 1 or more");
  assert.equal(await page.visible("#otherToggle"), true);
  assert.equal(await page.text("#otherCount"), "2");
  assert.match(await page.text("#otherToggle"), /Also show 2 other EU calls/);
  assert.equal(await page.eval(`[...document.querySelectorAll("#openList .card .title")].some(t => t.textContent.includes("No Fit"))`), false);
  // fit badge
  assert.match(await page.eval(`[...document.querySelectorAll("#openList .card")].find(c => c.textContent.includes("Strong Fit")).textContent`), /fit 5/);
  // best fit first is the default; the sort box can switch to deadline
  assert.equal(await page.eval(`document.getElementById("fSort").value`), "fit");
  assert.deepEqual(await page.eval(`[...document.querySelectorAll("#openList .card .title")].map(t => t.textContent)`),
    ["Browse Call Strong Fit", "Keyword Match Call", "Browse Call Some Fit"]);
  await select("fSort", "deadline");
  assert.equal(await page.eval(`document.querySelector("#openList .card .title").textContent`), "Keyword Match Call");
  // reveal the rest
  await page.click("#fOther");
  assert.equal(await openCount(), "(5)");
  assert.equal(await page.visible("#otherToggle"), true, "toggle stays so I can hide them again");
  assert.doesNotMatch(await page.text("#sourceInfo"), /other EU calls hidden/);
  assert.deepEqual(await page.eval(`[...document.getElementById("fFunder").options].slice(0, 3).map(o => o.textContent)`),
    ["All", "EU-funded only (4)", "Not EU-funded (1)"], "funder counts follow what is shown (climate one is hidden as not my topic)");
  await page.click("#fOther");
  assert.equal(await openCount(), "(3)");
});

// ---------------------------------------------------------------- A18
const search = async text => {
  await page.eval(`(() => { const i = document.getElementById("fSearch"); i.value = ""; i.dispatchEvent(new Event("input")); })()`);
  if (text) await page.type("#fSearch", text);
  await sleep(100);
};
test("A18 search box: finds words in title, funder and keywords; all words must match", async () => {
  assert.equal(await page.visible("#fSearch"), true);
  await search("speech");
  assert.equal(await openCount(), "(1)", "title and keyword 'speech recognition'");
  await search("SPEECH");
  assert.equal(await openCount(), "(1)", "capital letters do not matter");
  await search("test lab");
  assert.equal(await openCount(), "(1)"); assert.equal(await closedCount(), "(1)", "funder name, open and closed");
  await search("lab speech");
  assert.equal(await closedCount(), "(1)", "'hate speech' keyword of the closed call");
  await search("recognition lab");
  assert.equal(await openCount(), "(1)"); assert.equal(await closedCount(), "(0)", "every word must match, in any order");
  await search("machine translation");
  assert.equal(await openCount(), "(1)");
  await search("zzzz");
  assert.equal(await page.text("#openList .empty"), "No calls match the filters.");
  assert.equal(await tile("tOpen"), "0", "summary follows the search");
  await search("");
  assert.equal(await openCount(), "(7)");
  await search("grant"); await select("fType", "datathon");
  assert.equal(await openCount(), "(0)", "search combines with the other filters");
});

// ---------------------------------------------------------------- A19
test("A19 dismiss a call: hidden for good, can be shown again and restored", async () => {
  const firstTitle = await page.text("#openList .card .title");
  assert.equal(await page.visible("#dismissedToggle"), false, "nothing dismissed yet");
  await page.click("#openList .card .dismiss");
  assert.equal(await openCount(), "(6)");
  assert.equal(await tile("tOpen"), "6");
  assert.notEqual(await page.text("#openList .card .title"), firstTitle, "card is gone");
  await page.reload();
  assert.equal(await openCount(), "(6)", "still dismissed after reload");
  assert.equal(await page.visible("#dismissedToggle"), true);
  assert.match(await page.text("#dismissedToggle"), /Show 1 dismissed/);
  await page.click("#fDismissed");
  assert.equal(await openCount(), "(7)");
  assert.equal(await page.eval(`[...document.querySelectorAll("#openList .card")].find(c => c.querySelector(".title").textContent === ${JSON.stringify(firstTitle)}).querySelector(".dismiss").textContent`), "Restore");
  await page.eval(`[...document.querySelectorAll("#openList .card")].find(c => c.querySelector(".title").textContent === ${JSON.stringify(firstTitle)}).querySelector(".dismiss").setAttribute("data-pick", "1")`);
  await page.click('#openList .dismiss[data-pick="1"]');
  assert.equal(await page.visible("#dismissedToggle"), false, "nothing dismissed any more");
  assert.equal(await openCount(), "(7)");
  await page.reload();
  assert.equal(await openCount(), "(7)", "restored for good");
});

// ---------------------------------------------------------------- A20
test("A20 NEW badge: calls that appeared since my last visit", async () => {
  // first visit ever: nothing is marked new
  assert.equal(await page.eval(`document.querySelectorAll(".newtag").length`), 0);
  assert.equal(await page.visible("#newToggle"), false);
  // pretend I last saw every call except "Late Big Grant" (t07)
  await page.eval(`localStorage.setItem("callTracker.seen", JSON.stringify(["t01","t02","t03","t04","t05","t06","t08","t09","t10"]))`);
  await page.reload();
  assert.equal(await page.eval(`document.querySelectorAll("#openList .newtag").length`), 1);
  assert.match(await page.eval(`[...document.querySelectorAll("#openList .card")].find(c => c.querySelector(".newtag")).textContent`), /Late Big Grant/);
  assert.equal(await page.visible("#newToggle"), true);
  assert.match(await page.text("#newToggle"), /Only new \(1\)/);
  await page.click("#fNew");
  assert.equal(await openCount(), "(1)"); assert.equal(await closedCount(), "(0)");
  await page.click("#fNew");
  assert.equal(await openCount(), "(7)");
  // next visit: already seen
  await page.reload();
  assert.equal(await page.eval(`document.querySelectorAll(".newtag").length`), 0, "no longer new on the next visit");
  // loading my own CSV does not change what I have seen
  const before = await page.eval(`localStorage.getItem("callTracker.seen")`);
  await page.setFile("#csvFile", join(APP, "calls.csv"));
  assert.equal(await page.eval(`localStorage.getItem("callTracker.seen")`), before);
  assert.equal(await page.eval(`document.querySelectorAll(".newtag").length`), 0, "no NEW badges on my own file");
});

// ---------------------------------------------------------------- A21 – A23: share
const shareOpen = () => page.eval(`document.getElementById("shareDialog").open`);
const shareText = () => page.eval(`document.getElementById("shareText").value`);
const mailto = () => page.eval(`decodeURIComponent(document.getElementById("shareEmail").getAttribute("href"))`);
const markStatus = (index, value) => page.eval(`(() => { const s = document.querySelectorAll("#openList .card select")[${index}]; s.value = ${JSON.stringify(value)}; s.dispatchEvent(new Event("change")); })()`);

test("A21 share one call: message with details, e-mail draft, copy, system share", async () => {
  assert.equal(await shareOpen(), false);
  await page.click("#openList .card .share");
  assert.equal(await shareOpen(), true, "Share opens a window");
  const text = await shareText();
  for (const part of ["Funding call: Last Week Grant", "Funder: Test Fund D", "Type: grant · Deadline: 27 Nov 2026 (3 days left)",
                      "Who can apply: staff · Amount: €10", "Topics: multilingual", "Link: https://example.com/t10"])
    assert.ok(text.includes(part), `message contains "${part}"`);
  assert.ok(!text.includes("My status"), "no status line when none is set");
  // e-mail draft
  const m = await mailto();
  assert.ok(m.startsWith("mailto:?subject=Call: Last Week Grant (deadline 27 Nov 2026)&body=Funding call: Last Week Grant"), m.slice(0, 120));
  // editing the message changes the draft
  await page.eval(`(() => { const t = document.getElementById("shareText"); t.value = "Hello colleague,\\n\\n" + t.value; t.dispatchEvent(new Event("input")); })()`);
  assert.match(await mailto(), /body=Hello colleague,/);
  // copy
  await page.eval(`Object.defineProperty(navigator, "clipboard", { value: { writeText: async t => { window.__copied = t; } }, configurable: true })`);
  await page.click("#shareCopy");
  assert.equal(await page.eval(`window.__copied`), await shareText(), "copied exactly what is shown");
  assert.match(await page.text("#shareMsg"), /Copied/);
  // no system share where the browser does not offer it
  assert.equal(await page.visible("#shareNative"), false);
  // Esc closes
  await page.key("Escape");
  assert.equal(await shareOpen(), false, "Esc closes the share window");
  // my status is included when set; system share sheet where available
  await markStatus(0, "interesting");
  await page.eval(`navigator.share = async d => { window.__shared = d; }`);
  await page.click("#openList .card .share");
  assert.match(await shareText(), /My status: interesting/);
  assert.equal(await page.visible("#shareNative"), true, "system share offered when the browser supports it");
  await page.click("#shareNative");
  const shared = await page.eval(`window.__shared`);
  assert.match(shared.title, /Last Week Grant/); assert.equal(shared.text, await shareText());
  await page.click("#shareClose");
  assert.equal(await shareOpen(), false, "Close button closes it");
});

test("A22 share a list: calls I marked, or the calls shown now", async () => {
  // nothing marked: defaults to the calls shown now
  await page.click("#shareListBtn");
  assert.equal(await shareOpen(), true);
  assert.equal(await page.eval(`document.getElementById("shareScope").value`), "shown");
  assert.match(await shareText(), /Funding calls to look at \(7\)/);
  await page.key("Escape");
  // mark two calls, then share the marked ones
  await markStatus(0, "interesting"); await markStatus(1, "applying");
  await page.click("#shareListBtn");
  assert.equal(await page.eval(`document.getElementById("shareScope").value`), "marked");
  const text = await shareText();
  assert.match(text, /^Funding calls to look at \(2\)/);
  assert.match(text, /1\. Last Week Grant\n\s+Test Fund D · deadline 27 Nov 2026 \(3 days left\) · interesting\n\s+https:\/\/example\.com\/t10/);
  assert.match(text, /2\. NLP Research Grant/);
  assert.ok(!text.includes("3. "), "only the two marked calls");
  assert.match(await mailto(), /^mailto:\?subject=Funding calls to look at \(2\)&body=/);
  // switch to the calls shown now
  await page.eval(`(() => { const s = document.getElementById("shareScope"); s.value = "shown"; s.dispatchEvent(new Event("change")); })()`);
  assert.match(await shareText(), /Funding calls to look at \(7\)/);
  await page.key("Escape");
});

test("A23 a long list: the e-mail draft is shortened, the copied text is complete", async () => {
  const rows = ["id,title,funder,type,deadline,link,amount,who,keywords"];
  for (let i = 1; i <= 14; i++)
    rows.push(`L${i},Long call title number ${i} ${"about many research topics ".repeat(4)},Some Funder,grant,2027-01-${String(10 + i).padStart(2, "0")},https://example.com/long-call-${i},€1,staff,`);
  const file = join(HERE, ".tmp", "long.csv"); writeFileSync(file, rows.join("\n"));
  await page.setFile("#csvFile", file);
  await page.click("#shareListBtn");
  const text = await shareText();
  assert.equal((text.match(/^\d+\. /gm) || []).length, 10, "a list holds at most 10 calls");
  const body = (await mailto()).split("&body=")[1];
  assert.ok(body.length < text.length, "e-mail draft is shorter");
  assert.equal(await page.visible("#shareWarn"), true);
  assert.match(await page.text("#shareWarn"), /cut|shortened/i);
  assert.ok(text.includes("10. Long call title number 10"), "the full text is still there for copying");
  await page.key("Escape");
});

// ---------------------------------------------------------------- A24
const rgb = s => (s.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
const lum = ([r, g, b]) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
const contrast = (a, b) => { const [x, y] = [lum(rgb(a)), lum(rgb(b))].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
const style = (cardTitle, selector, prop) => page.eval(`(() => {
  const card = [...document.querySelectorAll(".card")].find(c => c.querySelector(".title").textContent === ${JSON.stringify(cardTitle)});
  const el = ${selector === "card" ? "card" : `card.querySelector(${JSON.stringify(selector)})`};
  return el ? getComputedStyle(el)[${JSON.stringify(prop)}] : null; })()`);

test("A24 card colours: each kind of data has its own background and readable text", async () => {
  // the first card (Last Week Grant: grant, €10, 3 days left, staff)
  const kinds = ["funder", "type", "amount", "deadline", "who"];
  const seen = {};
  for (const k of kinds) {
    const bg = await style("Last Week Grant", `.chip-${k}`, "backgroundColor");
    const fg = await style("Last Week Grant", `.chip-${k}`, "color");
    assert.ok(bg && bg !== "rgba(0, 0, 0, 0)", `${k} has a background colour`);
    assert.ok(contrast(fg, bg) >= 4.5, `${k}: text is readable (contrast ${contrast(fg, bg).toFixed(1)})`);
    seen[k] = bg;
  }
  assert.equal(new Set(Object.values(seen)).size, 5, "funder, type, amount, deadline and who-can-apply all differ: " + JSON.stringify(seen));
  // words stay: colour is never the only information
  assert.equal(await page.text(".card .chip-type"), "grant");
  assert.match(await page.text(".card .chip-deadline"), /^Deadline 27 Nov 2026$/);
  assert.equal(await page.text(".card .chip-amount"), "€10");
  // type: each type has its own tint and its own card edge
  const grantBg = await style("Last Week Grant", ".chip-type", "backgroundColor");
  const dataBg = await style("Speech Datathon", ".chip-type", "backgroundColor");
  const compBg = await style("Student Language Competition", ".chip-type", "backgroundColor");
  const thirdBg = await style("AI Industry Call", ".chip-type", "backgroundColor");
  assert.equal(new Set([grantBg, dataBg, compBg, thirdBg]).size, 4, "4 types, 4 colours");
  assert.notEqual(await style("Last Week Grant", "card", "borderLeftColor"), await style("Speech Datathon", "card", "borderLeftColor"), "card edge follows the type");
  // deadline: urgency colour (3 days vs 97 days)
  assert.notEqual(await style("Last Week Grant", ".chip-deadline", "backgroundColor"), await style("Machine Translation Grant", ".chip-deadline", "backgroundColor"));
  // EU funder looks different from other funders
  assert.notEqual(await style("AI Industry Call", ".chip-funder", "backgroundColor"), await style("Last Week Grant", ".chip-funder", "backgroundColor"));
  // each group of people has its own chip colour (staff, PhD)
  const whoBgs = await page.eval(`(() => { const card = [...document.querySelectorAll(".card")].find(c => c.querySelector(".title").textContent === "NLP Research Grant");
    return [...card.querySelectorAll(".chip-who")].map(e => e.textContent + ":" + getComputedStyle(e).backgroundColor); })()`);
  assert.equal(whoBgs.length, 2); assert.equal(new Set(whoBgs.map(x => x.split(":")[1])).size, 2, "staff and PhD differ: " + whoBgs);
  // my status colours the status box
  const none = await page.eval(`getComputedStyle(document.querySelector("#openList .card select")).backgroundColor`);
  await markStatus(0, "interesting");
  const interesting = await page.eval(`getComputedStyle(document.querySelector("#openList .card select")).backgroundColor`);
  await markStatus(0, "applying");
  const applying = await page.eval(`getComputedStyle(document.querySelector("#openList .card select")).backgroundColor`);
  assert.equal(new Set([none, interesting, applying]).size, 3, "status colours: " + [none, interesting, applying]);
});

// ---------------------------------------------------------------- A25
test("A25 card buttons sit at the bottom edge of every card, in one line across a row", async () => {
  await page.setFile("#csvFile", CSV("heights.csv"));
  await select("fSort", "deadline");
  const gaps = await page.eval(`(() => {
    const cards = [...document.querySelectorAll("#openList .card")];
    const rows = {};
    for (const c of cards) { const top = Math.round(c.getBoundingClientRect().top); (rows[top] = rows[top] || []).push(c); }
    return Object.values(rows).map(list => list.map(c => ({
      height: Math.round(c.getBoundingClientRect().height),
      gap: Math.round(c.getBoundingClientRect().bottom - c.querySelector(".row").getBoundingClientRect().bottom) })));
  })()`);
  const firstRow = gaps[0];
  assert.ok(firstRow.length >= 2, "cards sit side by side");
  assert.ok(new Set(firstRow.map(c => c.height)).size === 1, "cards in a row are equally tall");
  const rowHeights = await page.eval(`(() => { const c = document.querySelector("#openList .card"); return c.getBoundingClientRect().height; })()`);
  assert.ok(rowHeights > 200, "the tall card makes the row tall");
  for (const row of gaps) {
    const g = row.map(c => c.gap);
    assert.ok(Math.max(...g) - Math.min(...g) <= 1, `buttons end at the same height in a row: gaps ${g}`);
    assert.ok(Math.max(...g) <= 20, `buttons sit right at the bottom (gap ${g})`);
  }
});
