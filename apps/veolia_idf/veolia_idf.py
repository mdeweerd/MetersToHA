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
import sys

import adbase as ad  # pylint: disable=import-error
import hassapi as hass


class VeoliaIDF(hass.Hass):
    def initialize(self):
        self.listen_event(  # pylint: disable=no-member
            self.call_veolia_idf, "call_veolia"
        )

    @ad.app_lock
    def call_veolia_idf(self, *args, **kwargs):  # pylint: disable=unused-argument
        self.log("Start VEOLIA-IDF", level="INFO")  # pylint: disable=no-member
        try:
            if "script" in self.args:  # pylint: disable=no-member
                script = self.args["script"]  # pylint: disable=no-member
            else:
                mydir = os.path.dirname(os.path.realpath(__file__))
                script = os.path.join(mydir, "veolia-idf-domoticz.py")
            script_args = ["python3", script, "-r"]
            if "config_file" in self.args:  # pylint: disable=no-member
                cfg = self.args["config_file"]  # pylint: disable=no-member
                script_args.append("-c")
                script_args.append(str(cfg))
            if "log_folder" in self.args:  # pylint: disable=no-member
                log_folder = self.args["log_folder"]  # pylint: disable=no-member
                script_args.append("-l")
                script_args.append(str(log_folder))
            if (
                "keep_csv" in self.args and self.args["keep_csv"]  # pylint: disable=no-member
            ):
                script_args.append("--keep_csv")
            if (
                "debug_veolia" in self.args and self.args["debug_veolia"]  # pylint: disable=no-member
            ):
                script_args.append("--debug")
            if (
                "DISPLAY" in self.args and self.args["DISPLAY"]  # pylint: disable=no-member
            ):
                os.environ["DISPLAY"] = self.args[  # pylint: disable=no-member
                    "DISPLAY"
                ]

            out = sys.stdout
            err = sys.stderr
            closeout = False
            closeerr = False

            if "outfile" in self.args:  # pylint: disable=no-member
                out = open(self.args["outfile"], "w", encoding="utf_8")  # pylint: disable=no-member
                closeout = True
            if "errfile" in self.args:  # pylint: disable=no-member
                err = open(self.args["errfile"], "w", encoding="utf_8")  # pylint: disable=no-member
                closeerr = True

            self.log(f"Execute {script_args!r}", level="INFO")   # pylint: disable=no-member
            s.call(script_args, stdout=out, stderr=err)

            # Close files as needed
            if closeout:
                out.close()
            if closeerr:
                err.close()
        except Exception as e:
            self.log(f"{e!r}", level="ERROR")  # pylint: disable=no-member
        finally:
            self.log("Done veolia", level="INFO")  # pylint: disable=no-member
