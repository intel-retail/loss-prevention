# Copyright © 2025 Intel Corporation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

.PHONY: update-submodules download-models download-samples download-sample-videos build-assets-downloader run-assets-downloader build-pipeline-runner run-loss-prevention clean-images clean-containers clean-all clean-project-images validate-config validate-camera-config validate-all-configs check-models


HTTP_PROXY := $(or $(HTTP_PROXY),$(http_proxy))
HTTPS_PROXY := $(or $(HTTPS_PROXY),$(https_proxy))
export HTTP_PROXY
export HTTPS_PROXY


export PWD=$(shell pwd)
HOST_IP := $(shell hostname -I | cut -d' ' -f1 2>/dev/null || ipconfig getifaddr en0)
export VLM_DEVICE ?= CPU
export VLM_SERVICE_PORT ?= 8000
export LP_BASE_DIR=$(PWD)
export LLM_BASE_DIR=$(PWD)/microservices/vlm/ov-models
export MINIO_API_HOST_PORT=4000
export MINIO_CONSOLE_HOST_PORT=4001
export LP_IP=$(HOST_IP)


# Default values for benchmark
PIPELINE_COUNT ?= 1
INIT_DURATION ?= 30
TARGET_FPS ?= 14.95
CONTAINER_NAMES ?= gst0
DENSITY_INCREMENT ?= 1
MKDOCS_IMAGE ?= asc-mkdocs
RESULTS_DIR ?= $(PWD)/benchmark
CAMERA_STREAM ?= camera_to_workload.json
WORKLOAD_DIST ?= workload_to_pipeline.json
VLM_CAMERA_STREAM ?= camera_to_workload_vlm.json
BATCH_SIZE_DETECT ?= 1
BATCH_SIZE_CLASSIFY ?= 1
REGISTRY ?= true
DOCKER_COMPOSE ?= docker-compose.yml

TAG ?= 4.4.0
#local image references
MODELDOWNLOADER_IMAGE ?= model-downloader:$(TAG)
PIPELINE_RUNNER_IMAGE ?= pipeline-runner-lp:$(TAG)
BENCHMARK_IMAGE ?= benchmark:latest
REGISTRY ?= true
# Registry image references
REGISTRY_MODEL_DOWNLOADER ?= intel/model-downloader:$(TAG)
REGISTRY_PIPELINE_RUNNER ?= intel/pipeline-runner-lp:$(TAG)
REGISTRY_BENCHMARK ?= intel/retail-benchmark:$(TAG)

BASE_VLM_COMPOSE = "./lp-vlm/src/docker-compose-base.yml"
VLM_COMPOSE = "./lp-vlm/src/docker-compose.yaml"

VLM_LOGS_FILE ?= $(PWD)/vlm_loss_prevention.log
LP_VLM_WORKLOAD_ENABLED := $(shell python3 lp-vlm/src/workload_utils.py --camera-config configs/$(CAMERA_STREAM) --has-lp-vlm)

check-models:
	@chmod +x check_models.sh
	@./check_models.sh models || true

download-models: check-models
	@if ./check_models.sh models; then \
		echo ".....Downloading models....."; \
		if [ "$(REGISTRY)" = "true" ]; then \
			$(MAKE) fetch-model-downloader; \
		else \
			$(MAKE) build-model-downloader; \
		fi; \
		$(MAKE) run-model-downloader; \
	else \
		echo ".....All models already present, skipping download....."; \
	fi

download-sample-videos: | validate-camera-config
	@echo "Downloading and formatting videos for all cameras in $(CAMERA_STREAM)..."
	python3 download-scripts/download-video.py --camera-config configs/$(CAMERA_STREAM) --format-script performance-tools/benchmark-scripts/format_avc_mp4.sh

update-submodules:
	@echo "Cloning performance tool repositories"
	git submodule deinit -f .
	git submodule update --init --recursive
	@echo "Submodules updated (if any present)."

run-lp:
	@echo Running loss prevention pipeline	
	LOG_FILE="vlm_loss_prevention.log"; \
	mkdir -p $$(dirname $$LOG_FILE); \
	[ -f $$LOG_FILE ] || touch $$LOG_FILE; \
	if [ "$(RENDER_MODE)" != "0" ]; then \
		$(MAKE) run-render-mode; \
	else \
		$(MAKE) run; \
	fi

