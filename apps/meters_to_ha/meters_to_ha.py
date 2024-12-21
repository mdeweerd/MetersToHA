#!/usr/bin/env python3
"""
@author: s0nik42
@author: https://github.com/mdeweerd
"""
# Meters To Home Automation
#
# Forked from https://github.com/s0nik42/veolia-idf to:
#  - Change directory structure;
#  - Add more Meters (starting with GazPar).
#
# Copyright (C) 2019-2022 Julien NOEL (Veolia IDF, Domoticz Veolia IDF)
# Copyright (C) 2022-2023 https://github.com/mdeweerd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
# SCRIPT DEPENDENCIES
###############################################################################
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import inspect
import json
import logging
import os
import platform
import random
import re
import signal
import subprocess
import sys
import time
import traceback
import urllib
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from shutil import which
from typing import Any
from urllib.parse import urlencode, urlparse

VERSION = "v2.0"

LOGGER = logging.getLogger()

HA_API_SENSOR_FORMAT = "/api/states/%s"
PARAM_NO_CAPTCHA = "nocaptcha"
PARAM_2CAPTCHA_TOKEN = "2captcha_token"
PARAM_CAPMONSTER_TOKEN = "capmonster_token"
PARAM_CAPTCHAAI_TOKEN = "captchaai_token"
CAPTCHA_TOKENS = (
    PARAM_NO_CAPTCHA,
    PARAM_CAPMONSTER_TOKEN,
    PARAM_2CAPTCHA_TOKEN,
    PARAM_CAPTCHAAI_TOKEN,
)
PARAM_OPTIONAL_VALUE = (
    "Optional"  # Used internally to indicate optional dummy value
)
PARAM_USER_NONE_VALUE = (
    "None"  # Used by the user to indicate an absent configuration
)
PARAM_DOWNLOAD_FOLDER = "download_folder"
PARAM_TIMEOUT = "timeout"
PARAM_VEOLIA = "veolia"
PARAM_GRDF = "grdf"
PARAM_VEOLIA_LOGIN = "veolia_login"
PARAM_VEOLIA_PASSWORD = "veolia_password"
PARAM_VEOLIA_CONTRACT = "veolia_contract"
PARAM_GRDF_LOGIN = "grdf_login"
PARAM_GRDF_PASSWORD = "grdf_password"
PARAM_GRDF_PCE = "grdf_pce"
PARAM_GECKODRIVER = "geckodriver"
PARAM_FIREFOX = "firefox"
PARAM_CHROMIUM = "chromium"
PARAM_CHROMEDRIVER = "chromedriver"
PARAM_LOGS_FOLDER = "logs_folder"
PARAM_SCREENSHOT = "screenshot"
PARAM_SKIP_DOWNLOAD = "skip_download"
PARAM_KEEP_OUTPUT = "keep_output"
PARAM_CHROME_VERSION = "chrome_version"
PARAM_LOG_LEVEL = "log_level"

PARAM_SERVER_TYPE = "type"
PARAM_DOMOTICZ_VEOLIA_IDX = "domoticz_idx"
PARAM_DOMOTICZ_SERVER = "domoticz_server"
PARAM_DOMOTICZ_LOGIN = "domoticz_login"
PARAM_DOMOTICZ_PASSWORD = "domoticz_password"

PARAM_HA_SERVER = "ha_server"
PARAM_HA_TOKEN = "ha_token"

PARAM_MQTT_SERVER = "mqtt_server"
PARAM_MQTT_PORT = "mqtt_port"
PARAM_MQTT_LOGIN = "mqtt_login"
PARAM_MQTT_PASSWORD = "mqtt_password"

PARAM_INSECURE = "insecure"

PARAM_URL = "url"

# Name for parameter where local state is stored
STATE_FILE = "state_file"
INSTALL_DIR = "install_dir"

REPO_BASE = "s0nik42/veolia-idf"

# Script provided by 2captcha to identify captcha information on the page
SCRIPT_2CAPTCHA = r"""
//
window.findRecaptchaClients=function() {
// eslint-disable-next-line camelcase
if (typeof (___grecaptcha_cfg) !== 'undefined') {
// eslint-disable-next-line camelcase, no-undef
return Object.entries(___grecaptcha_cfg.clients).map(([cid, client]) => {
const data = { id: cid, version: cid >= 10000 ? 'V3' : 'V2' };
const objects = Object.entries(client).filter(([_, value]) =>
    value && typeof value === 'object');
objects.forEach(([toplevelKey, toplevel]) => {
const found = Object.entries(toplevel).find(([_, value]) => (
value && typeof value === 'object' && 'sitekey' in value && 'size' in value
));
if (typeof toplevel === 'object' && toplevel instanceof HTMLElement
    && toplevel['tagName'] === 'DIV'){
data.pageurl = toplevel.baseURI;
}
if (found) {
const [sublevelKey, sublevel] = found;
data.sitekey = sublevel.sitekey;
const callbackKey = data.version === 'V2' ? 'callback' : 'promise-callback';
const callback = sublevel[callbackKey];
if (!callback) {
data.callback = null;
data.function = null;
} else {
data.function = callback;
const keys = [cid, toplevelKey, sublevelKey, callbackKey].map((key) =>
    `['${key}']`).join('');
data.callback = `___grecaptcha_cfg.clients${keys}`;
}
}
});
return data;
});
}
return [];
}
"""
hasUndetectedDriver = False

try:
    # Only add packages that are not built-in here
    import requests
    import urllib3
    from colorama import Fore, Style
    from pyvirtualdisplay import Display, xauth

    try:
        # Double check and logging because 'not defined' uc
        # was observed despite this protected import.
        import undetected_chromedriver as uc

        LOGGER.debug("Undetected ChromeDriver import ok")
        _uc_options_test = uc.ChromeOptions()
        LOGGER.debug("Undetected ChromeDriver Options ok")

        hasUndetectedDriver = True
    except ImportError:
        pass

    import selenium
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

except ImportError as excImport:
    print(
        f"Error: failed to import required Python module : {excImport}",
        file=sys.stderr,
    )
    sys.exit(2)


class Worker:
    install_dir = os.path.dirname(os.path.realpath(__file__))
    configuration: dict[str, Any] = {}
    files_to_cleanup: list[str] = []
    _use_display = False
    WORKER_DESC = "Worker"

    def __init__(self, config_dict=None, super_print=None, use_display=False):
        self._use_display = use_display

        # Supersede local print function if provided as an argument
        self.mylog = super_print if super_print else self.default_mylog

        if config_dict is not None:
            self.mylog(f"Start Loading {self.WORKER_DESC} configuration")
            try:
                self._load_configuration_items(config_dict)
                self.mylog(
                    f"End loading {self.WORKER_DESC} configuration", end=""
                )
            except Exception:
                raise
            else:
                self.mylog(st="OK")

    def _load_configuration_items(self, config_dict: dict[str, Any]):
        """
        Load configuration items as defined in self.configuration
        from provided parameters.
        """
        for param in list((self.configuration).keys()):
            if param not in config_dict:
                if self.configuration[param] == PARAM_OPTIONAL_VALUE:
                    self.configuration[param] = None
                elif self.configuration[param] is not None:
                    self.mylog(
                        f'"{param}" not found in config file,'
                        " using default value",
                        "WW",
                    )
                else:
                    self.mylog(f'    "{param}"', end="")
                    raise RuntimeError(
                        f"param {param} is missing in configuration file"
                    )
            else:
                self.configuration[param] = config_dict[param]

            # Sanity check, parameter cleanup, report
            val = self.configuration[param]
            val_str = str(self.configuration[param])

            if (
                re.search(r"folder$", param, re.IGNORECASE)
                and val_str[-1] != os.path.sep
            ):
                val_str += os.path.sep
                self.configuration[param] = val_str

            if val is not None and re.search(
                r"(token|password)", param, re.IGNORECASE
            ):
                self.mylog(
                    f'    "{param}" = "{"*" * len(val_str)}"',
                    end="",
                )
            else:
                self.mylog(
                    f'    "{param}" = "{val_str}"',
                    end="",
                )

            self.mylog(st="OK")
        # LOGGER.debug("%r->%r", config_dict, self.configuration)

    def default_mylog(self, string="", st=None, end=None):
        st = f"[{st}] " if st else ""
        if end is None:
            print(f"{st}{string}")
        else:
            print(
                f"{st} {string} ", end=end, flush=True
            )  # type:ignore[call-overload]

    def cleanup(self, keep_output=False):
        pass


###############################################################################
# Output Class in charge of managing all script output to file or console
###############################################################################
class Output(Worker):
    def __init__(self, config_dict, use_display=False):
        super().__init__(
            super_print=self.__print_to_console, use_display=use_display
        )

        self.__print_buffer = ""
        logs_folder = (
            config_dict[INSTALL_DIR]
            if config_dict[PARAM_LOGS_FOLDER] is None
            else config_dict[PARAM_LOGS_FOLDER]
        )

        logfile = os.path.join(logs_folder, "service.log")

        # In standard mode log to a file
        if self._use_display is False:
            # Check if we can create logfile
            try:
                open(logfile, "a+", encoding="utf_8").close()
            except Exception as e:
                raise RuntimeError(f'"{logfile}" {e}')

            # Set the logfile format
            file_handler = RotatingFileHandler(logfile, "a", 1000000, 1)
            formatter = logging.Formatter("%(asctime)s : %(message)s")
            file_handler.setFormatter(formatter)
            LOGGER.setLevel(logging.INFO)
            LOGGER.addHandler(file_handler)
            self.mylog = self.__print_to_logfile

    def __print_to_console(self, string="", st=None, end=None):
        if st:
            st = st.upper()
            st = st.replace("OK", Fore.GREEN + "OK")
            st = st.replace("WW", Fore.YELLOW + "WW")
            st = st.replace("EE", Fore.RED + "EE")
            st = "[" + st + Style.RESET_ALL + "] "

        if end is not None:
            st = st + " " if st else ""
            print(st + "%-75s" % (string,), end=end, flush=True)
            self.__print_buffer = self.__print_buffer + string
        elif self.__print_buffer:
            st = st if st else "[--] "
            print(st + string.rstrip())
            self.__print_buffer = ""
        else:
            st = st if st else "[--]"
            print(("{:75s}" + st).format(string.rstrip()))
            self.__print_buffer = ""

    def __print_to_logfile(self, string="", st=None, end=None):
        if end is not None:
            self.__print_buffer = self.__print_buffer + string
        else:
            st = st if st else "--"
            LOGGER.info(
                "%s : %s %s",
                st.upper().lstrip(),
                self.__print_buffer.lstrip().rstrip(),
                string.lstrip().rstrip(),
            )
            self.__print_buffer = ""


# Utility classes


def document_initialised(driver):
    """
    Execute JavaScript in browser to confirm page is loaded.
    """
    return driver.execute_script("return true;")


def print_classes(modulename=__name__):
    """
    Help with introspection
    """
    for _name, obj in inspect.getmembers(sys.modules[modulename]):
        if inspect.isclass(obj):
            LOGGER.debug(obj)


# Source: https://www.novixys.com/blog/python-check-file-can-read-write/
def check_file_writable(fnm):
    """
    Check if we can write a file to the provided path (including the filename)
    """
    if os.path.exists(fnm):
        if os.path.isfile(fnm):
            return os.access(fnm, os.W_OK)
        return False
    pdir = os.path.dirname(fnm)
    if not pdir:
        pdir = "."
    return os.access(pdir, os.W_OK)


###############################################################################
# Configuration Class to parse and load config.json
###############################################################################
class Configuration(Worker):
    def load_configuration_file(self, configuration_file):
        python_version = platform.python_version()
        self.mylog(
            f"Using {sys.executable} Version {python_version}", end="--"
        )
        self.mylog(
            f"Loading configuration file : {configuration_file}", end="--"
        )
        try:
            with open(configuration_file, encoding="utf_8") as conf_file:
                content = json.load(conf_file)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"json format error : {e}")
        except Exception:
            raise
        else:
            self.mylog(st="OK")
            return content


