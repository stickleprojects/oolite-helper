"use strict";

// What the badge says when there's no clearance to show: docked and far from
// any station both send no badge, so the context tells them apart.
function clearanceEmpty(context) {
  if (context === "docked") return "Docked";
  if (context === "waiting for game" || context === "game not running") return "Waiting for the game";
  return "Away from stations";
}

Oolite.component("clearance", {
  render(state) {
    const badge = state.clearance;
    if (!badge) return OoliteDom.el("span", "empty", clearanceEmpty(state.context));
    const className = `badge ${badge.colour}${badge.flashes ? " flashes" : ""}`;
    return OoliteDom.el("span", className, `  ${badge.text}  `);
  },
});
