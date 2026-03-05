#!/usr/bin/env python3
"""
Test runner that handles the stdlib `signal` module name collision.

The project's `signal/` package shadows Python's stdlib `signal` module,
which breaks anyio (used by httpx/pytest-asyncio). This script pre-loads
the stdlib signal module before pytest imports anything.
"""
import importlib
import signal as stdlib_signal  # noqa: F401 — force stdlib signal to load first
import sys
from pathlib import Path

# Ensure project root is in path
project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now that stdlib signal is loaded and cached in sys.modules,
# we need to make our project's signal package importable under
# a different mechanism. We temporarily remove it and re-add after
# anyio loads.

# Save our signal package path
signal_pkg_path = Path(project_root) / "signal"

# Remove our signal from sys.modules if it got loaded
our_signal = sys.modules.pop("signal", None)

# Re-register stdlib signal
sys.modules["signal"] = stdlib_signal

# Now import pytest (which will load anyio, which needs stdlib signal)
import pytest

# Restore our signal package
if signal_pkg_path.exists():
    # Import our package with the correct path
    spec = importlib.util.spec_from_file_location(
        "signal",
        signal_pkg_path / "__init__.py",
        submodule_search_locations=[str(signal_pkg_path)],
    )
    signal_module = importlib.util.module_from_spec(spec)
    signal_module.__path__ = [str(signal_pkg_path)]
    sys.modules["signal"] = signal_module
    spec.loader.exec_module(signal_module)

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", "--tb=short", "tests/"] + sys.argv[1:]))
