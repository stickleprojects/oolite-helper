// A widgetwindow's page (#141): its title bar (title, ⚓ ✎ ×) over a column
// of the helper's widgets in it, which scrolls when they're taller than the
// window. Plugins' widgets aren't drawn here: they keep views of their own.
//
// The helper generates the page: it loads lib/, the widgets' components' files,
// this file, and _oolite/frame-config.js, which sets
// OOLITE_FRAME = {title_height: px, topics: [...], widgets: [{id, components,
// widget, topics, height: px or null, fill, hide_empty, scale}]}.
// The "frame" topic is what changes without a reload:
// {title, editing, shown: [ids of the widgets that are open]}.
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

    const sections = config.widgets.map((widget) => [widget.id, section(widget, state)]);
    const column = el("div", "oo-column", ...sections.map(([, part]) => part.node));
    document.getElementById("root").replaceChildren(bar, column);

    oolite.on("frame", (frame) => {
      title.textContent = frame.title;
      editing = Boolean(frame.editing);
      bar.className = editing ? "oo-bar editing" : "oo-bar";
      const shown = new Set(frame.shown);
      for (const [id, part] of sections) part.open(shown.has(id));
    });
    for (const topic of config.topics) {
      oolite.on(topic, (value) => {
        state[topic] = value;
        for (const [, part] of sections) if (part.topics.has(topic)) part.draw();
      });
    }
    for (const [, part] of sections) part.draw();
  }

  document.addEventListener("DOMContentLoaded", start);
})();
