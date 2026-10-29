"use strict";

// The radar (#100): every blip on the scanner, with a dot in its scanner
// colour that swaps to its flash colour every 0.25 s, as the scanner does.
// The sort order is local to this component; nearest first to begin with.
let radarSort = ["distance", false];
const RADAR_LIMIT = 16; // rows; the rest are counted in "+N more"

const RADAR_COLUMNS = [
  ["name", "Blip", false],
  ["distance", "Distance", false],
  ["doing", "Doing", true],
  ["bounty", "Bounty", true],
];

function radarValue(row, key) {
  if (key === "name") return row.name;
  if (key === "doing") return row.doing;
  if (key === "bounty") return row.bounty;
  return row.distance_km;
}

function radarRows(rows, key, descending) {
  const known = rows.filter((row) => radarValue(row, key) != null);
  const unknown = rows.filter((row) => radarValue(row, key) == null);
  known.sort((a, b) => {
    const left = radarValue(a, key);
    const right = radarValue(b, key);
    const order = typeof left === "string" ? left.localeCompare(right) : left - right;
    return descending ? -order : order;
  });
  return [...known, ...unknown];
}

function radarDot(row) {
  const dot = OoliteDom.el("span", row.flash ? "dot flashing" : "dot");
  dot.style.setProperty("--blip", row.colour);
  if (row.flash) dot.style.setProperty("--blip-flash", row.flash);
  return dot;
}

Oolite.component("radar", {
  render(state, refresh) {
    const { el, button } = OoliteDom;
    const all = radarRows(state.radar || [], ...radarSort);
    if (!all.length) {
      return el("section", "panel radar", el("h2", "", "Radar"), el("p", "empty", "Nothing on the scanner"));
    }
    const header = el("tr", "");
    for (const [key, title, highFirst] of RADAR_COLUMNS) {
      const active = key === radarSort[0];
      const label = `${title}${active ? (radarSort[1] ? " ▼" : " ▲") : ""}`;
      header.append(el("th", "", button(label, () => {
        radarSort = active ? [key, !radarSort[1]] : [key, highFirst];
        refresh();
      }, active ? "sort active" : "sort")));
    }
    const body = el("tbody", "");
    for (const row of all.slice(0, RADAR_LIMIT)) {
      const name = el("td", "blip", radarDot(row), el("span", "", row.name),
        row.role ? el("span", "dim role", row.role) : null);
      const distance = row.distance_km == null ? "" : `${row.distance_km.toFixed(1)} km`;
      body.append(el("tr", row.hostile ? "hostile" : "",
        name,
        el("td", "km", distance),
        el("td", row.hostile ? "warning" : "", row.doing || ""),
        el("td", "km", row.bounty > 0 ? `${row.bounty} ₢` : "")));
    }
    const more = all.length - RADAR_LIMIT;
    const count = `${all.length} ${all.length === 1 ? "blip" : "blips"}`;
    return el("section", "panel radar",
      el("h2", "", `Radar · ${count}`),
      el("table", "", el("thead", "", header), body),
      more > 0 ? el("p", "dim more", `+${more} more`) : null);
  },
});
