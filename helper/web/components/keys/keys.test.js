"use strict";

// Behaviour of the keys component, under a fake DOM (lib/testing.js).
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { render } = require("../../lib/testing.js");

const texts = (nodes) => nodes.map((node) => node.textContent);

const SECTIONS = [
  {
    title: "Docking",
    keys: [
      { action: "key_docking_clearance_request", keys: "Shift+L", description: "Request docking clearance" },
      { action: "key_ecm", keys: "E", description: "ECM", available: false },
      { action: "key_unbound", keys: "", description: "Something unbound" },
    ],
  },
];

test("keys: a panel per section; missing equipment and unbound keys are dimmed", () => {
  assert.equal(render("keys", { key_sections: [] }).node, null);
  const { node } = render("keys", { key_sections: SECTIONS });
  assert.deepEqual(texts(node.all("h2")), ["Docking"]);
  const keys = node.all(".key");
  assert.deepEqual(keys.map((key) => key.hasClass("unbound")), [false, true, true]);
  assert.deepEqual(texts(node.all("kbd")), ["Shift+L", "E", "—"]);
});
