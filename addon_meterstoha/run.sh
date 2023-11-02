#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

# Do not require that bash variables are set before use:
set +u

CONFIG_FILE="$(realpath .)/m2h_config.json"
RUN_OPT=""

# Defaults
TYPE="ha"
HA_SERVER="http://supervisor/core"
HA_TOKEN="${SUPERVISOR_TOKEN}"
GIT_VERSION_STR=

#
# Cloning on each run at this moment for testing
#
if bashio::config.has_value git_version ; then
  GIT_VERSION="$(bashio::config git_version)"
  # shellcheck disable=SC2089
  GIT_VERSION_STR="\"${GIT_VERSION/\"/\\\"}\""
fi

git clone --depth=1 "https://github.com/mdeweerd/MetersToHA.git" --no-checkout MetersToHA
(
  cd MetersToHA || exit 255
  git sparse-checkout set apps
  echo "git checkout $GIT_VERSION_STR"
  # shellcheck disable=SC2086,SC2090
  git checkout $GIT_VERSION_STR
  git show -s --pretty=format:"MetersToHA Python GIT version: %h on %ad"
)


echo "Generate configuration file"

keys="veolia_login veolia_password veolia_contract grdf_login grdf_password grdf_pce timeout download_folder domoticz_idx domoticz_server domoticz_login domoticz_password mqtt_server mqtt_port mqtt_login mqtt_password"
event_keys="veolia grdf"
event_conf=""
events=""

config=""
if bashio::config.has_value "captchaservice"; then
  captchaservice=$(bashio::config "captchaservice")
  if bashio::config.has_value "token_captchaservice"; then
    token_captchaservice=$(bashio::config "token_captchaservice")
    token_config="\"${captchaservice}_token\":\"${token_captchaservice//\"/\\\"}\""
    config="$config$token_config,
    "
  fi
fi

# shellcheck disable=SC2086
for key in $keys ; do
  if bashio::config.has_value $key; then
    value="$(bashio::config "$key")"
    config="$config\"${key//\"/\\\"}\":\"${value/\"/\\\"}\",
    "
  fi
done

event_matching=""
# shellcheck disable=SC2086
for key in $event_keys ; do
  if bashio::config.has_value "${key}_event"; then
    value="$(bashio::config "${key}_event")"
    event_conf="$key:$value"
    event_matching="$event_matching""[[ \"\$1\" == \"${value/\"/\\\"}\" ]] && TARGET_OPT=--$key
    "
    # shellcheck disable=SC2089
    events="$events ${value//\"/\\\"}"
  fi
done


if bashio::config.has_value ha_server ; then
  HA_SERVER="$(bashio::config ha_server)"
fi

if bashio::config.has_value ha_token ; then
  HA_TOKEN="$(bashio::config ha_token)"
fi

if bashio::config.has_value DISPLAY ; then
  DISPLAY="$(bashio::config DISPLAY)"
  export DISPLAY
fi

LOG_LEVEL=info
TRACE_OPT=""
CURL_OPT=""
if bashio::config.has_value log_level ; then
  LOG_LEVEL="$(bashio::config log_level)"
  if [ "${LOG_LEVEL}" == "trace" ] ; then
     # Maximum level inside app
     LOG_LEVEL="debug"
     # Enable tracing python
     TRACE_OPT="-m trace --ignore-dir=/usr/lib -t"
  fi
  if [ "${LOG_LEVEL}" == "debug" ] ; then
     # shellcheck disable=SC2034
     CURL_OPT_dis="-v"  # Only shows [xx bytes data]
  fi
fi

if bashio::config.has_value download_folder ; then
  # shellcheck disable=SC2089
  mkdir -p "$(bashio::config download_folder)"
fi

if bashio::config.has_value logs_folder ; then
  # shellcheck disable=SC2089
  RUN_OPT="${RUN_OPT} -l $(bashio::config logs_folder)"
  LOGS_FOLDER="$(bashio::config logs_folder)"
  mkdir -p "${LOGS_FOLDER}"
fi

if bashio::config.has_value type ; then
  TYPE="$(bashio::config type)"
  TYPE="${TYPE//\"/\\\"}"
fi

if bashio::config.true debug ; then
  RUN_OPT="${RUN_OPT} --debug"
fi

if bashio::config.true local_config ; then
  RUN_OPT="${RUN_OPT} --local-config"
fi

if bashio::config.true screenshot ; then
  RUN_OPT="${RUN_OPT} --screenshot"
fi

if bashio::config.true insecure ; then
  RUN_OPT="${RUN_OPT} --insecure"
fi

if bashio::config.true skip_download ; then
  RUN_OPT="${RUN_OPT} --skip-download"
fi

if bashio::config.true keep_output ; then
  RUN_OPT="${RUN_OPT} --keep-output"
fi

function debug_output
{
  # command 3>&1 1>&2 2>&3 | debug_output to show stderr only when debugging
  if [ "${LOG_LEVEL}" == "debug" ] ; then
    cat
  else
    cat > /dev/null
  fi
}

cat > "$CONFIG_FILE" <<EOJSON
{
  $config
  "ha_server": "$HA_SERVER",
  "ha_token": "$HA_TOKEN",
  "type": "$TYPE"
}
EOJSON

echo "Generated configuration file '$CONFIG_FILE':"
cat "$CONFIG_FILE"
echo "DISPLAY:'$DISPLAY'"
echo "EVENT CONF:$event_conf"

# ls -lRrt /MetersToHA

EXEC_EVENT_SH="$(realpath .)/execEvent.sh"
cat > "$EXEC_EVENT_SH" <<SCRIPT
#!/bin/bash
#!/usr/bin/with-contenv bashio
{
TARGET_OPT=""
$event_matching
[[ "\$TARGET_OPT" == "" ]] && ( echo "Unrecognized event '\$1'" ; exit 1 )
date
echo "python3 $TRACE_OPT MetersToHA/apps/meters_to_ha/meters_to_ha.py $RUN_OPT -c \"$CONFIG_FILE\" \$TARGET_OPT -r"
python3 $TRACE_OPT MetersToHA/apps/meters_to_ha/meters_to_ha.py $RUN_OPT -c "$CONFIG_FILE" \$TARGET_OPT -r
echo "Done \$(date)"
} >> "$LOGS_FOLDER/m2h_exec.log" 2>&1
SCRIPT
chmod +x "$EXEC_EVENT_SH"

echo "Generated script '$EXEC_EVENT_SH':"
cat "$EXEC_EVENT_SH"

echo "Test access to Home Assistant API (should show '{\"message\":\"API running.\"}')"
echo curl -H "'Authorization: Bearer ${HA_TOKEN}'" -H "'Content-Type: application/json'" "${HA_SERVER}/api/" | debug_output
API_OUT=/tmp/ha_api.out
# shellcheck disable=SC2086
curl ${CURL_OPT} -o "${API_OUT}" -H "Authorization: Bearer ${HA_TOKEN}" -H "Content-Type: application/json" "${HA_SERVER}/api/"  3>&1 1>&2 2>&3 | debug_output
cat "${API_OUT}"
echo ""

HAEVENT2EXEC=./haevent2exec.py
echo "\"${HAEVENT2EXEC}\" --config-json \"$CONFIG_FILE\" --external-program \"$EXEC_EVENT_SH\" --log-level=\"${LOG_LEVEL//\\"/\\\\"}\" $events"
# shellcheck disable=SC2086,SC2090
"${HAEVENT2EXEC}" --config-json "$CONFIG_FILE" --external-program "$EXEC_EVENT_SH" --log-level="${LOG_LEVEL//\"/\\\"}" $events
