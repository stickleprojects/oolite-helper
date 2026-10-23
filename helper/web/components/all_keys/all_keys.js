"use strict";

// Uses the key panel from keys.js: component.toml says it needs "keys", so
// the helper loads that component's files too.
let allKeysGroup = 0; // the group shown: local to this component

Oolite.component("all_keys", {
  render(state, refresh) {
    const { el, button } = OoliteDom;
    const groups = state.all_keys || [];
    if (!groups.length) return null;
    const chips = el("nav", "groups");
    groups.forEach((entry, index) =>
      chips.append(
        button(entry.title, () => {
          allKeysGroup = index;
          refresh();
        }, index === allKeysGroup ? "tab active" : "tab"),
      ),
    );
    const chosen = groups[allKeysGroup] || groups[0];
    return el("div", "all-keys", chips, OoliteKeyPanel(chosen.title, chosen.keys));
  },
});
