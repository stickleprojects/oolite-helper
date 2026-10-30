"use strict";

// Behaviour of the clearance component, under a fake DOM (lib/testing.js), in its
// named states (clearance.states.json). One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const { render, states } = require("../../lib/testing.js");

const STATES = states("clearance");

const badge = (name) => render("clearance", STATES[name]).node;

describe("clearance", () => {
  test("says away from stations", () => {
    assert.equal(badge("away from stations").textContent, "Away from stations");
  });

  test("shows the badge's text", () => {
    assert.equal(badge("granted").textContent.trim(), "Cleared to dock");
  });

  test("is coloured by the badge's colour", () => {
    assert.ok(badge("granted").hasClass("green"));
  });

  test("flashes while clearance is expiring", () => {
    assert.ok(badge("expiring").hasClass("flashes"));
  });

  test("doesn't flash otherwise", () => {
    assert.ok(!badge("granted").hasClass("flashes"));
  });
});
