.PHONY: all venv install link clean help build publish release realease

# Variables
PYTHON = python3
VENV = venv
BIN = $(VENV)/bin
PIP = $(BIN)/pip
GITOPS_BIN = /usr/local/bin/gitops
NGEN_BIN = /usr/local/bin/ngen-gitops

# Capture version argument for release or realease (alias)
ifeq ($(filter release realease,$(firstword $(MAKECMDGOALS))),$(firstword $(MAKECMDGOALS)))
  VERSION_ARG := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
  $(eval $(VERSION_ARG):;@:)
endif

help:
	@echo "Usage:"
	@echo "  make all             - Create venv and install package (recommended)"
	@echo "  make venv            - Create virtual environment"
	@echo "  make install         - Install package in editable mode within venv"
	@echo "  make link            - Create global symlinks (requires sudo)"
	@echo "  make unlink          - Remove global symlinks (requires sudo)"
	@echo "  make build           - Build source and wheel distributions"
	@echo "  make publish         - Upload package to PyPI using twine"
	@echo "  make release [v]     - Bump version, build, publish, and tag in git"
	@echo "                         Example: make release (auto-bump patch)"
	@echo "                         Example: make release 0.1.15 (specific version)"
	@echo "  make clean           - Remove venv and build artifacts"

all: venv install

venv:
	@echo "Creating virtual environment..."
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip build twine

install: venv
	@echo "Installing package in editable mode..."
	$(PIP) install -e .

link:
	@echo "Creating global symlinks in /usr/local/bin..."
	sudo ln -sf $(shell pwd)/$(BIN)/gitops $(GITOPS_BIN)
	sudo ln -sf $(shell pwd)/$(BIN)/ngen-gitops $(NGEN_BIN)
	@echo "✅ Symlinks created. You can now run 'gitops' globally."

unlink:
	@echo "Removing global symlinks..."
	sudo rm -f $(GITOPS_BIN)
	sudo rm -f $(NGEN_BIN)
	@echo "✅ Symlinks removed."

build: venv
	@echo "Cleaning old builds..."
	rm -rf dist/ build/ *.egg-info
	@echo "Building distributions..."
	$(BIN)/python -m build

publish: build
	@echo "Uploading to PyPI..."
	$(BIN)/twine upload dist/*

release: venv
	@echo "Starting release process..."
	@NEW_VER=$$($(BIN)/python update_version.py $(VERSION_ARG) | tail -n 1); \
	if [ -z "$$NEW_VER" ]; then echo "Failed to get new version"; exit 1; fi; \
	echo "New version: $$NEW_VER"; \
	echo "Building package..."; \
	$(MAKE) build; \
	echo "Publishing to PyPI..."; \
	$(MAKE) publish; \
	echo "Tagging in Git..."; \
	git add pyproject.toml ngen_gitops/__init__.py; \
	git commit -m "chore: release $$NEW_VER"; \
	git tag -a v$$NEW_VER -m "Release $$NEW_VER"; \
	git push origin main --tags; \
	echo "✅ Release $$NEW_VER completed successfully!"

realease: release

clean:
	@echo "Cleaning up..."
	rm -rf $(VENV)
	rm -rf *.egg-info
	rm -rf build
	rm -rf dist
	find . -type d -name "__pycache__" -exec rm -rf {} +
	@echo "✅ Cleanup complete."
