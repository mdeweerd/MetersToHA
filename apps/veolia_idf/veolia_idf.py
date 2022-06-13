#
# veolia_idf - Home Assistant AppDaemon Class
#
# Author: https://github.com/mdeweerd
#
# License: GNU General Public License V3
#
#

"""
Module for use with AppDaemon on Home Assistant
"""
import os
import subprocess as s

import adbase as ad
import hassapi as hass


class VeoliaIDF(hass.Hass):
    def initialize(self):
        self.listen_event(self.call_veolia_idf, "call_veolia")

    @ad.app_lock
    def call_veolia_idf(self, *args, **kwargs):  # pylint: disable=unused-argument
        if "script" in self.args:
            script = self.args["script"]
        else:
            mydir = os.path.dirname(os.path.realpath(__file__))
            script = os.path.join(mydir, "veolia-idf-domoticz.py")
        script_args = [ "python3", script, "-r" ]
        if "config_file" in self.args:
            cfg = self.args["config_file"]
            script_args.append("-c")
            script_args.append(str(cfg))
        if "log_folder" in self.args:
            log_folder = self.args["log_folder"]
            script_args.append("-l")
            script_args.append(str(log_folder))
        if "keep_csv" in self.args and self.args["keep_csv"]:
            script_args.append("--keep_csv")

        s.call(script_args)
