IMAGE_NAME ?= darc-el
IMAGE_TAG ?= latest
IMAGE := $(IMAGE_NAME):$(IMAGE_TAG)
ENV_FILE ?= .env
OUTPUT_FILE ?= zotero_group_items.json

.PHONY: help build docker-build run shell clean

help:
	@echo "Available targets:"
	@echo "  make build        - Build Python package with Hatch"
	@echo "  make docker-build - Build Docker image $(IMAGE)"
	@echo "  make run    - Run extraction using $(ENV_FILE)"
	@echo "  make shell  - Open a shell in the container"
	@echo "  make clean  - Remove generated output file"

build:
	hatch build

docker-build:
	docker build -t $(IMAGE) .

run:
	docker run --rm --env-file $(ENV_FILE) -v "$$(pwd):/app" $(IMAGE) python src/main.py

shell:
	docker run --rm -it --env-file $(ENV_FILE) -v "$$(pwd):/app" $(IMAGE) sh

clean:
	rm -f $(OUTPUT_FILE)
