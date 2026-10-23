"use strict";

// Behaviour of the trade_here component, under a fake DOM (lib/testing.js).
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { render } = require("../../lib/testing.js");

const texts = (nodes) => nodes.map((node) => node.textContent);

test("trade_here: a hint until you've docked, then the advice with warnings in red", () => {
  const hint = render("trade_here", { market_advice: [] });
  assert.match(hint.node.textContent, /Dock at a station for trade advice\./);
  const { node } = render("trade_here", {
    market_advice: [
      { heading: "Your hold", lines: [{ text: "2 t Food: sell here for +1.0 cr" }, { text: "Narcotics are illegal here", warning: true }] },
    ],
  });
  assert.deepEqual(texts(node.all("h3")), ["Your hold"]);
  assert.deepEqual(node.all("p").map((p) => p.hasClass("warning")), [false, true]);
});
