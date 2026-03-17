#!/usr/bin/env python3
import sys
import re
from pathlib import Path

def update_version(new_version=None):
    pyproject_path = Path("pyproject.toml")
    init_path = Path("ngen_gitops/__init__.py")
    
    # Get current version from pyproject.toml
    content = pyproject_path.read_text()
    match = re.search(r'version = "([^"]+)"', content)
    if not match:
        print("Error: Could not find version in pyproject.toml")
        sys.exit(1)
    
    current_version = match.group(1)
    
    if not new_version:
        # Increment patch version
        parts = current_version.split('.')
        if len(parts) >= 3:
            parts[-1] = str(int(parts[-1]) + 1)
            new_version = '.'.join(parts)
        else:
            new_version = f"{current_version}.1"
    
    print(f"Updating version: {current_version} -> {new_version}")
    
    # Update pyproject.toml
    new_content = re.sub(r'(version = ")[^"]+(")', rf'\g<1>{new_version}\g<2>', content)
    pyproject_path.write_text(new_content)
    
    # Update ngen_gitops/__init__.py
    if init_path.exists():
        init_content = init_path.read_text()
        new_init_content = re.sub(r'(__version__ = ")[^"]+(")', rf'\g<1>{new_version}\g<2>', init_content)
        init_path.write_text(new_init_content)
    
    return new_version

if __name__ == "__main__":
    version_input = sys.argv[1] if len(sys.argv) > 1 else None
    res = update_version(version_input)
    # The last line should be exactly the version string for Makefile to capture it
    print(res)
