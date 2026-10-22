"use strict";

const state = {
  context: "waiting for game",
  location: null,
  screen: {},
  details: [],
  drive: null,
  clearance: null,
  tip: [],
  key_sections: [],
  all_keys: [],
  tabs: null,
  selection: null, // subscribed like the rest: every key here is a topic
  market_age: null,
  trade_rows: [],
  trade_detail: null,
  market_advice: [],
  status: null,
};
let group = 0;
let sort = ["margin", true];

function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

function text(value) {
  return document.createTextNode(value);
}

function setClass(node, className) {
  node.className = className;
  return node;
}

function drawHeader() {
  const heading = document.getElementById("context");
  heading.textContent = state.context.toUpperCase();
  heading.className = ["red alert", "ship destroyed"].includes(state.context) ? "urgent" : "";

  const location = state.location || {};
  const name = location.system || "";
  const destination = location.reached_target
    ? "  ✓ your jump target"
    : location.aimed_at
      ? `  (aimed for ${location.aimed_at})`
      : "";
  const where = document.getElementById("location");
  where.textContent = name + destination;
  where.className = location.reached_target ? "reached" : location.aimed_at ? "aimed" : "";

  const details = state.details.map((item) => item.text);
  document.getElementById("details").textContent = LaptopFormat.detailsLines(
    details.filter(Boolean),
    state.screen || {},
    state.market_age,
  ).join("\n");
}

function drawTabs() {
  const tabs = document.getElementById("tab-list");
  const indicators = document.getElementById("indicators");
  const shown = state.tabs ? state.tabs.shown : "keys";
  tabs.replaceChildren(
    ...(state.tabs ? state.tabs.tabs : []).map((tab) => {
      const chip = setClass(
        el("button", { textContent: `  ${tab.text}  ` }),
        tab.id === shown ? "tab active" : "tab",
      );
      chip.addEventListener("click", () =>
        oolite.dispatch({ type: "ui/choose_tab", tab: tab.id }),
      );
      return chip;
    }),
  );

  const chips = [];
  if (state.clearance) {
    const badge = state.clearance;
    const chip = setClass(
      el("span", { textContent: `  ${badge.text}  ` }),
      `indicator clearance ${badge.colour}${badge.flashes ? " flashes" : ""}`,
    );
    chips.push(chip);
  }
  for (const name of ["torus", "jump"]) {
    const indicator = state.drive && state.drive[name];
    if (!indicator) continue;
    chips.push(
      setClass(
        el("span", { textContent: LaptopFormat.chipText(name.toUpperCase(), indicator) }),
        `indicator ${indicator.ok ? "good" : "bad"}`,
      ),
    );
  }
  indicators.replaceChildren(...chips);
}

function panel(title, keys) {
  return el(
    "section",
    { className: "panel keys" },
    el("h2", { textContent: title }),
    ...keys.map((key) =>
      el(
        "div",
        { className: key.keys ? "key" : "key unbound" },
        el("kbd", { textContent: key.keys || "—" }),
        el("span", { textContent: key.description }),
      ),
    ),
  );
}

function drawKeys(body, shown) {
  if (shown === "all") {
    const chips = el("nav", { id: "groups" });
    state.all_keys.forEach((entry, index) => {
      const chip = setClass(
        el("button", { textContent: entry.title }),
        index === group ? "tab active" : "tab",
      );
      chip.addEventListener("click", () => {
        group = index;
        draw();
      });
      chips.append(chip);
    });
    const chosen = state.all_keys[group];
    body.append(chips);
    if (chosen) body.append(panel(chosen.title, chosen.keys));
    return;
  }
  body.append(...state.key_sections.map((section) => panel(section.title, section.keys)));
}

