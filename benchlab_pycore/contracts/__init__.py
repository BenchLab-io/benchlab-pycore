"""Vendored firmware wire contracts.

The JSON files here are copied verbatim from ``protocol/`` in the
bl-benchlab-firmware repository, where they are generated from the firmware
headers by a compiled sizeof/offsetof probe and frozen immutably at release
time. They are the source of truth for struct layouts, opcodes, enums and
constants.

Do not hand-edit them. Refresh with::

    python tools/sync_contracts.py --from ../bl-benchlab-firmware

They are used at development and test time (see ``tests/test_contract.py``)
and for a cheap struct-size self-check at import; the library still decodes
with the hand-written ctypes structures in ``core/structures.py``.
"""
