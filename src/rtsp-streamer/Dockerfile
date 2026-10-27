# ================================
# Stage 1: grab MediaMTX binaries
# ================================
FROM bluenviron/mediamtx:1.20.0 AS mediamtx


# ================================
# Stage 2: runtime image
# ================================
FROM alpine:3.23.4

# ---- Use official Alpine HTTPS CDN (proxy-friendly) ----
RUN echo "https://dl-cdn.alpinelinux.org/alpine/v3.23/main" > /etc/apk/repositories && \
    echo "https://dl-cdn.alpinelinux.org/alpine/v3.23/community" >> /etc/apk/repositories && \
    apk update --no-cache && \
    apk add --no-cache \
        openssl \
        ffmpeg \
        busybox-extras \
        ca-certificates && \
    update-ca-certificates

# ---- App directory ----
WORKDIR /opt/rtsp-streamer

# ---- Copy MediaMTX from stage 1 ----
COPY --from=mediamtx /mediamtx ./mediamtx
COPY --from=mediamtx /mediamtx.yml ./mediamtx.yml

# ---- Startup script ----
COPY start.sh healthcheck.sh ./
RUN chmod +x ./start.sh ./healthcheck.sh ./mediamtx

# ---- Runtime config ----
ENV MEDIA_DIR=/media \
    RTSP_PORT=8554 \
    MEDIAMTX_BIN=/opt/rtsp-streamer/mediamtx

EXPOSE 8554

# ---- Health Check ----
HEALTHCHECK --interval=10s --timeout=15s --start-period=60s --retries=3 \
  CMD ["/opt/rtsp-streamer/healthcheck.sh"]

# ---- Run ----
ENTRYPOINT ["/opt/rtsp-streamer/start.sh"]