###############################################################################
# Object that retrieves the historical data from Service website(s)
###############################################################################
class ServiceCrawler(Worker):  # pylint:disable=too-many-instance-attributes
    # Go to login page directly
    # site_url = "https://espace-client.vedif.eau.veolia.fr/s/login/"
    # Go to login page directly only when not logged in
    site_url = "https://espace-client.vedif.eau.veolia.fr/s/"
    download_veolia_filename = "historique_jours_litres.csv"
    glob_download_veolia_filename = "historique_jours_litres*.csv"
    site_grdf_url = "https://monespace.grdf.fr/client/particulier/consommation"
    # site_grdf_url = "ttps://login.monespace.grdf.fr/mire/connexion"
    download_grdf_filename = "historique_gazpar.json"
    hasFirefox = False
    hasChromium = False

    def __init__(
        self,
        config_dict,
        super_print=None,
        use_display=False,
        local_config=False,
    ):
        super().__init__(super_print=super_print, use_display=use_display)

        self.__local_config = local_config

        self.__display = None
        self.__browser = None  # type: webdriver.Firefox
        self.__wait = None  # type: WebDriverWait
        self.configuration = {
            # Config values (veolia)
            PARAM_VEOLIA: False,
            PARAM_VEOLIA_LOGIN: PARAM_OPTIONAL_VALUE,
            PARAM_VEOLIA_PASSWORD: PARAM_OPTIONAL_VALUE,
            PARAM_VEOLIA_CONTRACT: PARAM_OPTIONAL_VALUE,
            # Config values (gazpar)
            PARAM_GRDF: False,
            PARAM_GRDF_LOGIN: PARAM_OPTIONAL_VALUE,
            PARAM_GRDF_PASSWORD: PARAM_OPTIONAL_VALUE,
            PARAM_GRDF_PCE: PARAM_OPTIONAL_VALUE,
            # Browser/Scraping config values
            PARAM_SCREENSHOT: False,
            PARAM_SKIP_DOWNLOAD: False,
            PARAM_KEEP_OUTPUT: False,
            PARAM_GECKODRIVER: which("geckodriver")
            if which("geckodriver")
            else os.path.join(config_dict[INSTALL_DIR], "geckodriver"),
            PARAM_FIREFOX: which("firefox")
            if which("firefox")
            else os.path.join(config_dict[INSTALL_DIR], "firefox"),
            PARAM_CHROMIUM: which("chromium")
            if which("chromium")
            else which("chromium-browser")
            if which("chromium-browser")
            else "/usr/bin/chromium-browser"
            if os.path.exists("/usr/bin/chromium-browser")
            else os.path.join(config_dict[INSTALL_DIR], "chromium"),
            PARAM_CHROMEDRIVER: which("chromedriver")
            if which("chromedriver")
            else os.path.join(config_dict[INSTALL_DIR], "chromedriver"),
            PARAM_CHROME_VERSION: PARAM_OPTIONAL_VALUE,
            PARAM_TIMEOUT: "30",
            PARAM_DOWNLOAD_FOLDER: self.install_dir,
            PARAM_LOGS_FOLDER: self.install_dir,
            PARAM_NO_CAPTCHA: PARAM_OPTIONAL_VALUE,
            PARAM_2CAPTCHA_TOKEN: PARAM_OPTIONAL_VALUE,
            PARAM_CAPMONSTER_TOKEN: PARAM_OPTIONAL_VALUE,
            PARAM_CAPTCHAAI_TOKEN: PARAM_OPTIONAL_VALUE,
            PARAM_LOG_LEVEL: "INFO",  # error, warning, info, debug
        }

        self.mylog("Start loading configuration")
        try:
            self._load_configuration_items(config_dict)
            self.mylog("End loading configuration", end="")
        except Exception:
            raise
        else:
            self.mylog(st="OK")

        self.__full_path_download_veolia_idf_file = os.path.join(
            self.configuration[PARAM_DOWNLOAD_FOLDER],
            self.download_veolia_filename,
        )
        self.__glob_path_download_veolia_idf_file = os.path.join(
            self.configuration[PARAM_DOWNLOAD_FOLDER],
            self.glob_download_veolia_filename,
        )
        self.__full_path_download_grdf_file = os.path.join(
            self.configuration[PARAM_DOWNLOAD_FOLDER],
            self.download_grdf_filename,
        )

    def init(self):
        if self.configuration[PARAM_SKIP_DOWNLOAD]:
            self.mylog("Skipping download, not initializing browser", st="--")
            return
        try:
            if self.hasFirefox:
                self.mylog("Try starting Firefox. ", end="")
                self.init_firefox()
                self.mylog(st="OK")
                return
        except (Exception, xauth.NotFoundError):
            self.mylog(st="~~")

        if self.hasChromium:
            # Firefox did not load, try Chromium
            self.mylog("Try starting Chromium. ", end="")
            self.init_chromium()
            self.mylog(st="OK")
            return

        raise RuntimeError(
            "No browser could be started with selenium"
            f" {self.hasFirefox}-{self.hasChromium}"
        )

    def get_log_level(self) -> int:
        """Get numeric value for logging level in configuration"""
        return logging.getLevelName(
            self.configuration[PARAM_LOG_LEVEL].upper()
        )

    # INIT DISPLAY & BROWSER
    def init_firefox(self):
        self.mylog("Start virtual display (Firefox).", end="")
        # veolia website needs at least 1600x1200 to render all components
        if sys.platform != "win32":
            if self._use_display:
                self.__display = Display(visible=1, size=(1600, 1200))
            else:
                self.__display = Display(visible=0, size=(1600, 1200))
            try:
                self.__display.start()
            except Exception as e:
                raise RuntimeError(
                    f"{e} if you launch the script through a ssh connection"
                    " with '--display' ensure X11 forwarding is activated"
                )
            else:
                self.mylog(st="OK")

        self.mylog("Setup Firefox profile", end="")
        try:
            accept_types = ",".join(["text/csv", "application/json"])
            # Enable Download
            opts = webdriver.FirefoxOptions()
            opts.set_preference(
                "browser.download.dir",
                self.configuration[PARAM_DOWNLOAD_FOLDER],
            )
            opts.set_preference("browser.download.folderList", 2)
            opts.set_preference(
                "browser.helperApps.neverAsk.saveToDisk", accept_types
            )
            opts.set_preference(
                "browser.download.manager.showWhenStarting", False
            )
            opts.set_preference(
                "browser.helperApps.neverAsk.openFile", accept_types
            )
            opts.set_preference("browser.helperApps.alwaysAsk.force", False)

            # Set firefox binary to use
            opts.binary_location = FirefoxBinary(
                str(self.configuration[PARAM_FIREFOX])
            )

            ff_service = FirefoxService(
                executable_path=self.configuration[PARAM_GECKODRIVER],
                log_path=os.path.join(
                    self.configuration[PARAM_LOGS_FOLDER], "geckodriver.log"
                ),
            )
            if not hasattr(ff_service, "process"):
                # Webdriver may complain about missing process.
                ff_service.process = None

            # Enable the browser
            try:
                browser = webdriver.Firefox(
                    options=opts,
                    service=ff_service,
                )
            except FileNotFoundError:
                raise
            except Exception as e:
                raise RuntimeError(
                    f"{e} If you launch the script through a ssh connection"
                    " with '--display' ensure X11 forwarding is activated,"
                    " and that you have a working X environment."
                    " '--display' starts Firefox on X Display "
                    " and shows dynamic evolution of the website"
                )
        except Exception:
            raise
        else:
            self.mylog(st="OK")

        self.mylog("Start Firefox", end="")
        try:
            # browser.maximize_window()
            # Replaced maximize_window by set_window_size
            # to get the window full screen
            browser.set_window_size(1600, 1200)
            timeout = int(self.configuration[PARAM_TIMEOUT])  # type:ignore
            self.__wait = WebDriverWait(browser, timeout=timeout)
        except Exception:
            raise
        else:
            # Now we know the browser works...
            self.__browser = browser
            self.mylog(st="OK")

    def init_chromium(self):
        if hasUndetectedDriver:
            options = uc.ChromeOptions()
        else:
            options = webdriver.ChromeOptions()

        log_level = self.get_log_level()

        # Set Chrome options
        if (
            sys.platform != "win32"
            and hasattr(os, "geteuid")
            and os.geteuid() == 0  # pylint: disable=no-member
        ):
            self.mylog("Add nix root user options.")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-modal-animations")
            options.add_argument("--disable-login-animations")
            options.add_argument("--disable-renderer-backgrounding")
            options.add_argument("--disable-dev-shm-usage")

        local_dir = str(self.configuration[PARAM_DOWNLOAD_FOLDER])

        # options.add_argument(f"--crash-dumps-dir={local_dir}/tmp")
        # options.add_argument("--remote-debugging-port=9222")

        # pylint: disable=condition-evals-to-constant
        if self.__local_config:  # Use fixed, reused datadir
            # datadir = os.path.expanduser("~/.config/google-chrome")
            datadir = os.path.expanduser(f"{local_dir}.config/google-chrome")
            os.makedirs(datadir, exist_ok=True)
            options.add_argument(f"--user-data-dir={datadir}")
            self.mylog(f"Use {datadir} for Google Chrome user data.")

        # options.add_argument('--user-data-dir=~/.config/google-chrome')
        options.add_argument("--mute-audio")
        # if self._use_display:
        #     Does not work well with veolia due to multiple "same" elements
        #     options.add_argument("--auto-open-devtools-for-tabs")
        options.add_experimental_option(
            "prefs",
            {
                "credentials_enable_service": False,
                "download.default_directory": self.configuration[
                    PARAM_DOWNLOAD_FOLDER
                ],
                "profile.default_content_settings.popups": 1,
                "profile.password_manager_enabled": False,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "extensions_to_open": ",".join(
                    ["text/csv", "application/json"]
                ),
                "safebrowsing.enabled": False,
            },
        )
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-translate")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-infobars")

        if not hasUndetectedDriver:
            options.add_experimental_option("useAutomationExtension", False)
            options.add_experimental_option(
                "excludeSwitches", ["enable-automation"]
            )
        if log_level >= logging.WARNING:
            options.add_experimental_option(
                "excludeSwitches", ["enable-logging"]
            )

        if sys.platform != "win32":
            self.mylog("Start virtual display (Chromium).", end="")

        if log_level < logging.INFO:
            options.add_argument("--enable-logging")
            options.add_argument("--log-level=1")
            options.add_argument("--v=1")
        elif log_level < logging.WARNING:
            options.add_argument("--enable-logging")
            options.add_argument("--log-level=0")
            options.add_argument("--v=0")

        if self._use_display:
            if sys.platform != "win32":
                self.__display = Display(visible=1, size=(1280, 1024))
            if getattr(options, "headless", "_DUMMY_") == "_DUMMY_":
                # Workaround breaking change selenium 4.13.0
                options.headless = False
        else:
            options.add_argument("--headless")
            if getattr(options, "headless", "_DUMMY_") == "_DUMMY_":
                # Workaround breaking change selenium 4.13.0
                options.headless = True
            if sys.platform != "win32":
                try:
                    options.add_argument("--disable-gpu")
                    self.__display = Display(visible=0, size=(1280, 1024))
                except Exception:
                    raise
            else:
                options.add_argument("window-size=1280,1024")

        if sys.platform != "win32":
            try:
                self.__display.start()
            except Exception:
                raise

        # No exception up to here, so ok
        self.mylog(st="OK")

        # Discover classes provided
        # print_classes("selenium.webdriver") ; sys.exit()
        # print_classes("selenium.webdriver.chrome.service") ; sys.exit()

        chromedriver_log = os.path.join(
            self.configuration[PARAM_LOGS_FOLDER],
            "chromedriver.log",
        )
        chromium_service_args = (
            ["--verbose"] if log_level < logging.INFO else None
        )

        self.mylog(
            f"LOG LEVEL {self.configuration[PARAM_LOG_LEVEL]}"
            f":{log_level}:{logging.INFO}"
            f" {chromium_service_args!r}",
            st="~~",
        )
        self.mylog("Start the browser", end="")
        try:
            if "chromium" in inspect.getmembers(webdriver):
                chromeService = webdriver.chromium.service.ChromiumService(
                    executable_path=self.configuration[PARAM_CHROMEDRIVER],
                    service_args=chromium_service_args,  # More debug info
                    log_output=chromedriver_log,
                )
            else:
                chromeService = webdriver.chrome.service.Service(
                    executable_path=self.configuration[PARAM_CHROMEDRIVER],
                    service_args=chromium_service_args,  # More debug info
                    log_output=chromedriver_log,
                )
            if hasUndetectedDriver:
                sys.path.append(
                    os.path.join(
                        os.path.expanduser("~"),
                        ".local",
                        "share",
                        "undetected_chromedriver",
                    )
                )
                chrome_version = self.configuration[PARAM_CHROME_VERSION]
                browser = uc.Chrome(
                    version_main=chrome_version,
                    service=chromeService,
                    options=options,
                )
            else:
                browser = webdriver.Chrome(
                    service=chromeService,
                    options=options,
                )

            browser.maximize_window()
            timeout = int(self.configuration[PARAM_TIMEOUT])  # type:ignore
            self.__wait = WebDriverWait(browser, timeout)
        except AttributeError:
            self.mylog("chromium unknown in selenium webdriver", end="--")
            raise
        except Exception:
            raise
        else:
            # Now we know the browser works
            self.__browser = browser
            self.mylog(st="OK")

    def sanity_check(self):
        checkBrowser = False  # True if we want to download something
        reason = " (Missing Veolia or GRDF or Unknown reason)"
        if self.configuration[PARAM_VEOLIA]:
            # Getting Veolia data
            v_file = self.__full_path_download_veolia_idf_file
            self.mylog("Check download location integrity", end="")

            if os.path.exists(v_file):
                if self.configuration[PARAM_SKIP_DOWNLOAD]:
                    self.mylog(
                        f"'{v_file}' already exists, reused (--skip_download)",
                        "--",
                    )
                    reason = " (Skip download)"
                else:
                    checkBrowser = True
                    self.mylog(
                        f"'{v_file}' already exists, will be removed", "WW"
                    )
            else:
                if self.configuration[PARAM_SKIP_DOWNLOAD]:
                    self.mylog(f"Can't reuse missing '{v_file}'", "EE")
                    raise RuntimeError(f"Can't reuse missing '{v_file}'")

                try:
                    open(v_file, "a+", encoding="utf_8").close()
                except Exception as e:
                    raise RuntimeError(f'"{v_file}" {e}')

                checkBrowser = True
                self.mylog(st="OK")

        if self.configuration[PARAM_GRDF]:
            if self.configuration[PARAM_SKIP_DOWNLOAD]:
                reason = " (Skip download)"
            else:
                checkBrowser = True

        if not checkBrowser:
            # Not checking browser, we do not need it
            self.mylog(f"Skip browser check, not needed{reason}", st="--")
            return

        self.mylog(
            'Check availability of "geckodriver"+"firefox"'
            ' or "chromedriver"+"chromium"',
            st="~~",
        )

        hasBrowser = False
        if os.access(
            str(self.configuration[PARAM_GECKODRIVER]), os.X_OK
        ) and os.access(str(self.configuration[PARAM_FIREFOX]), os.X_OK):
            self.mylog("Check firefox browser version", end="")
            try:
                major, minor = self.__get_firefox_version()
            except Exception:
                raise
            else:
                if (major, minor) < (60, 9):
                    self.mylog(
                        f"Firefox version ({major}.{minor})"
                        " is too old (< 60.9) script may fail",
                        st="WW",
                    )
                else:
                    self.hasFirefox = True
                    hasBrowser = True
                    self.mylog(st="OK")

        if (
            hasUndetectedDriver
            or os.access(str(self.configuration[PARAM_CHROMEDRIVER]), os.X_OK)
        ) and os.access(str(self.configuration[PARAM_CHROMIUM]), os.X_OK):
            if hasUndetectedDriver:
                extraMsg = " with undetected driver"
            else:
                extraMsg = ""
            self.mylog(f"Found chromium binary{extraMsg}", st="OK")
            self.hasChromium = True
            hasBrowser = True

        if not hasBrowser:
            raise OSError(
                '"%s"/"%s" or "%s"/"%s": no valid pair of executables found'
                % (
                    self.configuration[PARAM_GECKODRIVER],
                    self.configuration[PARAM_FIREFOX],
                    self.configuration[PARAM_CHROMEDRIVER],
                    self.configuration[PARAM_CHROMIUM],
                )
            )

    def __get_firefox_version(self):
        try:
            output = subprocess.check_output(
                [str(self.configuration[PARAM_FIREFOX]), "--version"]
            )
        except Exception:
            raise

        try:
            major, minor = map(
                int,
                re.search(
                    r"(\d+).(\d+)", str(output)
                ).groups(),  # type:ignore[union-attr]
            )
        except Exception:
            raise

        return major, minor

    def cleanup(self, keep_output=False):
        self.mylog("Close Browser", end="")
        if self.__browser:
            pid = self.__browser.service.process.pid
            try:
                self.__browser.quit()
            finally:
                # try to kill anyway,
                #  if kill fails, it was likely closed clean.
                try:
                    os.kill(pid, signal.SIGTERM)
                    self.mylog(
                        "Selenium didn't properly close the process, "
                        f"so we kill the browser manually (pid={pid})",
                        "WW",
                    )
                except:  # noqa: B001,E722
                    self.mylog(st="OK")
        else:
            self.mylog(st="OK")

        self.mylog("Close Display", end="")
        if self.__display is not None:
            try:
                self.__display.stop()
            except:  # noqa: B001,E722
                raise
            else:
                self.mylog(st="OK")

        # Remove downloaded files
        for fn in self.files_to_cleanup:
            try:
                if (
                    not self._use_display
                    and not keep_output
                    and os.path.exists(fn)
                ):
                    # Remove file
                    self.mylog(f"Remove downloaded file {fn}", end="")
                    os.remove(fn)
                else:
                    self.mylog(st="OK")
            except Exception as e:
                self.mylog(str(e), st="EE")

    def wait_until_disappeared(
        self, method, key, wait_message=None, timeout=None
    ):
        """Wait until element is gone"""

        if wait_message is None:
            wait_message = f"Wait until {key} is gone"

        self.mylog(wait_message, end="")

        if timeout is None:
            # No timeout provided, default timeout
            timeout = int(self.configuration[PARAM_TIMEOUT])

        ep = EC.visibility_of_element_located(
            (
                method,
                key,
            )
        )

        timeout_message = f"Failed, page timeout (timeout={timeout})"

        WebDriverWait(self.__browser, timeout=timeout).until_not(
            ep, message=timeout_message
        )

        self.mylog(st="OK")

    def click_in_view(  # pylint: disable=R0913
        self,
        method,
        key,
        click_message=None,
        wait_message=None,
        delay=0,
        timeout=None,
    ):
        """
        1. Wait until element is visible
        2. Wait for delay.
        3. Bring into view (location may have changed)
        4. Click
        """
        # Wait until element is visible
        if wait_message is None:
            wait_message = f"Wait for Button {method}:{key}. "
        self.mylog(wait_message, end="")

        if timeout is None:
            # No timeout provided, default timeout
            timeout = self.configuration[PARAM_TIMEOUT]

        timeout_message = f"Failed, page timeout (timeout={timeout})"

        # ep = EC.visibility_of_element_located(
        ep = EC.presence_of_element_located(
            (
                method,
                key,
            )
        )
        el = self.__wait.until(ep, message=timeout_message)

        self.mylog(st="OK")

        if delay != 0.0:
            self.mylog(f"Wait before clicking ({delay:.1f}s).", end="")
            self.mylog(st="~~")
            time.sleep(delay)

        # Bring the element into view
        el.location_once_scrolled_into_view

        # Click
        if click_message is None:
            click_message = f"Click on {key}"
        self.mylog(click_message, end="")

        try:
            el.click()
        except Exception:
            raise
        else:
            self.mylog(st="OK")

    def get_screenshot(self, basename: str, dump_html: bool = False):
        """
        Get screenshot and save to file in logs_folder
        """

        fn_img = os.path.join(self.configuration[PARAM_LOGS_FOLDER], basename)
        # Screenshots are only for debug, so errors are not blocking.
        try:
            self.mylog(f"Grab & Save '{fn_img}'. ", end="--")
            # img = self.__display.waitgrab()
            self.__browser.get_screenshot_as_file(fn_img)
        except Exception as e:
            self.mylog(
                f"Exception while getting screenshot {fn_img}: {e}", end=""
            )

        if dump_html:
            try:
                fn_html = fn_img + ".html"
                with open(fn_html, "w", encoding="utf_8") as html_file:
                    self.mylog(f"Writing '{fn_html}'. ", end="~~")
                    html_file.write(self.__browser.page_source)
            except Exception as e:
                self.mylog(f"Could not dump html {fn_html}: {e}", end="")

    def resolve_captcha2(self) -> str | None:
        # pylint: disable=too-many-locals,too-many-return-statements

        method = None
        for m in CAPTCHA_TOKENS:
            key = self.configuration[m]
            if key is not None and key != "":
                method = m
                break

        if method == PARAM_NO_CAPTCHA and key:
            self.mylog(
                "Captcha resolution is disabled by config.",
                st="WW",
            )
            return method

        if method is None:
            self.mylog(
                "Can not resolve using captcha service - "
                "missing one of ('%s')" % ("', '".join(CAPTCHA_TOKENS),),
                st="WW",
            )
            return None

        if False:
            captcha_results = "XXXXMARIOXXXXMARIO"
            SELECT_SCRIPT_TEMPLATE = """
               document.querySelector('[name="g-recaptcha-response"]').innerText='{}'
            """
            select_script = SELECT_SCRIPT_TEMPLATE.format(captcha_results)
            # print(f"select_script}\n")
            self.__browser.execute_script(select_script)
            time.sleep(5000)

        if False:
            self.__browser.switch_to.frame(2)
            # r"recaptcha-verify-button" is not the correct button
            #  to click after validation!
            button = self.__browser.find_element(
                By.ID, r"recaptcha-verify-button"
            )
            self.__browser.switch_to.default_content()

        # Method 1 to find key
        GET_KEY = r"""
            return (new URLSearchParams(
              document.querySelector("iframe[title=\'reCAPTCHA\']")
                .getAttribute("src")))
            .get("k")
            """
        # Method 2 to find key
        GET_KEY = (
            SCRIPT_2CAPTCHA + r"return (findRecaptchaClients())[0].sitekey;"
        )
        site_key = self.__browser.execute_script(GET_KEY)
        page_url = str(self.__browser.current_url)
        parsed = urlparse(page_url)
        # print(f"{parsed!r}\n")
        append_port = ""
        if ":" not in parsed.netloc:
            append_port = ":443" if parsed.scheme == "https" else ":80"
        new_url = parsed._replace(
            netloc=parsed.netloc + append_port,
            path="",
            params="",
            query="",
            fragment="",
        )
        short_url = new_url.geturl()

        # print(f"{short_url}\n")
        page_url = short_url

        if method in (PARAM_2CAPTCHA_TOKEN, PARAM_CAPTCHAAI_TOKEN):
            captchamethod = "userrecaptcha"
            # Compute request
            if method == PARAM_CAPTCHAAI_TOKEN:
                # @see https://help.captchaai.com/en/articles/6878224-how-to-solve-openbullet-captcha-using-captchaai # noqa
                service = "Captchaai"
                uri = "https://ocr.captchaai.com"
                url_args = {
                    "key": key,
                    "method": captchamethod,
                    "googlekey": site_key,
                    "pageurl": page_url,
                    "from": "151169",
                }
                url = f"{uri}/in.php?" + urlencode(url_args)
            else:
                service = "2Captcha"
                uri = "https://2captcha.com"
                url = (
                    f"{uri}/in.php?key={key}&method={captchamethod}"
                    f"&googlekey={site_key}&pageurl={page_url}"
                    "&soft_id=3887"
                )

            # submit request
            self.mylog(f"{service} {url}", st="~~")
            retries = 3
            while retries > 0:
                response = requests.get(url, timeout=10)
                retries -= 1
                if response.text[0:2] == "OK":
                    break
                self.mylog(
                    f"{service} Service error: Error code {response.text}",
                    st="WW",
                )
                if retries <= 0:
                    return None
                time.sleep(2)

            self.mylog(f"{service} Service response {response.text}", st="~~")

            captcha_id = response.text[3:]
            # Polling for response
            token_url = f"{uri}/res.php?key={key}&action=get&id={captcha_id}"

            max_loops = 12
            timeout = 20
            captcha_results = None
            while max_loops > 0:
                max_loops -= 1
                self.mylog(
                    f"Wait {timeout}s for {service}",
                    st="~~",
                )
                time.sleep(timeout)
                timeout = 10
                response = requests.get(token_url, timeout=10)

                self.mylog(
                    f"{service} Service response {response.text}", st="~~"
                )
                if response.text[0:2] == "OK":
                    captcha_results = response.text[3:]
                    break
        elif method == PARAM_CAPMONSTER_TOKEN:
            headers = {"Accept-Encoding": "application/json"}
            service = "capmonster"
            api_data = {
                "clientKey": key,
                "task": {
                    "type": "NoCaptchaTaskProxyless",
                    "websiteURL": page_url,
                    "websiteKey": site_key,
                    # "recaptchaDataSV": data_s_value, # "data-s" attribute
                    # "userAgent": ....
                    # "cookies": ....
                },
                # "softId":
            }
            api_url = "https://api.capmonster.cloud/createTask"
            response = requests.post(
                api_url, headers=headers, json=api_data, timeout=10
            )
            if response.status_code != 200:
                self.mylog(
                    f"{service} status {response.status_code}"
                    f"{response.text}",
                    st="EE",
                )
                return None
            resp_data = response.json()
            if "errorId" in resp_data and resp_data["errorId"] != 0:
                self.mylog(
                    f"{service} error {resp_data['errorId']}:"
                    f"{resp_data['errorDescription']}",
                    st="EE",
                )
                return None
            taskId = resp_data["taskId"]

            # Polling for response
            token_url = "https://api.capmonster.cloud/getTaskResult"
            token_data = {
                "clientKey": key,
                "taskId": taskId,
            }

            max_loops = 12
            captcha_results = None
            while max_loops > 0:
                max_loops -= 1
                self.mylog(f"Wait 10s for {service}", st="~~")
                time.sleep(10)
                response = requests.post(
                    token_url, headers=headers, json=token_data, timeout=10
                )

                if response.status_code != 200:
                    self.mylog(
                        f"{service} status {response.status_code}"
                        f"{response.text}",
                        st="EE",
                    )
                    # Try again - we've successfully requested a task
                    continue

                resp_data = response.json()
                if "errorId" in resp_data and resp_data["errorId"] != 0:
                    self.mylog(
                        f"{service} error {resp_data['errorId']}:"
                        f"{resp_data['errorDescription']}",
                        st="EE",
                    )
                    return None
                if resp_data["status"] == "ready":
                    captcha_results = resp_data["solution"][
                        "gRecaptchaResponse"
                    ]
                    break

        if captcha_results is not None:
            FILL_CAPTCHA_TEMPLATE = r"""
                document.querySelector('[name="g-recaptcha-response"]')
                   .innerText='{}';
            """
            select_script = FILL_CAPTCHA_TEMPLATE.format(captcha_results)
            VALIDATE_JS = """
                return (findRecaptchaClients())[0]
                  .function('{captcha_results}');
            """

            select_script += VALIDATE_JS

            # print(select_script)
            self.__browser.execute_script(select_script)

            if False:
                self.__browser.switch_to.frame(2)
                button = self.__browser.find_element(
                    By.ID, r"recaptcha-verify-button"
                )
                # print(f"button:{button!r}\n")
                button.click()

            # sys.exit()
            return captcha_results

        # time.sleep(120)  # For inspection
        return None

    def getDownloadedFileName(self, waitTime: float) -> str | None:
        """Get downloaded filename in browser, wait for end of download"""
        if isinstance(self.__browser, webdriver.Firefox):
            return self.ff_getDownloadedFileName(waitTime)

        return self.chrome_getDownloadedFileName(waitTime)

    def chrome_getDownloadedFileName(self, waitTime: float) -> str | None:
        """Get downloaded filename in chrome"""
        # https://itecnote.com/tecnote/python-selenium-give-file-name-when-downloading/
        self.__browser.execute_script("window.open()")
        time.sleep(20)
        # switch to new tab
        self.__browser.switch_to.window(self.__browser.window_handles[-1])
        # navigate to chrome downloads
        self.__browser.get("chrome://downloads")
        # define the endTime
        endTime = time.time() + waitTime
        while True:
            try:
                # get downloaded percentage
                downloadPercentage = self.__browser.execute_script(
                    "return document.querySelector('downloads-manager')"
                    " .shadowRoot"
                    " .querySelector('#downloadsList downloads-item')"
                    " .shadowRoot.querySelector('#progress').value"
                )

                # Wait until if downloadPercentage is 100, or timeout
                if downloadPercentage == 100:
                    # return the file name once the download is completed
                    return self.__browser.execute_script(
                        "return document.querySelector('downloads-manager')"
                        " .shadowRoot"
                        " .querySelector('#downloadsList downloads-item')"
                        " .shadowRoot.querySelector('div#content  #file-link')"
                        " .text"
                    )
            except:  # noqa: B001,E722
                pass
            time.sleep(1)
            if time.time() > endTime:
                break
        return None

    def ff_getDownloadedFileName(self, waitTime: float) -> str | None:
        """Wait and get last downloaded file"""
        # https://itecnote.com/tecnote/python-selenium-give-file-name-when-downloading/
        self.__browser.execute_script("window.open()")
        WebDriverWait(self.__browser, 10).until(EC.new_window_is_opened)
        self.__browser.switch_to.window(self.__browser.window_handles[-1])
        self.__browser.get("about:downloads")

        endTime = time.time() + waitTime
        while True:
            try:
                fileName = self.__browser.execute_script(
                    """
                    return document.querySelector(
                    '#contentAreaDownloadsView .downloadMainArea
                    .downloadContainer description:nth-of-type(1)')
                    .value
                    """
                )
                if fileName:
                    return fileName
            except:  # noqa: B001, E722
                pass
            time.sleep(1)
            if time.time() > endTime:
                break

        return None

    def get_veolia_idf_file(self):
        """
        Get Veolia IDF water consumption 'interactively'
        """
        # pylint: disable=too-many-locals

        v_file = self.__full_path_download_veolia_idf_file
        v_file_glob = self.__glob_path_download_veolia_idf_file

        if self.configuration[PARAM_SKIP_DOWNLOAD]:
            return v_file

        # Wait for Connexion #####
        self.mylog("Connexion au site Veolia Eau Ile de France", end="")

        self.__browser.get(self.__class__.site_url)
        time.sleep(0.5)  # Small wait after submit
        self.__wait.until(document_initialised)

        self.mylog(st="OK")

        ep = EC.visibility_of_any_elements_located(
            (By.CSS_SELECTOR, r'input[type="password"],.profileIcon')
        )
        self.__wait.until(
            ep,
            message="Failed, page timeout (timeout="
            + str(self.configuration[PARAM_TIMEOUT])
            + ")",
        )

        try:
            # If profile element is present, likely already logged in
            if self.configuration[PARAM_SCREENSHOT]:
                self.get_screenshot("check_profile.png")
            profile_el = self.__browser.find_element(
                By.CLASS_NAME, "profileIcon"
            )
            if profile_el is not None:
                isLoggedIn = True
        except Exception:
            isLoggedIn = False

        if not isLoggedIn:
            # Wait for Password ######
            # More than one email element on the page,
            # visibility depends on screen size.
            self.mylog("Waiting for Password", end="")

            ep = EC.visibility_of_any_elements_located(
                (By.CSS_SELECTOR, r'input[type="password"]')
            )
            el_password = self.__wait.until(
                ep,
                message="failed, page timeout (timeout="
                + str(self.configuration[PARAM_TIMEOUT])
                + ")",
            )
            # Get first (and normally only) visible element
            el_password = el_password[0]
            self.mylog(st="OK")

            # Wait for Email ########
            # More than one email element on the page,
            # visibility depends on screen size.
            self.mylog("Waiting for Email", end="")
            ep = EC.visibility_of_any_elements_located(
                (By.XPATH, r"//input[@inputmode='email']")
            )
            el_email = self.__wait.until(
                ep,
                message="failed, page timeout (timeout="
                + str(self.configuration[PARAM_TIMEOUT])
                + ")",
            )
            # Get first (and normally only) visible element
            el_email = el_email[0]
            self.mylog(st="OK")

            # Type Email ###########
            self.mylog("Type Email", end="")
            el_email.clear()
            el_email.send_keys(self.configuration[PARAM_VEOLIA_LOGIN])
            self.mylog(st="OK")

            # Type Password ########
            self.mylog("Type Password", end="")
            el_password.clear()
            el_password.send_keys(self.configuration[PARAM_VEOLIA_PASSWORD])
            self.mylog(st="OK")

            # Click Submit #########
            self.click_in_view(
                By.CLASS_NAME,
                "submit-button",
                wait_message="Waiting for submit button",
                click_message="Click on submit button",
                delay=1,
            )

            time.sleep(0.5)  # Small wait after submit
            self.__wait.until(document_initialised)
            # time.sleep(10)

        # Should be logged in here

        # for filename in glob.glob(v_file_glob):
        for filename in (v_file,):  # Loop to replace the above alternative
            try:
                self.mylog(
                    f"Remove temporary download file '{filename}'. ", end=""
                )
                os.remove(filename)
            except Exception:
                raise
            else:
                self.mylog(st="OK")

        # Wait until element is at least visible
        ep = EC.visibility_of_any_elements_located((By.CSS_SELECTOR, r".logo"))
        self.__wait.until(
            ep,
            message="Failed, page timeout (timeout="
            + str(self.configuration[PARAM_TIMEOUT])
            + ")",
        )

        # Wait until spinner is gone #####
        self.wait_until_disappeared(By.CSS_SELECTOR, "lightning-spinner")
        time.sleep(1)

        self.__browser.switch_to.default_content()

        # Different handling dependent on multiple or single contract

        self.mylog("Wait for MENU contrats or historique", end="")
        ep = EC.visibility_of_element_located(
            (
                By.XPATH,
                r"//span[contains(text(), 'CONTRATS')"
                r" or contains(text(), 'HISTORIQUE')]",
            )
        )
        try:
            el = self.__wait.until(
                ep,
                message="failed, page timeout (timeout="
                + str(self.configuration[PARAM_TIMEOUT])
                + ")",
            )
        except Exception:
            pass

        self.mylog(st="OK")

        time.sleep(2)

        menu_type = str(el.get_attribute("innerHTML"))

        # Click on Menu #####
        self.mylog(f"Click on menu : {menu_type}", end="")

        el.click()

        self.mylog(st="OK")

        # GESTION DU PARCOURS MULTICONTRATS
        if menu_type == "CONTRATS":
            time.sleep(2)
            contract_id = str(self.configuration[PARAM_VEOLIA_CONTRACT])
            self.click_in_view(
                By.LINK_TEXT,
                contract_id,
                wait_message=f"Select contract : {contract_id}",
                click_message="Click on contract",
                delay=0,
            )

        time.sleep(2)

        # Click Historique #####
        self.click_in_view(
            By.LINK_TEXT,
            "Historique",
            wait_message="Wait for historique menu",
            click_message="Click on historique menu",
            delay=4,
        )

        time.sleep(10)

        try:
            # Click Litres #####
            self.click_in_view(
                By.XPATH,
                r"//span[contains(text(), 'Litres')]/parent::node()",
                wait_message="Wait for button Litres",
                click_message="Click on button Litres",
                delay=2,
            )
        except selenium.common.exceptions.TimeoutException:
            self.mylog("Veolia bug, trying workaround", end="")
            self.click_in_view(
                By.XPATH,
                r"//a[contains(@class,'cICL_Tab')]"
                r"//span[contains(text(), 'Alertes de consommation')]"
                r"/parent::node()",
                wait_message="Wait Alertes de consommation",
                click_message="Click on Alertes de consommation",
                delay=2,
            )
            time.sleep(2)
            self.click_in_view(
                By.XPATH,
                r"//a[contains(@class,'cICL_Tab')]"
                r"//span[contains(text(), 'Historique')]/parent::node()",
                wait_message="Wait Historique",
                click_message="Click on Historique",
                delay=2,
            )
            time.sleep(2)
            self.click_in_view(
                By.XPATH,
                r"//span[contains(text(), 'Litres')]/parent::node()",
                wait_message="Wait for button Litres",
                click_message="Click on button Litres",
                delay=2,
            )

        time.sleep(2)

        # Click Jours #####
        self.click_in_view(
            By.XPATH,
            r"//span[contains(text(), 'Jours')]/parent::node()",
            wait_message="Wait for button Jours",
            click_message="Click on button Jours",
            delay=2,
        )

        time.sleep(2)
        # Click Telechargement #####
        self.click_in_view(
            By.XPATH,
            r'//button[contains(text(),"charger la p")]',
            wait_message="Wait for button Telechargement",
            click_message="Click on button Telechargement",
            delay=10,
        )

        self.mylog(
            f"Wait for end of download to '{v_file_glob}'",
            end="",
        )

        t = int(str(self.configuration[PARAM_TIMEOUT]))
        elapsed = 0
        while t > 0 and not glob.glob(v_file_glob):
            time.sleep(1)
            t -= 1
            elapsed += 1
            if elapsed < 2:
                # Do not try alternative until some time passed
                continue
            try:
                # For some reason (possibly Security setting),
                # the CSV file is not written to disk in Chrome 110.
                #
                # After the click on HISTORIQUE, the data is provided
                # in a hidden link as a data link.
                #
                # This code gets that data link, decodes it and saves
                # the data so that it is available at the expected
                # location.
                csvDataLink = self.__browser.find_element(
                    By.XPATH,
                    f"//a[@download='{self.download_veolia_filename}']",
                )
                data = csvDataLink.get_attribute("href")

                response = urllib.request.urlopen(data)  # nosec
                self.mylog(
                    f"Write '{v_file}'. ",
                    st="--",
                    end="",
                )
                with open(v_file, "wb") as f:
                    f.write(response.file.read())

            except Exception:
                pass

        found = glob.glob(v_file_glob)
        # Most recent first in list
        found.sort(key=os.path.getmtime, reverse=True)
        if found and os.path.exists(found[0]):
            self.mylog(st="OK")
            if found[0] != v_file:
                os.rename(found[0], v_file)
        else:
            self.get_screenshot("error.png")
            raise RuntimeError("File download timeout")

        if not self.configuration[PARAM_KEEP_OUTPUT]:
            self.files_to_cleanup.append(v_file)
        return v_file

    def get_gazpar_file(self):
        """
        Get consumption from GRDF for GazPar meter
        """
        # pylint: disable=too-many-locals
        g_file = self.__full_path_download_grdf_file

        if self.configuration[PARAM_SKIP_DOWNLOAD]:
            return g_file

        self.__browser.get(self.site_grdf_url)
        self.__wait.until(document_initialised)

        time.sleep(3)

        content: None | str = None
        isLoggedIn = False

        try:
            # If date_debut is present, likely already logged in
            date_debut_el = self.__browser.find_element(By.ID, "date-debut")
            if date_debut_el is not None:
                isLoggedIn = True
        except Exception:
            isLoggedIn = False

        if not isLoggedIn:
            # Check if there is a Cookies Consent popup deny button #####
            deny_btn = None
            try:
                deny_btn = self.__browser.find_element(
                    By.ID, "btn_option_deny_banner"
                )
            except Exception:
                pass

            if deny_btn is not None:
                self.click_in_view(
                    By.ID,
                    "btn_option_deny_banner",
                    wait_message="Waiting for cookie popup",
                    click_message="Click on deny",
                    delay=0,  # random.uniform(1, 2),
                )

            # Wait for Connexion #####
            self.mylog("Connexion au site GRDF", end="")

            self.__browser.get(self.__class__.site_grdf_url)
            self.mylog(st="OK")

            # Wait for Email #####
            self.mylog("Waiting for Email", end="")
            ep = EC.presence_of_element_located(
                (By.XPATH, r"//input[@name='identifier']")
            )
            el_email = self.__wait.until(
                ep,
                message="failed to locate email field, page timeout (timeout="
                + str(self.configuration[PARAM_TIMEOUT])
                + ")",
            )
            self.mylog(st="OK")

            # Type Email #####
            self.mylog("Type Email", end="")
            el_email.clear()
            el_email.send_keys(self.configuration[PARAM_GRDF_LOGIN])
            self.mylog(st="OK")

            # Try to click Next button to enter password
            try:
                self.click_in_view(
                    By.XPATH,
                    r"//input[@value='Suivant']",
                    # wait_message="",
                    click_message="Click on connexion",
                    delay=random.uniform(1, 2),
                )
                # Even if click succeeded, not always connected
            except Exception:
                pass

            # Wait for Password #####
            self.mylog("Waiting for Password", end="")

            ep = EC.presence_of_element_located(
                (By.XPATH, r"//input[@name='credentials.passcode']")
            )
            el_password = self.__wait.until(
                ep,
                message="failed, page timeout (timeout="
                + str(self.configuration[PARAM_TIMEOUT])
                + ")",
            )
            self.mylog(st="OK")

            # Type Password #####
            self.mylog("Type Password", end="")
            el_password.send_keys(self.configuration[PARAM_GRDF_PASSWORD])
            self.mylog(st="OK")

            # Some delay before clicking captcha
            # time.sleep(random.uniform(31.5, 33))
            # time.sleep(random.uniform(1.25, 3))

            # Give the user some time to resolve the captcha
            # FEAT: Wait until it disappears, use 2captcha if configured

            CONNEXION_XPATH = r"//input[@value='Se Connecter']"

            self.mylog("Proceed with captcha resolution. ", end="~~")
            if self.resolve_captcha2() is not None:
                # Some time for captcha to remove.
                self.mylog("Captcha resolution done. ", end="~~")
                time.sleep(2)
            else:
                # Manual
                time.sleep(0.33)

                # Not sure that click is needed for 2captcha
                clickRecaptcha = True
                if clickRecaptcha:
                    self.mylog("Clicking on the captcha button. ", end="~~")
                    self.__browser.switch_to.frame(0)
                    re_btn = self.__browser.find_element(
                        By.CLASS_NAME, "recaptcha-checkbox-border"
                    )
                    re_btn.click()
                    self.__browser.switch_to.default_content()

                    # Try to click connexion in case captcha worked.
                    try:
                        self.click_in_view(
                            By.XPATH,
                            CONNEXION_XPATH,
                            # wait_message="",
                            click_message="Click on connexion",
                            delay=random.uniform(1, 2),
                        )
                        # Even if click succeeded, not always connected
                    except Exception:
                        pass

                waitUntilConnexionGone = 2
                if self._use_display:
                    # Allow some some time to resolve captcha, and connect
                    self.mylog("Waiting 30 seconds for the user. ", end="~~")
                    waitUntilConnexionGone = 30
                else:
                    # Not using display, only wait a bit
                    self.mylog(
                        "Not using external display, proceed (delay 2s). ",
                        end="~~",
                    )

                try:
                    self.wait_until_disappeared(
                        By.XPATH,
                        CONNEXION_XPATH,
                        wait_message=None,
                        timeout=waitUntilConnexionGone,
                    )
                    # If button disappeared, then logged in
                    isLoggedIn = True
                except Exception:
                    pass

            self.__browser.switch_to.default_content()

            if self.configuration[PARAM_SCREENSHOT]:
                self.get_screenshot("screen_before_connection.png")

            if not isLoggedIn:
                try:
                    self.click_in_view(
                        By.XPATH,
                        CONNEXION_XPATH,
                        # wait_message="",
                        click_message="Click on connexion",
                        delay=random.uniform(1, 2),
                        timeout=2,
                    )
                    time.sleep(5)
                    self.mylog("End of wait after connexion. ", end="~~")
                except Exception:
                    # Already clicked or other error
                    pass

            # Get data from GRDF ############

            data_url = (
                # "view-source:"
                r"https://monespace.grdf.fr/api"
                r"/e-conso/pce/consommation/informatives"
                # r"/telecharger"
                # r"?dateDebut={}&dateFin={}&frequence=Journalier&pceList[]={}"
                r"?dateDebut={}&dateFin={}&pceList[]={}"
            ).format(
                (dt.datetime.now() - dt.timedelta(days=14)).strftime(
                    "%Y-%m-%d"
                ),
                dt.datetime.now().strftime("%Y-%m-%d"),
                self.configuration[PARAM_GRDF_PCE],
            )

            # Log URL while hiding personal information
            self.mylog(
                r"Get Data URL {}".format(
                    data_url
                    # .removesuffix(self.configuration[PARAM_GRDF_PCE])
                    # + "<PCE> . "
                ),
                end="~~",
            )

            # Next line would log without hiding data
            # self.mylog(r"Get Data URL {}".format(data_url), end="~~")
            # Go to the URL.
            dl_starttime = time.time()
            self.__browser.get(data_url)

            try:
                content = self.__browser.find_element(By.TAG_NAME, "pre").text
            except selenium.common.exceptions.NoSuchElementException:
                self.mylog("Get data url second time in 5 seconds", end="~~")
                time.sleep(5)
                self.__browser.get(data_url)

            self.mylog("Get Data Content. ", end="~~")
            # result = self.__browser.page_source
            try:
                content = self.__browser.find_element(By.TAG_NAME, "pre").text
            except selenium.common.exceptions.NoSuchElementException:
                msg = (
                    "<pre> Element not found."
                    " This may be due to an issue with the captcha resolution."
                    " Check the log for other errors and"
                    " check your captcha solver configuration"
                )
                content = None

                try:
                    filename = self.getDownloadedFileName(
                        int(self.configuration[PARAM_TIMEOUT])
                    )
                    if filename is None:
                        msg = f"No downloaded File. {msg}"
                    else:
                        f_mtime = os.path.getmtime(filename)
                        if f_mtime < dl_starttime:
                            msg = (
                                f"File {filename}@{f_mtime}"
                                f" older than {dl_starttime}. {msg}"
                            )
                        else:
                            self.mylog(f"Got {filename}", end="~~")
                            with open(filename, encoding="utf_8") as file:
                                content = file.read()
                except Exception as e:
                    msg = f"{e} {traceback.format_exc()}. {msg}"

            if content is None:
                self.mylog(msg, end="EE")
            # result = json.loads(content)
            # r=self.__browser.requests[-1:][0]
            # self.__browser(self.__browser.wait_for_request(r.path))
            # print(f"Url {data_url} -> R:{result!r}\n")

        if content is None:
            raise ValueError("No content")

        if not self.configuration[PARAM_KEEP_OUTPUT]:
            self.files_to_cleanup.append(g_file)

        with open(g_file, "w", encoding="utf_8") as grdf_file:
            # json.dump(result, grdf_file)
            self.mylog(f"Writing '{g_file}'. ", end="~~")
            grdf_file.write(content)

        return g_file


