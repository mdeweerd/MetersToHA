REM @echo OFF
REM Example BAT file pour windows
REM Vous pouvez ajuster ce script et le lancer comme une Tâche planifiée

REM Déterminez la version principale de Chrome
REM - Utile si `pip install undetected-chromedriver` a été effectué
for /f %%i in ('powershell -command "(Get-Command 'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe').Version.ToString()"') do SET RESULT=%%i
SET CHROME_VERSION=%RESULT:~0,3%

REM Démarre meters_to_ha.py pour GRDF.
REM Suppose la présence de 'winconfig.json' pour la configuration.
REM
python -m pip install pyvirtualdisplay selenium undetected-chromedriver

REM Décommenté le GOTO vers le mode de fonctionnement retenu
GOTO INTERACTIF
REM GOTO NONINTERACTIF
REM GOTO TRACE


:INTERACTIF
REM Interactif:
python apps/meters_to_ha/meters_to_ha.py -c ./winconfig.json --grdf -r --keep-output --display --screenshot --chrome-version %CHROME_VERSION%
GOTO END

:NONINTERACTIF
REM NON INTERACTIF
python apps/meters_to_ha/meters_to_ha.py -c ./winconfig.json --grdf -r --keep-output --screenshot --chrome-version %CHROME_VERSION%

GOTO END:

:TRACE
REM Avec trace détaillée
for /f %%i in ('python -c "import sys ; print(';'.join(sys.path)[1:])"') do SET PY_PATH=%%i
python -m trace "--ignore-dir=%PY_PATH%" -t ^
apps/meters_to_ha/meters_to_ha.py -c ./winconfig.json --display --grdf -r --keep-output --screenshot --chrome-version %CHROME_VERSION% 

:END

