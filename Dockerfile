## Start from the official Ubuntu image
FROM ubuntu:22.04

LABEL maintainer="MDW <MDW@private.fr>"

## Set environment variables
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

# Not on 22.04:        firefox-geckodriver, need ppa


# Next lines would upgrade image - skipping
#    && apt-get upgrade -y \
#    && apt-get dist-upgrade -y \

RUN export DEBIAN_FRONTEND="noninteractive" \
    && echo 'APT::Keep-Downloaded-Packages "false";' \
      > /etc/apt/apt.conf.d/01disable-cache \
    && echo 'DPkg::Post-Invoke {"/bin/rm -f /var/cache/apt/archives/*.deb || true";};' \
      > /etc/apt/apt.conf.d/clean \
    && apt-get update --fix-missing \
    && apt-get install -y \
        software-properties-common \
    && apt remove -y --purge \
        firefox* \
    && add-apt-repository ppa:mozillateam/firefox-next \
    && echo > /etc/apt/preferences.d/firefox "Package: firefox*\nPin: origin ppa.launchpadcontent.net\nPin-Priority: 600" \
    && apt-get install -y \
        firefox \
        firefox-geckodriver \
        xvfb \
        xserver-xephyr \
        python3-pip \
        python3-selenium \
        python3-pyvirtualdisplay \
        python3-colorama \
        python3-urllib3 \
        python3-requests \
        python3-paho-mqtt \
    && apt clean && apt autoremove -y \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup -gid 1000 docker &&  adduser -disabled-password -u 1000 -gid 1000 docker

# Install packages to Python3
# RUN pip3 install --upgrade pip \
#    && pip3 install \
#        "urllib3>=1.24.2" \
#        "colorama>=0.3.7" \
#        "selenium>=3.14.1" \
#        "PyVirtualDisplay>=0.2.4" \
#        "requests>=2.23.0"
