"use strict";

// Behaviour of the last_message component, under a fake DOM (lib/testing.js), in its
// named states (last_message.states.json). One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const { render, states } = require("../../lib/testing.js");

const STATES = states("last_message");

describe("last_message", () => {
  test("shows nothing before the first message", () => {
    assert.equal(render("last_message", STATES["before any"]).node, null);
  });

  test("shows the message's raw JSON", () => {
    const { node } = render("last_message", STATES.short);
    assert.equal(node.textContent, '{"type": "alert", "level": 3}');
  });
});
