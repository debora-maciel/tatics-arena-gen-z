#!/usr/bin/env bash
# Bakes a high-poly source GLB into a small web asset.
# Usage: scripts/bake-model.sh <source.glb> <output.glb> [yaw-degrees]
#   yaw-degrees: optional rotation about Y applied first, for exports that do not face +Z.
set -euo pipefail

SRC="${1:?source.glb}"
OUT="${2:?output.glb}"
YAW="${3:-0}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

GT="npx --no-install gltf-transform"
STAGE="$SRC"

if [ "$YAW" != "0" ]; then
  node scripts/rotate-glb.mjs "$STAGE" "$TMP/0-rotated.glb" "$YAW"
  STAGE="$TMP/0-rotated.glb"
fi

# ~1.5M → ~40k triangles. The normal map keeps the surface detail; the sprite is ~120 CSS px tall.
$GT simplify "$STAGE" "$TMP/1-simplified.glb" --ratio 0.027 --error 0.001
$GT resize "$TMP/1-simplified.glb" "$TMP/2-resized.glb" --width 1024 --height 1024
$GT webp "$TMP/2-resized.glb" "$TMP/3-webp.glb" --quality 85
$GT prune "$TMP/3-webp.glb" "$TMP/4-pruned.glb"
mkdir -p "$(dirname "$OUT")"
$GT meshopt "$TMP/4-pruned.glb" "$OUT" --level medium

$GT inspect "$OUT" | sed -n '1,60p'
ls -la "$OUT"
