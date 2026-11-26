#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
# Preserve caller working directory for explicitly supplied data paths/mounts.
distro=${1:-alpine}
if [[ $# -gt 0 ]]; then shift; fi
case "$distro" in alpine|debian) ;; *) echo 'usage: bash compat/unkernel/run.sh [alpine|debian] [upstream CLI options]' >&2; exit 2;; esac
node -e 'if (+process.versions.node.split(".")[0]<24 || typeof WebAssembly.Suspending!=="function" || typeof WebAssembly.promising!=="function") { console.error("Node 24+ with JSPI required"); process.exit(2); }'
release="$root/dist/unkernel-compat"
if [[ ! -f "$release/package/dist/cli.mjs" ]]; then echo 'Run bash compat/unkernel/prepare.sh first' >&2; exit 2; fi
# Operator-supplied CLI options are explicit authority, not guest requests.
exec node "$release/package/dist/cli.mjs" --distro "$release/$distro.erofs" --mem 512 --no-net "$@"
