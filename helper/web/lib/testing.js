"use strict";

// Testing for web components: just enough DOM for the built-in components
// (they build nodes through lib/dom.js), so their behaviour can be tested
// under Node, beside each component (components/<name>/<name>.test.js):
// what they render for a state, and what clicking does.
//
//   const { render } = require("../../lib/testing.js");
//   const { node, sent } = render("drive", { drive: {...} });
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class FakeNode {
  constructor(tagName) {
    this.tagName = tagName;
    this.className = "";
    this.children = [];
    this.listeners = {};
    this.text = "";
  }

  append(...nodes) {
    for (const node of nodes) {
      this.children.push(typeof node === "string" ? new FakeText(node) : node);
    }
  }

  replaceChildren(...nodes) {
    this.children = [];
    this.text = "";
    this.append(...nodes);
  }

  get textContent() {
    return this.text + this.children.map((child) => child.textContent).join("");
  }

  set textContent(value) {
    this.children = [];
    this.text = String(value);
  }

  get childElementCount() {
    return this.children.filter((child) => child instanceof FakeNode).length;
  }

  addEventListener(type, listener) {
    (this.listeners[type] ||= []).push(listener);
  }

  click() {
    for (const listener of this.listeners.click || []) listener();
  }

  getBoundingClientRect() {
    return { width: 100, height: 20 };
  }

  // Every element below this one (itself included) that matches test(node).
  findAll(test) {
    const found = test(this) ? [this] : [];
    for (const child of this.children) {
      if (child instanceof FakeNode) found.push(...child.findAll(test));
    }
    return found;
  }

  // Elements of this tag, or with this class: "button", ".chip".
  all(selector) {
    if (selector.startsWith(".")) {
      const name = selector.slice(1);
      return this.findAll((node) => node.className.split(" ").includes(name));
    }
    return this.findAll((node) => node.tagName === selector);
  }

  hasClass(name) {
    return this.className.split(" ").includes(name);
  }
}

class FakeText {
  constructor(text) {
    this.textContent = text;
  }
}

const WEB = path.join(__dirname, "..");
const LIB = ["lib/dom.js", "lib/format.js", "lib/widget.js"];

// What a component needs, from its component.toml (needs = ["keys"]), and
// what those need: the same files the helper's page for it would load.
function withNeeds(names) {
  const order = [];
  const add = (name) => {
    if (order.includes(name)) return;
    const toml = fs.readFileSync(path.join(WEB, "components", name, "component.toml"), "utf8");
    const needs = toml.match(/^needs\s*=\s*\[([^\]]*)\]/m);
    for (const need of needs ? needs[1].match(/"([^"]+)"/g) || [] : []) add(need.slice(1, -1));
    order.push(name);
  };
  names.forEach(add);
  return order;
}

// A fresh page with the shared files and these components' .js files (and
// what they need) loaded. Returns {Oolite, root, sent}: sent collects what
// oolite.dispatch() was given.
function loadComponents(...names) {
  const root = new FakeNode("div");
  const sent = [];
  const context = {
    document: {
      createElement: (tag) => new FakeNode(tag),
      getElementById: () => root,
      addEventListener: () => {},
      documentElement: { classList: { add: () => {} } },
    },
    oolite: {
      // Copied: the components run in their own context, so their objects
      // wouldn't compare equal with the test's.
      dispatch: (action) => sent.push(JSON.parse(JSON.stringify(action))),
      on: () => () => {},
      resize: () => {},
      show: () => {},
      log: () => {},
    },
  };
  context.globalThis = context;
  vm.createContext(context);
  const files = [...LIB];
  for (const name of withNeeds(names)) {
    const folder = path.join(WEB, "components", name);
    for (const file of fs.readdirSync(folder).sort()) {
      if (file.endsWith(".js") && !file.endsWith(".test.js")) {
        files.push(path.join("components", name, file));
      }
    }
  }
  for (const file of files) {
    vm.runInContext(fs.readFileSync(path.join(WEB, file), "utf8"), context, { filename: file });
  }
  return { Oolite: context.Oolite, root, sent };
}

// Render one component: {node, sent, refreshed()} where refreshed() counts
// the component's refresh() calls.
function render(name, state) {
  const page = loadComponents(name);
  let refreshes = 0;
  const component = page.Oolite.get(name);
  const node = component.render(state, () => {
    refreshes += 1;
  });
  return {
    node,
    sent: page.sent,
    refreshes: () => refreshes,
    again: () => component.render(state, () => {}),
  };
}

module.exports = { FakeNode, loadComponents, render, WEB };
