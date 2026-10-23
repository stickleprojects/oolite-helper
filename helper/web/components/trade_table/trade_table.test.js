"use strict";

// Behaviour of the trade_table component, under a fake DOM (lib/testing.js).
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { render } = require("../../lib/testing.js");

const texts = (nodes) => nodes.map((node) => node.textContent);

const row = (commodity, here, best, margin, extra = {}) => ({
  commodity,
  name: commodity[0].toUpperCase() + commodity.slice(1),
  unit: "t",
  illegal: false,
  stock: 5,
  here: { price: here, note: "", live: true },
  best: { price: best, note: "" },
  where: { name: "Zaonce", distance: 6.5 },
  margin,
  ...extra,
});

const ROWS = [row("food", 42, 50, 8), row("furs", 500, 650, 150), row("gold", null, 400, null, { stock: 0 })];

test("trade_table: rows by margin, best first; headings change the sort", () => {
  const table = render("trade_table", { trade_rows: ROWS, selection: null, trade_detail: null });
  const names = (node) => node.all("tr").slice(1).map((tr) => tr.children[0].textContent);
  assert.deepEqual(names(table.node), ["Furs", "Food", "Gold"]); // unknown margins last
  const commodity = table.node.all("button")[0];
  assert.equal(commodity.textContent, "Commodity");
  commodity.click();
  assert.equal(table.refreshes(), 1);
  assert.deepEqual(names(table.again()), ["Food", "Furs", "Gold"]);
});

test("trade_table: clicking a commodity opens it; with no data it says why", () => {
  const table = render("trade_table", { trade_rows: ROWS, selection: null, trade_detail: null });
  table.node.all("tr")[2].click(); // Food: the second row after the heading
  assert.deepEqual(table.sent, [{ type: "ui/open_commodity", commodity: "food" }]);
  const empty = render("trade_table", { trade_rows: [], selection: null, trade_detail: null });
  assert.match(empty.node.textContent, /No market data yet/);
});

const DETAIL = {
  commodity: "food",
  name: "Food",
  row: ROWS[0],
  chosen: 8,
  quantity: 3,
  limit: { most: 4, text: "hold space" },
  offers: [
    { system_id: 8, name: "Zaonce", price: 50, note: "", distance: 6.5, economy_name: "Poor Agricultural", government_name: "Democracy", dangerous: false, illegal: false },
    { system_id: 9, name: "Leesti", price: 47, note: "", distance: 3.1, economy_name: "Rich Industrial", government_name: "Anarchy", dangerous: true, illegal: false },
  ],
  steps: ["Press F8 for the market", "Press → three times"],
};

test("trade_table: an open commodity shows where to sell, the quantity and the steps", () => {
  const detail = render("trade_table", {
    trade_rows: ROWS,
    selection: { commodity: "food", destination: 8, quantity: 3 },
    trade_detail: DETAIL,
  });
  const node = detail.node;
  assert.ok(node.hasClass("detail"));
  const offers = node.all("tr").slice(1);
  assert.equal(offers[0].children[0].textContent, "▶ Zaonce"); // the chosen one
  assert.ok(offers[1].children[5].hasClass("warning")); // dangerous government
  assert.match(node.textContent, /Cost 12\.6 cr {4}cargo 3 t {4}profit at Zaonce \+2\.4 cr/);
  assert.deepEqual(texts(node.all(".step")), ["1. Press F8 for the market", "2. Press → three times"]);

  const buttons = Object.fromEntries(node.all("button").map((b) => [b.textContent.trim(), b]));
  buttons["+10"].click(); // clamped to the most you can buy
  buttons["−1"].click();
  offers[1].click();
  buttons["◀ All commodities"].click();
  assert.deepEqual(detail.sent, [
    { type: "ui/change_quantity", quantity: 4 },
    { type: "ui/change_quantity", quantity: 2 },
    { type: "ui/choose_destination", system: 9 },
    { type: "ui/open_commodity", commodity: null },
  ]);
  buttons["3 t"].click(); // the current quantity isn't a button that does anything
  assert.equal(detail.sent.length, 4);
});
