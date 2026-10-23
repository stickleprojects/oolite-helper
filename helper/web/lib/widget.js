// The widget page (#82): the components register themselves here, and this
// draws the ones the widget lists whenever a topic they read changes.
//
// The helper generates each widget's page: it loads this file, the listed
// components' files, and _oolite/widget.js, which sets
// OOLITE_WIDGET = {components: [...], topics: [...], width: px or null}.
// Each entry in components is a name, or {tabs: [names]}: a tab group, drawn
// as a tab row (the widget's own frame) over the tab shown. The model keeps
// the choice (ui/choose_tab, the "tabs" topic), so every widget agrees, and an
// emergency shows Keys.
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

  function part(name) {
    const component = registry.get(name);
    return component ? component.render(state, draw) : null;
  }

  // The tab of a group to show: the model's, else the player's choice if it's
  // in this group, else the group's first.
  function shownTab(group) {
    const tabs = state.tabs || {};
    return [tabs.shown, tabs.chosen].find((name) => group.includes(name)) || group[0];
  }

  // The group's tab row over the tab shown.
  function tabGroup(group) {
    const { el, button } = globalThis.OoliteDom;
    const shown = shownTab(group);
    const titles = new Map(((state.tabs || {}).tabs || []).map((tab) => [tab.id, tab.text]));
    const row = el(
      "div",
      "tab-row",
      ...group.map((name) =>
        button(
          titles.get(name) || name,
          () => oolite.dispatch({ type: "ui/choose_tab", tab: name }),
          name === shown ? "tab active" : "tab",
        ),
      ),
    );
    return el("div", "tabs", row, part(shown));
  }

  function draw() {
    const widget = globalThis.OOLITE_WIDGET;
    const root = document.getElementById("root");
    const parts = widget.components
      .map((item) => (typeof item === "string" ? part(item) : tabGroup(item.tabs)))
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
