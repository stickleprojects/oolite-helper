"use strict";

Oolite.component("status", {
  render(state) {
    const text = state.status && state.status.text;
    return text ? OoliteDom.el("footer", "status", text) : null;
  },
});
