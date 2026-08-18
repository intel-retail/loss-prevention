# =====================================
# Stage 1: build MediaMTX with patched Go
# =====================================
FROM golang:1.26.6-alpine3.23 AS mediamtx-build

RUN apk add --no-cache git ca-certificates
RUN update-ca-certificates
RUN git clone --depth 1 --branch v1.20.0 https://github.com/bluenviron/mediamtx.git /src/mediamtx
RUN printf 'v1.20.0\n' > /src/mediamtx/internal/core/VERSION
RUN : > /src/mediamtx/internal/servers/hls/hls.min.js
RUN mkdir -p /src/mediamtx/internal/staticsources/rpicamera/mtxrpicam_32 /src/mediamtx/internal/staticsources/rpicamera/mtxrpicam_64
RUN cd /src/mediamtx && /usr/local/go/bin/go build -buildvcs=false -trimpath -ldflags='-s -w' -o /out/mediamtx ./


# ========================================
# Stage 2: grab upstream default config
# ========================================
FROM bluenviron/mediamtx:1.20.0 AS mediamtx-config


# ================================
# Stage 3: runtime image
# ================================
FROM alpine:3.23.4

# ---- Use official Alpine HTTPS CDN (proxy-friendly) ----
RUN echo "https://dl-cdn.alpinelinux.org/alpine/v3.23/main" > /etc/apk/repositories && \
    echo "https://dl-cdn.alpinelinux.org/alpine/v3.23/community" >> /etc/apk/repositories && \
    apk update --no-cache && \
    apk upgrade --no-cache && \
    apk add --no-cache \
    ffmpeg \
    busybox-extras \
    ca-certificates \
    "libcrypto3>=3.5.7-r0" \
    "libssl3>=3.5.7-r0" && \
    update-ca-certificates

# ---- App directory ----
WORKDIR /opt/rtsp-streamer

# ---- Copy MediaMTX binary and default config ----
COPY --from=mediamtx-build /out/mediamtx ./mediamtx
COPY --from=mediamtx-config /mediamtx.yml ./mediamtx.yml

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
    