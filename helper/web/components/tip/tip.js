"use strict";

Oolite.component("tip", {
  render(state) {
    const lines = state.tip || [];
    return lines.length ? OoliteDom.el("div", "tip", lines.join("\n")) : null;
  },
});
