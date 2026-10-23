"use strict";

Oolite.component("heading", {
  render(state) {
    const { el } = OoliteDom;
    const context = state.context || "waiting for game";
    const urgent = ["red alert", "ship destroyed"].includes(context);
    const location = state.location || {};
    const destination = location.reached_target
      ? "  ✓ your jump target"
      : location.aimed_at
        ? `  (aimed for ${location.aimed_at})`
        : "";
    const where = location.reached_target ? "reached" : location.aimed_at ? "aimed" : "";
    const details = (state.details || []).map((item) => item.text).filter(Boolean);
    const lines = OoliteFormat.detailsLines(details, state.screen || {}, state.market_age);
    return el(
      "header",
      "heading",
      el("strong", urgent ? "context urgent" : "context", context.toUpperCase()),
      el("strong", `location ${where}`, (location.system || "") + destination),
      el("div", "details", lines.join("\n")),
    );
  },
});
