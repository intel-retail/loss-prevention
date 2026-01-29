# ================================
# Stage 1: grab MediaMTX binaries
# ================================
FROM bluenviron/mediamtx:1.15.6 AS mediamtx


# ================================
# Stage 2: runtime image
# ================================
FROM alpine:3.19

# ---- Proxy support (IMPORTANT for corp networks) ----
# These will be populated at build time if present
ARG http_proxy
ARG https_proxy
ARG HTTP_PROXY
ARG HTTPS_PROXY

ENV http_proxy=${http_proxy} \
    https_proxy=${https_proxy} \
    HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY}

# ---- Use official Alpine HTTPS CDN (proxy-friendly) ----
RUN echo "https://dl-cdn.alpinelinux.org/alpine/v3.19/main" > /etc/apk/repositories && \
    echo "https://dl-cdn.alpinelinux.org/alpine/v3.19/community" >> /etc/apk/repositories && \
    apk update --no-cache && \
    apk add --no-cache \
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
COPY start.sh ./start.sh
RUN chmod +x ./start.sh ./mediamtx

# ---- Runtime config ----
ENV MEDIA_DIR=/media \
    RTSP_PORT=8554 \
    MEDIAMTX_BIN=/opt/rtsp-streamer/mediamtx

EXPOSE 8554

# ---- Health Check ----
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD nc -z 127.0.0.1 ${RTSP_PORT} || exit 1

# ---- Run ----
ENTRYPOINT ["/opt/rtsp-streamer/start.sh"]
