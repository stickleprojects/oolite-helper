"use strict";

// The shared files: every component and widget folder registers itself, and
// the widget page draws its components, or lets the widget draw itself. One
// state or one action per test.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const { load, loadComponents, states, widget, WEB } = require("./testing.js");

function started(size) {
  const page = load(["tip"], null);
  page.start({ components: ["tip"], widget: null, topics: ["tip"], ...size }, { tip: ["Dock now."] });
  return page.classes;
}

test("every component folder registers a component of its name", () => {
  const folder = path.join(WEB, "components");
  const names = fs
    .readdirSync(folder)
    .filter((name) => fs.existsSync(path.join(folder, name, "component.toml")))
    .sort();
  const page = loadComponents(...names);
  for (const name of names) assert.ok(page.Oolite.get(name), name);
});

test("every widget folder with its own drawing registers a widget of its name", () => {
  const folder = path.join(WEB, "widgets");
  for (const name of fs.readdirSync(folder).sort()) {
    const files = fs.existsSync(path.join(folder, name, "widget.toml")) ? fs.readdirSync(path.join(folder, name)) : [];
    if (!files.some((file) => file.endsWith(".js") && !file.endsWith(".test.js"))) continue;
    assert.ok(load([], name).Oolite.getWidget(name), name);
  }
});

test("a widget without its own drawing draws its components in order", () => {
  const { root } = widget(["tip", "status"], { tip: ["Dock now."], status: { kind: "error", text: "No log" } });
  assert.deepEqual(root.children.map((node) => node.className.split(" ")[0]), ["tip", "status"]);
});

test("a named widget with its own drawing draws itself", () => {
  const { root } = widget(["keys", "all_keys"], { ...states("keys")["near a station"], tabs: {} }, "tabs");
  assert.equal(root.children[0].className, "tabs");
});

test("a widget with only a width set takes its components' height", () => {
  assert.deepEqual(started({ width: 640, height: null }), ["fixed"]);
});

test("a widget with a height set fills that height", () => {
  assert.deepEqual(started({ width: 640, height: 310 }), ["fixed", "fixed-height"]);
});
