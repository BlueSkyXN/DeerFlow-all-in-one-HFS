PROJECT_NAME ?= DeerFlow-all-in-one-HFS
IMAGE ?= deerflow-all-in-one-hfs
DEERFLOW_REF ?= 0f0955bf7b2ae64ecb5099551b86049c2091a80a
PORT ?= 7860
DATA_DIR ?= $(PWD)/.data
ENV_FILE ?= .env.local

.PHONY: build run smoke static-check shell clean

build:
	docker build \
		--build-arg DEERFLOW_REF=$(DEERFLOW_REF) \
		-t $(IMAGE) .

run:
	mkdir -p $(DATA_DIR)
	docker run --rm -it \
		-p $(PORT):7860 \
		--env-file $(ENV_FILE) \
		-v $(DATA_DIR):/data \
		$(IMAGE)

smoke:
	./scripts/smoke-test.sh http://localhost:$(PORT)

static-check:
	./scripts/static-check.sh

shell:
	docker run --rm -it \
		--env-file $(ENV_FILE) \
		-v $(DATA_DIR):/data \
		--entrypoint /bin/bash \
		$(IMAGE)

clean:
	rm -rf .data
