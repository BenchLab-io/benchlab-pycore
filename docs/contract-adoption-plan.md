# Adapting bl-benchlab-pycore to the firmware release contract

> Findings below were verified directly against the frozen contracts in
> `bl-benchlab-firmware/protocol/` and against pycore at v0.5.2.

## Context

`bl-benchlab-firmware` now publishes a machine-readable wire contract: one
`protocol/<variant>-fw<NN>.json` per `(ProductId, FwVersion)`, generated from the
firmware headers by a compiled `sizeof`/`offsetof` probe, validated against
`protocol/schema.json`, indexed by `protocol/index.json`, and frozen immutably at
release time. It is published as GitHub Release assets alongside the firmware images.

`bl-benchlab-pycore` predates this. It hand-transcribes the same facts from
`benchlab.h` as ctypes structs plus prose comments, guarded only by a hardcoded
`_EXPECTED_SIZES` table. It has never been reconciled against a released contract.

**The good news, verified directly:** every struct pycore defines already matches
the contract byte-for-byte. I loaded pycore's ctypes classes and compared against
`benchlab2-fw04.json` and `benchlab-original-fw03.json`:

| Struct | pycore | contract |
|---|---|---|
| `SensorStructOriginal` | 216 | 216 ✓ |
| `SensorStructBL2` | 368 | 368 ✓ |
| `CalibrationStruct` (Original) | 178 | 178 ✓ |
| `CalibrationStructBL2` | 294 | 294 ✓ |
| `PowerSensor` / `FanSensor` / `VendorDataStruct` | 12 / 4 / 3 | 12 / 4 / 3 ✓ |

Every *field offset* matches too (`Ts` at 32, `PowerReadings` at 56, `Fans` at 332
for BL2, etc.). So this is **not** a decoder rewrite. The binary layer is correct;
what is missing is the machinery to *prove* it stays correct, plus three genuine
defects the contract exposes.

### The defects the contract exposes

1. **`CAL_FACTORY` / `CAL_USER` are swapped — this is a live data-loss bug.**
   The constants flipped in firmware between fw02→fw03 (Original) and fw03→fw04 (BL2):

   | | fw02 / fw03-BL2 | fw03-Original / fw04-BL2 |
   |---|---|---|
   | `CAL_FACTORY` | 0 | **1** |
   | `CAL_USER` | 1 | **0** |

   pycore hardcodes the *old* values (`structures.py:175-176`). `cal_id` is passed
   straight onto the wire by `load_calibration()` / `store_calibration()`
   (`config_io.py:612,643`), and both values pass the validity check, so nothing
   catches it. On current firmware `store_calibration(CAL_USER)` **overwrites the
   factory calibration slot.** This alone justifies the work.

2. **Variant dispatch ignores `FwVersion`.** pycore branches on `product_id` alone
   (`serial_io.py:268` and three other sites). `protocol/index.json` explicitly warns
   the key is the `(product_id, fw_version)` *pair*. `BENCHLAB_BL2_FIRMWARE_VERSION`
   is still the placeholder `0xFF` (real value: 4) and is dead code — never read.
   Today two firmwares that differ on the wire are indistinguishable to pycore.

3. **Opcodes 15–20 exist in no firmware.** The contract stops at 14. pycore's
   `BENCHLAB_CMD` declares `READ_CONFIG`…`BOOTLOADER`; its own `migrate.md` admits
   these were ported speculatively from the C# reference and fail against hardware.
   They are already unexported from `core/__init__.py`.

### Approach (per your direction)

Contracts are the **development- and test-time source of truth**, not a runtime
construction mechanism. Hand-written ctypes stay exactly as they are — they are
readable, correct, and fast. The contract is what we *develop against* and what
tests assert against, plus one cheap self-check at import. No dynamic struct
building, no public API break.

Contracts are **vendored** into the package (~76 KB for all six files), keeping
`pyserial` the only runtime dependency and the library fully offline.

## Work

Sequenced so CI is standing before any library code moves: each rewiring step is
verified as it lands, not audited afterwards.

---

## Phase 1 - Add the contracts

Pure data. No logic changes, nothing can break.

