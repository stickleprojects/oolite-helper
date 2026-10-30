"use strict";

// The hold (#95): goods by lot, then passengers, parcels and contracts, each
// section only when it has rows. Goods prices are decicredits; fees credits.

function holdFrom(from) {
  if (from === "scooped") return "scooped";
  return from ? from.name : "?";
}

function holdTable(title, headings, rows) {
  const { el } = OoliteDom;
  const header = el("tr", "", ...headings.map((text) => el("th", "", text)));
  return el("div", `section ${title.toLowerCase()}`,
    el("h3", "", title),
    el("table", "", el("thead", "", header), el("tbody", "", ...rows)));
}

function holdGoods(goods) {
  const { el } = OoliteDom;
  const { formatPrice, formatMargin } = OoliteFormat;
  const rows = goods.map((row) => el("tr", "",
    el("td", "", row.name),
    el("td", "num", `${row.units} ${row.unit}`),
    el("td", "num", formatPrice(row.paid_each)),
    el("td", row.from ? "" : "dim", holdFrom(row.from)),
    el("td", "num", formatPrice(row.paid)),
    el("td", "num", formatPrice(row.worth)),
    el("td", row.profit > 0 ? "num good" : row.profit < 0 ? "num warning" : "num", formatMargin(row.profit))));
  return holdTable("Goods", ["Goods", "Qty", "Paid", "From", "Total", "Worth", "Profit"], rows);
}

function holdPeople(title, people) {
  const { el } = OoliteDom;
  const rows = people.map((row) => el("tr", row.late ? "late" : "",
    el("td", "", row.name || ""),
    el("td", "", row.destinationName || ""),
    el("td", row.late ? "num warning" : "num", row.time_left_text || ""),
    el("td", "num", row.fee == null ? "" : `${row.fee} ₢`)));
  return holdTable(title, ["Name", "To", "Time left", "Fee"], rows);
}

function holdContracts(contracts) {
  const { el } = OoliteDom;
  const rows = contracts.map((row) => el("tr", row.late ? "late" : "",
    el("td", "", row.name || ""),
    el("td", "num", row.quantity == null ? "" : `${row.quantity}`),
    el("td", "", row.destinationName || ""),
    el("td", row.late ? "num warning" : "num", row.time_left_text || ""),
    el("td", "num", row.fee == null ? "" : `${row.fee} ₢`)));
  return holdTable("Contracts", ["Goods", "Qty", "To", "Time left", "Fee"], rows);
}

function holdSpace(space) {
  if (!space || space.capacity == null) return "";
  return space.used == null ? `${space.capacity} t` : `${space.used} / ${space.capacity} t`;
}

Oolite.component("hold", {
  render(state) {
    const { el } = OoliteDom;
    const hold = state.hold;
    if (!hold) {
      return el("section", "panel hold", el("h2", "", "Hold"), el("p", "empty", "Waiting for the game"));
    }
    const space = holdSpace(hold.space);
    const panel = el("section", "panel hold", el("h2", "", space ? `Hold · ${space}` : "Hold"));
    const sections = [
      hold.goods.length ? holdGoods(hold.goods) : null,
      hold.passengers.length ? holdPeople("Passengers", hold.passengers) : null,
      hold.parcels.length ? holdPeople("Parcels", hold.parcels) : null,
      hold.contracts.length ? holdContracts(hold.contracts) : null,
    ].filter(Boolean);
    if (!sections.length) {
      const free = hold.space && hold.space.capacity != null
        ? ` · ${hold.space.capacity - (hold.space.used || 0)} t free` : "";
      panel.append(el("p", "empty", `Hold empty${free}`));
      return panel;
    }
    panel.append(...sections);
    const at = hold.worth_at;
    if (hold.goods.length && at) {
      const where = [at.system, at.station].filter(Boolean).join(", ");
      panel.append(el("p", "dim worth-at", `Worth at ${where}${at.age ? `, ${at.age}` : ""}`));
    }
    return panel;
  },
});
