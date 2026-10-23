"use strict";

// One commodity: every system in range to sell at, a quantity picker, the
// cost and profit, and the steps (keys) to do it.
function tradeDetail(detail) {
  const { el, button } = OoliteDom;
  const format = OoliteFormat;
  const dispatch = (action) => () => oolite.dispatch(action);
  const row = detail.row;
  const section = el("section", "panel detail");
  const here = row && row.here.price != null
    ? `here ${format.formatPrice(row.here.price, row.here.note)}, ${row.stock || 0} ${row.unit} on sale`
    : "";
  section.append(el(
    "div",
    "detail-heading",
    button("◀ All commodities", dispatch({ type: "ui/open_commodity", commodity: null })),
    el("strong", row && row.illegal ? "warning" : "", `${detail.name}${row && row.illegal ? "  illegal here" : ""}   ${here}`),
  ));

  if (!detail.offers.length) {
    section.append(el("p", "empty", "No prices for systems in fuel range yet."));
  } else {
    const headings = ["Sell at", "Price", "Margin", "Distance", "Economy", "Government"];
    const body = el("tbody", "");
    for (const offer of detail.offers) {
      const chosen = detail.chosen != null && offer.system_id === detail.chosen;
      const margin = row && row.here.price != null ? offer.price - row.here.price : null;
      const plain = chosen ? "accent" : ""; // the whole chosen row is accent
      const cells = [
        [`${chosen ? "▶ " : "  "}${offer.name}${offer.illegal ? "  illegal" : ""}`, offer.illegal ? "warning" : plain],
        [format.formatPrice(offer.price, offer.note), plain],
        [format.formatMargin(margin), margin == null ? plain : margin > 0 ? "good" : "dim"],
        [offer.distance == null ? "" : `${offer.distance.toFixed(1)} ly`, plain],
        [offer.economy_name || "?", plain],
        [`${offer.government_name || "?"}${offer.dangerous ? " ⚠" : ""}`, offer.dangerous ? "warning" : plain],
      ];
      const tr = el("tr", "clickable", ...cells.map(([text, className]) => el("td", className, text)));
      tr.addEventListener("click", dispatch({ type: "ui/choose_destination", system: offer.system_id }));
      body.append(tr);
    }
    const head = el("thead", "", el("tr", "", ...headings.map((title) => el("th", "", title))));
    section.append(el("table", "offers", head, body));
  }

  const quantity = detail.quantity;
  const most = detail.limit.most;
  const clamp = (value) => Math.max(0, Math.min(value, most));
  const picker = el("div", "picker", el("strong", "", "Buy"));
  for (const [label, value] of [
    ["−10", clamp(quantity - 10)],
    ["−1", clamp(quantity - 1)],
    [`${quantity} ${row ? row.unit : "t"}`, null],
    ["+1", clamp(quantity + 1)],
    ["+10", clamp(quantity + 10)],
    ["Max", most],
  ]) {
    const onClick = value == null ? null : dispatch({ type: "ui/change_quantity", quantity: value });
    picker.append(button(` ${label} `, onClick, value == null ? "quantity current" : "quantity"));
  }
  picker.append(el("span", "limit", `most ${most} (${detail.limit.text})`));
  section.append(picker);

  if (row && row.here.price != null) {
    const summary = [`Cost ${(quantity * row.here.price / 10).toFixed(1)} cr`, `cargo ${quantity} ${row.unit}`];
    const chosen = detail.offers.find((offer) => detail.chosen != null && offer.system_id === detail.chosen)
      || detail.offers[0];
    if (chosen) {
      const profit = quantity * (chosen.price - row.here.price) / 10;
      summary.push(`profit at ${chosen.name} ${profit >= 0 ? "+" : ""}${profit.toFixed(1)} cr`);
    }
    section.append(el("p", "summary", summary.join("    ")));
  }
  detail.steps.forEach((step, index) => section.append(el("p", "step", `${index + 1}. ${step}`)));
  return section;
}
globalThis.OoliteTradeDetail = tradeDetail;
