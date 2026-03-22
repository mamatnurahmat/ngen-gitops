.PHONY: all venv install link clean help build publish release realease dev

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
	@echo "  make dev             - Run server in development mode with auto-reload"
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
	echo "Generating release note entry in RELEASE.md..."; \
	DATE=$$(date +%Y-%m-%d); \
	TMP_NOTE=$$(mktemp); \
	echo "# Release Notes — ngen-gitops\n" > $$TMP_NOTE; \
	echo "---\n" >> $$TMP_NOTE; \
	echo "## v$$NEW_VER — $$DATE\n" >> $$TMP_NOTE; \
	echo "### Changes\n" >> $$TMP_NOTE; \
	echo "<!-- TODO: Add release notes for v$$NEW_VER above this line -->\n" >> $$TMP_NOTE; \
	if [ -f RELEASE.md ]; then \
		tail -n +2 RELEASE.md >> $$TMP_NOTE; \
		mv $$TMP_NOTE RELEASE.md; \
	else \
		mv $$TMP_NOTE RELEASE.md; \
	fi; \
	echo "Committing version bump and release notes..."; \
	git add pyproject.toml ngen_gitops/__init__.py RELEASE.md; \
	git commit -m "chore: release $$NEW_VER"; \
	git push origin main; \
	echo "Building package..."; \
	$(MAKE) build; \
	echo "Publishing to PyPI..."; \
	$(MAKE) publish; \
	echo "Tagging in Git..."; \
	git tag -a v$$NEW_VER -m "Release $$NEW_VER"; \
	git push origin main --tags; \
	echo "✅ Release $$NEW_VER completed successfully!"

realease: release

dev: venv
	@echo "Starting server in development mode with reload..."
	$(BIN)/uvicorn ngen_gitops.server:app --port 8080 --reload


clean:
	@echo "Cleaning up..."
	rm -rf $(VENV)
	rm -rf *.egg-info
	rm -rf build
	rm -rf dist
	find . -type d -name "__pycache__" -exec rm -rf {} +
	@echo "✅ Cleanup complete."
