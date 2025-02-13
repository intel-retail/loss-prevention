# Copyright © 2024 Intel Corporation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

.PHONY: build build-realsense run down
.PHONY: build-telegraf run-telegraf run-portainer clean-all clean-results clean-telegraf clean-models down-portainer
.PHONY: download-models clean-test run-demo run-headless download-yolov8s logs
.PHONY: clean-benchmark-results

MKDOCS_IMAGE ?= asc-mkdocs
PIPELINE_COUNT ?= 1
TARGET_FPS ?= 14.95
CONTAINER_NAMES ?= gst0
DOCKER_COMPOSE ?= docker-compose.yml
RESULTS_DIR ?= $(PWD)/results
RETAIL_USE_CASE_ROOT ?= $(PWD)
BENCHMARK_DURATION ?= 45
DENSITY_INCREMENT ?= 1

download-models: download-yolov8s
	./download_models/downloadModels.sh	
	
download-yolov8s:
	@if [ ! -d "$(PWD)/models/object_detection/yolov8s/" ]; then \
		echo "The yolov8s folder doesn't exist. Creating it and downloading the model..."; \
		mkdir -p $(PWD)/models/object_detection/yolov8s/; \
		docker run --user 1000:1000 -e HTTPS_PROXY=${HTTPS_PROXY} -e HTTP_PROXY=${HTTPS_PROXY} --rm \
			-e YOLO_DEBUG=1 \
			-v $(PWD)/models/object_detection/yolov8s:/models \
			ultralytics/ultralytics:8.2.101-cpu \
			bash -c "cd /models && yolo export model=yolov8s.pt format=openvino"; \
		mv $(PWD)/models/object_detection/yolov8s/yolov8s_openvino_model $(PWD)/models/object_detection/yolov8s/FP32; \
	else \
		echo "yolov8s already exists."; \
	fi
	
download-sample-videos:
	cd performance-tools/benchmark-scripts && ./download_sample_videos.sh

clean-models:
	@find ./models/ -mindepth 1 -maxdepth 1 -type d -exec sudo rm -r {} \;

run-smoke-tests: | download-models update-submodules download-sample-videos
	@echo "Running smoke tests for OVMS profiles"
	@./smoke_test.sh > smoke_tests_output.log
	@echo "results of smoke tests recorded in the file smoke_tests_output.log"
	@grep "Failed" ./smoke_tests_output.log || true
	@grep "===" ./smoke_tests_output.log || true

update-submodules:
	@git submodule update --init --recursive
	@git submodule update --remote --merge

build:
	docker build --build-arg HTTPS_PROXY=${HTTPS_PROXY} --build-arg HTTP_PROXY=${HTTP_PROXY} --target build-default -t dlstreamer:dev -f src/Dockerfile src/
	docker build --build-arg HTTPS_PROXY=${HTTPS_PROXY} --build-arg HTTP_PROXY=${HTTP_PROXY} -t loss-prevention:dev -f src/app/Dockerfile src/app

build-scale:
	docker build --build-arg HTTPS_PROXY=${HTTPS_PROXY} --build-arg HTTP_PROXY=${HTTP_PROXY} -t lp-scale:dev -f src/weightScale/Dockerfile src/weightScale

build-barcode:
	cd src/barcode-scanner-service && $(MAKE) build

build-realsense:
	docker build --build-arg HTTPS_PROXY=${HTTPS_PROXY} --build-arg HTTP_PROXY=${HTTP_PROXY} --target build-realsense -t dlstreamer:realsense -f src/Dockerfile src/

build-pipeline-server: | download-models update-submodules download-sample-videos
	docker build --build-arg HTTPS_PROXY=${HTTPS_PROXY} --build-arg HTTP_PROXY=${HTTP_PROXY} -t dlstreamer:pipeline-server -f src/pipeline-server/Dockerfile.pipeline-server src/pipeline-server

run:
	docker compose -f src/$(DOCKER_COMPOSE) up -d

run-render-mode:
	xhost +local:docker
	INPUTSRC=https://github.com/openvinotoolkit/openvino_notebooks/raw/refs/heads/recipes/recipes/automated_self_checkout/data/example.mp4 RENDER_MODE=1 docker compose -f src/$(DOCKER_COMPOSE) up -d

down:
	docker compose -f src/$(DOCKER_COMPOSE) down

