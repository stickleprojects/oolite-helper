// The widget page (#82): the components register themselves here, and this
// draws the ones the widget lists whenever a topic they read changes.
//
// The helper generates each widget's page: it loads this file, the listed
// components' files, and _oolite/widget.js, which sets
// OOLITE_WIDGET = {components: [names], widget: its name or null,
// topics: [...], width: px or null, height: px or null}.
//
// A component is
//   Oolite.component("name", {render(state, refresh) { return node or null; }});
// where state holds every topic the widget gets (each component lists its own
// in component.toml) and refresh() redraws after a change to the component's
// own local state, e.g. a sort order. render returns null when there's
// nothing to show; with every component empty the widget hides itself.
//
// A widget draws its components side by side (a column when it has a fixed
// size), unless it's a named widget that draws itself (helper/web/widgets/<name>/):
//   Oolite.widget("name", {draw(names, state, part, dispatch) { return node or null; }});
// where part(name) renders one of its components and dispatch sends an action.
//
// A widgetwindow's page (#141) draws several widgets in one page with
// Oolite.mount() instead; see lib/frame.js.
"use strict";

const Oolite = (() => {
  const registry = new Map();
  const widgets = new Map();

  // Draws a widget's components into root from state, whenever draw() is
  // called. page.show(bool) hears when it starts or stops having anything to
  // show, and page.drawn() after each draw that shows something. A widget page
  // mounts one; a widgetwindow's page (lib/frame.js) mounts one per widget.
  function mount(widget, root, state, page) {
    let shown = null;

    function part(name) {
      const component = registry.get(name);
      return component ? component.render(state, draw) : null;
    }

    // What the widget draws: its own drawing, or its components in order.
    function drawn() {
      const own = widgets.get(widget.widget);
      if (!own) return widget.components.map(part).filter(Boolean);
      const node = own.draw(widget.components, state, part, (action) => oolite.dispatch(action));
      return node ? [node] : [];
    }

    function draw() {
      const parts = drawn();
      root.replaceChildren(...parts);
      const show = parts.length > 0;
      if (show !== shown) {
        shown = show;
        page.show(show);
      }
      if (show) page.drawn();
    }

    return draw;
  }

  function start() {
    const widget = globalThis.OOLITE_WIDGET;
    if (!widget) return; // a widgetwindow's page: lib/frame.js draws it
    const root = document.getElementById("root");
    const state = {};
    let size = null;
    let shown = false;

    // Asks for the window the components need. Run after each draw, and again
    // when their layout changes without one: a page first laid out in the host's
    // small window wraps its text, so it measures too tall until it's resized.
    function measure() {
      const box = root.getBoundingClientRect();
      const want = [Math.ceil(box.width), Math.ceil(box.height)];
      if (!size || want[0] !== size[0] || want[1] !== size[1]) {
        size = want;
        oolite.resize(...want);
      }
    }

    const draw = mount(widget, root, state, {
      show(show) {
        shown = show;
        oolite.show(show);
      },
      drawn: measure,
    });
    // A width or height set in config.toml: the components fill the window's
    // width; only a set height fills its height, else it's their own (#80).
    if (widget.width || widget.height) document.documentElement.classList.add("fixed");
    if (widget.height) document.documentElement.classList.add("fixed-height");
    for (const topic of widget.topics) {
      oolite.on(topic, (value) => {
        state[topic] = value;
        draw();
      });
    }
    draw();
    if (typeof ResizeObserver === "function") {
      new ResizeObserver(() => shown && measure()).observe(root);
    }
  }

  document.addEventListener("DOMContentLoaded", start);
  return Object.freeze({
    mount,
    component(name, definition) {
      registry.set(name, definition);
    },
    get(name) {
      return registry.get(name); // for tests and the harness
    },
    widget(name, definition) {
      widgets.set(name, definition);
    },
    getWidget(name) {
      return widgets.get(name); // for tests
    },
  });
})();
globalThis.Oolite = Oolite;