class Injector(Worker):
    WORKER_DESC = "Injector"

    def __init__(self, config_dict=None, super_print=None, use_display=False):
        super().__init__(
            config_dict=config_dict,
            super_print=super_print,
            use_display=use_display,
        )

    def sanity_check(self):
        pass

    def update_veolia_device(self, csv_file):
        raise NotImplementedError(f"{self.WORKER_DESC}/Veolia")

    def update_grdf_device(self, json_file):
        raise NotImplementedError(f"{self.WORKER_DESC}/GRDF")

    def veolia_to_dict(self, csv_file) -> dict[str, Any] | None:
        """
        Convert Veolia IDF meter data to dict.
        """

        # pylint: disable=too-many-locals
        self.mylog("Parsing csv file.")

        with open(csv_file, encoding="utf_8") as f:
            data: dict[str, Any] = {}

            rows = list(csv.reader(f, delimiter=";"))
            # List has at least two rows, the exception handles it.
            row = rows[-1]
            p_row = rows[-2]

            method = row[3]  # "Mesuré" or "Estimé"
            if method in ("Estimé",):
                self.mylog(f"File contains estimated data in last line: {row}")
                # Try previous row which may be a measurement
                row = p_row
                p_row = rows[-3]

            date = row[0][0:10]
            date_time = row[0]
            meter_total = row[1]
            meter_period_total = row[2]
            method = row[3]  # "Mesuré" or "Estimé"

            p_date_time = p_row[0]
            p_meter_total = p_row[1]
            p_meter_period_total = p_row[2]

            if method in ("Estimé",):
                self.mylog("    Skip Method " + method)
                # Do not use estimated values which may result
                # in a total that is not increasing
                # (when the estimated value is smaller than the
                #  previous real value or higher than the next
                #  real value)
                raise RuntimeError(
                    f"File contains estimated data in last lines: {row!r}"
                )

            # Check line integrity (Date starting with 2 (Year))
            if date[0] == "2":
                # Verify data integrity :
                d1 = datetime.strptime(date, "%Y-%m-%d")
                d2 = datetime.now()
                if abs((d2 - d1).days) > 30:
                    raise RuntimeError(
                        f"File contains too old data (monthly?!?): {row!r}"
                    )
                self.mylog(
                    f"    previous value  {p_date_time}: "
                    f"{p_meter_total}L - {p_meter_period_total}L",
                    end="",
                )
                self.mylog(
                    f"    update value is {date_time}: "
                    f"{meter_total}L - {meter_period_total}L",
                    end="",
                )

                data = {
                    "date_time": date_time,
                    "contract": self.configuration[PARAM_VEOLIA_CONTRACT],
                    "meter_total": meter_total,
                    "total_unit": "L",
                    "device_class": "water",
                    "daily_total": meter_period_total,
                    "daily_unit": "L",
                }

                return data
        return None


