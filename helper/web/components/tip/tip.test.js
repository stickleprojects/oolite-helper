"use strict";

// Behaviour of the tip component, under a fake DOM (lib/testing.js).
// One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const { render } = require("../../lib/testing.js");


describe("tip", () => {
  test("shows nothing when there's no tip", () => {
    assert.equal(render("tip", { tip: [] }).node, null);
  });

  test("shows each line of the tip", () => {
    assert.equal(render("tip", { tip: ["one", "two"] }).node.textContent, "one\ntwo");
  });
});
