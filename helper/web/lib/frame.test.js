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

// -- plugins' widgets: placeholders their views go over -----------------------

const LAMP = { id: "lamp", plugin: true };
const OPEN = { title: "T", editing: false, shown: ["tip", "status"], plugins: { lamp: 100 } };

// A page with a plugin's widget between the helper's two, placed on screen:
// the column under a 24 px bar, the lamp's placeholder 60 px down it.
function withLamp(frameTopic = OPEN) {
  const made = page([TIP, LAMP, STATUS], STATE, frameTopic);
  made.column.rect = { x: 0, y: 24, width: 300, height: 500 };
  made.sections[1].rect = { x: 0, y: 84, width: 294, height: 100 };
  made.nextFrame();
  return made;
}

const lastPlaced = (placed) => placed[placed.length - 1];

test("a plugin's widget leaves a placeholder of its height in its place", () => {
  const { sections } = withLamp();
  assert.ok(sections[1].hasClass("oo-placeholder"));
  assert.equal(sections[1].style.values.height, "100px");
});

test("once drawn it tells the host where the column and the placeholder are", () => {
  assert.deepEqual(withLamp().placed, [{ column: [0, 24, 300, 500], rects: { lamp: [0, 84, 294, 100] } }]);
});

test("after a scroll it tells the host where the placeholder is now", () => {
  const { column, sections, placed, nextFrame } = withLamp();
  sections[1].rect = { ...sections[1].rect, y: 30 };
  column.fire("scroll");
  nextFrame();
  assert.deepEqual(lastPlaced(placed).rects, { lamp: [0, 30, 294, 100] });
});

test("after the window is resized it tells the host where the column is now", () => {
  const { column, placed, nextFrame, fireWindow } = withLamp();
  column.rect = { ...column.rect, width: 400 };
  fireWindow("resize");
  nextFrame();
  assert.deepEqual(lastPlaced(placed).column, [0, 24, 400, 500]);
});

test("after a widget above it is hidden it tells the host where the placeholder is now", () => {
  const { sections, placed, publish, nextFrame } = withLamp();
  sections[1].rect = { ...sections[1].rect, y: 24 };
  publish("frame", { ...OPEN, shown: ["status"] });
  nextFrame();
  assert.deepEqual(lastPlaced(placed).rects, { lamp: [0, 24, 294, 100] });
});

test("after a widget above it opens it tells the host where the placeholder is now", () => {
  const { sections, placed, publish, nextFrame } = withLamp({ ...OPEN, shown: ["status"] });
  sections[1].rect = { ...sections[1].rect, y: 140 };
  publish("frame", OPEN);
  nextFrame();
  assert.deepEqual(lastPlaced(placed).rects, { lamp: [0, 140, 294, 100] });
});

test("after a widget above it redraws taller it tells the host where the placeholder is now", () => {
  const { sections, placed, publish, nextFrame } = withLamp();
  sections[1].rect = { ...sections[1].rect, y: 140 };
  publish("tip", ["Dock now.", "Then sell."]);
  nextFrame();
  assert.deepEqual(lastPlaced(placed).rects, { lamp: [0, 140, 294, 100] });
});

test("several changes in one frame are told once", () => {
  const { column, sections, placed, nextFrame, fireWindow } = withLamp();
  sections[1].rect = { ...sections[1].rect, y: 30 };
  column.fire("scroll");
  column.fire("scroll");
  fireWindow("resize");
  nextFrame();
  assert.equal(placed.length, 2);
});

test("nothing is told when nothing moved", () => {
  const { column, placed, nextFrame } = withLamp();
  column.fire("scroll");
  nextFrame();
  assert.equal(placed.length, 1);
});

test("a plugin's widget that's hidden has no placeholder, and the host is told", () => {
  const { sections, placed } = withLamp({ ...OPEN, plugins: { lamp: null } });
  assert.equal(display(sections[1]), "none");
  assert.deepEqual(placed[0].rects, {});
});

test("a plugin's widget shown again gets its placeholder back", () => {
  const { sections, placed, publish, nextFrame } = withLamp({ ...OPEN, plugins: { lamp: null } });
  publish("frame", OPEN);
  nextFrame();
  assert.equal(display(sections[1]), "");
  assert.deepEqual(lastPlaced(placed).rects, { lamp: [0, 84, 294, 100] });
});

test("a page with no plugins' widgets tells the host nothing", () => {
  const made = page();
  made.nextFrame();
  assert.deepEqual(made.placed, []);
});

test("a wheel turn a plugin's view didn't use scrolls the column by WebKit's step", () => {
  const { column, wheel } = withLamp();
  wheel(0, 1);
  assert.deepEqual(column.scrolled, [{ left: 0, top: 44, behavior: "smooth" }]); // floor(300^(2/3))
});

test("a touchpad's smooth wheel turn scrolls the column its own distance", () => {
  const { column, wheel } = withLamp();
  wheel(0, -0.5);
  assert.deepEqual(column.scrolled, [{ left: 0, top: -22, behavior: "smooth" }]);
});

// -- edit mode: its edges and its list of places -----------------------------

