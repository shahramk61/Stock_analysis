"""Load canonical pipeline modules from repo scripts/."""
import importlib.util
import os
import sys

_SCRIPTS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "scripts")
)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)


def load_module(name: str, filename: str | None = None):
    """Import a module from scripts/ without shadowing local shim files."""
    path = os.path.join(_SCRIPTS, filename or f"{name}.py")
    spec = importlib.util.spec_from_file_location(f"_canonical_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load canonical module: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod