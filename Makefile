COMPOSE ?= docker compose
SERVICE ?= darc-el
OUTPUT_FILE ?= zotero_group_items.json

.PHONY: help build compose-build docker-build up run down recreate logs shell gpu-up gpu-logs gpu-shell clean

help:
	@echo "Available targets:"
	@echo "  make build        - Build Python package with Hatch"
	@echo "  make compose-build - Build services defined in docker-compose.yml"
	@echo "  make docker-build  - Alias for compose-build"
	@echo "  make up            - Start the full Compose stack"
	@echo "  make run           - Start only $(SERVICE) via Compose"
	@echo "  make down          - Stop the Compose stack"
	@echo "  make recreate      - Recreate $(SERVICE) with build"
	@echo "  make logs          - Follow $(SERVICE) logs"
	@echo "  make shell         - Open a shell in $(SERVICE)"
	@echo "  make gpu-up        - Start the GPU profile (llama-cpp-backend)"
	@echo "  make gpu-logs      - Follow llama-cpp-backend logs"
	@echo "  make gpu-shell     - Open a shell in llama-cpp-backend"
	@echo "  make clean  - Remove generated output file"

build:
	hatch build

compose-build:
	$(COMPOSE) build

run:
	$(COMPOSE) up --build $(SERVICE)

shell:
	$(COMPOSE) run --rm $(SERVICE) sh

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

recreate:
	$(COMPOSE) up -d --build --force-recreate $(SERVICE)

logs:
	$(COMPOSE) logs -f $(SERVICE)

gpu-up:
	$(COMPOSE) --profile gpu up --build llama-cpp-backend

gpu-logs:
	$(COMPOSE) logs -f llama-cpp-backend

gpu-shell:
	$(COMPOSE) --profile gpu run --rm llama-cpp-backend sh

docker-build: compose-build

clean:
	rm -f $(OUTPUT_FILE)
