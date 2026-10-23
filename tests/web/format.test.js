"use strict";

const assert = require("node:assert/strict");
const { test } = require("node:test");
const format = require("../../helper/web/lib/format.js");

test("prices are credits with optional notes", () => {
  assert.equal(format.formatPrice(42, ""), "4.2");
  assert.equal(format.formatPrice(48, "est."), "4.8 (est.)");
  assert.equal(format.formatPrice(null, ""), "—");
  assert.equal(format.formatMargin(0), "+0.0");
  assert.equal(format.formatMargin(-12), "-1.2");
});

test("trade sorting keeps missing values last in either direction", () => {
  const rows = [
    { commodity: "food", here: { price: 42 }, best: { price: 50 }, where: { distance: 5 }, margin: 8 },
    { commodity: "gold", here: { price: null }, best: { price: 80 }, where: { distance: 3 }, margin: null },
    { commodity: "computers", here: { price: 70 }, best: { price: null }, where: { distance: null }, margin: null },
  ];
  assert.deepEqual(format.sortRows(rows, "here", true).map((row) => row.commodity), ["computers", "food", "gold"]);
  assert.deepEqual(format.sortRows(rows, "here", false).map((row) => row.commodity), ["food", "computers", "gold"]);
  assert.deepEqual(format.sortRows(rows, "commodity", false).map((row) => row.commodity), ["computers", "food", "gold"]);
  assert.deepEqual(format.sortRows(rows, "margin", true).map((row) => row.commodity), ["food", "gold", "computers"]);
});

test("screen details use the public topic shape and include market age", () => {
  assert.deepEqual(
    format.screenLine(
      { gui: "GUI_SCREEN_STATUS", view: "VIEW_FORWARD" },
      { text: "5m ago" },
    ),
    ["Screen: Status    View: Forward", "Market prices: 5m ago"],
  );
  assert.deepEqual(format.screenLine({ gui: null, view: null }, null), ["Screen: -    View: -"]);
  assert.deepEqual(
    format.detailsLines(
      [{ text: "Jump in 9s" }, { text: "Docking computer on" }].map((item) => item.text),
      { gui: "GUI_SCREEN_STATUS", view: "VIEW_FORWARD" },
      null,
    ),
    ["Jump in 9s    Docking computer on", "Screen: Status    View: Forward"],
  );
});

test("drive chips use constants and preserve the shown blocker", () => {
  assert.equal(format.chipText("TORUS", { ok: true, by: null }), "  TORUS ✓  ");
  assert.equal(format.chipText("JUMP", { ok: false, by: "planet" }), "  JUMP ✗ planet  ");
});
