"use strict";

// The tabs widget: a tab row over the tab shown. One state or one action per test.
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { states, widget } = require("../../lib/testing.js");

const TABS = [
  { id: "keys", text: "Keys" },
  { id: "all_keys", text: "All keys" },
];
const state = (tabs) => ({
  ...states("keys")["near a station"],
  ...states("all_keys")["two groups"],
  tabs: { shown: "keys", chosen: "keys", urgent: false, tabs: TABS, ...tabs },
});
const page = (tabs, names = ["keys", "all_keys"]) => widget(names, state(tabs), "tabs");
const row = (root) => root.all(".tab-row")[0].all("button");

test("draws a tab per component, titled", () => {
  assert.deepEqual(row(page().root).map((tab) => tab.textContent), ["Keys", "All keys"]);
});

test("marks the tab shown", () => {
  const tabs = row(page({ shown: "all_keys", chosen: "all_keys" }).root);
  assert.deepEqual(tabs.map((tab) => tab.hasClass("active")), [false, true]);
});

test("draws only the tab shown", () => {
  const { root } = page({ shown: "all_keys", chosen: "all_keys" });
  assert.equal(root.all(".panel").length, 1); // all_keys draws one group's panel
});

test("clicking a tab chooses it in the model", () => {
  const { root, sent } = page();
  row(root)[1].click();
  assert.deepEqual(sent, [{ type: "ui/choose_tab", tab: "all_keys" }]);
});

test("shows the chosen tab when the one the model shows isn't one of its components", () => {
  const { root } = page({ shown: "keys", chosen: "all_keys" }, ["all_keys", "trade_table"]);
  assert.ok(row(root)[0].hasClass("active"));
});

test("shows its first tab when neither is one of its components", () => {
  const { root } = page({ shown: "trade_table", chosen: "trade_table" }, ["all_keys", "keys"]);
  assert.ok(row(root)[0].hasClass("active"));
});
