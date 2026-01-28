# Stage 1: grab MediaMTX binaries
FROM bluenviron/mediamtx:1.15.6 AS mediamtx

# Stage 2: runtime image with ffmpeg and netcat
FROM alpine:3.19

RUN apk add --no-cache ffmpeg busybox-extras

WORKDIR /opt/rtsp-streamer

COPY --from=mediamtx /mediamtx ./mediamtx
COPY --from=mediamtx /mediamtx.yml ./mediamtx.yml

COPY start.sh ./start.sh
RUN chmod +x ./start.sh ./mediamtx

EXPOSE 8554

ENV MEDIA_DIR=/media \
    RTSP_PORT=8554 \
    MEDIAMTX_BIN=/opt/rtsp-streamer/mediamtx

ENTRYPOINT ["/opt/rtsp-streamer/start.sh"]
