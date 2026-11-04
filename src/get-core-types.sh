#!/bin/bash
#
# Detect P-core / E-core / LPE-core IDs for CPU pinning.
#
# Usage:
#   src/get-core-types.sh [--reinstall] [PCORE|ECORE|LPECORE ...]
#
#   No core type     -> prints all detected types as KEY=VALUE lines, e.g.
#                         PCORE=0,1,2,3
#                         ECORE=4,5,6,7
#                         LPECORE=8,9
#   One core type    -> prints only its comma-separated core list, e.g.
#                         $ src/get-core-types.sh PCORE
#                         0,1,2,3
#   Many core types  -> prints the merged comma-separated core list, e.g.
#                         $ src/get-core-types.sh ECORE LPECORE
#                         4,5,6,7,8,9
#
#   Core type names are case-insensitive. Diagnostics go to stderr.
#   Exits with 3 if none of the requested core types exist on this platform.
#
# Options:
#   --reinstall   ignore /etc/core-types and detect again
#   VERBOSE=1     enable debug output of obtain_cores.sh (to stderr)

set -euo pipefail

OBTAIN_CORES_COMMIT="e7401a31d8ae40886ea5e8c608809895b1ce93ac"
OBTAIN_CORES_SHA256="4fec9b0e3d1b3d6db8d6ed01d2639d257060477d0bb82552ac17fbc21e95cde1"
OBTAIN_CORES_URL="https://raw.githubusercontent.com/open-edge-platform/edge-workloads-and-benchmarks/${OBTAIN_CORES_COMMIT}/utils/obtain_cores.sh"
CORE_TYPES_FILE="/etc/core-types"
VALID_TYPES=(PCORE ECORE LPECORE)

log() { echo "[get-core-types] $*" >&2; }

usage() { sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'; }

# Convert "pcore: 0,1" style lines to "PCORE=0,1"; other output (e.g. VERBOSE debug) goes to stderr
to_env() {
    local line
    while IFS= read -r line; do
        if [[ "$line" =~ ^[[:space:]]*(pcore|ecore|lpecore)[[:space:]]*:[[:space:]]*(.*)$ ]]; then
            echo "${BASH_REMATCH[1]^^}=${BASH_REMATCH[2]}"
        else
            echo "$line" >&2
        fi
    done
}

detect_core_types() {
    local cmd
    for cmd in curl sha256sum; do
        command -v "$cmd" >/dev/null 2>&1 || { log "ERROR: '$cmd' is required"; return 1; }
    done
    if ! command -v cpuid >/dev/null 2>&1; then
        log "WARNING: 'cpuid' not installed; detection falls back to sysfs/lscpu (install with: sudo apt install cpuid)"
    fi

    tmp_script="$(mktemp)"
    trap 'rm -f "${tmp_script:-}"' EXIT

    log "Fetching obtain_cores.sh @ ${OBTAIN_CORES_COMMIT}"
    curl -fsSL --retry 3 --max-time 60 -o "$tmp_script" "$OBTAIN_CORES_URL"

    if ! echo "${OBTAIN_CORES_SHA256}  ${tmp_script}" | sha256sum -c --status -; then
        log "ERROR: checksum mismatch for obtain_cores.sh; refusing to execute"
        return 1
    fi

    bash "$tmp_script" | to_env
}

reinstall=false
requested=()
for arg in "$@"; do
    case "$arg" in
        --reinstall) reinstall=true ;;
        -h|--help) usage; exit 0 ;;
        *)
            type="${arg^^}"
            if [[ " ${VALID_TYPES[*]} " != *" $type "* ]]; then
                log "ERROR: unknown argument '$arg' (expected one of: ${VALID_TYPES[*]})"
                exit 2
            fi
            [[ " ${requested[*]:-} " == *" $type "* ]] || requested+=("$type")
            ;;
    esac
done

if [[ -s "$CORE_TYPES_FILE" && "$reinstall" == false ]]; then
    log "Using existing $CORE_TYPES_FILE"
    core_types="$(grep -E '^[A-Z0-9_]+=' "$CORE_TYPES_FILE" || true)"
else
    core_types="$(detect_core_types)"
fi

if [[ -z "$core_types" ]]; then
    log "ERROR: no core types detected"
    exit 1
fi

if [[ ${#requested[@]} -eq 0 ]]; then
    echo "$core_types"
    exit 0
fi

cores=()
for type in "${requested[@]}"; do
    value="$(sed -n "s/^${type}=//p" <<<"$core_types" | head -n1)"
    if [[ -n "$value" ]]; then
        cores+=("$value")
    else
        log "WARNING: no ${type} cores on this platform"
    fi
done

if [[ ${#cores[@]} -eq 0 ]]; then
    log "ERROR: none of the requested core types (${requested[*]}) were found"
    exit 3
fi

(IFS=,; echo "${cores[*]}")
