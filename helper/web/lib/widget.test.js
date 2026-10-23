"use strict";

// The shared files: every component folder registers a component of its name.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const { loadComponents, WEB } = require("./testing.js");

test("every component folder registers a component of its name", () => {
  const names = fs.readdirSync(path.join(WEB, "components")).sort();
  const page = loadComponents(...names);
  for (const name of names) assert.ok(page.Oolite.get(name), name);
});
