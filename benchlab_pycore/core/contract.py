"""Read the vendored firmware wire contracts.

The contracts in ``benchlab_pycore/contracts/`` are generated from the firmware
headers by a compiled sizeof/offsetof probe and frozen at release time, so
reading expectations from them means this library and the firmware cannot drift
apart silently: re-vendor a contract and the tests follow. Nothing here
hardcodes a size, an offset or an opcode.

This is deliberately *not* a decoder. The library decodes with the hand-written
ctypes structures in :mod:`benchlab_pycore.core.structures`; the contract is what
those structures are checked against (see ``tests/test_contract.py``) and what
supplies firmware-dependent constants such as the calibration slot ids.

Stdlib only -- no ``jsonschema`` at runtime. Schema validation is CI's job and
the firmware repo already does it before freezing.
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "Contract",
    "available_contracts",
    "ContractMismatchError",
    "UnknownFirmwareError",
    "available",
    "contract_for",
]

_PACKAGE = "benchlab_pycore.contracts"


class ContractMismatchError(RuntimeError):
    """A ctypes structure disagrees with the firmware contract.

    Raised at import time by :mod:`benchlab_pycore.core.structures`. This means
    the library would decode the wire incorrectly, so it fails loudly rather
    than returning plausible-looking garbage.
    """


class UnknownFirmwareError(LookupError):
    """No vendored contract matches a device's (ProductId, FwVersion) pair.

    Raised rather than falling back to a nearby contract: decoding an unknown
    firmware with the wrong layout, or writing a calibration slot with the
    wrong id, is worse than refusing.
    """


def _read_json(name: str) -> Dict[str, Any]:
    return json.loads(files(_PACKAGE).joinpath(name).read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _index() -> Dict[str, Any]:
    return _read_json("index.json")


@lru_cache(maxsize=None)
def available() -> Dict[Tuple[int, int], str]:
    """(ProductId, FwVersion) -> contract filename, from index.json.

    Contracts are version-keyed and old ones are never deleted, so a device must
    be matched on the version it actually reports. The index is generated from
    the contracts themselves in the firmware repo, so vendoring a new contract
    is enough -- there is no table here to forget to update.
    """
    return {
        (e["product_id"], e["fw_version"]): e["file"]
        for e in _index()["contracts"]
    }


@lru_cache(maxsize=None)
def _display_names() -> Dict[int, str]:
    """ProductId -> human name, taken from the index rather than a local table."""
    return {e["product_id"]: e["name"] for e in _index()["contracts"]}


def _format_known() -> str:
    return ", ".join(
        f"{pid:#04x}/fw{fw:#04x}" for pid, fw in sorted(available())
    ) or "none"


class Contract:
    """One firmware's frozen wire contract."""

    def __init__(self, product_id: int, fw_version: int):
        filename = available().get((product_id, fw_version))
        if filename is None:
            raise UnknownFirmwareError(
                f"no contract for ProductId {product_id:#04x} "
                f"FwVersion {fw_version:#04x}. "
                f"Available: {_format_known()}. "
                "If the firmware was just released, re-vendor the contracts: "
                "python tools/sync_contracts.py --from ../bl-benchlab-firmware"
            )
        self.filename = filename
        self.raw = _read_json(filename)
        self.product_id = product_id
        self.name = _display_names().get(product_id, f"unknown ({product_id:#04x})")

    def __repr__(self) -> str:
        return (
            f"<Contract {self.filename} "
            f"pid={self.product_id:#04x} fw={self.fw_version:#04x}>"
        )

    # -- identity ---------------------------------------------------------
    @property
    def vendor_id(self) -> int:
        return self.raw["identity"]["vendor_id"]

    @property
    def fw_version(self) -> int:
        return self.raw["identity"]["fw_version"]

    @property
    def variant(self) -> str:
        return self.raw["variant"]

    @property
    def status(self) -> str:
        """``"released"`` or ``"draft"``. Draft contracts may be re-frozen."""
        return self.raw["status"]

    # -- lookups ----------------------------------------------------------
    def constant(self, name: str) -> int:
        """A firmware constant, e.g. ``CAL_FACTORY``.

        Several of these changed value between firmware versions, which is why
        they are read per-contract rather than hardcoded.
        """
        return self.raw["constants"][name]

    def opcode(self, command: str) -> int:
        for c in self.raw["commands"]:
            if c["name"] == command:
                return c["opcode"]
        raise KeyError(command)

    def opcodes(self) -> Dict[str, int]:
        """All command names to opcodes defined by this firmware."""
        return {c["name"]: c["opcode"] for c in self.raw["commands"]}

    def response_size(self, command: str) -> Optional[int]:
        """Expected response length, or None if the command sends nothing back.

        The wire has no framing and no checksum (see the contract's ``wire``
        block), so length is the only defence against a mis-sized reply.
        """
        for c in self.raw["commands"]:
            if c["name"] == command:
                return c.get("response_size")
        raise KeyError(command)

    def struct_size(self, name: str) -> int:
        return self.raw["structs"][name]["size"]

    def struct_names(self) -> List[str]:
        return list(self.raw["structs"])

    def fields(self, struct_name: str) -> List[Dict[str, Any]]:
        return self.raw["structs"][struct_name]["fields"]

    def field(self, struct_name: str, field_name: str) -> Dict[str, Any]:
        for f in self.fields(struct_name):
            if f["name"] == field_name:
                return f
        raise KeyError(f"{struct_name}.{field_name}")

    def enum(self, name: str) -> Dict[str, int]:
        return self.raw["enums"][name]

    def enum_names(self) -> List[str]:
        return list(self.raw["enums"])


@lru_cache(maxsize=None)
def contract_for(product_id: int, fw_version: int) -> Contract:
    """Resolve the contract for a device's reported identity.

    Cached: contracts are immutable once frozen, so one parse per pair is enough.
    """
    return Contract(product_id, fw_version)


# Exported under a less generic name at package level, where "available" alone
# would not say available *what*.
available_contracts = available
