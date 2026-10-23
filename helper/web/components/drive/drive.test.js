"use strict";

// Behaviour of the drive component, under a fake DOM (lib/testing.js).
// One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const { render } = require("../../lib/testing.js");


const texts = (nodes) => nodes.map((node) => node.textContent);
const FLYING = { drive: { torus: { ok: true, by: null }, jump: { ok: false, by: "planet" } } };

describe("drive", () => {
  test("shows nothing while docked", () => {
    assert.equal(render("drive", { drive: null }).node, null);
  });

  test("shows a lamp each for TORUS and JUMP, saying what blocks them", () => {
    const { node } = render("drive", FLYING);
    assert.deepEqual(texts(node.all(".chip")), ["  TORUS ✓  ", "  JUMP ✗ planet  "]);
  });

  test("lamps are green when ready and red when blocked", () => {
    const [torus, jump] = render("drive", FLYING).node.all(".chip");
    assert.deepEqual([torus.hasClass("good"), jump.hasClass("bad")], [true, true]);
  });

  test("leaves out a lamp the game hasn't reported", () => {
    const { node } = render("drive", { drive: { torus: { ok: true, by: null } } });
    assert.deepEqual(texts(node.all(".chip")), ["  TORUS ✓  "]);
  });
});
