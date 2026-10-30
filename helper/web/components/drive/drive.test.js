"use strict";

// Behaviour of the drive component, under a fake DOM (lib/testing.js), in its
// named states (drive.states.json). One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const { render, states } = require("../../lib/testing.js");

const STATES = states("drive");

const texts = (nodes) => nodes.map((node) => node.textContent);
const lamps = (name) => render("drive", STATES[name]).node.all(".chip");

describe("drive", () => {
  test("shows both lamps grey while docked", () => {
    const off = lamps("docked");
    assert.deepEqual(
      [texts(off), off.every((lamp) => lamp.hasClass("off"))],
      [["  TORUS  ", "  JUMP  "], true],
    );
  });

  test("shows a lamp each for TORUS and JUMP, saying what blocks them", () => {
    assert.deepEqual(texts(lamps("jump blocked")), ["  TORUS ✓  ", "  JUMP ✗ planet  "]);
  });

  test("a ready drive's lamp is green", () => {
    assert.ok(lamps("both ready")[0].hasClass("good"));
  });

  test("a blocked drive's lamp is red", () => {
    assert.ok(lamps("mass locked")[0].hasClass("bad"));
  });

  test("leaves out a lamp the game hasn't reported", () => {
    assert.deepEqual(texts(lamps("torus only")), ["  TORUS ✓  "]);
  });
});
