import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

// Lab 04 B1-B8 verification harness.
// Run two Flask servers first: a working one on 5000 and one with a bogus
// NGSPICE_BIN on 5001. Then: node scripts/verify_lab04.mjs docs/captures
// Optional overrides: BASE_URL, BROKEN_ENGINE_URL.
const BASE = process.env.BASE_URL || "http://127.0.0.1:5000";
const BROKEN = process.env.BROKEN_ENGINE_URL || "http://127.0.0.1:5001";
const OUT = process.argv[2] || "docs/captures";
fs.mkdirSync(OUT, { recursive: true });

const results = [];
const consoleErrors = [];
function record(id, name, ok, detail) {
  results.push({ id, name, status: ok ? "PASS" : "FAIL", detail });
  console.log(`${ok ? "PASS" : "FAIL"} ${id} ${name} :: ${detail}`);
}
function check(id, name, text, needles) {
  const missing = needles.filter((needle) => !text.includes(needle));
  record(id, name, missing.length === 0,
    missing.length ? `missing: ${missing.join(" | ")}` : "all expected strings present");
}
async function waitForServer(url) {
  for (let i = 0; i < 40; i++) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`server did not start: ${url}`);
}
async function shot(page, name, fullPage = true) {
  await page.screenshot({ path: path.join(OUT, name), fullPage });
}
async function runSpice(page) {
  await page.click("button.calculate");
  await page.waitForFunction(() => document.body.innerText.includes("RUN OK") ||
    document.body.innerText.includes("RUN FAILED") ||
    document.body.innerText.includes("Please fix the highlighted fields"),
    { timeout: 30000 });
}
async function textOf(page, selector) {
  return page.locator(selector).first().innerText();
}
async function svgText(page, selector) {
  return page.locator(selector).first().evaluate((node) => node.textContent);
}
function overflow(page) {
  return page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    bodyScrollWidth: document.body.scrollWidth,
  }));
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("pageerror", (error) => consoleErrors.push(String(error)));

