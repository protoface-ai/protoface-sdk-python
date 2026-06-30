.PHONY: generate sync-openapi openapi-check lint type test build check

SPEC := apispec/openapi.json
GENERATED := src/protoface_sdk/_generated.py
CANONICAL_SPEC ?= ../protoface/apispec/openapi.json

generate:
	uv run datamodel-codegen \
		--input $(SPEC) --input-file-type openapi \
		--output $(GENERATED) \
		--output-model-type pydantic_v2.BaseModel \
		--target-python-version 3.10 --use-standard-collections \
		--use-union-operator --use-schema-description --field-constraints --disable-timestamp \
		--set-default-enum-member --use-default-kwarg --formatters black
	uv run ruff format $(GENERATED)
	uv run ruff check --fix $(GENERATED)

sync-openapi:
	test -f $(CANONICAL_SPEC)
	cp $(CANONICAL_SPEC) $(SPEC)
	$(MAKE) generate

openapi-check:
	test -f $(CANONICAL_SPEC)
	cmp -s $(CANONICAL_SPEC) $(SPEC) || (diff -u $(CANONICAL_SPEC) $(SPEC); exit 1)

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
