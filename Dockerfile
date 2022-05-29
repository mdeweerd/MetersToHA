## Start from the official Ubuntu image
FROM ubuntu:21.04

LABEL maintainer="MDW <MDW@private.fr>"

## Set environment variables
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

# Not on 22.04:        firefox-geckodriver


# Next lines would upgrade image - skipping
#    && apt-get upgrade -y \
#    && apt-get dist-upgrade -y \

RUN export DEBIAN_FRONTEND="noninteractive" \
    && apt-get update --fix-missing \
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
    && apt clean && apt autoremove -y \
    && rm -rf /var/lib/apt/lists/*


# Install packages to Python3
# RUN pip3 install --upgrade pip \
#     && pip3 install \
#        "urllib3>=1.24.2" \
#        "colorama>=0.3.7" \
#        "selenium>=3.14.1" \
#        "PyVirtualDisplay>=0.2.4" \
#        "requests>=2.23.0"
