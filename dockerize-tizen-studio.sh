#!/usr/bin/env bash

set -euo pipefail

set -a
source ./.env
set +a

read -r -a REQUIRED_SDK_NAMES <<< "$REQUIRED_SDK_NAMES_STR"

mkdir -p "$TIZEN_DIR"

cat <<EOF

========================================
  Dockerize Tizen Studio

  Base image:           $BASE_IMAGE
  Image:                $IMAGE_NAME
  Container:            $CONTAINER_NAME
  Tizen dir (on host):  $TIZEN_DIR
  Tizen Studio version: $TIZEN_VERSION
  Required SDKs:        ${REQUIRED_SDK_NAMES[@]}
========================================

EOF

cat > "$TIZEN_DIR/Dockerfile" <<EOF
FROM $BASE_IMAGE

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV PATH="\$PATH:/home/tizen/tizen-studio/tools:/home/tizen/tizen-studio/tools/ide/bin"

RUN apt-get update && \
    apt-get install -y \
        wget \
        unzip \
        ca-certificates \
        default-jdk \
        libwebkit2gtk-4.0-37 \
        libgtk-3-0 \
        libxss1 \
        libgconf-2-4 \
        libnss3 \
        libasound2 \
        xauth && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash tizen && \
    echo "tizen ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER tizen
WORKDIR /home/tizen

RUN mkdir -p /home/tizen/tizen-installer && \
    cd /home/tizen/tizen-installer && \
    wget "https://download.tizen.org/sdk/Installer/tizen-studio_$TIZEN_VERSION/web-cli_Tizen_Studio_${TIZEN_VERSION}_ubuntu-64.bin" && \
    chmod +x "web-cli_Tizen_Studio_${TIZEN_VERSION}_ubuntu-64.bin"

RUN echo "Installing Tizen Studio..." && \
    "/home/tizen/tizen-installer/web-cli_Tizen_Studio_${TIZEN_VERSION}_ubuntu-64.bin" \
        --accept-license "Y" \
        --no-java-check \
        /home/tizen/tizen-studio && \
    echo "Tizen Studio installed."
EOF

for sdk_name in "${REQUIRED_SDK_NAMES[@]}"; do
    cat >> "$TIZEN_DIR/Dockerfile" <<EOF

RUN echo "Installing Tizen Studio $sdk_name extension..." && \
    /home/tizen/tizen-studio/package-manager/package-manager-cli.bin install "$sdk_name" && \
    echo "Tizen Studio $sdk_name extension installed."
EOF
done

cat >> "$TIZEN_DIR/Dockerfile" <<EOF

RUN echo "All required Tizen Studio extensions installed."

WORKDIR /home/tizen/project

CMD ["/bin/bash"]
EOF

echo ">>> Building Docker image $IMAGE_NAME..."

cd "$TIZEN_DIR"
docker build -t "$IMAGE_NAME" .

echo ">>> Creating container $CONTAINER_NAME (if not exists)..."

# If container exists, do nothing
if ! docker ps -a --format '{{.Names}}' | grep -q "^$CONTAINER_NAME\$"; then
  # X11 forwarding for any GUI tools if you run them
  xhost +local:docker >/dev/null 2>&1 || true

  docker create -it \
    --name "$CONTAINER_NAME" \
    -e DISPLAY="$DISPLAY" \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v "$TIZEN_DIR/project:/home/tizen/project" \
    "$IMAGE_NAME"
fi

cat <<EOF

========================================
  Done.

  To start Tizen Studio CLI shell:

    docker start $CONTAINER_NAME
    docker exec -it $CONTAINER_NAME /bin/bash

  Inside container, you can run:

    # Check Tizen CLI version
    tizen version

    # Build your web app (assuming files in /home/tizen/project)
    tizen build-web

    # Package (after creating a certificate with certificate-manager)
    tizen package -t wgt -s <your_certificate_name>

  Your shared project folder on host:

    $TIZEN_DIR/project

  Put your Tizen TV project (config.xml, index.html, etc.) in that folder.
========================================

EOF