function drawAdvice(parent) {
  if (!state.market_advice.length) return;
  const advice = el("section", { className: "panel advice" }, el("h2", { textContent: "TRADE HERE" }));
  for (const group of state.market_advice) {
    advice.append(el("h3", { textContent: group.heading }));
    for (const line of group.lines) {
      advice.append(el("p", { className: line.warning ? "warning" : "", textContent: line.text }));
    }
  }
  parent.append(advice);
}

const columns = [
  ["commodity", "Commodity", false],
  ["here", "Here", true],
  ["best", "Best in range", true],
  ["where", "Where", false],
  ["margin", "Margin", true],
];

function drawTradeTable(parent) {
  const rows = LaptopFormat.sortRows(state.trade_rows, ...sort);
  if (!rows.length) {
    parent.append(el("p", { className: "empty", textContent: "No market data yet. Dock at a station, or wait for the systems in fuel range to arrive." }));
    return;
  }
  const table = el("table");
  const head = el("thead");
  const header = el("tr");
  for (const [key, title, highFirst] of columns) {
    const active = key === sort[0];
    const button = el("button", {
      className: active ? "sort active" : "sort",
      textContent: `${title}${active ? (sort[1] ? " ▼" : " ▲") : ""}`,
    });
    button.addEventListener("click", () => {
      sort = key === sort[0] ? [key, !sort[1]] : [key, highFirst];
      draw();
    });
    header.append(el("th", {}, button));
  }
  head.append(header);
  table.append(head);
  const body = el("tbody");
  for (const row of rows) {
    const name = `${row.name}${row.illegal ? "  illegal" : ""}`;
    const where = row.where.name
      ? `${row.where.name}${row.where.distance == null ? "" : ` ${row.where.distance.toFixed(1)} ly`}`
      : "";
    const margin = LaptopFormat.formatMargin(row.margin);
    const values = [
      [name, row.illegal ? "warning" : ""],
      [LaptopFormat.formatPrice(row.here.price, row.stock ? row.here.note : "none"), row.stock ? "" : "dim"],
      [LaptopFormat.formatPrice(row.best.price, row.best.note), ""],
      [where, ""],
      [margin, row.margin > 0 ? "good" : "dim"],
    ];
    const tr = el("tr", { className: "clickable" });
    for (const [value, className] of values) tr.append(el("td", { className, textContent: value }));
    tr.addEventListener("click", () =>
      oolite.dispatch({ type: "ui/open_commodity", commodity: row.commodity }),
    );
    body.append(tr);
  }
  table.append(body);
  parent.append(
    table,
    el("p", {
      className: "hint",
      textContent: "Click a commodity for every system in range, a quantity and the keys to press.",
    }),
  );
}

function drawTrade(parent) {
  drawAdvice(parent);
  const table = el("section", { className: "panel trade" });
  drawTradeTable(table);
  parent.append(table);
}

function button(label, action, className = "") {
  const node = el("button", { className, textContent: label });
  if (action) node.addEventListener("click", action);
  return node;
}

