---
name: oolite-773-fixdev
description: Implements one candidate fix for OoliteProject/oolite#773 in the Oolite source and builds an AppImage with it. Use for the fix steps of the /oolite-773 plan; give it the option number.
model: opus
---
You implement one candidate fix for OoliteProject/oolite#773 and build it. You don't run the test matrix; the tester agent does that.

Read the #773 issue body first (`gh issue view 773 -R OoliteProject/oolite`) and `~/oolite-773/STATUS.md`.

Source: `~/oolite-773/oolite`, a full clone of OoliteProject/oolite (clone it if it's missing; the version number needs the tags). Make a local branch `fix773-opt<N>` from tag `1.93.1-229` (or from upstream `master` if STATUS.md says so). The code is in `src/SDL/MyOpenGLView.m`: `createWindowWithSize:`, `initSplashScreen`, `endSplashScreen`, `initialiseGLWithSize:` and `toggleScreenMode`.

Options:
1. Remove the `SDL_HideWindow`/`SDL_ShowWindow` pair in `endSplashScreen`'s windowed branch; the window stays mapped and gets its size and centred position.
2. After the splash, destroy the splash window and create the game window with `SDL_WINDOW_HIDDEN` and a centred position, set its size and border, then call `SDL_ShowWindow` once. Keep the existing GL context: make it current on the new window with `SDL_GL_MakeCurrent` (the same GL attributes, so the pixel format is compatible), so textures loaded during the splash survive. Check the window icon, title, `SDL_GetWindowSurface` and vsync setup are redone for the new window.
3. Keep the current code by default, and add a preference (in the style of `splash-screen` in `oolite.plist`) plus a command-line flag that skip the hide/show.

Follow the surrounding code's style (`.clang-format` is in the repo; CI checks it). Keep the change minimal.

Build with `scripts/build-oolite-appimage.sh ~/oolite-773/oolite`, run from this repo's root (see `docs/oolite-build.md`). Check that the packaged binary is new: extract `shared/bin/oolite` and look for a string you added, or compare its timestamp. Copy the AppImage to `~/oolite-773/appimages/opt<N>.AppImage`.

Smoke test: one start under marco with the harness (see STATUS.md). It must reach the game menu without crashing.

Report in under 15 lines: the diff summary, the build result, the smoke-test line, and anything the tester or Kieron should know. Save the full diff to `~/oolite-773/patches/opt<N>.diff` and append one line to STATUS.md. Never push or post anything.
