"use strict";

// Behaviour of the heading component, under a fake DOM (lib/testing.js), in its
// named states (heading.states.json). One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const { render, states } = require("../../lib/testing.js");

const STATES = states("heading");

const parts = (name) => {
  const [context, location, details] = render("heading", STATES[name]).node.children;
  return { context, location, details };
};

describe("heading", () => {
  test("shows the context in capitals", () => {
    assert.equal(parts("docked").context.textContent, "DOCKED");
  });

  test("shows the context in red during an emergency", () => {
    assert.ok(parts("red alert").context.hasClass("urgent"));
  });

  test("doesn't show an ordinary context in red", () => {
    assert.ok(!parts("docked").context.hasClass("urgent"));
  });

  test("says when you're aimed for a jump target", () => {
    assert.equal(parts("flying, aimed for a target").location.textContent, "Lave  (aimed for Leesti)");
  });

  test("shows an aimed-for target in red", () => {
    assert.ok(parts("flying, aimed for a target").location.hasClass("aimed"));
  });

  test("says when you've reached your jump target", () => {
    assert.equal(parts("arrived at the target").location.textContent, "Leesti  ✓ your jump target");
  });

  test("shows a reached target in green", () => {
    assert.ok(parts("arrived at the target").location.hasClass("reached"));
  });

  test("shows the details, then the screen and view", () => {
    const { details } = parts("flying, aimed for a target");
    assert.equal(details.textContent, "Mass locked by: planet\nScreen: Main    View: Forward");
  });

  test("shows the price age under the screen line", () => {
    assert.equal(parts("docked").details.textContent, "Screen: Status    View: -\nMarket prices: just now");
  });
});