function drawDetail(parent, detail) {
  const section = el("section", { className: "panel detail" });
  const top = el("div", { className: "detail-heading" });
  const back = button("◀ All commodities", () =>
    oolite.dispatch({ type: "ui/open_commodity", commodity: null }),
  );
  const row = detail.row;
  const here = row && row.here.price != null
    ? `here ${LaptopFormat.formatPrice(row.here.price, row.here.note)}, ${row.stock || 0} ${row.unit} on sale`
    : "";
  top.append(
    back,
    el("strong", {
      className: row && row.illegal ? "warning" : "",
      textContent: `${detail.name}${row && row.illegal ? "  illegal here" : ""}   ${here}`,
    }),
  );
  section.append(top);

  const offers = el("table", { className: "offers" });
  if (!detail.offers.length) {
    section.append(el("p", { className: "empty", textContent: "No prices for systems in fuel range yet." }));
  } else {
    const headings = ["Sell at", "Price", "Margin", "Distance", "Economy", "Government"];
    offers.append(el("thead", {}, el("tr", {}, ...headings.map((title) => el("th", { textContent: title })))));
    const body = el("tbody");
    for (const offer of detail.offers) {
      const chosen = detail.chosen != null && offer.system_id === detail.chosen;
      const margin = row && row.here.price != null ? offer.price - row.here.price : null;
      const plain = chosen ? "accent" : ""; // the whole chosen row is accent, as in Tk
      const cells = [
        [`${chosen ? "▶ " : "  "}${offer.name}${offer.illegal ? "  illegal" : ""}`, offer.illegal ? "warning" : chosen ? "accent" : ""],
        [LaptopFormat.formatPrice(offer.price, offer.note), plain],
        [LaptopFormat.formatMargin(margin), margin == null ? plain : margin > 0 ? "good" : "dim"],
        [offer.distance == null ? "" : `${offer.distance.toFixed(1)} ly`, plain],
        [offer.economy_name || "?", plain],
        [`${offer.government_name || "?"}${offer.dangerous ? " ⚠" : ""}`, offer.dangerous ? "warning" : plain],
      ];
      const tr = el("tr", { className: "clickable" });
      for (const [value, className] of cells) tr.append(el("td", { className, textContent: value }));
      tr.addEventListener("click", () =>
        oolite.dispatch({ type: "ui/choose_destination", system: offer.system_id }),
      );
      body.append(tr);
    }
    offers.append(body);
    section.append(offers);
  }

  const quantity = detail.quantity;
  const most = detail.limit.most;
  const clamp = (value) => Math.max(0, Math.min(value, most));
  const picker = el("div", { className: "picker" }, el("strong", { textContent: "Buy" }));
  for (const [label, value] of [
    ["−10", clamp(quantity - 10)],
    ["−1", clamp(quantity - 1)],
    [`${quantity} ${row ? row.unit : "t"}`, null],
    ["+1", clamp(quantity + 1)],
    ["+10", clamp(quantity + 10)],
    ["Max", most],
  ]) {
    picker.append(button(
      ` ${label} `,
      value == null ? null : () => oolite.dispatch({ type: "ui/change_quantity", quantity: value }),
      value == null ? "quantity current" : "quantity",
    ));
  }
  picker.append(el("span", { className: "limit", textContent: `most ${most} (${detail.limit.text})` }));
  section.append(picker);

  if (row && row.here.price != null) {
    const summary = [`Cost ${(quantity * row.here.price / 10).toFixed(1)} cr`, `cargo ${quantity} ${row.unit}`];
    const chosen = detail.offers.find((offer) => detail.chosen != null && offer.system_id === detail.chosen)
      || detail.offers[0];
    if (chosen) {
      const profit = quantity * (chosen.price - row.here.price) / 10;
      summary.push(`profit at ${chosen.name} ${profit >= 0 ? "+" : ""}${profit.toFixed(1)} cr`);
    }
    section.append(el("p", { className: "summary", textContent: summary.join("    ") }));
  }
  detail.steps.forEach((step, index) =>
    section.append(el("p", { className: "step", textContent: `${index + 1}. ${step}` })),
  );
  parent.append(section);
}

function draw() {
  drawHeader();
  drawTabs();
  const tip = document.getElementById("tip");
  tip.textContent = state.tip.join("\n");
  tip.className = state.tip.length ? "has-tip" : "";
  document.getElementById("status").textContent = state.status ? state.status.text : "";
  const body = document.getElementById("body");
  body.replaceChildren();
  const shown = state.tabs ? state.tabs.shown : "keys";
  if (shown === "trade") {
    if (state.selection && state.selection.commodity && state.trade_detail) {
      drawDetail(body, state.trade_detail);
    } else {
      drawTrade(body);
    }
  } else {
    drawKeys(body, shown);
  }
}

for (const topic of Object.keys(state)) {
  oolite.on(topic, (value) => {
    state[topic] = value;
    draw();
  });
}
