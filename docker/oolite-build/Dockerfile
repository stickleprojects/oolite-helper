# Build environment for Oolite AppImages, matching upstream CI
# (OoliteProject/oolite .github/workflows/build-all.yaml, job build-linux).
#
# The image holds the build dependencies only: system packages, GNUstep,
# the Mozilla JS library and gitversion. The Oolite source is mounted at
# /src when a build runs; see scripts/build-oolite-appimage.sh.
#
# OOLITE_REF picks which upstream revision's dependency scripts to use.
# Rebuild the image when you move to a ref whose ShellScripts/Linux changed.

FROM archlinux:latest

ARG OOLITE_REF=1.93.1-229

RUN pacman -Syu --noconfirm \
 && pacman -S --noconfirm --needed git \
 && pacman -Scc --noconfirm

RUN git clone --filter=blob:none https://github.com/OoliteProject/oolite.git /deps-src \
 && git -C /deps-src checkout "$OOLITE_REF" \
 && cd /deps-src \
 && ShellScripts/Linux/install_packages_root.sh --core+appimage \
 && ShellScripts/Linux/build_gnustep.sh system \
 && ShellScripts/Linux/install_mozilla_js.sh system \
 && echo /usr/local/lib >> /etc/ld.so.conf \
 && ldconfig \
 && rm -rf /deps-src \
 && pacman -Scc --noconfirm

RUN git config --system --add safe.directory /src

WORKDIR /src
