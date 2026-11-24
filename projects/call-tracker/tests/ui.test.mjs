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
