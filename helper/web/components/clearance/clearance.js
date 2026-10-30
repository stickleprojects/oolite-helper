"use strict";

Oolite.component("clearance", {
  render(state) {
    const badge = state.clearance;
    if (!badge) return OoliteDom.el("span", "empty", "Away from stations");
    const className = `badge ${badge.colour}${badge.flashes ? " flashes" : ""}`;
    return OoliteDom.el("span", className, `  ${badge.text}  `);
  },
});
