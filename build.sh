#!/usr/bin/env bash

set -euxo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

INSTALLER_FILE_NAME="web-cli_Tizen_SDK_${TIZEN_VERSION}_ubuntu-64.bin"
INSTALLER_FILE="$ROOT_DIR/installer/$INSTALLER_FILE_NAME"

if [[ ! -f "$INSTALLER_FILE" ]]; then
  mkdir -p "$ROOT_DIR/installer"
  wget "https://download.tizen.org/sdk/Installer/tizen-sdk_$TIZEN_VERSION/$INSTALLER_FILE_NAME" -O "$INSTALLER_FILE"
fi

chmod +x "$INSTALLER_FILE"

docker build -t tizen-studio \
  --platform linux/amd64 \
  --build-arg TIZEN_VERSION="$TIZEN_VERSION" \
  --build-arg REQUIRED_SDK_NAMES_SPACE_SEPARATED="$REQUIRED_SDK_NAMES_SPACE_SEPARATED" \
  "$ROOT_DIR"

rm -rf "$ROOT_DIR/dist" "$ROOT_DIR/package"
mkdir -p "$ROOT_DIR/dist"
mkdir -p "$ROOT_DIR/package"

rsync -a \
  --delete \
  --exclude-from="$ROOT_DIR/.buildignore" \
  "$ROOT_DIR/" "$ROOT_DIR/package/"

docker run --rm -it \
  --platform linux/amd64 \
  -v "$ROOT_DIR:/workspace" \
  -v "$PROFILES_DIR:/profiles" \
  tizen-studio \
  bash -lc "
    set -euxo pipefail
    trap 'cat /home/tizen/tizen-studio-data/cli/logs/cli.log 2>/dev/null || true' ERR

    tizen cli-config profiles.path=/profiles/profiles.xml

    tizen build-web -- /workspace/package -out /workspace/package/build
    tizen package --type wgt --sign \"$PROFILE\" -- /workspace/package/build
  "

mv "$ROOT_DIR"/package/build/*.wgt "$ROOT_DIR/dist/app.wgt"
rm -rf "$ROOT_DIR"/package
