"use strict";

function formatPrice(price, note) {
  if (price == null) return "—";
  const text = (price / 10).toFixed(1);
  return note ? `${text} (${note})` : text;
}

function formatMargin(margin) {
  if (margin == null) return "";
  const value = (margin / 10).toFixed(1);
  return margin >= 0 ? `+${value}` : value;
}

function sortRows(rows, key, descending = true) {
  const value = (row) => {
    if (key === "commodity") return row.commodity;
    if (key === "here") return row.here.price;
    if (key === "best") return row.best.price;
    if (key === "where") return row.where.distance;
    return row.margin;
  };
  const known = rows.filter((row) => value(row) != null);
  const unknown = rows.filter((row) => value(row) == null);
  known.sort((a, b) => {
    const left = value(a);
    const right = value(b);
    const order = typeof left === "string" ? left.localeCompare(right) : left - right;
    return descending ? -order : order;
  });
  return [...known, ...unknown];
}

function screenLine(screen, marketAge) {
  const label = (value, prefix) =>
    (value || "-")
      .replace(prefix, "")
      .replaceAll("_", " ")
      .toLowerCase()
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  const lines = [
    `Screen: ${label(screen.gui, "GUI_SCREEN_")}    View: ${label(screen.view, "VIEW_")}`,
  ];
  if (marketAge) lines.push(`Market prices: ${marketAge.text}`);
  return lines;
}

function detailsLines(details, screen, marketAge) {
  return [...(details.length ? [details.join("    ")] : []), ...screenLine(screen, marketAge)];
}

function chipText(name, indicator) {
  return indicator.ok
    ? `  ${name} ✓  `
    : `  ${name} ✗ ${indicator.by || ""}  `;
}

const OoliteFormat = { formatPrice, formatMargin, sortRows, screenLine, detailsLines, chipText };
globalThis.OoliteFormat = OoliteFormat;
if (typeof module !== "undefined") module.exports = OoliteFormat;
