"use strict";

// Behaviour of the trade_table component, under a fake DOM (lib/testing.js).
// One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
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
const TABLE = { trade_rows: ROWS, selection: null, trade_detail: null };
const names = (node) => node.all("tr").slice(1).map((tr) => tr.children[0].textContent);
const heading = (node, title) => node.all("button").find((b) => b.textContent.startsWith(title));

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
const OPEN = { trade_rows: ROWS, selection: { commodity: "food", destination: 8, quantity: 3 }, trade_detail: DETAIL };
const offers = (node) => node.all("tr").slice(1);
const button = (node, label) => node.all("button").find((b) => b.textContent.trim() === label);

describe("trade_table: the table", () => {
  test("says why when there's no market data", () => {
    const { node } = render("trade_table", { ...TABLE, trade_rows: [] });
    assert.match(node.textContent, /No market data yet/);
  });

  test("lists commodities by margin, best first, unknown margins last", () => {
    assert.deepEqual(names(render("trade_table", TABLE).node), ["Furs", "Food", "Gold"]);
  });

  test("marks the column it's sorted by", () => {
    assert.equal(heading(render("trade_table", TABLE).node, "Margin").textContent, "Margin ▼");
  });

  test("clicking a heading redraws", () => {
    const table = render("trade_table", TABLE);
    heading(table.node, "Commodity").click();
    assert.equal(table.refreshes(), 1);
  });

  test("clicking a heading sorts by that column", () => {
    const table = render("trade_table", TABLE);
    heading(table.node, "Commodity").click();
    assert.deepEqual(names(table.again()), ["Food", "Furs", "Gold"]);
  });

  test("clicking the sorted column again reverses it", () => {
    const table = render("trade_table", TABLE);
    heading(table.node, "Margin").click();
    assert.deepEqual(names(table.again()), ["Food", "Furs", "Gold"]);
  });

  test("clicking a commodity opens it", () => {
    const table = render("trade_table", TABLE);
    table.node.all("tr")[2].click(); // Food: the second row after the heading
    assert.deepEqual(table.sent, [{ type: "ui/open_commodity", commodity: "food" }]);
  });
});

describe("trade_table: an open commodity", () => {
  test("shows the detail instead of the table", () => {
    assert.ok(render("trade_table", OPEN).node.hasClass("detail"));
  });

  test("marks the chosen system to sell at", () => {
    assert.equal(offers(render("trade_table", OPEN).node)[0].children[0].textContent, "▶ Zaonce");
  });

  test("shows a dangerous government in red", () => {
    assert.ok(offers(render("trade_table", OPEN).node)[1].children[5].hasClass("warning"));
  });

  test("sums up the cost, the cargo and the profit at the chosen system", () => {
    const { node } = render("trade_table", OPEN);
    assert.equal(node.all(".summary")[0].textContent, "Cost 12.6 cr    cargo 3 t    profit at Zaonce +2.4 cr");
  });

  test("lists the steps, numbered", () => {
    const { node } = render("trade_table", OPEN);
    assert.deepEqual(texts(node.all(".step")), ["1. Press F8 for the market", "2. Press → three times"]);
  });

  test("+10 asks for no more than you can buy", () => {
    const detail = render("trade_table", OPEN);
    button(detail.node, "+10").click();
    assert.deepEqual(detail.sent, [{ type: "ui/change_quantity", quantity: 4 }]);
  });

  test("−1 asks for one fewer", () => {
    const detail = render("trade_table", OPEN);
    button(detail.node, "−1").click();
    assert.deepEqual(detail.sent, [{ type: "ui/change_quantity", quantity: 2 }]);
  });

  test("the current quantity isn't a button that does anything", () => {
    const detail = render("trade_table", OPEN);
    button(detail.node, "3 t").click();
    assert.deepEqual(detail.sent, []);
  });

  test("clicking a system chooses it", () => {
    const detail = render("trade_table", OPEN);
    offers(detail.node)[1].click();
    assert.deepEqual(detail.sent, [{ type: "ui/choose_destination", system: 9 }]);
  });

  test("◀ All commodities goes back to the table", () => {
    const detail = render("trade_table", OPEN);
    button(detail.node, "◀ All commodities").click();
    assert.deepEqual(detail.sent, [{ type: "ui/open_commodity", commodity: null }]);
  });
});
