---
name: refine-issue
description: Refine a rough oolite-helper issue into a buildable spec. Reads the issue and the code, checks game facts in the Oolite 1.92.1 source, asks Kieron only what's his to decide, and writes the spec into the issue body. Use when Kieron types /refine-issue [N | check], asks to refine an issue or which issues need refining, or an issue has the "needs refinement" label.
---
# Refine an issue

A rough issue holds Kieron's idea in a few lines. A refined one is a spec that someone can build in small, verified steps without guessing (examples: #70, #71, #89). Refining is design work only: don't write code or open a branch.

## Check: which issues need refining
With `check` (or when Kieron asks which issues need refining), only report; change nothing:
1. List the open issues labelled `needs refinement`: `gh issue list --label "needs refinement" --json number,title,labels,body`.
2. For each one, give a line with its number and title, what it's missing (no Goal, no Steps, open questions, unchecked game facts, stale terms or decisions), and whether it's blocked (`on hold`, or waiting on another issue).
3. Flag the open issues **without** the label that look rough: a body of a few lines, no `## Goal` or `## Steps`, or "to be refined" in the text. Suggest adding the label rather than adding it.
4. Recommend which one to refine first, and why.

## 1. Pick the issue
With a number, refine that issue. Without one, list the open issues labelled `needs refinement` (`gh issue list --label "needs refinement"`) and ask which one to do. Do one issue at a time.

## 2. Read
- The issue, its comments, and every issue or PR it mentions (`gh issue view N --comments`).
- The terms in [docs/architecture.md](../../../docs/architecture.md) ("Terms"), and use exactly those words: component, widget, dock, layout, panel. Don't use "preset" or "builtin".
- Any notes in memory that name the issue.

## 3. Find what already exists
Prefer reusing to adding. Check:
- **Add-on messages:** what [oxp/CtxKeys.oxp/Config/script.js](../../../oxp/CtxKeys.oxp/Config/script.js) already sends (`this._emit`), and its event handlers.
- **Model and topics:** `helper/state.py`, `helper/model.py`, and `plugin_api.TOPICS`/`ACTIONS`.
- **Components and widgets:** `helper/web/components/`, `helper/web/widgets/`, and their `states.json` files.
- **Keys:** `helper/contexts.py`. Key names always come from `keyconfig2.plist` and the player's overrides, never from memory.

## 4. Check game facts in the source
Every claim about the game (events, properties, screens, key actions, equipment, ship data) is checked in the Oolite **1.92.1** source, which is cloned at `/mnt/NTFSData/code/oolite`. Read the tag, not the working branch:

```bash
git -C /mnt/NTFSData/code/oolite grep -n "playerBoughtCargo" 1.92.1 -- src Resources
git -C /mnt/NTFSData/code/oolite show 1.92.1:Resources/Config/equipment.plist
```

Cite the file and function in the spec, e.g. "`shipDied` fires from `getDestroyedBy:` (`src/Core/Entities/PlayerEntity.m`)". If a fact can't be checked, list it under "To check" rather than guessing. When something the feature needs isn't exposed to scripts, say so, and suggest a change in Kieron's fork (`stickleprojects/oolite`) as an option.

## 5. Ask Kieron
Collect only the decisions that are his: what to show, where it shows, what matters most, and what to leave out. Don't ask what the code or the source can answer. Ask with AskUserQuestion, at most 4 questions per round, with the recommended option first and marked "(Recommended)". Each question must make sense on its own. Go round again only if an answer opens a new question.

## 6. Write the spec
Draft it in the scratchpad, then show Kieron a short summary (the goal, the steps, and anything you recommend) before replacing the body. Keep his original words in the first section. Use the sections that apply, in this order:

- **First refinement:** the old body goes under `## Idea (Kieron)` word for word, but drop its own top heading if it has one (e.g. `## Idea`), so there aren't two Idea headings. Turn its other `##` headings into `###`.
- **Refining again** (the body already starts with `## Idea (Kieron)`): keep that section as it is, and add Kieron's new words below it, each with its date, plus the decisions taken. Rewrite the other sections in place rather than nesting the old spec. Mark finished steps ✅ and keep them.

```markdown
## Idea (Kieron)
<the original body, word for word, without its own top heading>
<later: "YYYY-MM-DD, Kieron: ..." quotes and the decisions taken>

## Goal
<what the player gets, in 2 or 3 sentences>

## Where it shows
<widget or component, dock or screen, which game contexts; a small table if there are several>

## Game facts (1.92.1)
<each fact with its source citation>

## Design
<add-on messages (type and fields), model topic, plugin_api topic and actions, component or widget folders, config>

## Steps
1. <PR-sized, each verified on its own; say which needs Kieron to play-test>

## Tests
<one behaviour per test, beside the component>

## Not in this issue
<what's deliberately left out, with links to issues that cover it>

## To check
<facts still unverified, if any>
```

Write in plain, short English. Name the files and functions to change. Keep it as long as the feature needs and no longer.

## 7. Update the issue
- Replace the body with `gh api -X PATCH repos/stickleprojects/oolite-helper/issues/N -F body=@<file>`. `gh issue edit --body-file` can fail on this repo with the "Projects (classic)" error.
- Remove `needs refinement`. There's no `refined` label: an open issue without `needs refinement` counts as refined, so only the exceptions are tagged. If questions are still open, keep `needs refinement` and list them under "To check".
- If a refined issue's spec later needs reworking (a big edit, or new open questions), add `needs refinement` back.
- If the issue is really several features, propose a split and ask before creating the new issues.
- Give Kieron the link and a 2-line summary.
