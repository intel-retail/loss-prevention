.PHONY: build run down

build:
	docker build -f Dockerfile.python -t barcode:dev .

run:
	docker compose up -d

down:
	docker compose down