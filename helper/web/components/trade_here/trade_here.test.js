"use strict";

// Behaviour of the trade_here component, under a fake DOM (lib/testing.js).
// One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const { render } = require("../../lib/testing.js");


const texts = (nodes) => nodes.map((node) => node.textContent);
const ADVICE = [
  {
    heading: "Your hold",
    lines: [{ text: "2 t Food: sell here for +1.0 cr" }, { text: "Narcotics are illegal here", warning: true }],
  },
];

describe("trade_here", () => {
  test("shows a hint until you've docked somewhere", () => {
    assert.match(render("trade_here", { market_advice: [] }).node.textContent, /Dock at a station for trade advice\./);
  });

  test("shows each group of advice under its heading", () => {
    assert.deepEqual(texts(render("trade_here", { market_advice: ADVICE }).node.all("h3")), ["Your hold"]);
  });

  test("shows warnings in red", () => {
    const lines = render("trade_here", { market_advice: ADVICE }).node.all("p");
    assert.ok(lines[1].hasClass("warning"));
  });

  test("shows ordinary advice in the normal colour", () => {
    const lines = render("trade_here", { market_advice: ADVICE }).node.all("p");
    assert.ok(!lines[0].hasClass("warning"));
  });
});
