#!/usr/bin/env bash
#
# CCAS lab Management API helper - v4
#
# Changes since v3:
#   - set -euo pipefail for fail-fast behaviour
#   - EXIT trap so the session cookie is removed even on Ctrl-C / error
#   - mgmtCmd uses an if-form pipeline (compatible with set -e)
#   - login function tolerates an unset $1 under set -u
#   - -d MDS-domain path retained: needed for some Mgmt API quirks even on
#     non-MDS managements, harmless when domain is empty
#
# Usage:
#   ./bash_api_v4.sh                    # standalone SMS
#   ./bash_api_v4.sh "Domain_Name"      # MDS / Multi-Domain
#
set -euo pipefail

sessionName="Initial Build"
sessionDescription="Building my initial config for a new lab management."

publishEvery=80
changeCount=1
publishBatch=1
apiPort=$(api status | grep 'APACHE Gaia Port' | awk '{print $NF}')
sessionCookie=$(mktemp)

# Always clean up the session cookie, regardless of how the script exits
cleanup() {
	rm -f "${sessionCookie}"
}
trap cleanup EXIT INT TERM

#/Function Configuration

function mgmtCmd {
	commandToRun=""
	for element in "${@}"; do
		if [[ "$element" =~ \  ]]; then
			commandToRun="${commandToRun} \"${element}\""
		else
			commandToRun="${commandToRun} ${element}"
		fi
	done
	if echo "${commandToRun}" | xargs mgmt_cli --port "${apiPort}" -s "${sessionCookie}"; then
		echo "Success ${publishBatch}.${changeCount}"
		((changeCount+=1))
	else
		echo "Failed: ${commandToRun}"
	fi
	if [ ${changeCount} -gt ${publishEvery} ]; then
		echo "Publishing..."
		publish
		setupSession
		changeCount=1
		((publishBatch+=1))
	fi
}

function publish {
	mgmt_cli --port "${apiPort}" -s "${sessionCookie}" publish
}

function setupSession {
	mgmt_cli --port "${apiPort}" -s "${sessionCookie}" set session new-name "${sessionName}" description "${sessionDescription}" > /dev/null
}

function login {
    # Optional: support an MDS domain as $1, otherwise default (standalone SMS).
    # The -d flag is a Mgmt API quirk: needed for MDS, but the optional code
    # path is retained because some Mgmt API edge cases benefit from it.
    local domain="${1:-}"

    read -p "SmartConsole admin username: " apiUser

    if [ -n "$domain" ]; then
        # MDS / Multi-Domain
        if ! mgmt_cli --port "${apiPort}" -d "${domain}" login user "$apiUser" > "${sessionCookie}"; then
            echo "Login failed (MDS domain: ${domain}). Check username/password/API permissions."
            exit 1
        fi
    else
        # Standalone SMS
        if ! mgmt_cli --port "${apiPort}" login user "$apiUser" > "${sessionCookie}"; then
            echo "Login failed. Check username/password/API permissions."
            exit 1
        fi
    fi

    setupSession
}

function logout {
	publish
	mgmt_cli --port "${apiPort}" -s "${sessionCookie}" logout > /dev/null
	# cookie removed by EXIT trap
}

#/Start the Session
login "${1:-}"

#/Run these commands


#/End the Session
logout
