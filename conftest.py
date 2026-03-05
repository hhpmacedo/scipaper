"""Root conftest — ensure correct import resolution."""
import sys
from pathlib import Path

# Ensure the project root is first in sys.path so the `signal` package
# resolves to our project package, not the stdlib module.
# We also need to handle the conflict with stdlib `signal` carefully.
project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
