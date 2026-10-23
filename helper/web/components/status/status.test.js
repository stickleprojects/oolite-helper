"use strict";

// Behaviour of the status component, under a fake DOM (lib/testing.js).
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { render } = require("../../lib/testing.js");

test("status: nothing when there's nothing to say", () => {
  assert.equal(render("status", { status: { text: "" } }).node, null);
  assert.equal(render("status", { status: { text: "can't read the log" } }).node.textContent, "can't read the log");
});
