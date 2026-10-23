"use strict";

Oolite.component("clearance", {
  render(state) {
    const badge = state.clearance;
    if (!badge) return null;
    const className = `badge ${badge.colour}${badge.flashes ? " flashes" : ""}`;
    return OoliteDom.el("span", className, `  ${badge.text}  `);
  },
});
