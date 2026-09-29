"""Match firmware defect advisories to a device.

The firmware repo publishes ``protocol/advisories.json``: known defects in
released firmware, keyed by ``(ProductId, FwVersion)``. Where a contract says
how to *decode* a device, an advisory says what is *wrong* with it -- defects
no offset or size check can express, such as a unit that changed between
firmware versions or a command that corrupts adjacent config.

Unlike the contracts, advisories are **not vendored**. They are a living
document: an advisory published today applies to firmware that shipped a year
ago, so a frozen copy would go stale while looking authoritative. This module
holds only the matching rule and the record of what this library mitigates;
``tests/test_advisories.py`` fetches the live file and checks the two agree.

The matching rule is a reimplementation of ``tools/advisories_for.py`` in the
firmware repo, which is the reference.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = [
    "MITIGATIONS",
    "advisories_for",
    "affects",
]


# What this library does about each advisory it knows of.
#
# Every *active* advisory affecting a firmware pycore supports must appear
# here, and no *withdrawn* one may -- tests/test_advisories.py enforces both
# against the live file, so a newly published advisory fails CI rather than
# going unread.
#
# "Documented, not mitigated" is a legitimate entry: some defects cannot be
# worked around from the host, and saying so explicitly is the point. What is
# not legitimate is silence.
MITIGATIONS: Dict[str, str] = {
    "write-name-overrun": (
        "config_io.write_name() caps the payload at FRIENDLY_NAME_LEN - 2 so "
        "the firmware's off-by-one bound is never reached."
    ),
    "cal-slots-inverted": (
        "structures.resolve_cal_slot() reads CAL_FACTORY/CAL_USER from the "
        "contract for the device's own firmware; load_calibration() and "
        "store_calibration() take a CalSlot and resolve it per device."
    ),
    "cal-offset-8bit": (
        "config_io.write_calibration_chunk() rejects offset > 255 with a "
        "ValueError rather than silently truncating to a byte. On BL2 "
        "firmware below fw07, the tail (bytes 256-293) is unreachable and "
        "cannot be fixed from the host; BL2 fw07+ replaces the whole "
        "struct in one WRITE_CALIBRATION call, making the tail reachable."
    ),
    "tchip-whole-degrees": (
        "utils.format_chip_temp() scales by firmware version via "
        "_TCHIP_DECIDEG_FROM; translate_sensor_struct() threads the device's "
        "(product_id, fw_version) through to it."
    ),
    "no-error-response": (
        "serial_io.read_uart() validates the response length and returns None "
        "on a short or empty read, since a malformed request yields zero "
        "bytes rather than an error. Callers get None, not garbage."
    ),
    "fan-rgb-not-persisted": (
        "Documented, not mitigated: the host cannot make the firmware persist "
        "these. Callers must re-apply fan and RGB profiles after a power "
        "cycle."
    ),
    "tamb-hum-zero-on-failure": (
        "Documented, not mitigated: a failed I2C read is reported as 0, which "
        "is indistinguishable from a genuine 0.0 degC / 0.0 %RH reading. "
        "Mapping 0 to None would discard real readings, so the raw value is "
        "passed through."
    ),
}


def affects(advisory: Dict[str, Any], product_id: int, fw_version: int) -> bool:
    """True if *advisory* applies to a device reporting this identity.

    ``fixed_in`` is per-product on purpose: one defect can be fixed in
    different firmware versions on different variants, so a single top-level
    value would wrongly clear a variant that still has it.
    """
    for spec in advisory["affects"]:
        if spec["product_id"] != product_id:
            continue
        if fw_version < spec["fw_version_min"]:
            continue
        fixed = spec.get("fixed_in")
        if fixed is None or fw_version < fixed:
            return True
    return False


def advisories_for(
    data: Dict[str, Any],
    product_id: int,
    fw_version: int,
    include_withdrawn: bool = True,
) -> List[Dict[str, Any]]:
    """Advisories applying to one device, from an already-loaded advisories doc.

    Takes the parsed document rather than reading it, because this library
    never ships a copy -- the caller decides where it came from.

    Withdrawn advisories are included by default. They are not noise: a
    consumer that already shipped a mitigation for a defect later disproven
    needs to know to *remove* it. Filter on ``status`` rather than assuming
    everything returned is a live defect.
    """
    return [
        a for a in data["advisories"]
        if affects(a, product_id, fw_version)
        and (include_withdrawn or a.get("status") != "withdrawn")
    ]
