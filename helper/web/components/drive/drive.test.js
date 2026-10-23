"use strict";

// Behaviour of the drive component, under a fake DOM (lib/testing.js).
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { render } = require("../../lib/testing.js");

const texts = (nodes) => nodes.map((node) => node.textContent);

test("drive: nothing while docked, otherwise a lamp each for TORUS and JUMP", () => {
  assert.equal(render("drive", { drive: null }).node, null);
  const { node } = render("drive", {
    drive: { torus: { ok: true, by: null }, jump: { ok: false, by: "planet" } },
  });
  const chips = node.all(".chip");
  assert.deepEqual(texts(chips), ["  TORUS ✓  ", "  JUMP ✗ planet  "]);
  assert.ok(chips[0].hasClass("good") && chips[1].hasClass("bad"));
});
