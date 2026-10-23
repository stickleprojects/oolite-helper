# Building Oolite from source

To test a change to Oolite itself (for example a fix proposed upstream), build an AppImage in a container that matches upstream CI. Nothing is installed on the host.

```
git clone https://github.com/OoliteProject/oolite.git ~/src/oolite    # full clone: the version number needs the tags
git -C ~/src/oolite checkout 1.93.1-229                               # or any branch or tag
# ...edit the source...
scripts/build-oolite-appimage.sh ~/src/oolite                         # flavour: deployment (default), test or dev
```

The AppImage is written to `~/src/oolite/build/`. Run it like the release AppImage; it creates `GameData/` next to itself.

- [docker/oolite-build/Dockerfile](../docker/oolite-build/Dockerfile) builds the `oolite-builddeps` image: Arch Linux with the packages, GNUstep and Mozilla JS library that upstream's `ShellScripts/Linux` scripts install. The first build takes a few minutes; after that an AppImage takes about 2.
- `OOLITE_REF` (default `1.93.1-229`) picks which upstream revision's dependency scripts the image uses. Set it when building a revision whose `ShellScripts/Linux` has changed.
- `mk.sh pkg-appimage` reuses an existing `build/appimage/oolite.AppDir`, which would package the previous binary. The script removes it before packaging.
- Packaging needs FUSE, so the container gets `SYS_ADMIN` and `/dev/fuse`, as in upstream CI.

This was set up to investigate OoliteProject/oolite#773.
