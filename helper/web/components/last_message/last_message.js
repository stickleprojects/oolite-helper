"use strict";

Oolite.component("last_message", {
  render(state) {
    return state.last_message ? OoliteDom.el("pre", "last-message", state.last_message) : null;
  },
});
