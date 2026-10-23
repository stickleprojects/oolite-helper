"use strict";

// Behaviour of the heading component, under a fake DOM (lib/testing.js).
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { render } = require("../../lib/testing.js");

test("heading: red for emergencies, and where you are against your jump target", () => {
  const state = {
    context: "red alert",
    location: { system: "Lave", reached_target: false, aimed_at: "Leesti" },
    details: [{ text: "Mass locked by: planet" }],
    screen: { gui: "GUI_SCREEN_MAIN", view: "VIEW_FORWARD" },
    market_age: null,
  };
  const { node } = render("heading", state);
  const [context, location, details] = node.children;
  assert.equal(context.textContent, "RED ALERT");
  assert.ok(context.hasClass("urgent"));
  assert.equal(location.textContent, "Lave  (aimed for Leesti)");
  assert.ok(location.hasClass("aimed"));
  assert.equal(details.textContent, "Mass locked by: planet\nScreen: Main    View: Forward");
  const reached = render("heading", { ...state, context: "flying", location: { system: "Leesti", reached_target: true } });
  assert.ok(!reached.node.children[0].hasClass("urgent"));
  assert.equal(reached.node.children[1].textContent, "Leesti  ✓ your jump target");
});
