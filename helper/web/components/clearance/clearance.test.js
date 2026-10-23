"use strict";

// Behaviour of the clearance component, under a fake DOM (lib/testing.js).
// One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const { render } = require("../../lib/testing.js");


const TIMING_OUT = { status: "timing_out", text: "Clearance expiring", colour: "amber", flashes: true };

describe("clearance", () => {
  test("shows nothing away from stations", () => {
    assert.equal(render("clearance", { clearance: null }).node, null);
  });

  test("shows the badge's text", () => {
    const { node } = render("clearance", { clearance: TIMING_OUT });
    assert.equal(node.textContent.trim(), "Clearance expiring");
  });

  test("is coloured by the badge's colour", () => {
    const { node } = render("clearance", { clearance: TIMING_OUT });
    assert.ok(node.hasClass("amber"));
  });

  test("flashes while clearance is timing out", () => {
    const { node } = render("clearance", { clearance: TIMING_OUT });
    assert.ok(node.hasClass("flashes"));
  });

  test("doesn't flash otherwise", () => {
    const granted = { status: "granted", text: "Cleared to dock", colour: "green", flashes: false };
    assert.ok(!render("clearance", { clearance: granted }).node.hasClass("flashes"));
  });
});
