#!/usr/bin/env node
// Regression: S1/S2 routing card must show "--" for any window not backed by real data.
// dashboard.js is browser code, so the function source is extracted and evaluated.
const fs = require("fs");
const path = require("path");

const src = fs.readFileSync(path.join(__dirname, "../../assets/dashboard.js"), "utf8");
const m = src.match(/^function formatRoutingRatio\(w\) \{[\s\S]*?^\}/m);
if (!m) {
  console.error("FAIL: function formatRoutingRatio not found in assets/dashboard.js");
  process.exit(1);
}
const formatRoutingRatio = new Function(`${m[0]}; return formatRoutingRatio;`)();

const cases = [
  ["valid", { count: 16, local_pct: 87.5, remote_pct: 12.5 }, "S1: 88% · S2: 12% (24h, n=16)"],
  ["count 0", { count: 0, local_pct: 0, remote_pct: 0 }, "--"],
  ["out of range", { count: 1, local_pct: 150, remote_pct: -50 }, "--"],
  ["NaN", { count: 5, local_pct: NaN, remote_pct: 50 }, "--"],
  ["Infinity", { count: 5, local_pct: Infinity, remote_pct: 0 }, "--"],
  ["sum 90", { count: 5, local_pct: 50, remote_pct: 40 }, "--"],
  ["null", null, "--"],
  ["undefined", undefined, "--"],
  ["missing count", { local_pct: 50, remote_pct: 50 }, "--"],
  ["non-integer count", { count: 1.5, local_pct: 50, remote_pct: 50 }, "--"],
];

let failed = 0;
for (const [name, input, want] of cases) {
  const got = formatRoutingRatio(input);
  if (got !== want) {
    failed++;
    console.error(`FAIL ${name}: got ${JSON.stringify(got)} want ${JSON.stringify(want)}`);
  }
}
if (failed) process.exit(1);
console.log(`ok: ${cases.length} cases`);
