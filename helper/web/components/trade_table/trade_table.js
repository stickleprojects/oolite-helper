"use strict";

// The trade table, or the open commodity's detail (trade_detail.js) while one
// is chosen. The sort order is local to this component.
let tradeSort = ["margin", true];

const TRADE_COLUMNS = [
  ["commodity", "Commodity", false],
  ["here", "Here", true],
  ["best", "Best in range", true],
  ["where", "Where", false],
  ["margin", "Margin", true],
];

function tradeTable(state, refresh) {
  const { el, button } = OoliteDom;
  const format = OoliteFormat;
  const rows = format.sortRows(state.trade_rows || [], ...tradeSort);
  const panel = el("section", "panel trade");
  if (!rows.length) {
    panel.append(el("p", "empty", "No market data yet. Dock at a station, or wait for the systems in fuel range to arrive."));
    return panel;
  }
  const header = el("tr", "");
  for (const [key, title, highFirst] of TRADE_COLUMNS) {
    const active = key === tradeSort[0];
    const label = `${title}${active ? (tradeSort[1] ? " ▼" : " ▲") : ""}`;
    header.append(el("th", "", button(label, () => {
      tradeSort = active ? [key, !tradeSort[1]] : [key, highFirst];
      refresh();
    }, active ? "sort active" : "sort")));
  }
  const body = el("tbody", "");
  for (const row of rows) {
    const where = row.where.name
      ? `${row.where.name}${row.where.distance == null ? "" : ` ${row.where.distance.toFixed(1)} ly`}`
      : "";
    const cells = [
      [`${row.name}${row.illegal ? "  illegal" : ""}`, row.illegal ? "warning" : ""],
      [format.formatPrice(row.here.price, row.stock ? row.here.note : "none"), row.stock ? "" : "dim"],
      [format.formatPrice(row.best.price, row.best.note), ""],
      [where, ""],
      [format.formatMargin(row.margin), row.margin > 0 ? "good" : "dim"],
    ];
    const tr = el("tr", "clickable", ...cells.map(([text, className]) => el("td", className, text)));
    tr.addEventListener("click", () =>
      oolite.dispatch({ type: "ui/open_commodity", commodity: row.commodity }),
    );
    body.append(tr);
  }
  panel.append(
    el("table", "", el("thead", "", header), body),
    el("p", "hint", "Click a commodity for every system in range, a quantity and the keys to press."),
  );
  return panel;
}

Oolite.component("trade_table", {
  render(state, refresh) {
    const open = state.selection && state.selection.commodity && state.trade_detail;
    return open ? OoliteTradeDetail(state.trade_detail) : tradeTable(state, refresh);
  },
});
