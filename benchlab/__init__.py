# benchlab/__init__.py

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("benchlab-pycore")
except PackageNotFoundError:
    __version__ = "0.1.1"

from . import core

__all__ = ["core", "__version__"]
