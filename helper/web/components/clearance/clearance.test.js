"use strict";

// Behaviour of the clearance component, under a fake DOM (lib/testing.js).
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { render } = require("../../lib/testing.js");

test("clearance: nothing away from stations; the badge flashes while timing out", () => {
  assert.equal(render("clearance", { clearance: null }).node, null);
  const { node } = render("clearance", {
    clearance: { status: "timing_out", text: "Clearance expiring", colour: "amber", flashes: true },
  });
  assert.equal(node.textContent.trim(), "Clearance expiring");
  assert.ok(node.hasClass("amber") && node.hasClass("flashes"));
});
