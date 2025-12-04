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
BATCH_SIZE_DETECT ?= 1
BATCH_SIZE_CLASSIFY ?= 1
REGISTRY ?= true
DOCKER_COMPOSE ?= docker-compose.yml
DOCKER_COMPOSE_REGISTRY ?= docker-compose-reg.yml

TAG ?= rc1
#local image references
MODELDOWNLOADER_IMAGE ?= model-downloader-lp:$(TAG)
PIPELINE_RUNNER_IMAGE ?= pipeline-runner-lp:$(TAG)
BENCHMARK_IMAGE ?= benchmark:latest
REGISTRY ?= true
# Registry image references
REGISTRY_MODEL_DOWNLOADER ?= intel/model-downloader-lp:$(TAG)
REGISTRY_PIPELINE_RUNNER ?= intel/pipeline-runner-lp:$(TAG)
REGISTRY_BENCHMARK ?= intel/retail-benchmark:$(TAG)

BASE_VLM_COMPOSE = "./lp-vlm/src/docker-compose-base.yml"
VLM_COMPOSE = "./lp-vlm/src/docker-compose.yaml"

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

fetch-model-downloader:
	@echo "Fetching model downloader from registry..."
	docker pull $(REGISTRY_MODEL_DOWNLOADER)
	docker tag $(REGISTRY_MODEL_DOWNLOADER) $(MODELDOWNLOADER_IMAGE)
	@echo "Model downloader ready"

build-model-downloader: | validate-pipeline-config
	@echo "Building model downloader"
	docker build --build-arg HTTPS_PROXY=${HTTPS_PROXY} --build-arg HTTP_PROXY=${HTTP_PROXY} -t $(MODELDOWNLOADER_IMAGE) -f docker/Dockerfile.downloader .
	@echo "assets downloader completed"

run-model-downloader:
	@echo "Running assets downloader"
	docker run --rm \
		-e HTTP_PROXY=${HTTP_PROXY} \
		-e HTTPS_PROXY=${HTTPS_PROXY} \
		-e http_proxy=${HTTP_PROXY} \
		-e https_proxy=${HTTPS_PROXY} \
		-e MODELS_DIR=/workspace/models \
		-e WORKLOAD_DIST=${WORKLOAD_DIST} \
		-v "$(shell pwd)/models:/workspace/models" \
		-v "$(shell pwd)/configs:/workspace/configs" \
		$(MODELDOWNLOADER_IMAGE)
	@echo "assets downloader completed"

fetch-pipeline-runner:
	@echo "Fetching pipeline runner from registry..."
	docker pull $(REGISTRY_PIPELINE_RUNNER)
	docker tag $(REGISTRY_PIPELINE_RUNNER) $(PIPELINE_RUNNER_IMAGE)
	@echo "Pipeline runner ready"

build-pipeline-runner:
	@echo "Building pipeline runner"
	docker build \
		--build-arg HTTPS_PROXY=${HTTPS_PROXY} \
		--build-arg HTTP_PROXY=${HTTP_PROXY} \
		--build-arg BATCH_SIZE_DETECT=${BATCH_SIZE_DETECT} \
		--build-arg BATCH_SIZE_CLASSIFY=${BATCH_SIZE_CLASSIFY} \
		-t $(PIPELINE_RUNNER_IMAGE) \
		-f docker/Dockerfile.pipeline .
	@echo "pipeline runner build completed"


run-pipeline-runner:
	@echo "Running pipeline runner"
	docker run \
		--env DISPLAY=$(DISPLAY) \
		--env XDG_RUNTIME_DIR=$(XDG_RUNTIME_DIR) \
		--volume /tmp/.X11-unix:/tmp/.X11-unix \
		-e HTTP_PROXY=${HTTP_PROXY} \
		-e HTTPS_PROXY=${HTTPS_PROXY} \
		-e http_proxy=${HTTP_PROXY} \
		-e https_proxy=${HTTPS_PROXY} \
		--volume $(PWD)/results:/home/pipeline-server/results \
		$(PIPELINE_RUNNER_IMAGE)
	@echo "pipeline runner container completed successfully"


update-submodules:
	@echo "Cloning performance tool repositories"
	git submodule deinit -f .
	git submodule update --init --recursive
	@echo "Submodules updated (if any present)."

fetch-benchmark:
	@echo "Fetching benchmark image from registry..."
	docker pull $(REGISTRY_BENCHMARK)
	docker tag $(REGISTRY_BENCHMARK) $(BENCHMARK_IMAGE)
	@echo "Benchmark image ready"

build-benchmark:
	@if [ "$(REGISTRY)" = "true" ]; then \
		$(MAKE) fetch-pipeline-runner; \
		$(MAKE) fetch-benchmark; \
	else \
		$(MAKE) build-pipeline-runner; \
		cd performance-tools && $(MAKE) build-benchmark-docker; \
	fi

benchmark: build-benchmark download-sample-videos download-models	
	cd performance-tools/benchmark-scripts && \
	export MULTI_STREAM_MODE=1 && \
	( \
	python3 -m venv venv && \
	. venv/bin/activate && \
	pip3 install -r requirements.txt && \
	if [ "$(REGISTRY)" = "true" ]; then \
		python3 benchmark.py --compose_file ../../src/$(DOCKER_COMPOSE_REGISTRY) --pipelines $(PIPELINE_COUNT) --results_dir $(RESULTS_DIR) --benchmark_type reg; \
	else \
		python3 benchmark.py --compose_file ../../src/$(DOCKER_COMPOSE) --pipelines $(PIPELINE_COUNT) --results_dir $(RESULTS_DIR); \
	fi && \
	deactivate \
	)

