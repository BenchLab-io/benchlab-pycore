# benchlab/__init__.py

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("benchlab-pycore")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

from . import core

__all__ = ["core", "__version__"]