down-lp:	
	docker compose -f src/$(DOCKER_COMPOSE) down	
	@echo "Cleaning up VLM temporary files..."
	@rm -f vlm_loss_prevention.log
	@rm -f lp-vlm/lp-vlm.env
	@echo "VLM cleanup completed"

run:
	@if [ "$(REGISTRY)" = "true" ]; then \
		echo "##############Using registry mode - fetching pipeline runner..."; \
		LP_VLM_WORKLOAD_ENABLED=$(LP_VLM_WORKLOAD_ENABLED) BATCH_SIZE_DETECT=$(BATCH_SIZE_DETECT) BATCH_SIZE_CLASSIFY=$(BATCH_SIZE_CLASSIFY) docker compose -f src/$(DOCKER_COMPOSE) up -d; \
	else \
		docker compose -f src/$(DOCKER_COMPOSE) build pipeline-runner; \
		LP_VLM_WORKLOAD_ENABLED=$(LP_VLM_WORKLOAD_ENABLED) BATCH_SIZE_DETECT=$(BATCH_SIZE_DETECT) BATCH_SIZE_CLASSIFY=$(BATCH_SIZE_CLASSIFY) docker compose -f src/$(DOCKER_COMPOSE) up --build -d; \
	fi


run-render-mode: validate_workload_mapping
	@if [ -z "$(DISPLAY)" ] || ! echo "$(DISPLAY)" | grep -qE "^:[0-9]+(\.[0-9]+)?$$"; then \
		echo "ERROR: Invalid or missing DISPLAY environment variable."; \
		echo "Please set DISPLAY in the format ':<number>' (e.g., ':0')."; \
		echo "Usage: make <target> DISPLAY=:<number>"; \
		echo "Example: make $@ DISPLAY=:0"; \
		exit 1; \
	fi
	@echo "Using DISPLAY=$(DISPLAY)"
	@echo "Using config file: configs/$(CAMERA_STREAM)"
	@echo "Using workload config: configs/$(WORKLOAD_DIST)"
	@xhost +local:docker	
	@if [ "$(REGISTRY)" = "true" ]; then \
		echo "##############Using registry mode - fetching pipeline runner..."; \
		RENDER_MODE=1  LP_VLM_WORKLOAD_ENABLED=$(LP_VLM_WORKLOAD_ENABLED) CAMERA_STREAM=$(CAMERA_STREAM) WORKLOAD_DIST=$(WORKLOAD_DIST) BATCH_SIZE_DETECT=$(BATCH_SIZE_DETECT) BATCH_SIZE_CLASSIFY=$(BATCH_SIZE_CLASSIFY) docker compose -f src/$(DOCKER_COMPOSE) up -d; \
	else \
		docker compose -f src/$(DOCKER_COMPOSE) build; \
		RENDER_MODE=1 LP_VLM_WORKLOAD_ENABLED=$(LP_VLM_WORKLOAD_ENABLED) CAMERA_STREAM=$(CAMERA_STREAM) WORKLOAD_DIST=$(WORKLOAD_DIST) BATCH_SIZE_DETECT=$(BATCH_SIZE_DETECT) BATCH_SIZE_CLASSIFY=$(BATCH_SIZE_CLASSIFY) docker compose -f src/$(DOCKER_COMPOSE) up --build -d; \
	fi	
	$(MAKE) clean-images

fetch-benchmark:
	@echo "Fetching benchmark image from registry..."
	docker pull $(REGISTRY_BENCHMARK)
	docker tag $(REGISTRY_BENCHMARK) $(BENCHMARK_IMAGE)
	@echo "Benchmark image ready"

build-benchmark:
	@echo "Building benchmark Docker image..."$(REGISTRY)
	@if [ "$(REGISTRY)" = "true" ]; then \
		$(MAKE) fetch-benchmark; \
	else \
		cd performance-tools && $(MAKE) build-benchmark-docker; \
	fi

benchmark: build-benchmark
	mkdir -p $$(dirname $(VLM_LOGS_FILE)); \
	[ -f $(VLM_LOGS_FILE) ] || touch $(VLM_LOGS_FILE); \
	cd performance-tools/benchmark-scripts && \
	export MULTI_STREAM_MODE=1 && \
	export LP_VLM_WORKLOAD_ENABLED=$(LP_VLM_WORKLOAD_ENABLED) && \
	( \
		python3 -m venv venv && \
		. venv/bin/activate && \
		pip3 install -r requirements.txt && \
		python3 benchmark.py \
			--compose_file ../../src/$(DOCKER_COMPOSE) \
			--pipelines $(PIPELINE_COUNT) \
			--results_dir $(RESULTS_DIR); \
		deactivate \
	)



