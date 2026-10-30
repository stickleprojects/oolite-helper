"use strict";

// Errors, warnings and notices only; the raw last message is last_message's.
Oolite.component("status", {
  render(state) {
    const status = state.status;
    if (!status || !status.text || status.kind === "message") return OoliteDom.el("p", "empty", "No problems");
    return OoliteDom.el("footer", `status ${status.kind}`, status.text);
  },
});
