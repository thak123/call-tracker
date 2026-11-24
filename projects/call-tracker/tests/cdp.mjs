// Small helper that drives the Chrome already installed on this laptop (hidden window)
// through the Chrome DevTools Protocol. No extra installs needed.
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const sleep = ms => new Promise(r => setTimeout(r, ms));
export { sleep };

// Fixed "today" for every page: 24 Nov 2026, 10:00 local time (time still moves forward).
const FIXED_DATE_SCRIPT = `(() => {
  const FIX = new Date(2026, 10, 24, 10, 0, 0).getTime(), Real = Date, start = Real.now();
  const now = () => FIX + (Real.now() - start);
  class FixedDate extends Real {
    constructor(...a) { if (a.length === 0) super(now()); else super(...a); }
    static now() { return now(); }
  }
  window.Date = FixedDate;
})();`;

function findChrome() {
  for (const c of ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/snap/bin/chromium",
                   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]) if (existsSync(c)) return c;
  throw new Error("Chrome not found");
}

export async function launchBrowser() {
  const port = 9400 + Math.floor(Math.random() * 400);
  const profile = mkdtempSync(join(tmpdir(), "ct-chrome-"));
  const proc = spawn(findChrome(), ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
    `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore" });
  for (let i = 0; i < 50; i++) {
    try { await fetch(`http://127.0.0.1:${port}/json/version`); break; } catch { await sleep(200); }
  }
  return {
    port,
    async newPage(opts = {}) { return openPage(port, opts); },
    async close() { proc.kill(); await sleep(300); rmSync(profile, { recursive: true, force: true }); },
  };
}

async function openPage(port, { width = 1300, height = 900, downloads } = {}) {
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" })).json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  let n = 0; const pend = {}; const errors = []; const listeners = [];
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
    if (m.method) listeners.forEach(l => l(m));
    if (pend[m.id]) { pend[m.id](m); delete pend[m.id]; }
  };
  const send = (method, params = {}) => new Promise(r => { const id = ++n; pend[id] = r; ws.send(JSON.stringify({ id, method, params })); });
  await send("Page.enable"); await send("Runtime.enable"); await send("DOM.enable");
  await send("Page.addScriptToEvaluateOnNewDocument", { source: FIXED_DATE_SCRIPT });
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
  if (downloads) await send("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: downloads });

  const page = {
    errors,
    async eval(expr) {
      const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
      if (r.result.exceptionDetails) throw new Error("Page eval failed: " + (r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text));
      return r.result.result.value;
    },
    async goto(url) {
      const loaded = new Promise(r => listeners.push(function l(m) { if (m.method === "Page.loadEventFired") { listeners.splice(listeners.indexOf(l), 1); r(); } }));
      await send("Page.navigate", { url }); await loaded; await sleep(150);
    },
    async reload() {
      const loaded = new Promise(r => listeners.push(function l(m) { if (m.method === "Page.loadEventFired") { listeners.splice(listeners.indexOf(l), 1); r(); } }));
      await send("Page.reload"); await loaded; await sleep(150);
    },
    // a real mouse click in the middle of the element (like a person would click)
    async click(selector) {
      const box = await page.eval(`(() => { const el = document.querySelector(${JSON.stringify(selector)});
        if (!el) return null; el.scrollIntoView({block: "center"}); const r = el.getBoundingClientRect();
        return { x: r.x + r.width / 2, y: r.y + r.height / 2, visible: r.width > 0 && r.height > 0 }; })()`);
      if (!box) throw new Error("Not found: " + selector);
      if (!box.visible) throw new Error("Not visible: " + selector);
      for (const type of ["mouseMoved", "mousePressed", "mouseReleased"])
        await send("Input.dispatchMouseEvent", { type, x: box.x, y: box.y, button: "left", clickCount: 1 });
      await sleep(120);
    },
    async hover(x, y) { await send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y }); await sleep(80); },
    async key(key) {
      const code = { Escape: "Escape", Enter: "Enter" }[key] || key;
      const vk = { Escape: 27, Enter: 13 }[key];
      await send("Input.dispatchKeyEvent", { type: "keyDown", key, code, windowsVirtualKeyCode: vk });
      await send("Input.dispatchKeyEvent", { type: "keyUp", key, code, windowsVirtualKeyCode: vk });
      await sleep(120);
    },
    async type(selector, text) {
      await page.eval(`document.querySelector(${JSON.stringify(selector)}).focus()`);
      await send("Input.insertText", { text }); await sleep(60);
    },
    async setFile(selector, path) {
      const doc = await send("DOM.getDocument");
      const q = await send("DOM.querySelector", { nodeId: doc.result.root.nodeId, selector });
      await send("DOM.setFileInputFiles", { nodeId: q.result.nodeId, files: [path] }); await sleep(500);
    },
    async screenshot(path) {
      const s = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
      writeFileSync(path, Buffer.from(s.result.data, "base64"));
    },
    async text(selector) { return page.eval(`(e => e ? e.textContent.trim() : null)(document.querySelector(${JSON.stringify(selector)}))`); },
    async visible(selector) {
      // really on screen: displayed (not display:none, also through its parents), with a size, not invisible
      return page.eval(`(e => !!e && e.getClientRects().length > 0 && getComputedStyle(e).visibility !== "hidden" && e.getBoundingClientRect().height > 0)(document.querySelector(${JSON.stringify(selector)}))`);
    },
    async close() { ws.close(); await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`); },
  };
  return page;
}
