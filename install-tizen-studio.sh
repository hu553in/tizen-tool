#!/usr/bin/env bash

set -euxo pipefail

INSTALLER_FILE_NAME="web-cli_Tizen_SDK_${TIZEN_VERSION}_ubuntu-64.bin"
INSTALLER_FILE="/home/tizen/installer/$INSTALLER_FILE_NAME"

if [[ ! -f "$INSTALLER_FILE" ]]; then
  mkdir -p /home/tizen/installer
  wget "https://download.tizen.org/sdk/Installer/tizen-sdk_$TIZEN_VERSION/$INSTALLER_FILE_NAME" -O "$INSTALLER_FILE"
fi

chmod +x "$INSTALLER_FILE"

"$INSTALLER_FILE" \
  --accept-license "Y" \
  --no-java-check \
  /home/tizen/tizen-studio

read -r -a REQUIRED_SDK_NAMES <<<"$REQUIRED_SDK_NAMES_SPACE_SEPARATED"

for sdk in "${REQUIRED_SDK_NAMES[@]}"; do
  /home/tizen/tizen-studio/package-manager/package-manager-cli.bin install "$sdk"
done
