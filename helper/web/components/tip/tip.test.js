"use strict";

// Behaviour of the tip component, under a fake DOM (lib/testing.js), in its
// named states (tip.states.json). One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const { render, states } = require("../../lib/testing.js");

const STATES = states("tip");

describe("tip", () => {
  test("shows nothing when there's no tip", () => {
    assert.equal(render("tip", STATES["no tip"]).node, null);
  });

  test("shows each line of the tip", () => {
    const { node } = render("tip", STATES["two lines"]);
    assert.equal(node.textContent, "Waiting for clearance.\nPressing Shift+L again cancels the request.");
  });
});