###############################################################################
# Object injects historical data into domoticz
###############################################################################
class DomoticzInjector(Injector):
    WORKER_DESC = "Domoticz"

    def __init__(self, config_dict, super_print, use_display=False):
        self.configuration = {
            # Mandatory config values
            PARAM_DOMOTICZ_VEOLIA_IDX: None,
            PARAM_DOMOTICZ_SERVER: None,
            # Needed for veolia only
            PARAM_VEOLIA_CONTRACT: PARAM_OPTIONAL_VALUE,
            # Optional config values
            PARAM_DOMOTICZ_LOGIN: "",
            PARAM_DOMOTICZ_PASSWORD: "",
            PARAM_TIMEOUT: "30",
            PARAM_INSECURE: False,
        }

        super().__init__(
            config_dict=config_dict,
            super_print=super_print,
            use_display=use_display,
        )
        self.revision: int = 0

    def open_url(self, uri, data=None):  # pylint: disable=unused-argument
        # Generate URL
        url = str(self.configuration[PARAM_DOMOTICZ_SERVER]) + uri

        # Add Authentication Items if needed
        if (
            self.configuration[PARAM_DOMOTICZ_LOGIN] != ""
            and self.configuration[PARAM_DOMOTICZ_PASSWORD] != ""
        ):
            http_auth = (
                self.configuration[PARAM_DOMOTICZ_LOGIN],
                self.configuration[PARAM_DOMOTICZ_PASSWORD],
            )

        else:
            http_auth = None

        try:
            response = requests.get(
                url,
                verify=not (self.configuration[PARAM_INSECURE]),
                auth=http_auth,
                timeout=30,
            )
        except Exception as e:
            # HANDLE CONNECTIVITY ERROR
            raise RuntimeError(f"url={url} : {e}")

        # HANDLE SERVER ERROR CODE
        if not response.status_code == 200:
            raise RuntimeError(
                "url="
                + url
                + " - (code = "
                + str(response.status_code)
                + ")\ncontent="
                + str(response.content)
            )

        try:
            j = json.loads(response.content.decode("utf_8"))
        except Exception as e:
            # Handle JSON ERROR
            raise RuntimeError(f"Unable to parse the JSON : {e}")

        if j["status"].lower() != "ok":
            raise RuntimeError(
                f"url={url}\n"
                f"response={response.status_code}\n"
                f"content={response.text}"
            )

        return j

    def sanity_check(self):
        self.mylog("Check domoticz connectivity", st="--", end="")
        response = self.open_url("/json.htm?type=command&param=getversion")
        if response["status"].lower() == "ok":
            self.mylog(st="OK")
            if "Revision" in response:
                self.revision = response["Revision"]
            else:
                result = re.findall(r"\(build (\d+)\)", response["version"])
                if len(result) > 0:
                    self.revision = int(result[0])
                else:
                    self.revision = 0

        rid = str(self.configuration[PARAM_DOMOTICZ_VEOLIA_IDX])
        if self.revision < 15457:
            url = f"/json.htm?type=devices&rid={rid}"
        else:
            url = f"/json.htm?type=command&param=getdevices&rid={rid}"

        self.mylog("Check domoticz Device", end="")
        # generate 2 urls, one for historique, one for update
        response = self.open_url(url)

        if "result" not in response:
            raise RuntimeError(
                "device "
                + str(self.configuration[PARAM_DOMOTICZ_VEOLIA_IDX])
                + " could not be found on domoticz server "
                + str(self.configuration[PARAM_DOMOTICZ_SERVER])
            )
        else:
            properly_configured = True
            dev_AddjValue = response["result"][0]["AddjValue"]
            dev_AddjValue2 = response["result"][0]["AddjValue2"]
            dev_SubType = response["result"][0]["SubType"]
            dev_Type = response["result"][0]["Type"]
            dev_SwitchTypeVal = response["result"][0]["SwitchTypeVal"]
            dev_Name = response["result"][0]["Name"]

            self.mylog(st="OK")

            # Retrieve Device Name
            self.mylog(
                '    Device Name            : "'
                + dev_Name
                + '" (idx='
                + self.configuration[PARAM_DOMOTICZ_VEOLIA_IDX]
                + ")",
                end="",
            )
            self.mylog(st="OK")

            # Checking Device Type
            self.mylog(f'    Device Type            : "{dev_Type}"', end="")
            if dev_Type == "General":
                self.mylog(st="OK")
            else:
                self.mylog(
                    "wrong sensor type. Go to Domoticz/Hardware"
                    ' - Create a pseudo-sensor type "Managed Counter"',
                    st="EE",
                )
                properly_configured = False

            # Checking device subtype
            self.mylog(f'    Device SubType         : "{dev_SubType}"', end="")
            if dev_SubType == "Managed Counter":
                self.mylog(st="OK")
            else:
                self.mylog(
                    "wrong sensor type. Go to Domoticz/Hardware"
                    ' - Create a pseudo-sensor type "Managed Counter"',
                    st="EE",
                )
                properly_configured = False

            # Checking for SwitchType
            self.mylog(
                f'    Device SwitchType      : "{dev_SwitchTypeVal}"',
                end="",
            )
            if dev_SwitchTypeVal == 2:
                self.mylog(st="OK")
            else:
                self.mylog(
                    "wrong switch type. Go to Domoticz"
                    " - Select your counter"
                    " - click edit"
                    " - change type to water",
                    st="EE",
                )
                properly_configured = False

            # Checking for Counter Divider
            self.mylog(
                f'    Device Counter Divided : "{dev_AddjValue2}"',
                end="",
            )
            if dev_AddjValue2 == 1000:
                self.mylog(st="OK")
            else:
                self.mylog(
                    "wrong counter divided. Go to Domoticz"
                    " - Select your counter"
                    " - click edit"
                    ' - set "Counter Divided" to 1000',
                    st="EE",
                )
                properly_configured = False

            # Checking Meter Offset
            self.mylog(
                f'    Device Meter Offset    : "{dev_AddjValue}"',
                end="",
            )
            if dev_AddjValue == 0:
                self.mylog(st="OK")
            else:
                self.mylog(
                    "wrong value for meter offset. Go to Domoticz"
                    " - Select your counter"
                    " - click edit"
                    ' - set "Meter Offset" to 0',
                    st="EE",
                )
                properly_configured = False

            if properly_configured is False:
                raise RuntimeError(
                    "Set your device correctly and run the script again"
                )

    def update_veolia_device(self, csv_file):
        self.mylog("Parsing veolia csv file")
        with open(csv_file, encoding="utf_8") as f:
            # Remove first line

            # Parse each line of the file.

            for row in list(csv.reader(f, delimiter=";")):
                date = row[0][0:10]
                date_time = row[0]
                counter = row[1]
                conso = row[2]
                method = row[3]  # "Mesuré" or "Estimé"

                if method in ("Estimé",):
                    # Do not use estimated values which may result
                    # in a total that is not increasing
                    # (when the estimated value is smaller than the
                    #  previous real value or higher than the next
                    #  real value)
                    continue

                # Check line integrity (Date starting by 2 or 1)
                if date[0] == "2" or date[0] == "1":
                    # Verify data integrity :
                    d1 = datetime.strptime(date, "%Y-%m-%d")
                    d2 = datetime.now()
                    if abs((d2 - d1).days) > 30:
                        raise RuntimeError(
                            "File contains too old data (monthly?!?): "
                            + str(row)
                        )

                    # Generate 3 URLs: historical, daily, current
                    url_args = {
                        "type": "command",
                        "param": "udevice",
                        "idx": self.configuration[PARAM_DOMOTICZ_VEOLIA_IDX],
                        "svalue": f"{counter};{conso};{date}",
                    }
                    url_historique = "/json.htm?" + urlencode(url_args)

                    # Daily
                    url_args["svalue"] = f"{counter};{conso};{date_time}"
                    url_daily = "/json.htm?" + urlencode(url_args)

                    # Current
                    url_args["nvalue"] = conso
                    url_current = "/json.htm?" + urlencode(url_args)

                    # Send historical data.
                    self.mylog(f"    update value for {date}", end="")
                    self.open_url(url_historique)
                    self.mylog(st="OK")

        # Update Dashboard
        if url_current:
            self.mylog("    update current value", end="")
            self.open_url(url_current)
            self.mylog(st="OK")

        if url_daily:
            self.mylog("    update daily value", end="")
            self.open_url(url_daily)
            self.mylog(st="OK")

    def update_grdf_device(self, json_file):
        raise NotImplementedError(f"{self.WORKER_DESC}/GRDF")

    def cleanup(self, keep_output=False):
        pass


