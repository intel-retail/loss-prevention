# Copyright © 2025 Intel Corporation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

.PHONY: run-demo down build 
export PWD=$(shell pwd)
HOST_IP := $(shell hostname -I | cut -d' ' -f1 2>/dev/null || ipconfig getifaddr en0)
export VLM_DEVICE ?= CPU
export VLM_SERVICE_PORT ?= 8000
export LP_BASE_DIR=$(PWD)
export LLM_BASE_DIR=$(PWD)/microservices/vlm/ov-models
export MINIO_API_HOST_PORT=4000
export MINIO_CONSOLE_HOST_PORT=4001
export LP_IP=$(HOST_IP)

run-demo: clean 
	@echo "🏁 Starting Loss Prevention Enhanced Demo..."
	@echo "🔹 using LP_BASE_DIR: $(LP_BASE_DIR)"
	@echo "🔹 setting up VLM service"
	cd microservices/vlm/docker && docker compose up -d --build
	@echo "🔹 setting up rabbitmq"
	cd microservices/rabbitmq/docker && docker compose up -d --build
	@echo "⏳ Waiting for RabbitMQ to become healthy..."
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' rabbitmq)" = "healthy" ]; do \
		printf "."; \
		sleep 2; \
	done
	@echo "🔹 RabbitMQ is healthy"
	@echo "🔹 setting up minio"
	cd microservices/minio/docker && docker compose up -d --build
	@echo "🔹 running prod-consumer combined docker file $(PWD)"
	cd $(PWD) && docker compose -f src/docker-compose.yaml up -d --build

clean:
	@echo "🧹 Cleaning up logs..."
	@find . -maxdepth 1 -type f -name "*.log" -exec rm -f {} \;
	@echo "✅ Logs removed successfully."

down:
	@echo "🔹 Stopping VLM service"
	cd microservices/vlm/docker && docker compose down
	@echo "🔹 Stopping rabbitmq"
	cd microservices/rabbitmq/docker && docker compose down
	@echo "🔹 Stopping minio"
	cd microservices/minio/docker && docker compose down
	@echo "🔹 Removing all containers (keeping images)"
	@echo "🔹 stopping prod-consumer combined docker file $(PWD)"
	cd $(PWD) && docker compose -f src/docker-compose.yaml down
	@docker rm -f $$(docker ps -aq) 2>/dev/null || echo "No containers to remove"

build:
	@echo "🔹 creating a virtual environment"
	bash src/scripts/create_venv.sh

check-env:
	@bash src/scripts/check_env_vars.sh

	