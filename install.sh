#!/usr/bin/env bash

set -euxo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

DIST_DIR="$ROOT_DIR/dist"

if [[ "$TV_IP" == *:* ]]; then
  TV_SERIAL="$TV_IP"
else
  TV_SERIAL="$TV_IP:26101"
fi

docker run --rm -it \
  --platform linux/amd64 \
  -v "$DIST_DIR:/dist" \
  -w /dist \
  tizen-studio \
  bash -lc "
    set -euxo pipefail
    sdb connect \"$TV_SERIAL\"
    tizen install --name app.wgt --serial \"$TV_SERIAL\"
  "
