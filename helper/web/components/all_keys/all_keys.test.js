"use strict";

// Behaviour of the all_keys component, under a fake DOM (lib/testing.js).
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { render } = require("../../lib/testing.js");

const texts = (nodes) => nodes.map((node) => node.textContent);

test("all_keys: one group at a time; clicking a group shows it", () => {
  const groups = [
    { group: "screens", title: "Screen access", keys: [{ keys: "F1", description: "Launch ship" }] },
    { group: "travel", title: "Navigation", keys: [{ keys: "J", description: "Jump" }] },
  ];
  const shown = render("all_keys", { all_keys: groups }, { needs: ["keys"] });
  assert.deepEqual(texts(shown.node.all("h2")), ["Screen access"]);
  const buttons = shown.node.all("button");
  assert.ok(buttons[0].hasClass("active"));
  buttons[1].click();
  assert.equal(shown.refreshes(), 1);
  assert.deepEqual(texts(shown.again().all("h2")), ["Navigation"]);
  assert.equal(render("all_keys", { all_keys: [] }, { needs: ["keys"] }).node, null);
});
