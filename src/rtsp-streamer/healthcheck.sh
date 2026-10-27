#!/bin/sh
set -eu

MEDIA_DIR=${MEDIA_DIR:-/media}
RTSP_PORT=${RTSP_PORT:-8554}
FFPROBE_BIN=${FFPROBE_BIN:-ffprobe}

set -- "$MEDIA_DIR"/*.mp4
if [ ! -f "$1" ]; then
  echo "No .mp4 files found in $MEDIA_DIR" >&2
  exit 1
fi

# Probe in parallel so the healthcheck deadline does not grow with the file count.
pids=""
for file in "$@"; do
  [ -f "$file" ] || continue
  filename=${file##*/}
  stream_name=${filename%.*}
  (
    if ! packets=$(timeout 10 "$FFPROBE_BIN" \
      -v fatal \
      -rtsp_transport tcp \
      -timeout 3000000 \
      -select_streams v:0 \
      -read_intervals "%+#1" \
      -count_packets \
      -show_entries stream=nb_read_packets \
      -of csv=p=0 \
      "rtsp://127.0.0.1:${RTSP_PORT}/${stream_name}"); then
      echo "RTSP stream $stream_name is not ready" >&2
      exit 1
    fi
    if [ "$packets" != "1" ]; then
      echo "RTSP stream $stream_name is not delivering video packets" >&2
      exit 1
    fi
  ) &
  pids="$pids $!"
done

status=0
for pid in $pids; do
  if ! wait "$pid"; then
    status=1
  fi
done
exit "$status"
