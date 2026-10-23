"use strict";

// Behaviour of the all_keys component, under a fake DOM (lib/testing.js).
// One state or one action per test.
const assert = require("node:assert/strict");
const { describe, test } = require("node:test");
const { render } = require("../../lib/testing.js");


const texts = (nodes) => nodes.map((node) => node.textContent);
const GROUPS = [
  { group: "screens", title: "Screen access", keys: [{ keys: "F1", description: "Launch ship" }] },
  { group: "travel", title: "Navigation", keys: [{ keys: "J", description: "Jump" }] },
];
const allKeys = (groups = GROUPS) => render("all_keys", { all_keys: groups });

describe("all_keys", () => {
  test("shows nothing before the keys are known", () => {
    assert.equal(allKeys([]).node, null);
  });

  test("shows a button for each group", () => {
    assert.deepEqual(texts(allKeys().node.all("button")), ["Screen access", "Navigation"]);
  });

  test("shows the first group to begin with", () => {
    assert.deepEqual(texts(allKeys().node.all("h2")), ["Screen access"]);
  });

  test("marks the shown group's button", () => {
    assert.ok(allKeys().node.all("button")[0].hasClass("active"));
  });

  test("clicking a group redraws", () => {
    const page = allKeys();
    page.node.all("button")[1].click();
    assert.equal(page.refreshes(), 1);
  });

  test("clicking a group shows it", () => {
    const page = allKeys();
    page.node.all("button")[1].click();
    assert.deepEqual(texts(page.again().all("h2")), ["Navigation"]);
  });
});