class HomeAssistantInjector(Injector):
    WORKER_DESC = "Home Assistant"

    def __init__(self, config_dict, super_print, use_display=False):
        self.configuration = {
            # Mandatory config values
            PARAM_HA_SERVER: None,
            PARAM_HA_TOKEN: None,
            # Needed for veolia only
            PARAM_VEOLIA_CONTRACT: PARAM_OPTIONAL_VALUE,
            # Optional config values
            PARAM_TIMEOUT: "30",
            PARAM_INSECURE: False,
            STATE_FILE: PARAM_OPTIONAL_VALUE,
        }
        super().__init__(
            config_dict, super_print=super_print, use_display=use_display
        )

    def open_url(self, uri, data=None):
        """
        GET or POST (if data) request from Home Assistant API.
        """
        # Generate URL
        api_url = self.configuration[PARAM_HA_SERVER] + uri

        headers = {
            "Authorization": "Bearer {}".format(
                self.configuration[PARAM_HA_TOKEN]
            ),
            "Content-Type": "application/json",
        }

        try:
            if data is None:
                response = requests.get(
                    api_url,
                    headers=headers,
                    verify=not (self.configuration[PARAM_INSECURE]),
                    timeout=30,
                )
            else:
                response = requests.post(
                    api_url,
                    headers=headers,
                    json=data,
                    verify=not (self.configuration[PARAM_INSECURE]),
                    timeout=30,
                )
        except Exception as e:
            # HANDLE CONNECTIVITY ERROR
            raise RuntimeError(f"url={api_url} : {e}")

        # HANDLE SERVER ERROR CODE
        if response.status_code not in (200, 201):
            raise RuntimeError(
                "url=%s - (code = %u)\ncontent=%r)"
                % (
                    api_url,
                    response.status_code,
                    response.content,
                )
            )

        try:
            j = json.loads(response.content.decode("utf-8"))
        except Exception as e:
            # Handle JSON ERROR
            raise RuntimeError(f"Unable to parse JSON : {e}")

        return j

    def sanity_check(self):
        self.mylog("Check Home Assistant connectivity", st="--", end="")
        response = self.open_url("/api/")
        if response["message"] == "API running.":
            self.mylog(st="OK")
        else:
            self.mylog(st="EE")
            if "result" not in response:
                raise RuntimeError(
                    "No valid response '%s' from %s"
                    % (
                        response["message"],
                        self.configuration[PARAM_HA_SERVER],
                    )
                )

    def update_veolia_device(self, csv_file):
        """
        Inject Veolia Data into Home Assistant.
        """
        # pylint: disable=too-many-locals
        self.mylog("Parsing csv file")

        with open(csv_file, encoding="utf_8") as f:
            rows = list(csv.reader(f, delimiter=";"))
            # List has at least two rows, the exception handles it.
            row = rows[-1]
            p_row = rows[-2]

            method = row[3]  # "Mesuré" or "Estimé"
            if method in ("Estimé",):
                self.mylog(f"File contains estimated data in last line: {row}")
                # Try previous row which may be a measurement
                row = p_row
                p_row = rows[-3]

            date = row[0][0:10]
            date_time = row[0]
            meter_total = row[1]
            meter_period_total = row[2]
            method = row[3]  # "Mesuré" or "Estimé"

            p_date_time = p_row[0]
            p_meter_total = p_row[1]
            p_meter_period_total = p_row[2]

            if method in ("Estimé",):
                self.mylog("    Skip Method " + method)
                # Do not use estimated values which may result
                # in a total that is not increasing
                # (when the estimated value is smaller than the
                #  previous real value or higher than the next
                #  real value)
                raise RuntimeError(
                    f"File contains estimated data in last lines: {row!r}"
                )

            # Check line integrity (Date starting with 2 (Year))
            if date[0] == "2":
                # Verify data integrity :
                d1 = datetime.strptime(date, "%Y-%m-%d")
                d2 = datetime.now()
                if abs((d2 - d1).days) > 30:
                    raise RuntimeError(
                        f"File contains too old data (monthly?!?): {row!r}"
                    )
                self.mylog(
                    f"    previous value  {p_date_time}: "
                    f"{p_meter_total}L - {p_meter_period_total}L",
                    end="",
                )
                self.mylog(
                    f"    update value is {date_time}: "
                    f"{meter_total}L - {meter_period_total}L",
                    end="",
                )

                data = {
                    "state": meter_total,
                    "attributes": {
                        "date_time": date_time,
                        "unit_of_measurement": "L",
                        "device_class": "water",
                        "state_class": "total_increasing",
                    },
                }
                self.open_url(
                    HA_API_SENSOR_FORMAT
                    % (
                        "sensor.veolia_%s_total"
                        % (self.configuration[PARAM_VEOLIA_CONTRACT],),
                    ),
                    data,
                )
                data = {
                    "state": meter_period_total,
                    "attributes": {
                        "date_time": date_time,
                        "unit_of_measurement": "L",
                        "device_class": "water",
                        "state_class": "measurement",
                    },
                }
                self.open_url(
                    HA_API_SENSOR_FORMAT
                    % (
                        "sensor.veolia_%s_period_total"
                        % (self.configuration[PARAM_VEOLIA_CONTRACT],),
                    ),
                    data,
                )
                self.mylog(st="OK")

    def get_date_from_ha_state(self, response):
        if "date_time" in response["attributes"]:
            previous_date_str = response["attributes"]["date_time"]
        elif "last_changed" in response:
            previous_date_str = response["last_changed"]
        elif "last_updated" in response:
            previous_date_str = response["last_updated"]
        else:
            previous_date_str = None

        if previous_date_str is not None:
            previous_date = dt.datetime.fromisoformat(previous_date_str)
        else:
            previous_date = None
        return previous_date

    def update_grdf_device(self, json_file):
        """
        Inject Gazpar Data from GRDF into Home Assistant.
        """
        # pylint: disable=too-many-locals
        self.mylog("Parsing JSON file.")

        with open(json_file, encoding="utf_8") as f:
            data = json.load(f)

        pce = list(data.keys())[0]
        now_isostr = datetime.now(timezone.utc).isoformat()

        # M3 TOTAL
        sensor_name_generic_m3 = "sensor.gas_consumption_m3"
        sensor_name_pce_m3 = f"sensor.grdf_{pce}_m3"
        # KWH TOTAL
        sensor_name_generic_kwh = "sensor.gas_consumption_kwh"
        sensor_name_pce_kwh = f"sensor.grdf_{pce}_kwh"
        # DAILY SENSORS
        sensor_name_daily_generic_kwh = "sensor.gas_daily_kwh"
        sensor_name_daily_pce_kwh = f"sensor.grdf_{pce}_daily_kwh"

        # Response looks like:
        # {'entity_id': 'sensor.gas_consumption_kwh', 'state': '28657',
        #  'attributes': {
        #    'state_class': 'total_increasing',
        #    'unit_of_measurement': 'kWh',
        #    'device_class': 'energy', 'friendly_name': 'gas_consumption_kwh'},
        #  'last_changed': '2023-01-18T16:58:35.199786+00:00',
        #  'last_updated': '2023-01-18T16:58:35.199786+00:00',
        #  'context': {'id': '01GQ2X2VS69EDZMJ4RZ2T8E774',
        #              'parent_id': None, 'user_id': None}
        # }
        #
        # LOGGER.debug("%r", response)
        current_total_kWh: float = 0
        previous_date = datetime.now(timezone.utc) - dt.timedelta(days=7)

        previous_m3 = None
        previous_kWh = None

        entity_data = None

        # Get last known data - response looks as shown above
        #  - should load this before loading JSON to get maximum range of data.

        for sensor in (
            sensor_name_pce_kwh,
            sensor_name_generic_kwh,
        ):
            try:
                response = self.open_url(HA_API_SENSOR_FORMAT % (sensor,))
            except RuntimeError:
                response = None

            self.mylog(f"From {sensor}: {response!r}")

            if isinstance(response, dict) and "state" in response:
                entity_data = response
                previous_kWh = float(response["state"])
                if previous_kWh is not None:
                    try:
                        previous_kWh = float(previous_kWh)
                    except ValueError:
                        pass

                attributes = response["attributes"]
                if "meter_m3" in attributes:
                    try:
                        previous_m3 = float(attributes["meter_m3"])
                        rdate = self.get_date_from_ha_state(response)
                        if rdate is not None:
                            previous_date = rdate
                            self.mylog(
                                f"Previous HA date (kWh) {previous_date}"
                            )
                    except ValueError:
                        pass
                break

        # Get last known data now - from m3 sensor
        for m3_sensor in (
            sensor_name_pce_m3,
            sensor_name_generic_m3,
        ):
            if previous_m3 is not None:
                # m3 already known
                break

            # previous_m3 is None:
            try:
                sensor = m3_sensor
                response = self.open_url(
                    HA_API_SENSOR_FORMAT % (sensor_name_generic_m3,)
                )

                if isinstance(response, dict) and "state" in response:
                    previous_m3 = float(response["state"])
                    rdate = self.get_date_from_ha_state(response)
                    if rdate is not None:
                        previous_date = rdate
                        self.mylog(f"Previous date (m3) {previous_date}")
            except (ValueError, RuntimeError):
                sensor = "None"  # For log message just below

        if previous_kWh is None:
            state = get_state_file(self.configuration[STATE_FILE])
            if "grdf" in state:
                grdf_state = state["grdf"]
                self.mylog(f"grdf_state: {grdf_state!r}", "~~")
                previous_kWh = float(grdf_state["state"])
                previous_date_str = grdf_state["attributes"]["date_time"]
                previous_date = dt.datetime.fromisoformat(previous_date_str)
                if "m3" in grdf_state:
                    previous_m3 = float(grdf_state["m3"])

        self.mylog(
            f"Previous {previous_m3} m3 {previous_kWh} kWh {previous_date}"
            f" from {sensor}"
        )

        if previous_kWh is not None:
            current_total_kWh = previous_kWh

        # sys.exit()   # For debug
        date_time = None
        for row in data[pce]["releves"]:
            row_date = row["dateFinReleve"]
            row_date_time = dt.datetime.fromisoformat(row_date)
            row_data_qual = row[
                "qualificationReleve"
            ]  # "Informative Journalier"
            row_meter_kWh_day = row["energieConsomme"]
            row_meter_m3_endIndex = row["indexFin"]

            if row_data_qual != "Mesuré":
                # Known qualities:
                # - "Mesuré"
                # - "Absence de Données"
                #    -> Seems to be updated later, so wait for it.
                self.mylog(
                    f"    Got Quality '{row_data_qual}@{row_date}'"
                    " -> Wait until backlog retrieved"
                )
                break
                # continue

            if row_date_time > previous_date:
                # Sum daily kWh consumption
                # FEAT: May need to do more complex calculation
                # to cope with kWh rounding
                current_total_kWh += row_meter_kWh_day
                self.mylog(
                    f"New Total {current_total_kWh}kWh (+{row_meter_kWh_day})"
                )
            else:
                # Not new data, continue with next data
                continue

            if (date_time is not None) and (row_date_time < date_time):
                # Use the most recent data.
                continue

            if abs((row_date_time - datetime.now(timezone.utc)).days) > 30:
                raise RuntimeError(
                    f"File contains too old data (monthly?!?): {row}"
                )

            if previous_m3 is not None:
                if row_meter_m3_endIndex < previous_m3:
                    self.mylog(
                        f"New index {row_meter_m3_endIndex} m³"
                        f" ({row_date_time})"
                        " is lower"
                        f" than old index {previous_m3} m³ ({previous_date})."
                        " Error in source or old data - stopping",
                        st="EE",
                    )
                    break

            # Acceptable data
            date_time = row_date_time
            # date_type = row["indexFin"]  # "Informative Journalier"

            meter_m3_total = row_meter_m3_endIndex
            meter_kWh_day = row["energieConsomme"]

        # Has data (latest data)
        if date_time is None:
            self.mylog(
                "    No new data, no update",
                st="WW",
            )
            if entity_data is not None:
                if previous_m3 is not None:
                    entity_data["m3"] = previous_m3
                update_state_file(
                    self.configuration[STATE_FILE], {"grdf": entity_data}
                )
        else:
            self.mylog(
                f"    update value is {date_time.isoformat()}:"
                f" {meter_m3_total} m³ -"
                f" {current_total_kWh} kWh -"
                f" {meter_kWh_day} kWh",
                end="",
            )

            # M3 METER TOTAL
            entity_data = {
                "state": meter_m3_total,
                "attributes": {
                    "date_time": date_time.isoformat(),
                    "unit_of_measurement": "m³",
                    "device_class": "gas",
                    "state_class": "total_increasing",
                    "last_check": now_isostr,
                },
            }
            r = self.open_url(
                HA_API_SENSOR_FORMAT % (sensor_name_generic_m3,), entity_data
            )
            self.mylog(f"{r!r}")
            r = self.open_url(
                HA_API_SENSOR_FORMAT % (sensor_name_pce_m3,), entity_data
            )
            self.mylog(f"{r!r}")

            # kWh Daily
            entity_data = {
                "state": meter_kWh_day,
                "attributes": {
                    "date_time": date_time.isoformat(),
                    "unit_of_measurement": "kWh",
                    "device_class": "energy",
                    "state_class": "measurement",
                    "last_check": now_isostr,
                },
            }

            r = self.open_url(
                HA_API_SENSOR_FORMAT % (sensor_name_daily_generic_kwh,),
                entity_data,
            )
            self.mylog(f"{r!r}")

            r = self.open_url(
                HA_API_SENSOR_FORMAT % (sensor_name_daily_pce_kwh,),
                entity_data,
            )
            self.mylog(f"{r!r}")

            # Total kWh
            entity_data = {
                "state": current_total_kWh,
                "attributes": {
                    "date_time": date_time.isoformat(),
                    "unit_of_measurement": "kWh",
                    "device_class": "energy",
                    "state_class": "total_increasing",
                    "last_check": now_isostr,
                },
            }

            r = self.open_url(
                HA_API_SENSOR_FORMAT % (sensor_name_generic_kwh,), entity_data
            )

            # Store state to local file to cope with HA restart
            entity_data["m3"] = meter_m3_total
            update_state_file(
                self.configuration[STATE_FILE], {"grdf": entity_data}
            )

            self.mylog(f"{r!r}")
            r = self.open_url(
                HA_API_SENSOR_FORMAT % (sensor_name_pce_kwh,), entity_data
            )
            self.mylog(f"{r!r}")

            self.mylog(st="OK")

    def cleanup(self, keep_output=False):
        pass


