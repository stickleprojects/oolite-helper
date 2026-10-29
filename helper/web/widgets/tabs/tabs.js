// The tabs widget (#89): a tab row, the widget's own frame, over one of its
// components at a time. The model keeps the choice (ui/choose_tab, the "tabs"
// topic), so every widget agrees, and an emergency shows Keys.
"use strict";

(() => {
  // The tab to show: the model's, else the player's choice if it's one of
  // these, else the first.
  function shownTab(names, tabs) {
    return [tabs.shown, tabs.chosen].find((name) => names.includes(name)) || names[0];
  }

  Oolite.widget("tabs", {
    draw(names, state, part, dispatch) {
      const { el, button } = globalThis.OoliteDom;
      const tabs = state.tabs || {};
      const shown = shownTab(names, tabs);
      const titles = new Map((tabs.tabs || []).map((tab) => [tab.id, tab.text]));
      const row = el(
        "div",
        "tab-row",
        ...names.map((name) =>
          button(
            titles.get(name) || name,
            () => dispatch({ type: "ui/choose_tab", tab: name }),
            name === shown ? "tab active" : "tab",
          ),
        ),
      );
      return el("div", "tabs", row, part(shown));
    },
  });
})();
