#!/usr/bin/env bash
set -euo pipefail

# Helper: fail if important var is unset or empty
require_var() {
  local var_name="$1"
  if [[ -z "${!var_name:-}" ]]; then
    echo "❌ ERROR: Required environment variable '$var_name' is not set or is empty."
    exit 1
  fi
}

# Helper: set default only if var is unset or empty (DO NOT overwrite user-set values)
set_default_if_unset_or_empty() {
  local var_name="$1"
  local default_value="$2"

  # If variable is unset or empty, export the default
  if [[ -z "${!var_name:-}" ]]; then
    export "$var_name"="$default_value"
    echo "ℹ️  '$var_name' was not set — using default: $default_value"
  else
    # Keep whatever user set (do NOT overwrite)
    echo "✅  '$var_name' is already set (keeping user value)."
  fi
}

echo "🔍 Checking environment variables..."

# -----------------------
# Unimportant vars -> set defaults only if NOT set or empty
# -----------------------
set_default_if_unset_or_empty MINIO_ROOT_USER "admin"
set_default_if_unset_or_empty MINIO_ROOT_PASSWORD "passwd"
set_default_if_unset_or_empty RABBITMQ_USER "admin"
set_default_if_unset_or_empty RABBITMQ_PASSWORD "passwd"
set_default_if_unset_or_empty VLM_DEVICE "GPU"
set_default_if_unset_or_empty ENABLE_VLM_GPU "True"

# -----------------------
# Important vars -> must be set and non-empty, otherwise exit
# -----------------------
require_var VLM_COMPRESSION_WEIGHT_FORMAT
require_var HUGGINGFACE_TOKEN
require_var VLM_MODEL_NAME
require_var ENABLED_WHISPER_MODELS
require_var GATED_MODEL

echo "✅ All required environment variables validated."
