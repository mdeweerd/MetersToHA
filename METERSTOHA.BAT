@echo OFF
REM Example BAT file pour windows
REM Vous pouvez ajuster ce script et le lancer comme une Tâche planifiée

REM Déterminez la version principale de Chrome
REM - Utile si `pip install undetected-chromedriver` a été effectué
for /f %%i in ('powershell -command "(Get-Command 'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe').Version.ToString()"') do SET RESULT=%%i
SET CHROME_VERSION=%RESULT:~0,3%

REM Démarre meters_to_ha.py pour GRDF.
REM Suppose la présence de 'winconfig.json' pour la configuration.

REM Interactif:
REM python apps/meters_to_ha/meters_to_ha.py -c ./winconfig.json --grdf -r --keep-output --debug --screenshot --chrome-version %CHROME_VERSION%
REM NON INTERACTIF
python apps/meters_to_ha/meters_to_ha.py -c ./winconfig.json --grdf -r --keep-output --screenshot --chrome-version %CHROME_VERSION%