run-demo: | download-models update-submodules download-sample-videos
	@echo "Building Loss Prevention app"	
	$(MAKE) build
	$(MAKE) build-scale
	@echo Running Loss Prevention pipeline
	$(MAKE) run-render-mode

run-headless: | download-models update-submodules download-sample-videos
	@echo "Building Loss Prevention app"
	$(MAKE) build
	$(MAKE) build-scale
	@echo Running Loss Prevention pipeline
	$(MAKE) run

run-pipeline-server: | build-pipeline-server
	RETAIL_USE_CASE_ROOT=$(RETAIL_USE_CASE_ROOT) docker compose -f src/pipeline-server/docker-compose.pipeline-server.yml up -d

down-pipeline-server:
	docker compose -f src/pipeline-server/docker-compose.pipeline-server.yml down

build-benchmark:
	cd performance-tools && $(MAKE) build-benchmark-docker

benchmark: build-benchmark download-models
	cd performance-tools/benchmark-scripts && python benchmark.py --compose_file ../../src/$(DOCKER_COMPOSE) \
	--pipeline $(PIPELINE_COUNT) --duration $(BENCHMARK_DURATION) --results_dir $(RESULTS_DIR)
# consolidate to show the summary csv
	@cd performance-tools/benchmark-scripts && ROOT_DIRECTORY=$(RESULTS_DIR) $(MAKE) --no-print-directory consolidate && \
	echo "Loss Prevention benchmark results are saved in $(RESULTS_DIR)/summary.csv file" && \
	echo "====== Loss prevention benchmark results summary: " && cat $(RESULTS_DIR)/summary.csv

benchmark-stream-density: build-benchmark download-models
# example commands:
# 1. for single container pipeline stream density
# ```console
#     make PIPELINE_SCRIPT=yolov8s_roi.sh benchmark-stream-density
# ```
# 2. for multiple container pipelines stream density:
# ```console
#     make DOCKER_COMPOSE=docker-compose-2-clients.yml BENCHMARK_DURATION=90 TARGET_FPS="10.95 2.95" CONTAINER_NAMES="gst1 gst2" \
#				benchmark-stream-density
# ```
#
	cd performance-tools/benchmark-scripts && python benchmark.py --compose_file ../../src/$(DOCKER_COMPOSE) \
	--target_fps $(TARGET_FPS) --container_names $(CONTAINER_NAMES) \
	--density_increment $(DENSITY_INCREMENT) --results_dir $(RESULTS_DIR)

clean-benchmark-results:
	cd performance-tools/benchmark-scripts && rm -rf $(RESULTS_DIR)/* || true

build-telegraf:
	cd telegraf && $(MAKE) build

run-telegraf:
	cd telegraf && $(MAKE) run

clean-telegraf: 
	./clean-containers.sh influxdb2
	./clean-containers.sh telegraf

run-portainer:
	docker compose -p portainer -f docker-compose-portainer.yml up -d

down-portainer:
	docker compose -p portainer -f docker-compose-portainer.yml down

clean-results:
	rm -rf results/*

clean-all: 
	docker rm -f $(docker ps -aq)

docs: clean-docs
	mkdocs build
	mkdocs serve -a localhost:8008

docs-builder-image:
	docker build \
		-f Dockerfile.docs \
		-t $(MKDOCS_IMAGE) \
		.

build-docs: docs-builder-image
	docker run --rm \
		-u $(shell id -u):$(shell id -g) \
		-v $(PWD):/docs \
		-w /docs \
		$(MKDOCS_IMAGE) \
		build

serve-docs: docs-builder-image
	docker run --rm \
		-it \
		-u $(shell id -u):$(shell id -g) \
		-p 8008:8000 \
		-v $(PWD):/docs \
		-w /docs \
		$(MKDOCS_IMAGE)

clean-docs:
	rm -rf docs/

helm-package:
	helm package helm/ -u -d .deploy
	helm package helm/
	helm repo index .
	helm repo index --url https://github.com/intel-retail/loss-prevention .

logs:
	@CONTAINER_ID=$(shell docker ps --filter "name=loss-prevention" --format "{{.ID}}") && \
	if [ -n "$$CONTAINER_ID" ]; then \
		docker logs -f $$CONTAINER_ID; \
	else \
		echo "No running container found with name containing 'loss-prevention'"; \
	fi