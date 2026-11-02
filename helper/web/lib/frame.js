// A widgetwindow's page (#141): its title bar (title, ⚓ ✎ ×) over a column
// of its widgets, which scrolls when they're taller than the window. The
// helper's widgets are drawn here. A plugin's widget keeps a view (and a web
// process) of its own: here it has a placeholder of its height, and the page
// tells the web host where the column and each placeholder are, so the host
// lays the plugin's view over it and clips it to the column.
//
// The helper generates the page: it loads lib/, the widgets' components' files,
// this file, and _oolite/frame-config.js, which sets
// OOLITE_FRAME = {title_height: px, topics: [...], widgets: [{id, components,
// widget, topics, height: px or null, fill, hide_empty, scale}, or for a
// plugin's widget {id, plugin: true}]}, in the column's order.
// The "frame" topic is what changes without a reload:
// {title, editing, shown: [ids of the helper's widgets that are open],
//  plugins: {id: its height in px, or null while it's hidden}}.
//
// The bar's buttons, and pressing on the bar in edit mode to move the window,
// go to the web host through window.ooliteFrame, which only this page gets.
"use strict";

(() => {
  function section(widget, state) {
    const { el } = globalThis.OoliteDom;
    const sized = widget.height ? " sized" : "";
    const node = el("div", `oo-widget fixed${widget.fill ? " fills" : ""}${sized}`);
    node.style.setProperty("--oo-scale", String(widget.scale));
    if (widget.height) node.style.setProperty("height", `${widget.height}px`);
    const root = el("div", "oo-root");
    node.append(root);
    let open = true;
    let empty = false;
    const update = () => node.style.setProperty("display", open && !empty ? "" : "none");
    const draw = Oolite.mount(widget, root, state, {
      show(show) {
        empty = !show && widget.hide_empty;
        update();
      },
      drawn() {},
    });
    return {
      node,
      draw,
      topics: new Set(widget.topics),
      open(value) {
        open = value;
        update();
      },
    };
  }

  // A plugin's widget: an empty box its view goes over.
  function placeholder() {
    const node = globalThis.OoliteDom.el("div", "oo-widget oo-placeholder");
    let height = null;
    return {
      node,
      plugin: true,
      draw() {},
      topics: new Set(),
      open() {}, // a plugin's widget is shown while it has a height
      size(value) {
        height = typeof value === "number" ? value : null;
        node.style.setProperty("display", height === null ? "none" : "");
        if (height !== null) node.style.setProperty("height", `${height}px`);
      },
      shown: () => height !== null,
    };
  }

  const box = (node) => {
    const r = node.getBoundingClientRect();
    return [r.x, r.y, r.width, r.height].map(Math.round);
  };

  function start() {
    const config = globalThis.OOLITE_FRAME;
    if (!config) return;
    const { el, button } = globalThis.OoliteDom;
    const host = globalThis.ooliteFrame;
    const state = {};

    const title = el("span", "oo-title");
    const anchor = button("⚓", () => host.anchor(), "oo-anchor");
    const pencil = button("✎", () => host.edit(), "oo-pencil");
    const close = button("×", () => host.close(), "oo-close");
    for (const node of [anchor, pencil, close]) {
      node.addEventListener("mousedown", (event) => event.stopPropagation()); // not a move
    }
    const bar = el("div", "oo-bar", title, el("span", "oo-buttons", anchor, pencil, close));
    const size = config.title_height;
    bar.style.setProperty("height", `${size}px`);
    bar.style.setProperty("font-size", `${Math.max(8, Math.round(size * 0.5))}px`);
    let editing = false;
    bar.addEventListener("mousedown", (event) => {
      if (editing && event.button === 0) host.move();
    });

    const sections = config.widgets.map((widget) => [
      widget.id,
      widget.plugin ? placeholder() : section(widget, state),
    ]);
    const column = el("div", "oo-column", ...sections.map(([, part]) => part.node));
    document.getElementById("root").replaceChildren(bar, column);

    // Where the column and the shown placeholders are, sent at most once an
    // animation frame and only when it changed: after a scroll, a resize, or
    // anything above a placeholder changing its height.
    const plugins = sections.filter(([, part]) => part.plugin);
    let pending = false;
    let last = null;
    const report = () => {
      if (!plugins.length || pending) return;
      pending = true;
      globalThis.requestAnimationFrame(() => {
        pending = false;
        const rects = {};
        for (const [id, part] of plugins) if (part.shown()) rects[id] = box(part.node);
        const where = box(column);
        const text = JSON.stringify([where, rects]);
        if (text === last) return;
        last = text;
        host.placeholders(where, rects);
      });
    };
    column.addEventListener("scroll", report);
    globalThis.addEventListener("resize", report);
    if (globalThis.ResizeObserver) {
      const observer = new globalThis.ResizeObserver(report);
      for (const [, part] of sections) observer.observe(part.node);
    }

    oolite.on("frame", (frame) => {
      title.textContent = frame.title;
      editing = Boolean(frame.editing);
      bar.className = editing ? "oo-bar editing" : "oo-bar";
      const shown = new Set(frame.shown);
      const heights = frame.plugins || {};
      for (const [id, part] of sections) {
        if (part.plugin) part.size(heights[id]);
        else part.open(shown.has(id));
      }
      report();
    });
    for (const topic of config.topics) {
      oolite.on(topic, (value) => {
        state[topic] = value;
        for (const [, part] of sections) if (part.topics.has(topic)) part.draw();
        report();
      });
    }
    for (const [, part] of sections) part.draw();
    report();
  }

  document.addEventListener("DOMContentLoaded", start);
})();