benchmark-stream-density: build-benchmark download-models
	@if [ "$(OOM_PROTECTION)" = "0" ]; then \
        echo "╔════════════════════════════════════════════════════════════╗";\
		echo "║ WARNING                                                    ║";\
		echo "║                                                            ║";\
		echo "║ OOM Protection is DISABLED. This test may:                 ║";\
		echo "║ • Cause system instability or crashes                      ║";\
		echo "║ • Require hard reboot if system becomes unresponsive       ║";\
		echo "║ • Result in data loss in other applications                ║";\
		echo "║                                                            ║";\
		echo "║ Press Ctrl+C now to cancel, or wait 5 seconds...           ║";\
		echo "╚════════════════════════════════════════════════════════════╝";\
		sleep 5;\
    fi
	cd performance-tools/benchmark-scripts && \
	export MULTI_STREAM_MODE=1 && \
    ( \
	python3 -m venv venv && \
	. venv/bin/activate && \
	pip3 install -r requirements.txt && \	
	python3 benchmark.py \
		--compose_file ../../src/$(DOCKER_COMPOSE) \
		--init_duration $(INIT_DURATION) \
		--target_fps $(TARGET_FPS) \
		--container_names $(CONTAINER_NAMES) \
		--density_increment $(DENSITY_INCREMENT) \
		--results_dir $(RESULTS_DIR); \	
	deactivate \
	)
	
benchmark-quickstart: download-models download-sample-videos
	@if [ "$(REGISTRY)" = "true" ]; then \
		echo "Using registry mode - skipping benchmark container build..."; \
	else \
		echo "Building benchmark container locally..."; \
		$(MAKE) build-benchmark; \
	fi
	cd performance-tools/benchmark-scripts && \
	export MULTI_STREAM_MODE=1 && \
	( \
	python3 -m venv venv && \
	. venv/bin/activate && \
	pip3 install -r requirements.txt && \	
	python3 benchmark.py --compose_file ../../src/$(DOCKER_COMPOSE) --pipelines $(PIPELINE_COUNT) --results_dir $(RESULTS_DIR); \
	&& \
	deactivate \
	)
	$(MAKE) consolidate-metrics

clean-images:
	@echo "Cleaning up dangling Docker images..."
	@docker image prune -f
	@echo "Cleaning up unused Docker images..."
	@docker images -f "dangling=true" -q | xargs -r docker rmi
	@echo "Dangling images cleaned up"

clean-containers:
	@echo "Cleaning up stopped containers..."
	@docker container prune -f
	@echo "Stopped containers cleaned up"

clean-all:
	@echo "Cleaning up all unused Docker resources..."
	@docker system prune -f
	@echo "Cleaning up build cache..."
	@docker builder prune -f
	@echo "All unused Docker resources cleaned up"

clean-project-images:
	@echo "Cleaning up project-specific images..."
	@docker rmi $(MODELDOWNLOADER_IMAGE) $(PIPELINE_RUNNER_IMAGE) 2>/dev/null || true
	@echo "Project images cleaned up"

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

validate_workload_mapping:
	python3 src/validate-configs.py --validate-workload-mapping --camera-config configs/$(CAMERA_STREAM) --pipeline-config configs/$(WORKLOAD_DIST)

validate-pipeline-config:
	@echo "Validating pipeline configuration..."
	@python3 src/validate-configs.py --validate-pipeline --pipeline-config configs/$(WORKLOAD_DIST)

validate-camera-config:
	@echo "Validating camera configuration..."
	@python3 src/validate-configs.py --validate-camera --camera-config configs/$(CAMERA_STREAM)

validate-all-configs:
	@echo "Validating all configuration files..."
	@python3 src/validate-configs.py --validate-all

consolidate-metrics:
	cd performance-tools/benchmark-scripts && \
	( \
	python3 -m venv venv && \
	. venv/bin/activate && \
	pip install -r requirements.txt && \
	python3 consolidate_multiple_run_of_metrics.py --root_directory $(RESULTS_DIR) --output $(RESULTS_DIR)/metrics.csv && \
	deactivate \
	)

plot-metrics:
	cd performance-tools/benchmark-scripts && \
	( \
	python3 -m venv venv && \
	. venv/bin/activate && \
	pip install -r requirements.txt && \
	python3 usage_graph_plot.py --dir $(RESULTS_DIR)  && \
	deactivate \
	)
