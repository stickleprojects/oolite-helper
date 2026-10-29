// Small DOM helpers shared by the components (#82).
"use strict";

// el("span", "chip good", "TORUS ✓") or el("div", "row", childA, childB):
// text when the third argument is a string, otherwise child nodes.
function el(tag, className, ...content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content.length === 1 && typeof content[0] === "string") node.textContent = content[0];
  else node.append(...content.filter((child) => child != null));
  return node;
}

// A button that runs onClick; null onClick makes a plain, unclickable one.
function button(label, onClick, className = "") {
  const node = el("button", className, label);
  if (onClick) node.addEventListener("click", onClick);
  return node;
}

const OoliteDom = { el, button };
globalThis.OoliteDom = OoliteDom;
