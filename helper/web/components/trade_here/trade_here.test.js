"use strict";

// Behaviour of the trade_here component, under a fake DOM (lib/testing.js), in its
// named states (trade_here.states.json). One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const { render, states } = require("../../lib/testing.js");

const STATES = states("trade_here");

const texts = (nodes) => nodes.map((node) => node.textContent);
const advice = (name) => render("trade_here", STATES[name]).node;

describe("trade_here", () => {
  test("shows a hint until you've docked somewhere", () => {
    assert.match(advice("not docked yet").textContent, /Dock at a station for trade advice\./);
  });

  test("shows each group of advice under its heading", () => {
    assert.deepEqual(texts(advice("docked with cargo").all("h3")), ["Your hold", "Best buys here"]);
  });

  test("shows warnings in red", () => {
    assert.ok(advice("docked with cargo").all("p")[1].hasClass("warning"));
  });

  test("shows ordinary advice in the normal colour", () => {
    assert.ok(!advice("docked with cargo").all("p")[0].hasClass("warning"));
  });
});
