"use strict";

// Behaviour of the keys component, under a fake DOM (lib/testing.js).
// One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const { render } = require("../../lib/testing.js");


const texts = (nodes) => nodes.map((node) => node.textContent);
const DOCKING = {
  title: "Docking",
  keys: [
    { action: "key_docking_clearance_request", keys: "Shift+L", description: "Request docking clearance" },
    { action: "key_ecm", keys: "E", description: "ECM", available: false },
    { action: "key_unbound", keys: "", description: "Something unbound" },
  ],
};
const keys = () => render("keys", { key_sections: [DOCKING] }).node;

describe("keys", () => {
  test("shows nothing when there are no keys for the context", () => {
    assert.equal(render("keys", { key_sections: [] }).node, null);
  });

  test("shows a panel per section, titled", () => {
    assert.deepEqual(texts(keys().all("h2")), ["Docking"]);
  });

  test("shows each key, with a dash for an unbound one", () => {
    assert.deepEqual(texts(keys().all("kbd")), ["Shift+L", "E", "—"]);
  });

  test("dims keys for equipment you haven't got", () => {
    assert.ok(keys().all(".key")[1].hasClass("unbound"));
  });

  test("dims unbound keys", () => {
    assert.ok(keys().all(".key")[2].hasClass("unbound"));
  });

  test("doesn't dim a bound key you can use", () => {
    assert.ok(!keys().all(".key")[0].hasClass("unbound"));
  });
});
