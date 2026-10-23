"use strict";

// The shared formatting (format.js). One case per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const format = require("./format.js");

describe("formatPrice", () => {
  test("shows decicredits as credits", () => {
    assert.equal(format.formatPrice(42, ""), "4.2");
  });

  test("adds a note in brackets", () => {
    assert.equal(format.formatPrice(48, "est."), "4.8 (est.)");
  });

  test("shows a dash for an unknown price", () => {
    assert.equal(format.formatPrice(null, ""), "—");
  });
});

describe("formatMargin", () => {
  test("signs a zero or positive margin with +", () => {
    assert.equal(format.formatMargin(0), "+0.0");
  });

  test("shows a negative margin as it is", () => {
    assert.equal(format.formatMargin(-12), "-1.2");
  });

  test("shows nothing for an unknown margin", () => {
    assert.equal(format.formatMargin(null), "");
  });
});

describe("sortRows", () => {
  const rows = [
    { commodity: "food", here: { price: 42 }, best: { price: 50 }, where: { distance: 5 }, margin: 8 },
    { commodity: "gold", here: { price: null }, best: { price: 80 }, where: { distance: 3 }, margin: null },
    { commodity: "computers", here: { price: 70 }, best: { price: null }, where: { distance: null }, margin: null },
  ];
  const sorted = (key, descending) => format.sortRows(rows, key, descending).map((row) => row.commodity);

  test("sorts high to low, unknown values last", () => {
    assert.deepEqual(sorted("here", true), ["computers", "food", "gold"]);
  });

  test("sorts low to high, unknown values still last", () => {
    assert.deepEqual(sorted("here", false), ["food", "computers", "gold"]);
  });

  test("sorts names alphabetically", () => {
    assert.deepEqual(sorted("commodity", false), ["computers", "food", "gold"]);
  });

  test("keeps the original order among unknown values", () => {
    assert.deepEqual(sorted("margin", true), ["food", "gold", "computers"]);
  });
});

describe("screenLine", () => {
  test("names the screen and view, then the price age", () => {
    const line = format.screenLine({ gui: "GUI_SCREEN_STATUS", view: "VIEW_FORWARD" }, { text: "5m ago" });
    assert.deepEqual(line, ["Screen: Status    View: Forward", "Market prices: 5m ago"]);
  });

  test("shows dashes before the game says", () => {
    assert.deepEqual(format.screenLine({ gui: null, view: null }, null), ["Screen: -    View: -"]);
  });
});

describe("detailsLines", () => {
  test("puts the details on one line above the screen line", () => {
    const lines = format.detailsLines(
      ["Jump in 9s", "Docking computer on"],
      { gui: "GUI_SCREEN_STATUS", view: "VIEW_FORWARD" },
      null,
    );
    assert.deepEqual(lines, ["Jump in 9s    Docking computer on", "Screen: Status    View: Forward"]);
  });
});

describe("chipText", () => {
  test("ticks a drive that's ready", () => {
    assert.equal(format.chipText("TORUS", { ok: true, by: null }), "  TORUS ✓  ");
  });

  test("says what blocks a drive", () => {
    assert.equal(format.chipText("JUMP", { ok: false, by: "planet" }), "  JUMP ✗ planet  ");
  });
});
