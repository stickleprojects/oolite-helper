// The widget page (#82): the components register themselves here, and this
// draws the ones the widget lists whenever a topic they read changes.
//
// The helper generates each widget's page: it loads this file, the listed
// components' files, and _oolite/widget.js, which sets
// OOLITE_WIDGET = {components: [...], topics: [...], width: px or null}.
//
// A component is
//   Oolite.component("name", {render(state, refresh) { return node or null; }});
// where state holds every topic the widget gets (each component lists its own
// in component.toml) and refresh() redraws after a change to the component's
// own local state, e.g. a sort order. render returns null when there's
// nothing to show; with every component empty the widget hides itself.
"use strict";

const Oolite = (() => {
  const registry = new Map();
  const state = {};
  let shown = null;
  let size = null;

  function draw() {
    const widget = globalThis.OOLITE_WIDGET;
    const root = document.getElementById("root");
    const parts = widget.components
      .map((name) => registry.get(name))
      .filter(Boolean)
      .map((component) => component.render(state, draw))
      .filter(Boolean);
    root.replaceChildren(...parts);
    const show = parts.length > 0;
    if (show !== shown) {
      shown = show;
      oolite.show(show);
    }
    if (!show) return;
    const box = root.getBoundingClientRect();
    const want = [Math.ceil(box.width), Math.ceil(box.height)];
    if (!size || want[0] !== size[0] || want[1] !== size[1]) {
      size = want;
      oolite.resize(...want);
    }
  }

  function start() {
    const widget = globalThis.OOLITE_WIDGET;
    // A width or height set in config.toml: the components fill the window.
    if (widget.width) document.documentElement.classList.add("fixed");
    for (const topic of widget.topics) {
      oolite.on(topic, (value) => {
        state[topic] = value;
        draw();
      });
    }
    draw();
  }

  document.addEventListener("DOMContentLoaded", start);
  return Object.freeze({
    component(name, definition) {
      registry.set(name, definition);
    },
    get(name) {
      return registry.get(name); // for tests and the harness
    },
  });
})();
globalThis.Oolite = Oolite;