class MqttInjector(Injector):
    WORKER_DESC = "MQTT"

    def __init__(self, config_dict, super_print, use_display=False):
        self.configuration = {
            # Mandatory config values
            PARAM_URL: None,
            # Needed for veolia only (to do: add to request as parameter)
            PARAM_VEOLIA_CONTRACT: PARAM_OPTIONAL_VALUE,
            PARAM_MQTT_SERVER: None,
            PARAM_MQTT_LOGIN: None,
            PARAM_MQTT_PASSWORD: None,
            PARAM_MQTT_PORT: None,
            # Optional config values
            PARAM_TIMEOUT: "30",
            PARAM_INSECURE: False,
        }
        super().__init__(
            config_dict, super_print=super_print, use_display=use_display
        )

    def sanity_check(self):
        pass

    def update_veolia_device(self, csv_file):
        # pylint:disable=import-outside-toplevel

        import paho.mqtt.client as mqtt
        from paho.mqtt import publish

        data = self.veolia_to_dict(csv_file)

        if data is not None:
            state_topic = f"veolia/{data['contract']}/last_data"
            mqtt_server = self.configuration[PARAM_MQTT_SERVER]
            mqtt_port = int(self.configuration[PARAM_MQTT_PORT])
            mqtt_login = self.configuration[PARAM_MQTT_LOGIN]
            mqtt_password = self.configuration[PARAM_MQTT_PASSWORD]
            auth: publish.AuthParameter = {
                "username": mqtt_login,
                "password": mqtt_password,
            }
            # tls_dict= {'ca_certs':"<ca_certs>", 'certfile':"<certfile>",
            #            'keyfile':"<keyfile>", 'tls_version':"<tls_version>",
            #            'ciphers':"<ciphers">}
            tls_dict = None
            # will =  {'topic': "<topic>", 'payload':"<payload">,
            #          'qos':<qos>, 'retain':<retain>}

            self.mylog(
                f"MQTT Publish {mqtt_server}:{mqtt_port} {auth} {data!r}"
            )

            publish.single(
                state_topic,
                payload=json.dumps(data),
                qos=0,
                retain=True,  # Retain this data as a state
                hostname=mqtt_server,
                port=mqtt_port,
                # will=will,
                auth=auth,
                keepalive=60,
                client_id="",
                tls=tls_dict,
                protocol=mqtt.MQTTv311,
                transport="tcp",
            )

    def update_grdf_device(self, json_file):
        # pylint:disable=import-outside-toplevel
        data = {}
        import paho.mqtt.client as mqtt
        from paho.mqtt import publish

        # data = self.veolia_to_dict(json_file)
        with open(json_file, encoding="utf_8") as f:
            data = json.load(f)

        if len(data) > 0:
            pce = list(data.keys())[0]
            data = data[pce]["releves"][-1]
            self.mylog(f"MQTT GRDF data: {data}")
        else:
            self.mylog("MQTT GRDF data: No JSON data in reply")

        if data is not None:
            state_topic = f"grdf/{pce}/last_data"
            mqtt_server = self.configuration[PARAM_MQTT_SERVER]
            mqtt_port = int(self.configuration[PARAM_MQTT_PORT])
            mqtt_login = self.configuration[PARAM_MQTT_LOGIN]
            mqtt_password = self.configuration[PARAM_MQTT_PASSWORD]
            auth: publish.AuthParameter = {
                "username": mqtt_login,
                "password": mqtt_password,
            }
            # tls_dict= {'ca_certs':"<ca_certs>", 'certfile':"<certfile>",
            #            'keyfile':"<keyfile>", 'tls_version':"<tls_version>",
            #            'ciphers':"<ciphers">}
            tls_dict = None
            # will =  {'topic': "<topic>", 'payload':"<payload">,
            #          'qos':<qos>, 'retain':<retain>}

            self.mylog(
                f"MQTT GRDF Publish {mqtt_server}:{mqtt_port} {auth} {data!r}"
            )
            data_out: dict[str, Any] = {}
            data_out = {
                "period_start_datetime": data.get("dateDebutReleve", None),
                "period_end_datetime": data.get("dateFinReleve", None),
                "period_start_date": data.get("journeeGaziere", None),
                "index_period_start_m3": data.get("indexDebut", None),
                "index_period_end_m3": data.get("indexFin", None),
                "volume_period_m3": data.get("volumeBrutConsomme", None),
                "energy_period_kWh": data.get("energieConsomme", None),
                "conversion_coefficient": data.get("coeffConversion", None),
                "status": data.get("status", None),
            }

            publish.single(
                state_topic,
                payload=json.dumps(data_out),
                qos=0,
                retain=True,  # Retain this data as a state
                hostname=mqtt_server,
                port=mqtt_port,
                # will=will,
                auth=auth,
                keepalive=60,
                client_id="",
                tls=tls_dict,
                protocol=mqtt.MQTTv311,
                transport="tcp",
            )

    def cleanup(self, keep_output=False):
        pass


