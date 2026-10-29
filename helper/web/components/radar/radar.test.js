"use strict";

// Behaviour of the radar component, under a fake DOM (lib/testing.js), in its
// named states (radar.states.json). One state or one action per test.
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { render, states } = require("../../lib/testing.js");

const STATES = states("radar");
const rows = (node) => node.all("tr").slice(1);
const names = (node) => rows(node).map((tr) => tr.children[0].children[1].textContent);
const heading = (node, title) => node.all("button").find((b) => b.textContent.startsWith(title));

test("draws nothing with nothing on the scanner", () => {
  assert.equal(render("radar", STATES["nothing on the scanner"]).node, null);
});

test("draws a row per blip", () => {
  assert.equal(rows(render("radar", STATES.quiet).node).length, 3);
});

test("lists the nearest first", () => {
  assert.deepEqual(names(render("radar", STATES.quiet).node), ["Python", "Coriolis Station", "Navigation Buoy"]);
});

test("shows the distance in km with one decimal", () => {
  const [first] = rows(render("radar", STATES.quiet).node);
  assert.equal(first.children[1].textContent, "3.0 km");
});

test("gives the dot the blip's scanner colour", () => {
  const dot = render("radar", STATES.quiet).node.all(".dot")[0];
  assert.equal(dot.style.values["--blip"], "#ffff00");
});

test("flashes the dot only when the blip has a flash colour", () => {
  const dots = render("radar", STATES.quiet).node.all(".dot");
  assert.deepEqual(dots.map((dot) => dot.hasClass("flashing")), [false, false, true]); // the buoy flashes
});

test("says what a hostile ship is doing, marked", () => {
  const krait = rows(render("radar", STATES["pirate attacking you"]).node)[0];
  assert.deepEqual([krait.hasClass("hostile"), krait.children[2].textContent], [true, "attacking you"]);
});

test("shows a bounty only above zero", () => {
  const bounties = rows(render("radar", STATES["pirate attacking you"]).node).map((tr) => tr.children[3].textContent);
  assert.deepEqual(bounties, ["45 ₢", "", ""]);
});

test("marks the column it's sorted by", () => {
  assert.equal(heading(render("radar", STATES.quiet).node, "Distance").textContent, "Distance ▲");
});

test("clicking a heading sorts by that column", () => {
  const { node, again } = render("radar", STATES["police chasing an offender"]);
  heading(node, "Bounty").click();
  assert.equal(names(again())[0], "Mamba");
});

test("clicking the sorted column again reverses it", () => {
  const { node, again } = render("radar", STATES.quiet);
  heading(node, "Distance").click();
  assert.equal(names(again())[0], "Navigation Buoy");
});

test("counts the rows past the limit as +N more", () => {
  assert.equal(render("radar", STATES["many blips"]).node.all(".more")[0].textContent, "+4 more");
});
