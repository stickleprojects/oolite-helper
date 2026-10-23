"use strict";

// A key panel: a title, then each key and what it does. all_keys uses it too.
function keyPanel(title, keys) {
  const { el } = OoliteDom;
  return el(
    "section",
    "panel keys",
    el("h2", "", title),
    ...keys.map((key) =>
      el(
        "div",
        key.keys && key.available !== false ? "key" : "key unbound",
        el("kbd", "", key.keys || "—"),
        el("span", "", key.description),
      ),
    ),
  );
}
globalThis.OoliteKeyPanel = keyPanel;

Oolite.component("keys", {
  render(state) {
    const sections = state.key_sections || [];
    if (!sections.length) return null;
    return OoliteDom.el("div", "key-grid", ...sections.map((s) => keyPanel(s.title, s.keys)));
  },
});
