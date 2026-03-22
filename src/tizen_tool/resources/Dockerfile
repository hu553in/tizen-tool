FROM ubuntu:22.04

ARG TIZEN_VERSION
ARG REQUIRED_PACKAGES_JSON
ARG TIZEN_INSTALLER_SHA256
ARG BUILD_CONTEXT_FINGERPRINT

ENV REQUIRED_PACKAGES_JSON=$REQUIRED_PACKAGES_JSON
ENV TIZEN_INSTALLER_SHA256=$TIZEN_INSTALLER_SHA256

LABEL com.github.hu553in.tizen.tool.version="$TIZEN_VERSION"
LABEL com.github.hu553in.tizen.tool.required-packages="$REQUIRED_PACKAGES_JSON"
LABEL com.github.hu553in.tizen.tool.installer-sha256="$TIZEN_INSTALLER_SHA256"
LABEL com.github.hu553in.tizen.tool.build-context-fingerprint="$BUILD_CONTEXT_FINGERPRINT"

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
ENV PATH="$PATH:/home/tizen/tizen-studio/tools:/home/tizen/tizen-studio/tools/ide/bin"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    python3 \
    unzip && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash tizen
USER tizen

COPY --chown=tizen:tizen --chmod=755 install_tizen_studio.py /home/tizen/install_tizen_studio.py
COPY --chown=tizen:tizen installer.bin /home/tizen/installer.bin
RUN python3 -u /home/tizen/install_tizen_studio.py
RUN tizen version && command -v sdb

WORKDIR /home/tizen/project
CMD ["/bin/bash"]
