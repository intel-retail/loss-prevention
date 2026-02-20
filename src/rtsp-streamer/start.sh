#!/bin/sh
set -eu

MEDIA_DIR=${MEDIA_DIR:-/media}
RTSP_PORT=${RTSP_PORT:-8554}
FFMPEG_BIN=${FFMPEG_BIN:-ffmpeg}
MEDIAMTX_BIN=${MEDIAMTX_BIN:-/opt/rtsp-streamer/mediamtx}
STREAM_LOOP=${STREAM_LOOP:-true}

if [ ! -d "$MEDIA_DIR" ]; then
  echo "Media directory $MEDIA_DIR does not exist" >&2
  exit 1
fi

if [ ! -x "$MEDIAMTX_BIN" ]; then
  echo "mediamtx binary $MEDIAMTX_BIN not found or not executable" >&2
  exit 1
fi

set -- "$MEDIA_DIR"/*.mp4
if [ ! -e "$1" ]; then
  echo "No .mp4 files found in $MEDIA_DIR" >&2
  exit 1
fi

"$MEDIAMTX_BIN" >/tmp/mediamtx.log 2>&1 &
mediamtx_pid=$!
pids="$mediamtx_pid"

# Wait for RTSP server to accept connections
retry=50
while ! nc -z 127.0.0.1 "$RTSP_PORT" >/dev/null 2>&1; do
  retry=$((retry - 1))
  if [ "$retry" -le 0 ]; then
    echo "RTSP server failed to start on port $RTSP_PORT" >&2
    kill "$mediamtx_pid"
    wait "$mediamtx_pid" 2>/dev/null || true
    exit 1
  fi
  sleep 0.2
done

pids="$pids"
for file in "$@"; do
  [ -f "$file" ] || continue
  filename=$(basename "$file")
  stream_name=${filename%.*}
  echo "Starting RTSP stream $stream_name from $file"
  # -re throttles playback to real-time
  # -stream_loop -1 loops the video indefinitely (if STREAM_LOOP=true)
  # -c copy copies audio/video streams without re-encoding
  # -f rtsp publishes to MediaMTX via RTSP protocol
  loop_args=""
  if [ "$STREAM_LOOP" = "true" ]; then
    loop_args="-stream_loop -1"
  fi
  "$FFMPEG_BIN" \
    -hide_banner \
    -loglevel info \
    -re \
    $loop_args \
    -i "$file" \
    -c copy \
    -rtsp_transport tcp \
    -f rtsp \
    "rtsp://127.0.0.1:${RTSP_PORT}/${stream_name}" &
  pid=$!
  pids="$pids $pid"
  sleep 0.2
done

cleanup() {
  echo "Stopping RTSP streams"
  for pid in $pids; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid"
    fi
  done
}

trap 'cleanup' INT TERM

status=0
for pid in $pids; do
  if ! wait "$pid"; then
    status=$?
  fi
done

exit $status