- Copy `protocol/*.json` (4 contracts + `index.json` + `schema.json`) into
  `benchlab_pycore/contracts/`.
- Ship as package data: `[tool.setuptools.package-data]` in `pyproject.toml`, mirrored
  in `setup.cfg` (both are maintained; release CI cross-checks them).
- Add `tools/sync_contracts.py` to refresh from a local firmware checkout or a release
  tag, so later updates are one command rather than a manual copy.

**Done when:** `pip install .` into a clean venv and the JSON is importable via
`importlib.resources` from a different working directory.

---

## Phase 2 - Create the CI gate

Written before the fixes, so phase 3 has a target. Needs the contract loader, which is
test infrastructure at this point rather than library API.

**Contract loader** - new `benchlab_pycore/core/contract.py`. Port `tests/contract.py`
from the firmware repo: a proven, stdlib-only, offset-driven reader whose `_available()`
builds the `(pid, fw) -> path` map from `index.json` and whose `_FMT` maps C scalars to
struct chars. Adapt it to read the vendored package directory. No `jsonschema` at
runtime; schema validation is CI's job and the firmware repo already does it.

**Checks that pass immediately** (verified - every offset already matches):
- Every ctypes field's `offset` and `size` against every vendored contract.
- Struct sizes for all four contracts.
- Opcodes 0-14: names and values against the contract's `commands`.
- Sensor name list lengths against `SENSOR_POWER_NUM` / `TS_NUM` / `FAN_NUM`. Names
  themselves are not in the contract, so this checks cardinality only.

**Checks that fail until phase 3** - write them now, mark `xfail(strict=True)` so they
are visible and flip automatically when fixed:
- `CAL_FACTORY` / `CAL_USER` per firmware version.
- `TempSrc` against the contract's `TEMP_SRC` enum (BL2 defines four HPWR sources at
  values 6-9 that pycore lacks).
- `FanMode`, `RGBMode`, `RGBDirection`, `FanStop` against their contract enums.

Opcodes 15-20 have no contract counterpart: assert them as a documented `_SPECULATIVE`
set so the test pins the known gap rather than failing on it.

**Workflow changes** - `.github/workflows/tests.yml` names `test_config.py` and
`test_core.py` explicitly, so a new test file would silently never run. Switch to
`pytest tests/` with the hardware scripts ignored, which also fixes that latent trap.

**Done when:** suite is green, with exactly the three xfail groups above marked.

---

## Phase 3 - Rewire the library

Every change here is now covered by phase 2.

**3a. Import-time compatibility check.** Replace the hardcoded `_EXPECTED_SIZES` table
in `structures.py` with sizes read from the vendored contracts for the current firmware
of each variant. Deliberately cheap - struct sizes only, two contracts only; full offset
verification is phase 2's job, not an import-time cost. `DeviceConfigStruct` (426 B) has
no contract counterpart (it belongs to the speculative commands) - exclude it explicitly
with a comment saying why. Raise `ContractMismatchError` naming struct, both sizes and
the file, rather than today's bare `AssertionError`.

**3b. Fix the calibration swap.** `CAL_FACTORY`/`CAL_USER` become per-contract values
read via `Contract.constant()`, since they are firmware-dependent. Module-level names
stay bound to current-firmware values for back-compat. `load_calibration()` /
`store_calibration()` (`config_io.py:590-646`) take the resolved contract. **This is a
behavioural change on a destructive path** - it needs prominent notes in `migrate.md`
and the release notes, and a decision (yours) on what to tell users whose factory slot
may already have been overwritten.

**3c. Version-aware resolution.** Set `BENCHLAB_BL2_FIRMWARE_VERSION = 4` and
`BENCHLAB_ORIGINAL_FIRMWARE_VERSION = 3`, retiring the `0xFF` placeholder. `read_device()`
already returns the `(ProductId, FwVersion)` pair - resolve the contract from it and
thread it through `read_sensors`, `read_calibration`, `write_calibration_chunk`,
`translate_sensor_struct`. Unknown pairs raise `UnknownFirmwareError` listing known ones,
mirroring the firmware repo's error text: fail loudly rather than decode an unknown
firmware with the wrong layout. Validate response lengths against
`Contract.command(...).response_size` - the wire has no framing or checksum, so length is
the only defence. Keep `product_id`-only entry points working (defaulting to current
firmware) so the public API does not break.

