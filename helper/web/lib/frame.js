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
// widget, topics, height: px or null, fill, min_height: px or null,
// hide_empty, scale}, or for a plugin's widget {id, plugin: true}]}, in the column's order.
// The "frame" topic is what changes without a reload:
// {title, editing, edges: [the window's edges that resize it: "left", ...],
//  places: [[place, label], ...] its ⚓ list offers while editing,
//  shown: [ids of the helper's widgets that are open],
//  plugins: {id: its height in px, or null while it's hidden}}.
//
// In edit mode it draws those edges, and its column moves in from them so
// plugins' views don't cover them; ⚓ opens the list of places, and while it's
// open plugins' views hide, as they'd cover it. The bar's buttons, pressing an
// edge or (in edit mode) the bar to resize or move the window, and a place
// picked go to the web host through window.ooliteFrame, which only this page gets.
// The host calls ooliteFrameWheel(dx, dy) with a wheel turn a plugin's view
// didn't use.
"use strict";

(() => {
  function section(widget, state) {
    const { el } = globalThis.OoliteDom;
    const sized = widget.height ? " sized" : "";
    const node = el("div", `oo-widget fixed${widget.fill ? " fills" : ""}${sized}`);
    node.style.setProperty("--oo-scale", String(widget.scale));
    if (widget.height) node.style.setProperty("height", `${widget.height}px`);
    if (widget.fill && widget.min_height) node.style.setProperty("min-height", `${widget.min_height}px`);
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

  const EDGE_PX = 6; // as the web host's ghost outline
  const SIDES = ["left", "right", "top", "bottom"];

  // The ⚓ list's cells, in rows: a column per target (the game, each screen)
  // headed by its name, a row per side, then Float across the bottom.
  function placeCells(places, pick) {
    const { el, button } = globalThis.OoliteDom;
    const columns = new Map(); // "game" or "screen:<name>" -> its heading
    for (const [place, label] of places) {
      if (place === "float") continue;
      const target = place.slice(0, place.lastIndexOf(":"));
      if (!columns.has(target)) columns.set(target, label.slice(0, label.lastIndexOf(":")));
    }
    const cells = [...columns.values()].map((heading) => el("span", "oo-place-head", heading));
    for (const side of SIDES) {
      for (const target of columns.keys()) cells.push(button(side, () => pick(`${target}:${side}`), "oo-place"));
    }
    cells.push(button("Float", () => pick("float"), "oo-place oo-float"));
    return { cells, columns: Math.max(1, columns.size) };
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
    let editing = false;
    let edges = [];
    let places = [];
    const list = el("div", "oo-places");
    let listOpen = false;
    let report = () => {}; // set below
    const showList = (open) => {
      listOpen = open && editing;
      list.style.setProperty("display", listOpen ? "grid" : "none");
      report(); // plugins' views hide while it's open, and come back
    };
    const anchor = button("⚓", () => showList(!listOpen), "oo-anchor");
    const pencil = button("✎", () => host.edit(), "oo-pencil");
    const close = button("×", () => host.close(), "oo-close");
    for (const node of [anchor, pencil, close]) {
      node.addEventListener("mousedown", (event) => event.stopPropagation()); // not a move
    }
    const bar = el("div", "oo-bar", title, el("span", "oo-buttons", anchor, pencil, close));
    const size = config.title_height;
    bar.style.setProperty("height", `${size}px`);
    bar.style.setProperty("font-size", `${Math.max(8, Math.round(size * 0.5))}px`);
    bar.addEventListener("mousedown", (event) => {
      if (editing && event.button === 0) host.move();
    });
    list.style.setProperty("top", `${size}px`);
    list.style.setProperty("max-height", `calc(100% - ${size}px)`);
    list.style.setProperty("font-size", `${Math.max(8, Math.round(size * 0.5))}px`);
    list.style.setProperty("display", "none");
    const drawList = () => {
      const { cells, columns } = placeCells(places, (place) => {
        showList(false);
        host.dock(place);
      });
      list.replaceChildren(...cells);
      list.style.setProperty("grid-template-columns", `repeat(${columns}, auto)`);
    };

    const edgeNodes = SIDES.map((side) => {
      const node = el("div", `oo-edge oo-edge-${side}`);
      node.addEventListener("mousedown", (event) => {
        event.stopPropagation(); // the top one is over the bar: a resize, not a move
        if (editing && event.button === 0) host.resize(side);
      });
      return [side, node];
    });

    const sections = config.widgets.map((widget) => [
      widget.id,
      widget.plugin ? placeholder() : section(widget, state),
    ]);
    const column = el("div", "oo-column", ...sections.map(([, part]) => part.node));
    document.getElementById("root").replaceChildren(bar, column, list, ...edgeNodes.map(([, node]) => node));
    // In edit mode: the edges that resize it, with the column moved in from
    // them (the top one is over the bar, so the column needs no room there).
    const drawEdges = () => {
      for (const [side, node] of edgeNodes) {
        const on = editing && edges.includes(side);
        node.style.setProperty("display", on ? "block" : "none");
        if (side !== "top") column.style.setProperty(`margin-${side}`, on ? `${EDGE_PX}px` : "0");
      }
    };

    // Where the column and the shown placeholders are, sent at most once an
    // animation frame and only when it changed: after a scroll, a resize, or
    // anything above a placeholder changing its height.
    const plugins = sections.filter(([, part]) => part.plugin);
    let pending = false;
    let last = null;
    report = () => {
      if (!plugins.length || pending) return;
      pending = true;
      globalThis.requestAnimationFrame(() => {
        pending = false;
        const rects = {};
        if (!listOpen) for (const [id, part] of plugins) if (part.shown()) rects[id] = box(part.node);
        const where = box(column);
        const text = JSON.stringify([where, rects]);
        if (text === last) return;
        last = text;
        host.placeholders(where, rects);
      });
    };
    // A wheel turn over a plugin's view that its page didn't use (it can't
    // scroll that way): the host passes it here, in lines, and the column
    // scrolls, as a scrolling div does for a child that can't. A line is
    // WebKitGTK's own wheel step for a page this high (measured in 4.1: 44 px
    // at 300 px high, 62 px at 500), so both scroll alike.
    globalThis.ooliteFrameWheel = (dx, dy) => {
      const step = Math.floor(globalThis.innerHeight ** (2 / 3));
      column.scrollBy({ left: dx * step, top: dy * step, behavior: "smooth" });
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
      edges = frame.edges || [];
      bar.className = editing ? "oo-bar editing" : "oo-bar";
      drawEdges();
      const offered = frame.places || [];
      if (JSON.stringify(offered) !== JSON.stringify(places)) {
        places = offered;
        drawList();
      }
      if (!editing && listOpen) showList(false);
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
