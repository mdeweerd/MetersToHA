#!/usr/bin/env python3
"""Update the version in config.yaml for Home Assistant apps."""

import os
import sys

import yaml

CONFIG_PATH = "addon_meterstoha/config.yaml"


def update_config_version():
    """Update the version in config.yaml."""
    version = "0.0.0"
    for index, value in enumerate(sys.argv):
        if value in ["--version", "-V"]:
            version = sys.argv[index + 1]

    with open(
        f"{os.getcwd()}/{CONFIG_PATH}",
        encoding="utf_8",
    ) as configfile:
        config = yaml.safe_load(configfile)

    config["version"] = version

    with open(
        f"{os.getcwd()}/{CONFIG_PATH}",
        "w",
        encoding="utf_8",
    ) as configfile:
        yaml.dump(
            config, configfile, default_flow_style=False, sort_keys=False
        )


if __name__ == "__main__":
    update_config_version()
