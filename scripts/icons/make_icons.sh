#!/bin/sh
# Renders the app's four PNG icons from the SVG sources beside this file (macOS `qlmanage`; the
# sources are square, because qlmanage honours width and height and not the viewBox).
# Run from the repository root: `sh scripts/icons/make_icons.sh`. Change a colour in the sources and
# in web/src/app/globals.css (`--brand`, `--highlight`) together; tests/test_design_tokens.py holds
# icon.svg, the manifest and the stylesheet to the same brand colour.
set -e
out=$(mktemp -d)
for name in icon-192 icon-512 icon-maskable-512 apple-touch-icon; do
  size=512; [ "$name" = icon-192 ] && size=192; [ "$name" = apple-touch-icon ] && size=180
  qlmanage -t -s "$size" -o "$out" "scripts/icons/$name.svg" >/dev/null 2>&1
  cp "$out/$name.svg.png" "web/public/$name.png"
done
rm -rf "$out"
