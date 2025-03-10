# Copyright © 2025 Intel Corporation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

.PHONY: build run down

build:
	docker build -f Dockerfile.python -t barcode:dev .

run:
	docker compose up -d

down:
	docker compose down