FROM ubuntu:22.04

ARG TIZEN_VERSION
ARG REQUIRED_SDK_NAMES_SPACE_SEPARATED

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV PATH="$PATH:/home/tizen/tizen-studio/tools:/home/tizen/tizen-studio/tools/ide/bin"

RUN apt-get update && \
  apt-get install -y \
  wget \
  unzip \
  ca-certificates && \
  rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash tizen && echo "tizen ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
USER tizen

COPY --chown=tizen:tizen installer/ /home/tizen/installer/
COPY --chown=tizen:tizen --chmod=755 install-tizen-studio.sh /home/tizen/install-tizen-studio.sh
RUN /home/tizen/install-tizen-studio.sh

WORKDIR /home/tizen/project
CMD ["/bin/bash"]
