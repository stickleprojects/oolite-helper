// The Keys tab as a plugin. Everything comes from topics; the tab chips send
// ui/choose_tab, which the helper shares with its own window.
const state = { tabs: null, key_sections: [], all_keys: [] };
let group = 0; // which group "All keys" shows: local to this page

function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

function panel(title, keys) {
  return el(
    "section",
    { className: "panel" },
    el("h2", { textContent: title }),
    ...keys.map((k) =>
      el(
        "div",
        { className: k.keys && k.available !== false ? "key" : "key unbound" },
        el("kbd", { textContent: k.keys || "—" }),
        el("span", { textContent: k.description }),
      ),
    ),
  );
}

function draw() {
  const tabs = document.getElementById("tabs");
  const panels = document.getElementById("panels");
  const shown = state.tabs ? state.tabs.shown : "keys";
  tabs.replaceChildren(
    ...(state.tabs ? state.tabs.tabs : [])
      .filter((t) => t.id !== "trade_table") // this plugin only shows keys
      .map((t) => {
        const chip = el("span", { className: t.id === shown ? "tab active" : "tab", textContent: t.text });
        chip.addEventListener("click", () => oolite.dispatch({ type: "ui/choose_tab", tab: t.id }));
        return chip;
      }),
  );
  if (shown === "all_keys") {
    const chips = el("nav", { id: "groups" });
    state.all_keys.forEach((g, i) => {
      const chip = el("span", { className: i === group ? "tab active" : "tab", textContent: g.title });
      chip.addEventListener("click", () => { group = i; draw(); });
      chips.append(chip);
    });
    const chosen = state.all_keys[group];
    panels.replaceChildren(chips, ...(chosen ? [panel(chosen.title, chosen.keys)] : []));
  } else {
    panels.replaceChildren(...state.key_sections.map((s) => panel(s.title, s.keys)));
  }
}

for (const topic of Object.keys(state)) {
  oolite.on(topic, (value) => { state[topic] = value; draw(); });
}
