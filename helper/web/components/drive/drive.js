"use strict";

Oolite.component("drive", {
  render(state) {
    if (!state.drive) return null;
    const chips = OoliteDom.el("div", "chips");
    for (const name of ["torus", "jump"]) {
      const lamp = state.drive[name];
      if (!lamp) continue;
      const text = OoliteFormat.chipText(name.toUpperCase(), lamp);
      chips.append(OoliteDom.el("span", `chip ${lamp.ok ? "good" : "bad"}`, text));
    }
    return chips.childElementCount ? chips : null;
  },
});
