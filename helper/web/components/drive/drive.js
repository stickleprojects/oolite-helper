"use strict";

// TORUS and JUMP lamps while flying; both grey (off) when not flying.
Oolite.component("drive", {
  render(state) {
    const { el } = OoliteDom;
    if (!state.drive) {
      return el("div", "chips", el("span", "chip off", "  TORUS  "), el("span", "chip off", "  JUMP  "));
    }
    const chips = el("div", "chips");
    for (const name of ["torus", "jump"]) {
      const lamp = state.drive[name];
      if (!lamp) continue;
      const text = OoliteFormat.chipText(name.toUpperCase(), lamp);
      chips.append(el("span", `chip ${lamp.ok ? "good" : "bad"}`, text));
    }
    return chips;
  },
});
