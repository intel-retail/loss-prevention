# Copyright © 2025 Intel Corporation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

.PHONY: update-submodules download-models download-samples download-sample-videos build-assets-downloader run-assets-downloader build-pipeline-runner run-loss-prevention clean-images clean-containers clean-all clean-project-images validate-config validate-camera-config validate-all-configs


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
REGISTRY ?= false

download-models:
	@echo ".....Checking if models exist....."
	@chmod +x ./check_models.sh
	@if ./check_models.sh; then \
		echo "All models present, skipping download."; \
	else \
		echo "Models missing, starting download process..."; \
		if [ "$(REGISTRY)" = "true" ]; then \
			echo "Using registry mode - pulling model downloader..."; \
			docker pull iotgdevcloud/model-downloader-lp:latest; \
			docker tag iotgdevcloud/model-downloader-lp:latest model-downloader:lp; \
		else \
			$(MAKE) build-model-downloader; \
		fi; \
		$(MAKE) run-model-downloader; \
	fi

download-sample-videos: | validate-camera-config
	@echo "Downloading and formatting videos for all cameras in $(CAMERA_STREAM)..."
	python3 download-scripts/download-video.py --camera-config configs/$(CAMERA_STREAM) --format-script performance-tools/benchmark-scripts/format_avc_mp4.sh

build-model-downloader: | validate-pipeline-config
	@echo "Building model downloader locally"
	docker build --build-arg HTTPS_PROXY=${HTTPS_PROXY} --build-arg HTTP_PROXY=${HTTP_PROXY} -t model-downloader:lp -f docker/Dockerfile.downloader .
	@echo "Model downloader build completed"

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
		model-downloader:lp
	@echo "assets downloader completed"


build-pipeline-runner:
	@echo "Building pipeline runner"
	docker build \
		--build-arg HTTPS_PROXY=${HTTPS_PROXY} \
		--build-arg HTTP_PROXY=${HTTP_PROXY} \
		--build-arg BATCH_SIZE_DETECT=${BATCH_SIZE_DETECT} \
        --build-arg BATCH_SIZE_CLASSIFY=${BATCH_SIZE_CLASSIFY} \
		-t pipeline-runner:lp \
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
		pipeline-runner:lp
	@echo "pipeline runner container completed successfully"


update-submodules:
	@echo "Cloning performance tool repositories"
	git submodule deinit -f .
	git submodule update --init --recursive
	git submodule update --remote --merge
	@echo "Submodules updated (if any present)."

build-benchmark:
	cd performance-tools && $(MAKE) build-benchmark-docker


benchmark: build-benchmark download-sample-videos download-models	
	cd performance-tools/benchmark-scripts && \
    ( \
	python3 -m venv venv && \
	. venv/bin/activate && \
	pip3 install -r requirements.txt && \
	python3 benchmark.py --compose_file ../../src/docker-compose.yml --pipelines $(PIPELINE_COUNT) --results_dir $(RESULTS_DIR) && \
	deactivate \
	)

run:
	@if [ "$(REGISTRY)" = "true" ]; then \
		echo "Using registry mode with docker-compose-reg.yml--------------------------------------"; \
		BATCH_SIZE_DETECT=$(BATCH_SIZE_DETECT) BATCH_SIZE_CLASSIFY=$(BATCH_SIZE_CLASSIFY) \
		docker compose -f src/docker-compose-reg.yml up -d; \
	else \
		echo "Using local build mode with docker-compose.yml========================================="; \
		BATCH_SIZE_DETECT=$(BATCH_SIZE_DETECT) BATCH_SIZE_CLASSIFY=$(BATCH_SIZE_CLASSIFY) \
		docker compose -f src/docker-compose.yml up -d; \
	fi

run-lp: | validate_workload_mapping update-submodules download-sample-videos
	@echo downloading the models
	$(MAKE) download-models
	@echo Running loss prevention pipeline
	@if [ "$(RENDER_MODE)" != "0" ]; then \
		$(MAKE) run-render-mode; \
	else \
		$(MAKE) run; \
	fi

down-lp:
	@if [ "$(REGISTRY)" = "true" ]; then \
		docker compose -f src/docker-compose-reg.yml down; \
	else \
		docker compose -f src/docker-compose.yml down; \
	fi

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
		echo "Using registry mode - pulling pipeline runner...------------------------------------------------"; \
		docker pull iotgdevcloud/pipeline-runner-lp:latest; \
		RENDER_MODE=1 CAMERA_STREAM=$(CAMERA_STREAM) WORKLOAD_DIST=$(WORKLOAD_DIST) BATCH_SIZE_DETECT=$(BATCH_SIZE_DETECT) BATCH_SIZE_CLASSIFY=$(BATCH_SIZE_CLASSIFY) docker compose -f src/docker-compose-reg.yml up -d; \
	else \
		echo "Using local build mode"; \
		docker compose -f src/docker-compose.yml build pipeline-runner; \
		RENDER_MODE=1 CAMERA_STREAM=$(CAMERA_STREAM) WORKLOAD_DIST=$(WORKLOAD_DIST) BATCH_SIZE_DETECT=$(BATCH_SIZE_DETECT) BATCH_SIZE_CLASSIFY=$(BATCH_SIZE_CLASSIFY) docker compose -f src/docker-compose.yml up -d; \
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
    ( \
	python3 -m venv venv && \
	. venv/bin/activate && \
	pip3 install -r requirements.txt && \
	python3 benchmark.py \
	  --compose_file ../../src/docker-compose.yml \
	  --init_duration $(INIT_DURATION) \
	  --target_fps $(TARGET_FPS) \
	  --container_names $(CONTAINER_NAMES) \
	  --density_increment $(DENSITY_INCREMENT) \
	  --results_dir $(RESULTS_DIR) && \
	deactivate \
	)
	
benchmark-quickstart:
	CAMERA_STREAM=camera_to_workload_full.json WORKLOAD_DIST=workload_to_pipeline_gpu.json RENDER_MODE=0 $(MAKE) benchmark
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
	@docker rmi model-downloader:lp pipeline-runner:lp 2>/dev/null || true
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