try {
  await waitForServer(BASE);
  await waitForServer(BROKEN);

  // ---------- B1: Lab 03 regression across all three analytical modes ----------
  const lab3 = [
    { css: "voltage-divider", label: "Voltage Divider Bias",
      fields: { vcc: "12", r1: "47", r2: "10", rc: "2.2", re: "0.47", beta: "150", vbe: "0.7" },
      expected: ["17.74", "2.661", "4.887", "Forward active"] },
    { css: "fixed-bias", label: "Fixed Bias",
      fields: { vcc: "12", rb: "470", rc: "2.2", beta: "150", vbe: "0.7" },
      expected: ["24.04", "3.606", "4.066", "Forward active"] },
    { css: "emitter-bias", label: "Emitter Bias",
      fields: { vcc: "12", rb: "470", rc: "2.2", re: "0.47", beta: "150", vbe: "0.7" },
      expected: ["20.89", "3.133", "3.624", "Forward active"] },
  ];
  for (const item of lab3) {
    await page.goto(`${BASE}/`);
    await page.check(`#circuit-${item.css}`);
    for (const [name, value] of Object.entries(item.fields)) {
      await page.fill(`#${name}`, value);
    }
    await page.click("button.calculate");
    await page.waitForFunction((label) => document.body.innerText.includes(`Results for ${label}`),
      item.label, { timeout: 15000 });
    const body = await page.locator("body").innerText();
    check("B1", `Lab 03 ${item.label}`, body, [...item.expected, "Closed-form", "Nodal", "agree"]);
    await shot(page, `b1-lab03-${item.css}.png`);
  }

  // ---------- B2: CE reference DC SPICE ----------
  await page.goto(`${BASE}/amplifier`);
  await runSpice(page);
  let dc = await textOf(page, 'section[aria-labelledby="dc-heading"]');
  const provenance = await textOf(page, ".provenance");
  check("B2", "CE reference .op", dc,
    ["2.004", "1.333", "9.087", "7.754", "1.324", "Forward active"]);
  check("B2", "Engine and model provenance", provenance,
    ["ngspice", "46", "Q2N3904", "Run ID", "Exit code"]);
  const baselineIc = dc.match(/I\s*C\s*([\d.]+)\s*mA/i)?.[1] ?? "";
  const baselineGain = (await textOf(page, 'section[aria-labelledby="ac-heading"]'))
    .match(/([\d.]+)×/)?.[1] ?? "";
  await shot(page, "b2-ce-dc.png");

  // ---------- B3: RE change updates the real operating point and gain ----------
  await page.fill("#amp-re", "0.47");
  await runSpice(page);
  dc = await textOf(page, 'section[aria-labelledby="dc-heading"]');
  const acSection = await textOf(page, 'section[aria-labelledby="ac-heading"]');
  const changedIc = dc.match(/I\s*C\s*([\d.]+)\s*mA/i)?.[1] ?? "";
  const changedGain = acSection.match(/([\d.]+)×/)?.[1] ?? "";
  record("B3", "RE 1k -> 0.47k changes IC",
    Boolean(changedIc && baselineIc && changedIc !== baselineIc),
    `IC ${baselineIc} mA -> ${changedIc} mA`);
  record("B3", "RE change moves AC gain",
    Boolean(changedGain && baselineGain && changedGain !== baselineGain),
    `gain ${baselineGain} -> ${changedGain}`);
  await shot(page, "b3-re-change.png");

  // restore reference values for B4/B5
  await page.fill("#amp-re", "1");
  await runSpice(page);

  // ---------- B4: AC Bode magnitude + phase ----------
  const acText = await textOf(page, 'section[aria-labelledby="ac-heading"]');
  const acSvg = await svgText(page, 'section[aria-labelledby="ac-heading"]');
  const acPlots = await page.locator('section[aria-labelledby="ac-heading"] svg.plot-svg').count();
  check("B4", "AC summary and cutoff units", acText,
    ["Gain at 1000 Hz", "dB", "−3 dB cutoff", "Hz", "inverting stage"]);
  check("B4", "Bode axes and data", acSvg,
    ["Frequency (Hz, log scale)", "Gain (dB)", "Phase (degrees)", "|Vout / Vin|"]);
  record("B4", "Two AC plots rendered", acPlots >= 2, `${acPlots} SVG plots`);
  await page.locator('section[aria-labelledby="ac-heading"]').screenshot(
    { path: path.join(OUT, "b4-ac-bode.png") });

  // ---------- B5: transient at 10 mV peak / 1 kHz ----------
  const tranText = await textOf(page, 'section[aria-labelledby="tran-heading"]');
  const tranSvg = await svgText(page, 'section[aria-labelledby="tran-heading"]');
  check("B5", "Transient waveform and inversion", tranText,
    ["Vin amplitude", "10 mV", "Vout amplitude", "17.56", "phase inverted", "Time (ms)"]);
  check("B5", "Transient axes and traces", tranSvg, ["Time (ms)", "Voltage (mV)", "Vin", "Vout"]);
  await page.locator('section[aria-labelledby="tran-heading"]').screenshot(
    { path: path.join(OUT, "b5-tran.png") });

  // ---------- B6: amplitude / frequency change updates the waveform ----------
  await page.fill("#amp-amp_mv", "20");
  await page.fill("#amp-freq_hz", "2000");
  await page.fill("#amp-tran_step_us", "5");
  await runSpice(page);
  const tranChanged = await textOf(page, 'section[aria-labelledby="tran-heading"]');
  const tranChangedSvg = await svgText(page, 'section[aria-labelledby="tran-heading"]');
  check("B6", "20 mV peak / 2 kHz updates waveform", tranChanged,
    ["20 mV", "35.12", "phase inverted"]);
  check("B6", "Plot title reflects 2000 Hz", tranChangedSvg, ["2000 Hz"]);
  await shot(page, "b6-amplitude-frequency.png");

  // ---------- B7: invalid input and unavailable engine ----------
  await page.fill("#amp-re", "0");
  await page.click("button.calculate");
  await page.waitForFunction(() => document.body.innerText.includes("RE must be greater than 0."),
    { timeout: 15000 });
  const invalidBody = await page.locator("body").innerText();
  record("B7", "RE=0 rejected without fake success",
    invalidBody.includes("RE must be greater than 0.") &&
    !invalidBody.includes("RUN OK") && !invalidBody.includes("DC operating point"),
    "validation error shown; no RUN OK and no stale DC table");
  await shot(page, "b7-invalid-re.png");

  await page.goto(`${BROKEN}/amplifier`);
  const brokenBadge = await textOf(page, ".engine-badge");
  await runSpice(page);
  const brokenBody = await page.locator("body").innerText();
  record("B7", "Unavailable engine badge", brokenBadge.includes("unavailable"),
    `badge: ${brokenBadge.trim()}`);
  record("B7", "Unavailable engine fails clearly",
    brokenBody.includes("RUN FAILED") && brokenBody.includes("ngspice") &&
    !brokenBody.includes("RUN OK"),
    "RUN FAILED with ngspice diagnostic; no fake success");
  await shot(page, "b7-engine-unavailable.png");

  // ---------- B8: desktop and mobile layouts ----------
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`${BASE}/amplifier`);
  await runSpice(page);
  const desktop = await overflow(page);
  await shot(page, "b8-desktop-1280.png");
  record("B8", "Desktop 1280px no horizontal overflow",
    desktop.scrollWidth <= desktop.innerWidth + 1,
    `scrollWidth ${desktop.scrollWidth} vs viewport ${desktop.innerWidth}`);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/amplifier`);
  await runSpice(page);
  const mobile = await overflow(page);
  const vccBox = await page.locator("#amp-vcc").boundingBox();
  const buttonBox = await page.locator("button.calculate").boundingBox();
  const controlsVisible = Boolean(vccBox && buttonBox && vccBox.width > 40 &&
    buttonBox.width > 40 && vccBox.x >= 0 && vccBox.x + vccBox.width <= 390 + 1);
  await shot(page, "b8-mobile-390.png");
  record("B8", "Mobile 390px no horizontal overflow",
    mobile.scrollWidth <= mobile.innerWidth + 1,
    `scrollWidth ${mobile.scrollWidth} vs viewport ${mobile.innerWidth}`);
  record("B8", "Mobile key controls visible", controlsVisible,
    vccBox && buttonBox ? `VCC x=${vccBox.x.toFixed(0)} w=${vccBox.width.toFixed(0)}, button w=${buttonBox.width.toFixed(0)}` : "missing control");

  await page.goto(`${BASE}/`);
  const lab3Mobile = await overflow(page);
  await shot(page, "b8-mobile-lab03.png");
  record("B8", "Lab 03 mobile no horizontal overflow",
    lab3Mobile.scrollWidth <= lab3Mobile.innerWidth + 1,
    `scrollWidth ${lab3Mobile.scrollWidth} vs viewport ${lab3Mobile.innerWidth}`);
} catch (error) {
  record("RUN", "Browser harness", false, String(error?.stack || error));
} finally {
  record("RUN", "No browser console errors", consoleErrors.length === 0,
    consoleErrors.length ? consoleErrors.join(" | ") : "none");
  await browser.close();
}

const summary = {
  generatedAt: new Date().toISOString(),
  baseUrl: BASE,
  results,
  passed: results.filter((item) => item.status === "PASS").length,
  failed: results.filter((item) => item.status === "FAIL").length,
};
fs.writeFileSync(path.join(OUT, "b1-b8-results.json"), JSON.stringify(summary, null, 2));
console.log(JSON.stringify({ passed: summary.passed, failed: summary.failed }, null, 2));
process.exit(summary.failed === 0 ? 0 : 1);