class UrlInjector(Injector):
    WORKER_DESC = "URL Destination"

    def __init__(self, config_dict, super_print, use_display=False):
        self.configuration = {
            # Mandatory config values
            PARAM_URL: None,
            # Needed for veolia only (to do: add to request as parameter)
            PARAM_VEOLIA_CONTRACT: PARAM_OPTIONAL_VALUE,
            # Optional config values
            PARAM_TIMEOUT: "30",
            PARAM_INSECURE: False,
        }
        super().__init__(
            config_dict, super_print=super_print, use_display=use_display
        )

    def open_url(self, api_url, data=None, content_type=None):
        """
        Write to file or POST request.
        """
        # Generate URL
        api_url = self.configuration[PARAM_URL]

        headers: dict[str, str] = {}

        if content_type is not None:
            headers["Content-Type"] = content_type

        parsed_url = urlparse(api_url)

        if parsed_url.scheme == "file":
            try:
                file_path = parsed_url.netloc + parsed_url.path
                # Save data to file given by path
                with open(file_path, "wb") as f:
                    f.write(data)
            except Exception as e:
                raise RuntimeError(f"url={api_url} - {file_path} : {e}")

        elif parsed_url.scheme in ("https", "http"):
            try:
                response = requests.post(
                    api_url,
                    headers=headers,
                    data=data,
                    verify=not (self.configuration[PARAM_INSECURE]),
                    timeout=30,
                )
            except Exception as e:
                # HANDLE CONNECTIVITY ERROR
                raise RuntimeError(f"url={api_url} : {e}")

            # HANDLE SERVER ERROR CODE
            if response.status_code not in (200, 201):
                raise RuntimeError(
                    "url=%s - (code = %u)\ncontent=%r)"
                    % (
                        api_url,
                        response.status_code,
                        response.content,
                    )
                )

    def sanity_check(self):
        api_url = self.configuration[PARAM_URL]
        parsed_url = urlparse(api_url)

        self.mylog("Check Destination Url", st="--", end="")
        if parsed_url.scheme == "file":
            # Save data to file given by path
            file_path = parsed_url.netloc + parsed_url.path
            if check_file_writable(file_path):
                self.mylog(st="OK")
            else:
                self.mylog(st="EE")
                raise RuntimeError(
                    f"Can not write to {file_path} (check path and rights)"
                )
        elif parsed_url.scheme in ("https", "http"):
            # Note: Maybe check if url is accessible
            pass
        else:
            raise RuntimeError(f"Unsupported URL scheme {parsed_url.scheme}")

    def update_veolia_device(self, csv_file):
        with open(csv_file, "rb") as f:
            self.open_url(
                self.configuration[PARAM_URL],
                data=f.read(),
                content_type="text/csv",
            )

    def update_grdf_device(self, json_file):
        with open(json_file, "rb") as f:
            self.open_url(
                self.configuration[PARAM_URL],
                data=f.read(),
                content_type="application/json",
            )

    def cleanup(self, keep_output=False):
        pass


