# Dev targets for the Python SDK. Run from the repo root as `make <target>`.
.PHONY: generate lint type test build check

SPEC := apispec/openapi.json
GENERATED := src/protoface_sdk/_generated.py

# Regenerate the wire models from the committed OpenAPI spec, then normalize
# the output to the SDK's ruff style (double quotes, import order).
generate:
	uv run datamodel-codegen \
		--input $(SPEC) --input-file-type openapi \
		--output $(GENERATED) \
		--output-model-type pydantic_v2.BaseModel \
		--target-python-version 3.10 --use-standard-collections \
		--use-union-operator --use-schema-description --field-constraints \
		--set-default-enum-member --use-default-kwarg --formatters black
	uv run ruff format $(GENERATED)
	uv run ruff check --fix $(GENERATED)

lint:
	uv run ruff check .
	uv run ruff format --check .

type:
	uv run pyright .

test:
	uv run pytest

build:
	rm -rf dist
	uv run python -m build
	uv run twine check dist/*

check: lint type test build
