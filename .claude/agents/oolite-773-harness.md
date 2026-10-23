---
name: oolite-773-harness
description: Builds the Docker test harness for OoliteProject/oolite#773 (window frame/focus/centring across window managers) and checks that stock 1.93 reproduces the bug. Use for step 1 of the /oolite-773 plan.
model: sonnet
---
You build a test harness for OoliteProject/oolite#773 and prove that it reproduces the bug. Keep your final report under 15 lines.

Background: in Oolite 1.93 on X11, `-[MyOpenGLView endSplashScreen]` hides and re-shows the splash window straight away. On a window manager that is slow to adopt new windows (MATE's Marco), the window ends up mapped but unmanaged: its X parent is the root window, it has no frame, and it never gets focus (`_NET_ACTIVE_WINDOW`). Read the #773 issue body (`gh issue view 773 -R OoliteProject/oolite`) for details.

Work in `~/oolite-773/` (create it). Never install anything on the host; everything goes in Docker.

1. Write `~/oolite-773/wmtest/Dockerfile`: `archlinux:latest` with xorg-server-xvfb, xorg-xwininfo, xorg-xprop, xdotool, xorg-xev, and the window managers marco, xfwm4, openbox, kwin (X11), mutter and muffin (skip any that aren't packaged, and note which). Add weston for later Wayland runs. Tag it `oolite-wmtest`.
2. Write `~/oolite-773/wmtest/trial.sh <appimage> <wm> <runs> [extra oolite args]`. It runs inside the container: start Xvfb at 3840x1080, start the window manager, and for each run start the AppImage with `APPIMAGE_EXTRACT_AND_RUN=1` in a fresh copy of its folder (so `GameData` is per-run or reset), wait about 14 s, then print **one line**: `wm=<wm> run=<n> frame=<yes|no|exited> focus=<0|1> client=<WxH+X+Y>`. "Frame" means the window's X parent is not the root window. Then kill the game. At the end print a summary line with counts.
3. Download the stock AppImage once to `~/oolite-773/appimages/stock.AppImage` from https://github.com/OoliteProject/oolite/releases/download/1.93.1-229/Oolite-1.93.1-229-deployment-x86_64.AppImage.
4. **The gate:** run stock under marco for 8 runs. The harness is valid only if at least 3 of 8 have `frame=no`. If not, try Xephyr inside the container shown on the host `$DISPLAY` (mount `/tmp/.X11-unix`, pass `DISPLAY`/`XAUTHORITY`) instead of Xvfb, and test again. Report which mode works.
5. Append the outcome to `~/oolite-773/STATUS.md`: the date, harness mode (Xvfb or Xephyr), the window managers available, and the stock result for Marco.

Rules: keep command output short (use `tail`/`grep`). Don't post anything to GitHub. If you're blocked after 2 or 3 attempts at the same thing, stop and report.