**3d. Extend `TempSrc`** to cover BL2's HPWR sources, clearing that xfail.

**3e. Decide opcodes 15-20** - delete, or keep as documented-unimplemented. A
compatibility call on your published API; they are already unexported from
`core/__init__.py`.

**Done when:** all three xfail groups pass and the markers are removed.

---

## Phase 4 - Recheck CI

- Drift check: fail if vendored contracts differ from the firmware repo's released ones.
  Compare bytes, not text, as `gen_index.py --check` does, to avoid CRLF false positives.
  Scheduled/nightly is the right cadence.
- Confirm the full suite runs in CI, including the new file.
- Python version: CI runs 3.13 only while `requires-python = ">=3.8"`, and
  `importlib.resources` differs across that range. Either add 3.8 to the matrix or raise
  the floor. Flagging, not fixing unasked.

---

## Optional phase 5 - Generate structs from contracts

Deferred by design; the decision point sits here, after the tests exist to police it.

I prototyped this: a ~20-line generator built every struct in all four contracts with
**every size and every field offset exact**, no packing tricks or special cases. So it is
viable, not theoretical.

- **Gain:** new firmware becomes "drop in the JSON" instead of hand-editing ctypes; plus
  multi-version decoding in one process, useful for mixed fleets.
- **Cost:** the ~60-name public `__all__` must be synthesized at import to avoid breaking
  downstream users and the existing tests; struct classes stop being greppable; and
  `isinstance()` checks break, since each contract yields a distinct class
  (`sensor_translation.py` has one such fallback).
- **Decide on:** how often the wire format will change. If fw05/fw06 are coming, it pays
  for itself; if BL2 is the last generation for a while, hand-written is more readable.

Phase 2's offset tests make this contained and reversible - flip it on and the suite
confirms equivalence immediately.

## Effort

**Roughly 1–1.5 days** for phases 1–4. It is mostly mechanical because the layouts
already agree and the loader is a port, not a design. By phase: 1 (vendoring) ~1h,
2 (loader + tests + workflow) ~4h, 3 (rewiring) ~5h, 4 (drift check) ~1h.
Optional phase 5 is a further ~half day, most of it on the `__all__` compatibility
shim rather than the generator itself.

The risk is concentrated in 3c (threading `fw_version` through four call sites
without breaking the ~60-name public `__all__`) and 3b (a behavioural change on
a destructive path).

## Out of scope — flagged, not fixed

- `benchlab_pycore/version.py` says `0.5.1`; `pyproject.toml`/`setup.cfg` say `0.5.2`.
  Release CI checks the latter two but not the former.
- `tests/test_device.py`, `test_deviceConfig.py`, `test_write_validation.py` are
  hardware scripts shaped like `test_*` functions with arguments; pytest miscollects
  them as missing fixtures (9 errors today). Unrelated pre-existing issue.
- Committed build artifacts (`dist/`, `*.egg-info/`, `__pycache__/`) tracked in-tree.
- `read_calibration` docstring references a nonexistent `cal.Entries[0].Offset`.
- Power-grouping index ranges (`range(6, 11)` for GPU) encode firmware topology as
  magic numbers; the contract does not describe these groupings, so they stay.

## Verification

1. `python -m pytest tests/ -v` — 83 existing unit tests still pass, new contract
   tests pass. (The 9 hardware-script collection errors are pre-existing.)
2. Deliberately corrupt a vendored contract's `SensorStruct` size → confirm import
   raises `ContractMismatchError` naming the struct and file; revert.
3. `python -c "import benchlab_pycore"` — confirm no measurable import slowdown.
4. `pip install .` into a clean venv, then import from a *different* working directory
   to prove the contracts are packaged, not just present in the source tree.
5. Against hardware if available: `read_device()` → confirm it resolves
   `(0x11, 4)` → `benchlab2-fw04.json`, sensor read decodes to sane values, and
   `load_calibration(CAL_FACTORY)` targets slot 1 on fw04.
