#
# Copyright (C) 2024-25 Intel Corporation.
#
# SPDX-License-Identifier: Apache-2.0
#

.PHONY: build run down

build:
	docker build --build-arg HTTPS_PROXY=${HTTPS_PROXY} --build-arg HTTP_PROXY=${HTTP_PROXY} -f Dockerfile -t lp-sensor:dev .

run:
	docker compose up -d
down:
	docker compose down