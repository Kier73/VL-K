#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
base=https://github.com/pithings/unkernel/releases/download/v0.2.0-261126-fd204d3
out=dist/unkernel-compat
if [[ -e "$out" ]]; then echo "Remove $out before preparing a fresh verified release" >&2; exit 2; fi
mkdir -p dist
stage=$(mktemp -d dist/.unkernel-compat.XXXXXX)
trap 'rm -rf "$stage"' EXIT
for file in unkernel.tgz alpine.erofs; do
  curl --fail --location --silent --show-error --connect-timeout 20 --max-time 300 "$base/$file" -o "$stage/$file"
done
(cd "$stage" && sha256sum -c <<'SUMS'
0970d262dab8d584a162e0daec8e9a0a7dcd5212a81bf51f2c6323d5a4eabcf1  unkernel.tgz
4253fdcaf3fe289f6a48eb565b5ca1eb43e147e6b9d9985ffbca865b3984a9a8  alpine.erofs
SUMS
)
tar -xzf "$stage/unkernel.tgz" -C "$stage"
test -f "$stage/package/dist/node.mjs"
mv "$stage" "$out"
