// The helper's built-in widget views as one page (#50). _oolite/widget.js says
// which views this window shows: OOLITE_WIDGET = {views: [...], width: px or null}.
// Each view draws nothing when it has nothing to show; with every view empty
// the widget hides itself, like the Tk widgets.
"use strict";

const widget = globalThis.OOLITE_WIDGET || { views: ["clearance", "drive"], width: null };
const state = { drive: null, clearance: null, market_advice: null };

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function chipText(name, indicator) {
  return indicator.ok ? `  ${name} ✓  ` : `  ${name} ✗ ${indicator.by || ""}  `;
}

const VIEWS = {
  // TORUS ✓/✗ and JUMP ✓/✗ while flying.
  drive() {
    if (!state.drive) return null;
    const chips = el("div", "chips");
    for (const name of ["torus", "jump"]) {
      const lamp = state.drive[name];
      if (lamp) chips.append(el("span", `chip ${lamp.ok ? "good" : "bad"}`, chipText(name.toUpperCase(), lamp)));
    }
    return chips.childElementCount ? chips : null;
  },
  // Docking clearance near a station; "timing out" flashes.
  clearance() {
    const badge = state.clearance;
    if (!badge) return null;
    return el("span", `chip ${badge.colour}${badge.flashes ? " flashes" : ""}`, `  ${badge.text}  `);
  },
  // Hold, last market and best buys; a hint until you dock somewhere.
  trade_here() {
    const panel = el("section", "advice");
    panel.append(el("h2", "", "TRADE HERE"));
    const groups = state.market_advice && state.market_advice.length
      ? state.market_advice
      : [{ heading: "Dock at a station for trade advice.", lines: [] }];
    for (const group of groups) {
      panel.append(el("h3", "", group.heading));
      for (const line of group.lines) panel.append(el("p", line.warning ? "warning" : "", line.text));
    }
    return panel;
  },
};

const root = document.getElementById("root");
let shown = null;
let size = null;

function draw() {
  const parts = widget.views.map((name) => VIEWS[name] && VIEWS[name]()).filter(Boolean);
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

if (widget.width) {
  // A width set in config.toml: Trade here fills it, as in the Tk widget.
  document.documentElement.style.setProperty("--advice-width", `calc(${widget.width}px - 12px * var(--oo-scale))`);
}
for (const topic of Object.keys(state)) {
  oolite.on(topic, (value) => {
    state[topic] = value;
    draw();
  });
}
draw();
