"use strict";

// Behaviour of the status component, under a fake DOM (lib/testing.js), in its
// named states (status.states.json). One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const { render, states } = require("../../lib/testing.js");

const STATES = states("status");

const line = (name) => render("status", STATES[name]).node;

describe("status", () => {
  test("says there are no problems when all is well", () => {
    assert.equal(line("all well").textContent, "No problems");
  });

  test("doesn't show the game's raw messages (last_message does)", () => {
    assert.equal(line("a message only").textContent, "No problems");
  });

  test("shows a notice", () => {
    assert.equal(line("notice").textContent, "Market prices loaded from your last visit");
  });

  test("shows an error in red", () => {
    assert.ok(line("error").hasClass("error"));
  });

  test("shows a warning in red", () => {
    assert.ok(line("warning").hasClass("warning"));
  });
});
