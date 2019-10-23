#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
@author: s0nik42
"""
# veolia-idf
# Copyright (C) 2019 Julien NOEL
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
#
VERSION="v1.0"
################################################################################
# SCRIPT DEPENDENCIES 
################################################################################

try:
    import argparse
    import base64
    from   colorama import Fore, Style
    import csv
    import getopt
    import http.cookiejar
    import json
    import logging
    from   logging.handlers import RotatingFileHandler
    import os
    from   pyvirtualdisplay import Display  
    import re
    from   selenium import webdriver
    from   selenium.webdriver.common.desired_capabilities import DesiredCapabilities
    from   selenium.webdriver.common.by import By
    import selenium.webdriver.firefox
    from   selenium.webdriver.firefox.options import Options
    from   selenium.webdriver.firefox.firefox_binary import FirefoxBinary
    from   selenium.webdriver.support.ui import WebDriverWait
    from   selenium.webdriver.support import expected_conditions as EC
    from   shutil import which
    import signal
    import subprocess
    import sys
    import time
    import urllib3
    from   urllib.parse import urlencode
except ImportError as e:
    print("Error: failed to import python required module : " + str(e), file=sys.stderr)
    sys.exit(2)

################################################################################
# Output Class in charge of managing all script output to file or console
################################################################################
class Output():
    def __init__(self, logfile, debug = False):
        self.__debug = debug
        self.__logger = logging.getLogger()
        self.__print_buffer=""

        # By default log to console
        self.print      = self.__print_to_console

        # In standard mode log to a file
        if self.__debug is False:
            # Check if we can create logfile
            try:
                f = open(logfile, "a+").close()
            except Exception as e:
                raise RuntimeError('"' + logfile + '" ' + e.strerror)

            # Set the logfile format
            file_handler = RotatingFileHandler(logfile, 'a', 1000000, 1)
            formatter = logging.Formatter('%(asctime)s : %(message)s')
            file_handler.setFormatter(formatter)
            self.__logger.setLevel(logging.INFO)
            self.__logger.addHandler(file_handler)
            self.print = self.__print_to_logfile
        pass

    def __print_to_console(self, string="", st=None, end=None):
        if st:
            st = st.upper()
            st = st.replace("OK", Fore.GREEN + "OK")
            st = st.replace("WW", Fore.YELLOW + "WW")
            st = st.replace("EE", Fore.RED + "EE")
            st = "[" + st + Style.RESET_ALL + "] "
        
        if end != None:
            st = st + " " if st else ""
            print(st + "{:75s}".format(string), end="", flush=True)
            self.__print_buffer=self.__print_buffer + string
        elif self.__print_buffer:
            st = st if st else "[--] "
            print(st + string.rstrip())
            self.__print_buffer=""
        else:
            st = st if st else "[--]"
            print(("{:75s}" + st).format(string.rstrip()))
            self.__print_buffer=""
        pass

    def __print_to_logfile(self, string="", st=None, end=None):
        if end != None:
            self.__print_buffer=self.__print_buffer + string
        else:
            st = st if st else "--"
            self.__logger.info(st.upper() + " : " + (self.__print_buffer.lstrip().rstrip() + " " + string.lstrip().rstrip()).lstrip())
            self.__print_buffer=""
        pass
        
    def print():
        pass

################################################################################
# Configuration Class toparse and load config.json
################################################################################
class Configuration():

    def __init__(self, super_print=None, debug = False):
        self.__debug = debug
        
        # Supersede local print function if provided as an argument
        self.print = super_print if super_print else self.print

    def load_configuration_file(self, configuration_file):
        self.print("Loading configuration file : " + configuration_file, end="") #############################################################
        try: 
            with open(configuration_file) as data_file:
                content =  json.load(data_file)
        except json.JSONDecodeError as e:
            raise RuntimeError("json format error : " + str(e))
        except Exception: 
            raise
        else:
            self.print(st = "OK")
            return (content)
        pass

    def print(self, string="", st=None, end=None):
        st = "[" + st + "] " if st else ""
        if end is None:
            print(st + string)
        else:
            print(st + string + " ", end="", flush="True")


################################################################################
# Object that retrieve the historycal data from Veolia website
################################################################################
class VeoliaCrawler():
    site_url           = 'https://espace-client.vedif.eau.veolia.fr/s/login/'
    download_filename  = "historique_jours_litres.csv"

    def __init__(self, configuration_json, super_print=None, debug = False):
        self.__debug = debug

        # Supersede local print function if provided as an argument
        self.print = super_print if super_print else self.print

        self.__display = None
        self.__browser = None
        self.__wait    = None
        self.configuration = {
            # Mandatory config values
            'veolia_login'      : None,
            'veolia_password'   : None,
            'veolia_contract'   : None,

            # Optional config values
            'geckodriver'       : which('geckodriver') if which('geckodriver') else "/usr/local/bin/geckodriver",
            'firefox'           : which('firefox') if which('firefox') else "/usr/local/bin/firefox",
            'timeout'           : "30",
            'download_folder'   : os.path.dirname(os.path.realpath(__file__)) + "/"
        }

        self.print("Start loading veolia configuration")
        try:
            self.__load_configuration_items(configuration_json)
            self.print("End loading veolia configuration", end="")
        except Exception:
            raise
        else:
            self.print(st="ok")
 
        self.__full_path_download_file = self.configuration['download_folder'] + self.download_filename

        pass

    # Load configuration items
    def __load_configuration_items(self, configuration_json):
        for param in list((self.configuration).keys()):
            if param not in configuration_json:
                if self.configuration[param] is not None:
                    self.print('    "' + param + '" = "' + self.configuration[param] + '"', end="") 
                    self.print("param is not found in config file, using default value","WW")
                else:
                    self.print('    "' + param + '"', end="") 
                    raise RuntimeError("param is missing in " + self.__configuration_file)
            else:
                if param == "veolia_password":
                    self.print('    "' + param + '" = "' + "*"*len(configuration_json[param]) + '"', end="") 
                else:
                    self.print('    "' + param + '" = "' + configuration_json[param] + '"', end="") 
                self.print(st = "OK")
                self.configuration[param] = configuration_json[param]


    # INIT DISPLAY & BROWSER
    def init_browser_firefox(self):
        self.print("Start virtual display", end="") #############################################################
        if self.__debug:
            self.__display = Display(visible=1, size=(1280, 1024))   
        else: 
            self.__display = Display(visible=0, size=(1280, 1024))   
        try:
            self.__display.start()
        except Exception as e:
            raise RuntimeError(str(e) + "if you launch the script from a ssh connection ensure X11 forwarding is activated")
        else:
            self.print(st = "OK")

        self.print("Setup Firefox profile", end="") #############################################################
        try:
            # Enable Download
            opts = Options()
            fp = webdriver.FirefoxProfile()
            opts.profile = fp 
            fp.set_preference('browser.download.dir', self.configuration['download_folder'])
            fp.set_preference('browser.download.folderList', 2)
            fp.set_preference('browser.helperApps.neverAsk.saveToDisk', 'text/csv')
            fp.set_preference("browser.download.manager.showWhenStarting",False)
            fp.set_preference("browser.helperApps.neverAsk.openFile","text/csv")
            fp.set_preference("browser.helperApps.alwaysAsk.force", False);

            # Set firefox binary to use
            binary = FirefoxBinary(self.configuration['firefox'])

            # Enable Mirionette drivers
            firefox_capabilities = DesiredCapabilities.FIREFOX
            firefox_capabilities['marionette'] = True

            # Enable the browser
            self.__browser = webdriver.Firefox(capabilities=firefox_capabilities, firefox_binary=binary, options = opts)
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print("Start Firefox", end="") #############################################################
        try:
            self.__browser.maximize_window()
            self.__wait = WebDriverWait(self.__browser, int(self.configuration["timeout"]))
        except Exception:
            raise
        else:
            self.print(st = "OK")
        pass


    def init_browser_chrome(self):
        # Set Chrome options
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_experimental_option("prefs", {
                "download.default_directory": self.configuration['download_folder'],
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "extensions_to_open": "text/csv",
                "safebrowsing.enabled": True})

        self.print("Start virtual display", end="") #############################################################
        if self.__debug:
            self.__display = Display(visible=1, size=(1280, 1024))   
        else: 
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            self.__display = Display(visible=0, size=(1280, 1024))   
        try:
            self.__display.start()
        except Exception:
            raise
        else:
            self.print(st = "OK")

        self.print("Start the browser", end="") #############################################################
        try:
            self.__browser = webdriver.Chrome(executable_path=self.configuration["chromedriver"],chrome_options=options)
            self.__browser.maximize_window()
            self.__wait = WebDriverWait(self.__browser, int(self.configuration["timeout"]))
        except Exception:
            raise
        else:
            self.print(st = "OK")
        pass

    def sanity_check(self):
        
        self.print("Check download location integrity", end="") #############################################################
        if os.path.exists(self.__full_path_download_file):
            self.print(self.__full_path_download_file + " already exists, will be removed", "WW")
        else:
            try:
                f = open(self.__full_path_download_file, "a+").close()
            except Exception as e:
                raise RuntimeError('"' + self.__full_path_download_file + '" ' + e.strerror)
            else:
                self.print(st="ok")

        self.print("Remove temporary download file", end="") #############################################################
        try:
            os.remove(self.download_filename)
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print('Check if "geckodriver" is intalled properly', end="") #############################################################
        if os.access(self.configuration['geckodriver'], os.X_OK):
            self.print(st="ok")
        else:
            raise OSError('"' + self.configuration['geckodriver'] + '" is not executable or not found')

        self.print('Check if "firefox" is intalled properly', end="") #############################################################
        if os.access(self.configuration['firefox'], os.X_OK):
            self.print(st="ok")
        else:
            raise OSError('"' + self.configuration['firefox'] + '" is not executable or not found')

        self.print("Check firefox browser version", end="") #############################################################
        try:
            major, minor = self.__get_firefox_version()
        except Exception:
            raise
        else:
            if (major, minor) < (60, 9):
                self.print("Firefox version (" + str(major) + "." + str(minor) + " is too old (< 60.9) script may fail",st="WW")
            else:
                self.print(st="ok")
        pass

    def __get_firefox_version(self):
        try:
            output = subprocess.check_output([self.configuration['firefox'], '--version'])
        except Exception:
            raise

        try:
            major, minor = map(int, re.search(r"(\d+).(\d+)", str(output)).groups())
        except Exception:
            raise

        return major, minor

    def clean_up(self):
        self.print("Close Browser", end="") #############################################################
        if self.__browser:
            try:
                self.__browser.quit()
            except Exception as e:
                os.kill(self.__browser.service.process.pid, signal.SIGTERM)
                self.print("selenium didnt properly close the process, so we kill firefox manually (pid=" + str(self.__browser.service.process.pid) + ")", "WW")
            else:
                self.print(st = "OK")
        else:
            self.print(st = "OK")
 
        self.print("Close Display", end="") #############################################################
        try:
            self.__display.stop()
        except:
            raise
        else:
            self.print(st="ok")

        # Remove downloaded file
        try:
            os.path.exists(self.__full_path_download_file)
        except:
            pass
        else:
            if os.path.exists(self.__full_path_download_file):
                self.print("Remove downloaded file "+ self.download_filename, end="") #############################################################
            
                # Remove file
                try:
                    os.remove(self.__full_path_download_file)
                except Exception as e:
                    self.print(str(e),st="EE")
                else:
                    self.print(st="ok")
        pass

    def get_file(self):
         
        self.print('Connexion au site Veolia Eau Ile de France', end="") #############################################################
        try:
            self.__browser.get(self.__class__.site_url)
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print('Waiting for Email', end="") #############################################################
        try:
            ep = EC.presence_of_element_located((By.CSS_SELECTOR,"input[type='email'"))
            el_email = self.__wait.until(ep, message="failed, page timeout (timeout=" + self.configuration['timeout'] + ")")
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print('Waiting for Password', end="") #############################################################
        try:
            ep = EC.presence_of_element_located((By.CSS_SELECTOR,'input[type="password"]'))
            el_password = self.__wait.until(ep, message="failed, page timeout (timeout=" + self.configuration['timeout'] + ")")
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print('Type Email', end="") ############################################################# 
        try:
            el_email.clear()
            el_email.send_keys(self.configuration['veolia_login'])
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print('Type Password', end="") #############################################################
        try:
            el_password.send_keys(self.configuration['veolia_password'])
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print('Waiting for submit button', end="") #############################################################
        try:
            ep = EC.visibility_of_element_located((By.CLASS_NAME,'submit-button'))
            el = self.__wait.until(ep, message="failed, page timeout (timeout=" + self.configuration['timeout'] + ")")
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print('Click on submit button', end="") #############################################################
        try:
            el.click()
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print('Wait for MENU contrats', end="") #############################################################
        try:
            ep = EC.visibility_of_element_located((By.XPATH,"//span[contains(text(), 'CONTRATS')]"))
            el = self.__wait.until(ep, message="failed, page timeout (timeout=" + self.configuration['timeout'] + ")")
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print('Click on menu : contrats', end="") #############################################################
        try:
            el.click()
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print('Select contract : ' + self.configuration['veolia_contract'], end="") #############################################################
        try:
            ep = EC.visibility_of_element_located((By.LINK_TEXT,self.configuration['veolia_contract']))
            el = self.__wait.until(ep, message="failed, page timeout (timeout=" + self.configuration['timeout'] + ")")
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print('Click on contract', end="") #############################################################
        try:
            el.click()
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print('Wait for historique menu', end="") #############################################################
        try:
            ep = EC.visibility_of_element_located((By.LINK_TEXT,"Historique"))
            el = self.__wait.until(ep, message="failed, page timeout (timeout=" + self.configuration['timeout'] + ")")
        except Exception:
            raise
        else:
            self.print(st="ok")


        self.print('Click on historique menu', end="") #############################################################
        try:
            el.click()
        except Exception:
            raise
        else:
            self.print(st="ok")


        self.print('Wait for boutton telechargement', end="") #############################################################
        try:
            ep = EC.presence_of_element_located((By.XPATH,'//*[contains(text(),"charger la p")]'))
            el = self.__wait.until(ep, message="failed, page timeout (timeout=" + self.configuration['timeout'] + ")")
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print('Wait before clicking (10)', end="") #############################################################
        time.sleep(10)
        self.print(st="ok")

        self.print('Click on Button telechargement', end="") #############################################################
        try:
            el.click()
        except Exception:
            raise
        else:
            self.print(st="ok")

        self.print('Wait for download finished of ' + self.__full_path_download_file, end="") #############################################################
        t = int(self.configuration['timeout'])
        while t > 0 and not os.path.exists(self.__full_path_download_file):
            time.sleep(1)
            t - 1
        if os.path.exists(self.__full_path_download_file):
            self.print(st="ok")
        else:
            raise RuntimeError("File download timeout")

        return self.__full_path_download_file

################################################################################
# Object injects historical data into domoticz
################################################################################
class DomoticzInjector():
    
    def __init__(self, configuration_json, super_print, debug = False):
        self.__debug = debug

        # Supersede local print function if provided as an argument
        self.print = super_print if super_print else self.print

        self.configuration = {
            # Mandatory config values
            'domoticz_idx'      : None,
            'domoticz_server'   : None,

            # Optional config values
            'domoticz_login'    : "",
            'domoticz_password' : "",
            'timeout'           : "30",
            'download_folder'   : os.path.dirname(os.path.realpath(__file__)) + "/"
        }
        self.print("Start Loading Domoticz configuration")
        try:
            self.__load_configuration_items(configuration_json)
            self.print("End loading domoticz configuration", end="")
        except Exception:
            raise
        else:
            self.print(st="ok")
 
        self.__http = urllib3.PoolManager(retries=1, timeout=int(self.configuration['timeout']))
        pass

    def open_url(self, uri):
        # Generate URL
        url_test = self.configuration["domoticz_server"] + uri

        # Add authentification Items if needed
        if self.configuration['domoticz_login'] is not "":
            b64domoticz_login = base64.b64encode(self.configuration['domoticz_login'].encode())
            b64domoticz_password = base64.b64encode(self.configuration['domoticz_password'].encode())
            url_test = url_test + '&username=' + b64domoticz_login.decode()  + '&password=' + b64domoticz_password.decode()

        try:
            response = self.__http.request('GET',url_test)
        except urllib3.exceptions.MaxRetryError as e:
            # HANDLE CONNECTIVITY ERROR
            raise RuntimeError("url=" + url_test + " : " + str(e))

        # HANDLE SERVER ERROR CODE
        if not response.status == 200:
            raise RuntimeError('url=' + url_test + ' - (code = ' + str(response.status) + ')\ncontent=' + str(response.data))

        try:
            j=json.loads(response.data)
        except Exception as e:
            # Handle JSON ERROR
            raise RuntimeError("unable to parse the JSON : " + str(e))

        if (int(response.status) != 200 ) or (j["status"].lower() != "ok"):
            raise RuntimeError('url=' + url_test + '\nrepsonse=' + str(response.status) + '\ncontent=' + str(j))

        return j

    # Load configuration items
    def __load_configuration_items(self, configuration_json):
        for param in list((self.configuration).keys()):
            if param not in configuration_json:
                if self.configuration[param] is not None:
                    self.print('    "' + param + '" = "' + self.configuration[param] + '"', end="") 
                    self.print("param is not found in config file, using default value","WW")
                else:
                    self.print('    "' + param + '"', end="") 
                    raise RuntimeError("param is missing in " + self.__configuration_file)
            else:
                if param == "domoticz_password":
                    self.print('    "' + param + '" = "' + "*"*len(configuration_json[param]) + '"', end="") 
                else:
                    self.print('    "' + param + '" = "' + configuration_json[param] + '"', end="") 
                self.print(st = "OK")
                self.configuration[param] = configuration_json[param]


    def sanity_check(self):
        self.print("Check domoticz connectivity", end="") #############################################################
        response = self.open_url('/json.htm?type=command&param=getversion')
        if response["status"].lower() == 'ok':
            self.print(st = "ok")

        self.print('Check domoticz Device', end="") #############################################################
        # generate 2 urls, one for historique, one for update
        response = self.open_url('/json.htm?type=devices&rid=' + self.configuration['domoticz_idx'])
        
        if not "result" in response:
                raise RuntimeError('device ' + self.configuration['domoticz_idx'] + " could not be found on domoticz server " + self.configuration['domoticz_server'])
        else :
                properly_configured = True
                dev_AddjValue       = response["result"][0]['AddjValue']
                dev_AddjValue2      = response["result"][0]['AddjValue2']
                dev_SubType         = response["result"][0]["SubType"]
                dev_Type            = response["result"][0]["Type"]
                dev_SwitchTypeVal   = response["result"][0]["SwitchTypeVal"]
                dev_Name            = response["result"][0]["Name"]

                self.print(st="ok")

                # Retrieve Device Name
                self.print('    Device Name            : "' + dev_Name + '" (idx=' +  self.configuration['domoticz_idx'] + ')' , end="") #############################################################
                self.print(st="ok")
               
                # Checking Device Type
                self.print('    Device Type            : "' + dev_Type + '"', end="") #############################################################
                if dev_Type =="General":
                    self.print(st="ok")
                else:
                    self.print('wrong sensor type. Go to Domoticz/Hardware - Create a pseudo-sensor type "Managed Counter"', st="EE")
                    properly_configured = False

                # Checking device subtype
                self.print('    Device SubType         : "' + dev_SubType + '"', end="") #############################################################
                if dev_SubType == "Managed Counter":
                    self.print(st = "ok")
                else:
                    self.print('wrong sensor type. Go to Domoticz/Hardware - Create a pseudo-sensor type "Managed Counter"', st="ee")
                    properly_configured = False
    
                # Checking for SwitchType
                self.print('    Device SwitchType      : "' + str(dev_SwitchTypeVal), end="") #############################################################
                if dev_SwitchTypeVal == 2:
                    self.print(st = "ok")
                else:
                    self.print("wrong switch type. Go to Domoticz - Select your counter - click edit - change type to water", st="ee")
                    properly_configured = False
    
                # Checking for Counter Divider
                self.print('    Device Counter Divided : "' + str(dev_AddjValue2) + '"', end="") #############################################################
                if dev_AddjValue2 == 1000:
                    self.print(st = "ok")
                else:
                    self.print('wrong counter divided. Go to Domoticz - Select your counter - click edit - set "Counter Divided" to 1000', st="ee")
                    properly_configured = False
    
                # Checking Meter Offset
                self.print('    Device Meter Offset    : "' + str(dev_AddjValue) + '"', end="") #############################################################
                if dev_AddjValue == 0:
                    self.print(st = "ok")
                else:
                    self.print('wrong value for meter offset. Go to Domoticz - Select your counter - click edit - set "Meter Offset" to 0', st="ee")
                    properly_configured = False

                if properly_configured == False:
                    raise RuntimeError("Set your device correctly and run the script again")
        pass

    def update_device(self, data_file):
        self.print("Parsing csv file")
        with open(data_file, 'r') as f:
            # PArse each line of the file. 
            for row in list(csv.reader(f, delimiter=';')):
                date      = row[0][0:10]
                date_time = row[0]
                counter   = row[1]
                conso     = row[2]

                # Generate 2 URLs, one for historique, one for update
                args = {'type': 'command', 'param': 'udevice', 'idx': self.configuration['domoticz_idx'], 'svalue': counter + ";" + conso + ";" + date}
                url_historique = '/json.htm?' + urlencode(args)
                
                args['svalue'] = counter + ";" + conso + ";" + date_time
                url_daily = '/json.htm?' + urlencode(args)

                args['svalue'] = conso
                url_current = '/json.htm?' + urlencode(args)

                # Check line integrity (Date starting by 2 or 1)
                if date[0] == "2" or date[0] == "1":
                    self.print("    update value for " + date, end="") #############################################################
                    self.open_url(url_historique)
                    self.print(st = "ok")

        # Update Dashboard
        self.print("    update current value", end="") #############################################################
        self.open_url(url_current)
        self.print(st = "ok")

        self.print("    update daily value", end="") #############################################################
        self.open_url(url_daily)
        self.print(st = "ok")
        pass

    def clean_up(self):
        pass

def exit_on_error(veolia=None, domoticz=None, string=""):
    try:
        o
    except: 
        print(string)
    else:
        o.print(string,st="EE")
 
    if veolia is not None:
        veolia.clean_up()
    if domoticz:
        domoticz.clean_up()
    try:
        o
    except:
        print("Ended with error : // re-run the program with '--debug' option")
    else:
        o.print("Ended with error : // re-run the program with '--debug' option",st="EE")
    sys.exit(2)

def check_new_script_version():
    o.print("Check script version is up to date",end="")
    try:
            http=urllib3.PoolManager()
            user_agent = {'user-agent': 'veolia-idf - ' + VERSION}
            r = http.request('GET', 'https://api.github.com/repos/s0nik42/veolia-idf/releases/latest', headers=user_agent)
            j = json.loads(r.data.decode('utf-8'))
    except Exception:
        raise
    else:
        if j["tag_name"] > VERSION:
            o.print('New version "' + j["name"] + '"(' + j["tag_name"] + ') available. Check : https://github.com/s0nik42/veolia-idf/releases/latest', st="ww")
        else:
            o.print(st="ok")

def version():
    print(VERSION)
    sys.exit(0)

if __name__ == '__main__':
        # Default config value
        default_logfile = "/var/log/veolia.log"
        default_configuration_file = os.path.dirname(os.path.realpath(__file__))+ '/config.json'


        # COMMAND LINE OPTIONS
        parser = argparse.ArgumentParser(description="Load water consumption from veolia Ile de France into domoticz")
        parser.add_argument("-v", "--version", action="store_true",help="script version")
        parser.add_argument("-d", "--debug", action="store_true",help="active graphical debug mode (only for troubleshooting)")
        parser.add_argument("-l", "--log", help="specify logfile location (" + default_logfile + ")", default=default_logfile, nargs=1)
        parser.add_argument("-c", "--config", help="specify configuration location (" + default_configuration_file + ")", default=default_configuration_file, nargs=1)
        parser.add_argument("-r", "--run", action="store_true",help="run the script", required=True)
        args = parser.parse_args()

        # VERSION
        if args.version:
            version()

        # Init output
        try:
            o = Output(logfile = str(args.log).strip("[]'"), debug=args.debug)
        except Exception as e:
            exit_on_error(string = str(e))

        # Print Debug Message
        o.print("DEBUG MODE ACTIVATED", end="")
        o.print("only use '--debug' for troubleshooting", st="WW")

        # New version checking
        try:
            check_new_script_version()
        except Exception as e:
            exit_on_error(string = str(e))


        # Load configuration
        try:
            c = Configuration(debug=args.debug, super_print=o.print)
            configuration_json = c.load_configuration_file(str(args.config).strip("[]'"))
        except Exception as e:
            exit_on_error(string = str(e))

        # Create objects
        try:
            veolia = VeoliaCrawler(configuration_json, super_print=o.print, debug=args.debug)
            domoticz = DomoticzInjector(configuration_json, super_print=o.print, debug=args.debug)
        except Exception as e:
            exit_on_error(string = str(e))
        
        # Check requirements
        try:
            veolia.sanity_check()
        except Exception as e:
            exit_on_error(veolia, domoticz, str(e))

        try:
            domoticz.sanity_check()
        except Exception as e:
            exit_on_error(veolia, domoticz, str(e))

        try:
            veolia.init_browser_firefox()
        except Exception as e:
            exit_on_error(veolia, domoticz, str(e))

        try:
            data_file = veolia.get_file()
        except Exception as e:
            # REtry once on failure to manage stalement exception that occur sometimes
            try:
                o.print("Encountered error" + str(e).rstrip() + "// -> Retrying once",st="ww")
                data_file = veolia.get_file()
            except Exception as e:
                exit_on_error(veolia, domoticz, str(e))

        try:
            domoticz.update_device(data_file)
        except Exception as e:
            exit_on_error(veolia, domoticz, str(e))

        veolia.clean_up()
        o.print("Finished on success")
        sys.exit(0)