const PLACES = [
  ["game:left", "Game: left"],
  ["game:right", "Game: right"],
  ["game:top", "Game: top"],
  ["game:bottom", "Game: bottom"],
  ["screen:eDP-1:left", "eDP-1: left"],
  ["screen:eDP-1:right", "eDP-1: right"],
  ["screen:eDP-1:top", "eDP-1: top"],
  ["screen:eDP-1:bottom", "eDP-1: bottom"],
  ["float", "Float"],
];
const EDITING = { title: "T", editing: true, edges: ["left", "bottom"], places: PLACES };

test("in edit mode it draws the edges that resize it", () => {
  const { edges } = page(undefined, undefined, EDITING);
  assert.deepEqual(
    Object.entries(edges).map(([side, node]) => [side, node.style.values.display]),
    [["left", "block"], ["right", "none"], ["top", "none"], ["bottom", "block"]],
  );
});

test("outside edit mode it draws no edges", () => {
  const { edges } = page(undefined, undefined, { ...EDITING, editing: false });
  assert.ok(Object.values(edges).every((node) => node.style.values.display === "none"));
});

test("in edit mode its column is inset from its edges", () => {
  const { column } = page(undefined, undefined, EDITING);
  const margins = ["left", "right", "bottom"].map((side) => column.style.values[`margin-${side}`]);
  assert.deepEqual(margins, ["6px", "0", "6px"]);
});

test("leaving edit mode its column fills it again", () => {
  const { column, publish } = page(undefined, undefined, EDITING);
  publish("frame", { ...EDITING, editing: false, shown: ["tip", "status"] });
  assert.equal(column.style.values["margin-left"], "0");
});

test("in edit mode pressing an edge asks the host to resize it from there", () => {
  const { edges, asked } = page(undefined, undefined, EDITING);
  edges.left.fire("mousedown", { button: 0 });
  assert.deepEqual(asked, ["resize left"]);
});

test("outside edit mode pressing an edge does nothing", () => {
  const { edges, asked } = page(undefined, undefined, { ...EDITING, editing: false });
  edges.left.fire("mousedown", { button: 0 });
  assert.deepEqual(asked, []);
});

test("pressing its top edge, over the bar, doesn't move it", () => {
  const { edges, bar, asked } = page(undefined, undefined, { ...EDITING, edges: ["top"] });
  edges.top.fire("mousedown", { button: 0 }, bar);
  assert.deepEqual(asked, ["resize top"]);
});

test("its list of places is closed at first", () => {
  assert.equal(page(undefined, undefined, EDITING).places.style.values.display, "none");
});

test("in edit mode its anchor opens its list of places", () => {
  const { bar, places } = page(undefined, undefined, EDITING);
  button(bar, "anchor").click();
  assert.equal(places.style.values.display, "grid");
});

test("its list opens under its bar, and no taller than the window below it, so it scrolls", () => {
  const { places } = page(undefined, undefined, EDITING);
  assert.equal(places.style.values.top, "24px");
  assert.equal(places.style.values["max-height"], "calc(100% - 24px)");
});

test("its anchor again closes the list", () => {
  const { bar, places } = page(undefined, undefined, EDITING);
  button(bar, "anchor").click();
  button(bar, "anchor").click();
  assert.equal(places.style.values.display, "none");
});

test("its list has a column per target headed by its name, a row per side, and Float", () => {
  const { places } = page(undefined, undefined, EDITING);
  assert.deepEqual(
    places.children.map((cell) => cell.textContent),
    ["Game", "eDP-1", "left", "left", "right", "right", "top", "top", "bottom", "bottom", "Float"],
  );
  assert.equal(places.style.values["grid-template-columns"], "repeat(2, auto)");
});

test("picking a place asks the host to dock it there and closes the list", () => {
  const { bar, places, asked } = page(undefined, undefined, EDITING);
  button(bar, "anchor").click();
  places.children[3].click(); // eDP-1's left
  assert.deepEqual(asked, ["dock screen:eDP-1:left"]);
  assert.equal(places.style.values.display, "none");
});

test("leaving edit mode closes the list", () => {
  const { bar, places, publish } = page(undefined, undefined, EDITING);
  button(bar, "anchor").click();
  publish("frame", { ...EDITING, editing: false, places: [] });
  assert.equal(places.style.values.display, "none");
});

test("outside edit mode its anchor opens nothing", () => {
  const { bar, places } = page();
  button(bar, "anchor").click();
  assert.equal(places.style.values.display, "none");
});

test("while its list is open the host is told no placeholders, so plugins' views hide", () => {
  const { bar, placed, nextFrame } = withLamp({ ...OPEN, ...EDITING });
  button(bar, "anchor").click();
  nextFrame();
  assert.deepEqual(lastPlaced(placed).rects, {});
});

test("when its list closes the placeholders come back", () => {
  const { bar, placed, nextFrame } = withLamp({ ...OPEN, ...EDITING });
  button(bar, "anchor").click();
  nextFrame();
  button(bar, "anchor").click();
  nextFrame();
  assert.deepEqual(lastPlaced(placed).rects, { lamp: [0, 84, 294, 100] });
});
