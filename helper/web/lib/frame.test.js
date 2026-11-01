"use strict";

// A widgetwindow's page (#141): its title bar over the helper's widgets in it.
// One state or one action per test.
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { frame } = require("./testing.js");

function widget(id, components, more = {}) {
  return { id, components, widget: null, topics: ["tip", "status"], height: null, fill: false, hide_empty: false, scale: 1, ...more };
}

const TIP = widget("tip", ["tip"]);
const STATUS = widget("status", ["status"]);
const STATE = { tip: ["Dock now."], status: { kind: "error", text: "No log" } };

function page(widgets = [TIP, STATUS], state = STATE, frameTopic = undefined) {
  return frame({ title_height: 24, topics: ["tip", "status"], widgets }, state, frameTopic);
}

const button = (bar, name) => bar.all(`.oo-${name}`)[0];
const display = (section) => section.style.values.display;

test("it draws a section for each widget, in order", () => {
  const { sections } = page();
  assert.deepEqual(sections.map((s) => s.children[0].children[0].className.split(" ")[0]), ["tip", "status"]);
});

test("its title bar shows the widgetwindow's title", () => {
  assert.equal(page().bar.all(".oo-title")[0].textContent, "Trading");
});

test("its title bar is the height it's given", () => {
  assert.equal(page().bar.style.values.height, "24px");
});

test("its pencil asks the host to toggle edit mode", () => {
  const { bar, asked } = page();
  button(bar, "pencil").click();
  assert.deepEqual(asked, ["edit"]);
});

test("its cross asks the host to close it", () => {
  const { bar, asked } = page();
  button(bar, "close").click();
  assert.deepEqual(asked, ["close"]);
});

test("its anchor asks the host for the list of places", () => {
  const { bar, asked } = page();
  button(bar, "anchor").click();
  assert.deepEqual(asked, ["anchor"]);
});

test("in edit mode its bar is marked editing", () => {
  const { bar } = page(undefined, undefined, { title: "T", editing: true });
  assert.ok(bar.hasClass("editing"));
});

test("in edit mode pressing its title bar asks the host to move it", () => {
  const { bar, asked } = page(undefined, undefined, { title: "T", editing: true });
  bar.fire("mousedown", { button: 0 });
  assert.deepEqual(asked, ["move"]);
});

test("outside edit mode pressing its title bar does nothing", () => {
  const { bar, asked } = page();
  bar.fire("mousedown", { button: 0 });
  assert.deepEqual(asked, []);
});

test("pressing a button on its bar doesn't move it", () => {
  const { bar, asked } = page(undefined, undefined, { title: "T", editing: true });
  button(bar, "pencil").fire("mousedown", { button: 0 }, bar);
  assert.deepEqual(asked, []);
});

test("a widget that isn't open is hidden", () => {
  const { sections } = page(undefined, undefined, { title: "T", editing: false, shown: ["status"] });
  assert.deepEqual(sections.map(display), ["none", ""]);
});

test("a widget with nothing to show and hide_empty is hidden", () => {
  const { sections } = page([widget("tip", ["tip"], { hide_empty: true })], { tip: [] });
  assert.equal(display(sections[0]), "none");
});

test("a widget with nothing to show stays by default", () => {
  const { sections } = page([TIP], { tip: [] });
  assert.equal(display(sections[0]), "");
});

test("a widget with a height set is that height", () => {
  const { sections } = page([widget("tip", ["tip"], { height: 310 })]);
  assert.equal(sections[0].style.values.height, "310px");
});

test("the widget that fills is marked so", () => {
  const { sections } = page([widget("tip", ["tip"], { fill: true })]);
  assert.ok(sections[0].hasClass("fills"));
});

test("a widget's text is its own size", () => {
  const { sections } = page([widget("tip", ["tip"], { scale: 0.6 })]);
  assert.equal(sections[0].style.values["--oo-scale"], "0.6");
});

test("a widget redraws when a topic it reads changes", () => {
  const { sections, publish } = page([widget("tip", ["tip"], { topics: ["tip"] })]);
  publish("tip", ["Undock."]);
  assert.equal(sections[0].textContent, "Undock.");
});
