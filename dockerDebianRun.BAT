@ECHO OFF

REM Run veolia-idf in Docker container 

SET IMAGE=py-veolia-debian

REM BUILD DOCKER CONTAINER
docker build --rm -t %IMAGE% -f ./DockerfileDebian ./

REM VcXsvr can provide an XServer on Windows
SET DISPLAY=host.docker.internal:0.0
SET ARGS=./veolia-idf-domoticz.py --run --debug

REM This does not need an XServer
SET ARGS=./veolia-idf-domoticz.py --run

docker run --rm -it -e DISPLAY=%DISPLAY% -v %cd%:/root/workdir --env NO_AT_BRIDGE=1 --workdir="/root" %IMAGE% /bin/bash -c "cd workdir ; %ARGS%" 
