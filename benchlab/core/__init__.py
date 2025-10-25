"""
BenchLab Python Core Library

Provides core telemetry, sensor IO, and hardware monitoring functions
for BENCHLAB systems.

Usage:
    import benchlab
    from benchlab.core import read_sensors
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("benchlab-pycore")
except PackageNotFoundError:
    __version__ = "0.1.0"

from . import core

__all__ = ["core", "__version__"]