def exit_on_error(
    workers: list[Worker] | None = None,
    string="",
    use_display=False,
    o: Output | None = None,
):
    if o is None:
        print(string)
    else:
        o.mylog(string, st="EE")

    if workers is not None:
        for w in workers:
            if w is not None:
                w.cleanup(use_display)

    if o is None:
        print(
            "Ended with error%s"
            % (
                ""
                if use_display
                else " : // re-run with '--display' option if you can",
            )
        )
    else:
        o.mylog(
            "Ended with error%s"
            % (
                ""
                if use_display
                else " : // re-run with '--display' option if you can",
            ),
            st="EE",
        )
    print(traceback.format_exc())
    # raise Exception
    sys.exit(2)


def get_state_file(file):
    try:
        with open(file, encoding="utf_8") as state_file:
            state = json.load(state_file)
    except json.JSONDecodeError:  # as e:
        # self.mylog(f"JSON format error : {e}", "EE")
        pass
    except Exception:
        # self.mylog("No previous state available", "~~")
        pass
    else:
        return state
    return {}


def update_state_file(file, data):
    LOGGER.info(f"Get_state_file {file} {data!r}")
    state = get_state_file(file)
    # Add CLI arguments to the configuration (CLI has precedence)
    state.update(data)

    try:
        with open(file, "w", encoding="utf_8") as state_file:
            state_file.write(json.dumps(state, indent=2))
    except Exception:  # as _e:
        # self.mylog(f"Could not write state to {file}: {e}", "EE")
        pass


def check_new_script_version(o):
    # FEAT: Check only if not running in HAOS (AppDaemon) instance
    #       Maybe with env variable?
    o.mylog("Check script version is up to date", end="")
    try:
        http = urllib3.PoolManager()
        user_agent = {"user-agent": "meters_to_ha - " + VERSION}
        r = http.request(
            "GET",
            f"https://api.github.com/repos/{REPO_BASE}/releases/latest",
            headers=user_agent,
        )
        j = json.loads(r.data.decode("utf-8"))
    except Exception:
        raise
    else:
        if j["tag_name"] > VERSION:
            o.mylog(
                f'New version "{j["name"]}"({j["tag_name"]}) available.'
                f"Check : https://github.com/{REPO_BASE}/releases/latest",
                st="WW",
            )
        else:
            o.mylog(st="OK")


def doWork():
    # pylint:disable=too-many-locals
    # Default config value
    script_dir = os.path.dirname(os.path.realpath(__file__)) + os.path.sep
    default_logfolder = script_dir
    default_configuration_file = script_dir + "config.json"
    workers: list[Worker] = []

    # COMMAND LINE OPTIONS
    parser = argparse.ArgumentParser(
        description=(
            "Load water or gas meter data into Home Automation System\n"
            "Sources: Veolia Ile de France, GRDF\n"
            "Home Automation:  Domiticz or Home Assistant"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument(
        "--version-check",
        action="store_true",
        help="Perform a version check @github",
    )
    parser.add_argument(
        "--veolia",
        action="store_true",
        help="Query Veolia IDF",
    )
    parser.add_argument(
        "--grdf",
        action="store_true",
        help="Query GRDF",
    )
    parser.add_argument(
        "--display",
        action="store_true",
        help="active graphical display mode (only for troubleshooting)",
    )
    parser.add_argument(
        "--screenshot",
        action="store_true",
        help="Take screenshot(s) (for troubleshooting)",
    )
    parser.add_argument(
        "--local-config",
        action="store_true",
        help="Local configuration directory for browser",
    )
    parser.add_argument(
        "-l",
        "--logs-folder",
        help=f"specify the logs location folder ({default_logfolder})",
        default=default_logfolder,
        nargs=1,
    )
    parser.add_argument(
        "-c",
        "--config",
        help="specify configuration location ("
        + default_configuration_file
        + ")",
        default=default_configuration_file,
        nargs=1,
    )
    parser.add_argument(
        "-r",
        "--run",
        action="store_true",
        help="run the script",
        required=True,
    )
    parser.add_argument(
        "-k",
        "--keep-output",
        action="store_true",
        help="Keep the downloaded files",
        required=False,
    )
    parser.add_argument(
        "--keep_csv",
        action="store_true",
        help="Keep the downloaded CSV file (Deprecated, use --keep-output)",
        required=False,
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Ignore invalid and self-signed certificate checks"
        " (ignore SSL issues)",
        required=False,
    )
    parser.add_argument(
        "--server-type",
        help="""
            Type of destination
            'dom'  Domoticz
            'ha'   Home Assistant
            'url'  Local file or http/https (content is posted)
            """,
        # formatter_class=argparse.RawTextHelpFormatter,
        required=False,
    )
    parser.add_argument(
        "--url",
        help="Url when destination is 'url' (file://..., http(s)://...)",
        required=False,
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip downloading file from web, use local file",
    )
    parser.add_argument(
        "--chrome-version",
        help="When using undetected-chromedriver, "
        "version to use in case of error "
        "'This version of ChromeDriver only supports Chrome version ...'",
        required=False,
        nargs=1,
        type=int,
    )
    args = parser.parse_args()

    # Deprecated keep_csv, but still use its value
    # Also keep the file if download is skipped
    args.keep_output = args.keep_output or args.keep_csv or args.skip_download
    if args.logs_folder is not None:
        args.logs_folder = str(args.logs_folder).strip("[]'")
    if args.chrome_version is not None:
        args.chrome_version = args.chrome_version[0]

    install_dir = os.path.dirname(os.path.realpath(__file__))

    # Init output
    try:
        d = {PARAM_LOGS_FOLDER: args.logs_folder, INSTALL_DIR: install_dir}
        o = Output(d, use_display=args.display)
    except Exception as exc:
        exit_on_error(string=f"Init output - {exc}", use_display=args.display)

    # Print debug message
    if args.display:
        o.mylog("DISPLAY DEBUG MODE ACTIVATED", end="")
        o.mylog("Only use '--display' with X Server display", st="WW")

    # New version checking
    if args.version_check:
        try:
            check_new_script_version(o)
        except Exception as exc:
            exit_on_error(string=str(exc), use_display=args.display, o=o)

    # Load configuration
    try:
        c = Configuration(use_display=args.display, super_print=o.mylog)
        configuration_json = c.load_configuration_file(
            str(args.config).strip("[]'")
        )
        configuration_json[PARAM_LOGS_FOLDER] = str(args.logs_folder).strip(
            "[]'"
        )
    except Exception as exc:
        exit_on_error(string=str(exc), use_display=args.display, o=o)

    configuration_json.update({INSTALL_DIR: install_dir})
    if PARAM_DOWNLOAD_FOLDER not in configuration_json:
        configuration_json.update({PARAM_DOWNLOAD_FOLDER: install_dir})

    # When neither veolia nor grdf is set,
    #  get all those that are in the configuration
    isGetAvailable = not (args.veolia or args.grdf)

    if isGetAvailable:
        if configuration_json.get(PARAM_VEOLIA_CONTRACT) is not None:
            args.veolia = True
        if configuration_json.get(PARAM_GRDF_PCE) is not None:
            args.grdf = True

    if not (args.grdf or args.veolia):
        exit_on_error(
            string="Must select/configure at least one contract",
            use_display=args.display,
        )

    # Add CLI arguments to the configuration (CLI has precedence)
    # Also include update to veolia/grdf options.
    configuration_json.update(vars(args))

    configuration_json.update({INSTALL_DIR: install_dir})

    if args.server_type is not None:
        configuration_json.update({PARAM_SERVER_TYPE: args.server_type})
    if args.url is not None:
        configuration_json.update({PARAM_URL: args.url})

    configuration_json.update(
        {
            STATE_FILE: os.path.join(
                configuration_json[PARAM_DOWNLOAD_FOLDER],
                "meters2ha_state.json",
            )
        }
    )

    # Create objects
    try:
        crawler = ServiceCrawler(
            configuration_json,
            super_print=o.mylog,
            use_display=args.display,
            local_config=args.local_config,
        )
        workers.append(crawler)
        server_type = configuration_json.get(PARAM_SERVER_TYPE, None)
        injector: Injector
        if server_type == "ha":
            injector = HomeAssistantInjector(
                configuration_json,
                super_print=o.mylog,
                use_display=args.display,
            )
            workers.append(injector)
        elif server_type == "url":
            injector = UrlInjector(
                configuration_json,
                super_print=o.mylog,
                use_display=args.display,
            )
            workers.append(injector)
        elif server_type == "mqtt":
            injector = MqttInjector(
                configuration_json,
                super_print=o.mylog,
                use_display=args.display,
            )
            workers.append(injector)
        else:
            injector = DomoticzInjector(
                configuration_json,
                super_print=o.mylog,
                use_display=args.display,
            )
            workers.append(injector)
    except Exception as exc:
        exit_on_error(string=str(exc), use_display=args.display, o=o)

    # Check requirements
    try:
        crawler.sanity_check()
        injector.sanity_check()
        crawler.init()

    except Exception as exc:
        exit_on_error(workers, str(exc), use_display=args.display, o=o)

    # Do actual work

    if args.grdf:
        try:
            # Get data
            try:
                gazpar_file = crawler.get_gazpar_file()
            except Exception:
                exc_info = " - ".join(traceback.format_exc().splitlines())
                # Retry once on failure to manage stalement
                # exception that occurs sometimes
                o.mylog(exc_info, st="WW")
                o.mylog(
                    "Encountered error -> Retrying once",
                    st="WW",
                )
                gazpar_file = crawler.get_gazpar_file()

            # Inject data
            injector.update_grdf_device(gazpar_file)

        except Exception as exc:
            exit_on_error(workers, str(exc), use_display=args.display, o=o)

    if args.veolia:
        try:
            try:
                veolia_idf_file = crawler.get_veolia_idf_file()
                # veolia_idf_file = "./veolia_test_data.csv"
            except Exception:
                exc_info = " - ".join(traceback.format_exc().splitlines())
                o.mylog(exc_info, st="WW")

                try:
                    if configuration_json[PARAM_SCREENSHOT]:
                        crawler.get_screenshot("screen_on_exception1.png")
                except Exception:
                    pass

                # Retry once on failure to manage
                # stalement exception that occurs sometimes
                o.mylog(
                    "Encountered error -> Retrying once",
                    st="WW",
                )
                veolia_idf_file = crawler.get_veolia_idf_file()

            injector.update_veolia_device(veolia_idf_file)
        except Exception as exc:
            try:
                if configuration_json[PARAM_SCREENSHOT]:
                    crawler.get_screenshot("screen_on_exception2.png", True)
            except Exception:
                pass

            exit_on_error(workers, str(exc), use_display=args.display, o=o)

    o.mylog("Finished on success, cleaning up", st="OK")

    for w in workers:
        w.cleanup(keep_output=args.keep_output)

    sys.exit(0)


if __name__ == "__main__":
    doWork()
