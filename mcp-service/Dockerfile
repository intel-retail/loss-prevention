# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Loss Prevention MCP service image using FastMCP and a service-owned SQLite log.
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts
RUN pip install --no-cache-dir .

ENV MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=9100 \
    STORE_ID=store_001 \
    LP_LOG_PATH=/data/lp_log.sqlite \
    SEED_DEMO=false \
    PYTHONUNBUFFERED=1

RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 9100

# Optional local demo seeding when SEED_DEMO=true, then run the MCP server.
CMD ["sh", "-c", "if [ \"$SEED_DEMO\" = \"true\" ]; then python /app/scripts/seed_demo.py || true; fi; exec lp-mcp"]
