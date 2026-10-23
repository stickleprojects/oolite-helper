"use strict";

// The shared files: every component folder registers a component of its name,
// and the widget page draws tab groups. One state or one action per test.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { describe, test } = require("node:test");
const { loadComponents, states, widget, WEB } = require("./testing.js");

test("every component folder registers a component of its name", () => {
  const folder = path.join(WEB, "components");
  const names = fs
    .readdirSync(folder)
    .filter((name) => fs.existsSync(path.join(folder, name, "component.toml")))
    .sort();
  const page = loadComponents(...names);
  for (const name of names) assert.ok(page.Oolite.get(name), name);
});

describe("tab groups", () => {
  const TABS = [
    { id: "keys", text: "Keys" },
    { id: "all_keys", text: "All keys" },
  ];
  const state = (tabs) => ({
    ...states("keys")["near a station"],
    ...states("all_keys")["two groups"],
    tabs: { shown: "keys", chosen: "keys", urgent: false, tabs: TABS, ...tabs },
  });
  const page = (tabs) => widget([{ tabs: ["keys", "all_keys"] }], state(tabs));
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

  test("shows the chosen tab when the one the model shows isn't in the group", () => {
    const { root } = widget([{ tabs: ["all_keys", "trade_table"] }], state({ shown: "keys", chosen: "all_keys" }));
    assert.ok(row(root)[0].hasClass("active"));
  });

  test("shows the group's first tab when neither is in it", () => {
    const { root } = widget([{ tabs: ["all_keys", "keys"] }], state({ shown: "trade_table", chosen: "trade_table" }));
    assert.ok(row(root)[0].hasClass("active"));
  });
});
