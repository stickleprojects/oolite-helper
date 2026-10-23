"use strict";

// Behaviour of the status component, under a fake DOM (lib/testing.js).
// One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const { render } = require("../../lib/testing.js");


describe("status", () => {
  test("shows nothing when there's nothing to say", () => {
    assert.equal(render("status", { status: { text: "" } }).node, null);
  });

  test("shows the status text", () => {
    const { node } = render("status", { status: { text: "can't read the log" } });
    assert.equal(node.textContent, "can't read the log");
  });
});
