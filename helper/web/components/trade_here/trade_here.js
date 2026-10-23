"use strict";

Oolite.component("trade_here", {
  render(state) {
    const { el } = OoliteDom;
    const panel = el("section", "panel trade-here", el("h2", "", "Trade here"));
    const groups = state.market_advice && state.market_advice.length
      ? state.market_advice
      : [{ heading: "Dock at a station for trade advice.", lines: [] }];
    for (const group of groups) {
      panel.append(el("h3", "", group.heading));
      for (const line of group.lines) panel.append(el("p", line.warning ? "warning" : "", line.text));
    }
    return panel;
  },
});
