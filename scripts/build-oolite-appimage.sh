#!/bin/bash
# Build an Oolite AppImage from source in a container that matches upstream CI.
#
# Usage: scripts/build-oolite-appimage.sh <oolite-source-dir> [flavour]
#   oolite-source-dir  a full git clone of OoliteProject/oolite (history and
#                      tags are needed for the version number); local edits
#                      in it are built as they are
#   flavour            deployment (default), test or dev
#
# The AppImage is written to <oolite-source-dir>/build/. The first run builds
# the oolite-builddeps image (a few minutes); later builds take about 2.
# Set OOLITE_REF to build the image from another upstream revision's scripts.
#
# Packaging needs FUSE, so the container gets SYS_ADMIN and /dev/fuse, the
# same options upstream CI uses.
set -euo pipefail

src=${1:?usage: $0 <oolite-source-dir> [deployment|test|dev]}
flavour=${2:-deployment}
src=$(realpath "$src")
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
image=oolite-builddeps:${OOLITE_REF:-1.93.1-229}

if [[ ! -d "$src/.git" || ! -x "$src/mk.sh" ]]; then
    echo "Not an Oolite git checkout: $src" >&2
    exit 1
fi

if ! docker image inspect "$image" >/dev/null 2>&1; then
    docker build --build-arg "OOLITE_REF=${OOLITE_REF:-1.93.1-229}" \
        -t "$image" "$here/../docker/oolite-build"
fi

# mk.sh pkg-appimage reuses an existing build/appimage/oolite.AppDir, which
# would package the previous binary, so it is removed before packaging.
docker run --rm \
    --cap-add SYS_ADMIN --device /dev/fuse --security-opt apparmor:unconfined \
    -v "$src:/src" "$image" \
    bash -c "set -e
        ./mk.sh build $flavour
        rm -rf build/appimage
        ./mk.sh pkg-appimage $flavour
        chown -R $(id -u):$(id -g) /src"

ls -l "$src"/build/Oolite-*-"$flavour"-x86_64.AppImage
