"use strict";

// Behaviour of the tip component, under a fake DOM (lib/testing.js).
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { render } = require("../../lib/testing.js");

test("tip: nothing when there's no tip, otherwise its lines", () => {
  assert.equal(render("tip", { tip: [] }).node, null);
  assert.equal(render("tip", { tip: ["one", "two"] }).node.textContent, "one\ntwo");
});
