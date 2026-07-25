PROJECT_NAME ?= DeerFlow-all-in-one-HFS
IMAGE ?= deerflow-all-in-one-hfs
DEERFLOW_REF ?= 3b77a7401b549fa6da4c8e1f8c2c0081d56e3d7a
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
