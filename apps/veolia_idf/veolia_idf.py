import hassapi as hass
import os
import subprocess as s
import adbase as ad


class VeoliaIDF(hass.Hass):
    def initialize(self):
        self.listen_event(self.call_veolia_idf, "call_veolia")

    @ad.app_lock
    def call_veolia_idf(self, *args, **kwargs):
        if "script" in self.args:
            script = self.args["script"]
        else:
            mydir = os.path.dirname(os.path.realpath(__file__))
            script = os.path.join(mydir, "veolia-idf-domoticz.py")
        script_args = [ script, "-r" ]
        if "config_file" in self.args:
            cfg = self.args["config_file"]
            script_args.append("-c")
            script_args.append(str(cfg))
        if "log_folder" in self.args:
            log_folder = self.args["log_folder"]
            script_args.append("-l")
            script_args.append(str(log_folder))

        s.call(script_args)