run-lp: | validate_workload_mapping update-submodules download-sample-videos download-models
	@echo Running loss prevention pipeline
	@if [ "$(RENDER_MODE)" != "0" ]; then \
		$(MAKE) run-render-mode; \
	else \
		$(MAKE) run; \
	fi
	$(MAKE) run-vlm

down-lp:
	@if [ "$(REGISTRY)" = "true" ]; then \
		echo "Stopping registry demo containers..."; \
		docker compose -f src/$(DOCKER_COMPOSE_REGISTRY) down; \
		echo "Registry demo containers stopped and removed."; \
	else \
		docker compose -f src/$(DOCKER_COMPOSE) down; \
	fi
	$(MAKE) down-vlm

run:
	@if [ "$(REGISTRY)" = "true" ]; then \
		echo "##############Using registry mode - fetching pipeline runner..."; \
		BATCH_SIZE_DETECT=$(BATCH_SIZE_DETECT) BATCH_SIZE_CLASSIFY=$(BATCH_SIZE_CLASSIFY) docker compose -f src/$(DOCKER_COMPOSE_REGISTRY) up -d; \
	else \
		docker compose -f src/$(DOCKER_COMPOSE) build pipeline-runner; \
		BATCH_SIZE_DETECT=$(BATCH_SIZE_DETECT) BATCH_SIZE_CLASSIFY=$(BATCH_SIZE_CLASSIFY) docker compose -f src/$(DOCKER_COMPOSE) up -d; \
	fi

run-vlm:
	@VIDEO_NAME=$$(python3 lp-vlm/src/workload_utils.py --camera-config configs/$(CAMERA_STREAM)); \
	echo "VIDEO_NAME=$$VIDEO_NAME" > lp-vlm/lp-vlm.env; \
	echo "Using VIDEO_NAME=$$VIDEO_NAME"; \
	# Create log file on host if it doesn't exist
	LOG_FILE=vlm_loss_prevention.log; \
	mkdir -p $$(dirname $$LOG_FILE); \
	[ -f $$LOG_FILE ] || touch $$LOG_FILE; \
	docker compose -f $(VLM_COMPOSE) --env-file lp-vlm/lp-vlm.env build --pull; \
	docker compose -f $(VLM_COMPOSE) --env-file lp-vlm/lp-vlm.env up -d
	$(MAKE) clean-images

down-vlm:
	@echo "Stopping VLM demo containers..."
	docker compose -f $(VLM_COMPOSE) down
	@echo "Cleaning up VLM temporary files..."
	@rm -f vlm_loss_prevention.log
	@rm -f lp-vlm/lp-vlm.env
	@echo "VLM cleanup completed"

run-render-mode:
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
		RENDER_MODE=1 CAMERA_STREAM=$(CAMERA_STREAM) WORKLOAD_DIST=$(WORKLOAD_DIST) BATCH_SIZE_DETECT=$(BATCH_SIZE_DETECT) BATCH_SIZE_CLASSIFY=$(BATCH_SIZE_CLASSIFY) docker compose -f src/$(DOCKER_COMPOSE_REGISTRY) up -d; \
	else \
		docker compose -f src/$(DOCKER_COMPOSE) build pipeline-runner; \
		RENDER_MODE=1 CAMERA_STREAM=$(CAMERA_STREAM) WORKLOAD_DIST=$(WORKLOAD_DIST) BATCH_SIZE_DETECT=$(BATCH_SIZE_DETECT) BATCH_SIZE_CLASSIFY=$(BATCH_SIZE_CLASSIFY) docker compose -f src/$(DOCKER_COMPOSE) up -d; \
	fi
	$(MAKE) clean-images

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
	if [ "$(REGISTRY)" = "true" ]; then \
		python3 benchmark.py \
			--compose_file ../../src/$(DOCKER_COMPOSE_REGISTRY) \
			--init_duration $(INIT_DURATION) \
			--target_fps $(TARGET_FPS) \
			--container_names $(CONTAINER_NAMES) \
			--density_increment $(DENSITY_INCREMENT) \
			--benchmark_type reg \
			--results_dir $(RESULTS_DIR); \
	else \
		python3 benchmark.py \
			--compose_file ../../src/$(DOCKER_COMPOSE) \
			--init_duration $(INIT_DURATION) \
			--target_fps $(TARGET_FPS) \
			--container_names $(CONTAINER_NAMES) \
			--density_increment $(DENSITY_INCREMENT) \
			--results_dir $(RESULTS_DIR); \
	fi; \
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
	if [ "$(REGISTRY)" = "true" ]; then \
		python3 benchmark.py --compose_file ../../src/$(DOCKER_COMPOSE_REGISTRY) --pipelines $(PIPELINE_COUNT) --results_dir $(RESULTS_DIR) --benchmark_type reg; \
	else \
		python3 benchmark.py --compose_file ../../src/$(DOCKER_COMPOSE) --pipelines $(PIPELINE_COUNT) --results_dir $(RESULTS_DIR); \
	fi && \
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
