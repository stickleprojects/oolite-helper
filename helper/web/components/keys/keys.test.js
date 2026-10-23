"use strict";

// Behaviour of the keys component, under a fake DOM (lib/testing.js), in its
// named states (keys.states.json). One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const { render, states } = require("../../lib/testing.js");

const STATES = states("keys");

const texts = (nodes) => nodes.map((node) => node.textContent);
const keys = (name) => render("keys", STATES[name]).node;

describe("keys", () => {
  test("shows nothing when there are no keys for the context", () => {
    assert.equal(keys("no keys"), null);
  });

  test("shows a panel per section, titled", () => {
    assert.deepEqual(texts(keys("near a station").all("h2")), ["Docking", "Flight"]);
  });

  test("shows each key, with a dash for an unbound one", () => {
    assert.deepEqual(texts(keys("missing and unbound").all("kbd")), ["Shift+L", "E", "—"]);
  });

  test("dims keys for equipment you haven't got", () => {
    assert.ok(keys("missing and unbound").all(".key")[1].hasClass("unbound"));
  });

  test("dims unbound keys", () => {
    assert.ok(keys("missing and unbound").all(".key")[2].hasClass("unbound"));
  });

  test("doesn't dim a bound key you can use", () => {
    assert.ok(!keys("missing and unbound").all(".key")[0].hasClass("unbound"));
  });
});
