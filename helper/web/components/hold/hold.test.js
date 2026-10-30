"use strict";

// Behaviour of the hold component, under a fake DOM (lib/testing.js), in its
// named states (hold.states.json). One state per test.
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { render, states } = require("../../lib/testing.js");

const STATES = states("hold");
const draw = (name) => render("hold", STATES[name]).node;
const titles = (node) => node.all("h3").map((h) => h.textContent);
const rows = (node, section) => node.all(section)[0].all("tr").slice(1);

test("says Hold empty with the space free when nothing is aboard", () => {
  assert.equal(draw("empty").all(".empty")[0].textContent, "Hold empty · 35 t free");
});

test("says it's waiting before the game sends the hold", () => {
  assert.equal(draw("waiting for the game").all(".empty")[0].textContent, "Waiting for the game");
});

test("is headed Hold with the space used", () => {
  assert.equal(draw("one lot").all("h2")[0].textContent, "Hold · 12 / 35 t");
});

test("shows only the Goods section when only goods are aboard", () => {
  assert.deepEqual(titles(draw("one lot")), ["Goods"]);
});

test("shows only Passengers and Parcels when only they are aboard", () => {
  assert.deepEqual(titles(draw("passengers and parcels")), ["Passengers", "Parcels"]);
});

test("shows goods and contracts together", () => {
  assert.deepEqual(titles(draw("contract")), ["Goods", "Contracts"]);
});

test("draws a row per lot, with where each was bought", () => {
  const from = rows(draw("two lots of food"), ".goods").map((tr) => tr.children[3].textContent);
  assert.deepEqual(from, ["Lave", "Zaonce"]);
});

test("shows prices in credits", () => {
  const [row] = rows(draw("one lot"), ".goods");
  assert.deepEqual(row.children.slice(2, 7).map((td) => td.textContent), ["4.4", "Lave", "52.8", "62.4", "+9.6"]);
});

test("colours a profit green", () => {
  assert.ok(rows(draw("two lots of food"), ".goods")[0].children[6].hasClass("good"));
});

test("colours a loss red", () => {
  assert.ok(rows(draw("two lots of food"), ".goods")[1].children[6].hasClass("warning"));
});

test("says scooped, and shows no price or profit for it", () => {
  const [row] = rows(draw("scooped"), ".goods");
  assert.deepEqual([row.children[3].textContent, row.children[2].textContent, row.children[6].textContent], ["scooped", "—", ""]);
});

test("marks goods of unknown origin with a dim ?", () => {
  const cell = rows(draw("scooped"), ".goods")[1].children[3];
  assert.deepEqual([cell.textContent, cell.hasClass("dim")], ["?", true]);
});

test("marks a late passenger in red", () => {
  const [row] = rows(draw("late passenger"), ".passengers");
  assert.deepEqual([row.hasClass("late"), row.children[2].hasClass("warning")], [true, true]);
});

test("shows a passenger's destination, time left and fee", () => {
  const [row] = rows(draw("passengers and parcels"), ".passengers");
  assert.deepEqual(row.children.slice(1).map((td) => td.textContent), ["Zaonce", "2d 3h", "240 ₢"]);
});

test("says which market the goods are worth at", () => {
  assert.equal(draw("one lot").all(".worth-at")[0].textContent, "Worth at Diso, Coriolis Station, 5m ago");
});
