#
# MetersToHA - Home Assistant AppDaemon Class
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

METERS_TO_HA_SCRIPT = "meters_to_ha.py"


# pylint: disable=no-member
class MetersToHA(hass.Hass):
    def initialize(self):
        if "event_name" in self.args:
            event_name = self.args["event_name"]
        else:
            event_name = "call_meters_to_ha"

        self.log(f"Initialise {self.args!r} {event_name}", level="INFO")

        self.listen_event(self.call_meters_to_ha, event_name)

    @ad.app_lock
    def call_meters_to_ha(
        self, *args, **kwargs
    ):  # pylint: disable=unused-argument
        self.log("Start MetersToHA", level="INFO")
        try:
            if "script" in self.args:
                script = self.args["script"]
            else:
                mydir = os.path.dirname(os.path.realpath(__file__))
                script = os.path.join(mydir, METERS_TO_HA_SCRIPT)

            trace = False
            if "trace" in self.args:
                # Get truthy value of argument
                trace = bool(self.args["trace"])

            if not trace:
                # Standard execution
                script_args = ["python3", script, "-r"]
            else:
                # Enable detailed trace
                script_args = [
                    "python3",
                    "-m",
                    "trace",
                    "--ignore-dir=/usr/lib",
                    "-t",
                    script,
                    "-r",
                ]

            if "config_file" in self.args:
                cfg = self.args["config_file"]
                script_args.append("-c")
                script_args.append(str(cfg))
            if "log_folder" in self.args:
                log_folder = self.args["log_folder"]
                script_args.append("-l")
                script_args.append(str(log_folder))
            if ("keep_output" in self.args and self.args["keep_output"]) or (
                "keep_csv" in self.args and self.args["keep_csv"]
            ):
                script_args.append("--keep-output")
            if "debug" in self.args and self.args["debug"]:
                script_args.append("--debug")
            if "DISPLAY" in self.args and self.args["DISPLAY"]:
                os.environ["DISPLAY"] = self.args["DISPLAY"]
            if "extra_opts" in self.args and isinstance(
                self.args["extra_opts"], list
            ):
                script_args.extend(self.args["extra_opts"])

            out = sys.stdout
            err = sys.stderr
            closeout = False
            closeerr = False

            if "outfile" in self.args:
                out = open(self.args["outfile"], "w", encoding="utf_8")
                closeout = True
            if "errfile" in self.args:
                err = open(self.args["errfile"], "w", encoding="utf_8")
                closeerr = True

            self.log(f"Execute {script_args!r}", level="INFO")
            s.run(
                script_args, stdout=out, stderr=err, timeout=300, check=False
            )

            # Close files as needed
            if closeout:
                out.close()
            if closeerr:
                err.close()
        except Exception as e:
            self.log(f"{e!r}", level="ERROR")
        finally:
            self.log("Done MetersToHA", level="INFO")
