ARG BUILD_FROM=ghcr.io/hassio-addons/base:15.0.2
# hadolint ignore=DL3006
FROM ${BUILD_FROM}


## Set environment variables
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Using Chromium, Firefox not available on Alpine Linux

# Might benefit from `mesa-dri-swrast` module

# hadolint ignore=DL3018
RUN \
    apk add --no-cache \
        git \
        py-urllib3 \
        py3-colorama \
        mesa-dev \
        xvfb \
        py3-pip \
        xorg-server-xephyr \
        chromium-chromedriver \
        chromium \
        py3-aiohttp \
        py3-openssl \
        py3-pysocks \
        py3-wsproto \
        py3-requests \
        py3-sniffio \
        py3-async_generator \
        py3-sortedcontainers \
        py3-attrs \
        py3-outcome \
        py3-trio \
        py3-paho-mqtt \
  && pip install --no-cache-dir \
        'urllib3>=1.24.2' \
        'colorama>=0.3.7' \
        'selenium>=3.14.1' \
        'PyVirtualDisplay>=0.2.4' \
        'requests>=2.23.0'

#
#  && addgroup -g 1000 docker &&  adduser -D -u 1000 -G docker docker \
#        && apk add --no-cache alpine-conf && setup-keymap fr fr

COPY rootfs /

# Copy data for add-on
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]


# Build arguments
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION

# Labels
LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="MDW <MDW@private.fr>" \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.vendor="MetersToHA" \
    org.opencontainers.image.authors="MDW <MDW@private.fr>" \
    org.opencontainers.image.licenses="MIT (Add-on), GPL (MetersToHA)" \
    org.opencontainers.image.url="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}
