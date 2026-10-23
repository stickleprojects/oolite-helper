"use strict";

// Behaviour of the heading component, under a fake DOM (lib/testing.js).
// One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const { render } = require("../../lib/testing.js");


const FLYING = {
  context: "flying",
  location: { system: "Lave", reached_target: false, aimed_at: null },
  details: [],
  screen: { gui: "GUI_SCREEN_MAIN", view: "VIEW_FORWARD" },
  market_age: null,
};
const parts = (state) => {
  const [context, location, details] = render("heading", { ...FLYING, ...state }).node.children;
  return { context, location, details };
};

describe("heading", () => {
  test("shows the context in capitals", () => {
    assert.equal(parts({}).context.textContent, "FLYING");
  });

  test("shows the context in red during an emergency", () => {
    assert.ok(parts({ context: "red alert" }).context.hasClass("urgent"));
  });

  test("doesn't show an ordinary context in red", () => {
    assert.ok(!parts({}).context.hasClass("urgent"));
  });

  test("says when you're aimed for a jump target", () => {
    const { location } = parts({ location: { system: "Lave", aimed_at: "Leesti" } });
    assert.equal(location.textContent, "Lave  (aimed for Leesti)");
  });

  test("shows an aimed-for target in red", () => {
    assert.ok(parts({ location: { system: "Lave", aimed_at: "Leesti" } }).location.hasClass("aimed"));
  });

  test("says when you've reached your jump target", () => {
    const { location } = parts({ location: { system: "Leesti", reached_target: true } });
    assert.equal(location.textContent, "Leesti  ✓ your jump target");
  });

  test("shows a reached target in green", () => {
    assert.ok(parts({ location: { system: "Leesti", reached_target: true } }).location.hasClass("reached"));
  });

  test("shows the details, then the screen and view", () => {
    const { details } = parts({ details: [{ text: "Mass locked by: planet" }] });
    assert.equal(details.textContent, "Mass locked by: planet\nScreen: Main    View: Forward");
  });
});
