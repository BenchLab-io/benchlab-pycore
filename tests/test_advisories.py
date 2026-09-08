# tests/test_advisories.py
"""Check pycore against the firmware's published defect advisories.

``protocol/advisories.json`` in the firmware repo records known defects in
released firmware. This suite asserts that every active advisory affecting a
firmware pycore supports has a corresponding entry in ``MITIGATIONS`` -- so a
newly published advisory fails CI here rather than going unread.

Advisories are a living document and are deliberately **not vendored**: an
advisory published today applies to firmware that shipped a year ago, so a
frozen copy would go stale while looking authoritative. The file is therefore
fetched from the firmware repo's main branch.

That fetch needs access to a private repo, so these tests skip when the source
is unavailable (a fork, or a checkout without the sibling repo). Skipping is
deliberate: a network or permissions problem should not look like a defect.
Nightly CI has the token and does not skip.
"""

import json
import os
from pathlib import Path

import pytest

from benchlab_pycore.core.advisories import (
    MITIGATIONS,
    advisories_for,
    affects,
)
from benchlab_pycore.core.contract import available


def _load_advisories():
    """The live advisories document, or None if it cannot be reached.

    Looks for a local firmware checkout first (the usual developer setup),
    then an explicit path via BENCHLAB_ADVISORIES, which is how CI points at
    the copy it checked out.
    """
    override = os.environ.get("BENCHLAB_ADVISORIES")
    candidates = [Path(override)] if override else []
    candidates.append(
        Path(__file__).resolve().parents[2]
        / "bl-benchlab-firmware" / "protocol" / "advisories.json"
    )
    for path in candidates:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


ADVISORIES = _load_advisories()

requires_advisories = pytest.mark.skipif(
    ADVISORIES is None,
    reason="advisories.json unavailable (needs a firmware checkout or "
           "BENCHLAB_ADVISORIES); nightly CI provides it",
)

# The firmware pycore claims to speak. Advisories for anything else are not
# this library's problem.
SUPPORTED = sorted(available())


@requires_advisories
def test_document_shape():
    """Fail loudly if the published format changes under us."""
    assert "advisories" in ADVISORIES
    for advisory in ADVISORIES["advisories"]:
        assert advisory["id"]
        assert advisory["status"] in {"active", "withdrawn"}
        assert advisory["affects"]
        # A wrong advisory is worse than a missing one, so the source requires
        # evidence for each. Check it survived the trip.
        assert advisory["verified"]["method"]


@requires_advisories
@pytest.mark.parametrize(
    "pid,fw", SUPPORTED, ids=["pid{:#04x}-fw{:02d}".format(*p) for p in SUPPORTED]
)
def test_every_active_advisory_is_mitigated(pid, fw):
    """The check the whole advisory mechanism exists for.

    An advisory that nobody reads is a tidier FIXES.md. This makes a new one
    fail pycore's CI until somebody decides what to do about it -- including
    deciding, explicitly, that nothing can be done from the host.
    """
    unhandled = [
        a["id"] for a in advisories_for(ADVISORIES, pid, fw, include_withdrawn=False)
        if a["status"] == "active" and a["id"] not in MITIGATIONS
    ]
    assert not unhandled, (
        "advisories affecting pid {:#04x} fw{:02d} with no MITIGATIONS entry: {}. "
        "Add one to benchlab_pycore/core/advisories.py saying what pycore does "
        "about it -- \"documented, not mitigated\" is a valid answer.".format(
            pid, fw, unhandled)
    )


@requires_advisories
def test_no_mitigation_for_withdrawn_advisories():
    """A withdrawn advisory was disproven; mitigating it re-introduces the bug.

    rgb-green-blue-swap is the cautionary case: it reached eight files before
    hardware refuted it. A consumer still 'fixing' it would be swapping
    correct channels.
    """
    withdrawn = {
        a["id"] for a in ADVISORIES["advisories"]
        if a.get("status") == "withdrawn"
    }
    wrongly_mitigated = withdrawn & set(MITIGATIONS)
    assert not wrongly_mitigated, (
        "MITIGATIONS entries for withdrawn advisories: {}. These defects were "
        "disproven -- the mitigation is itself the bug.".format(
            sorted(wrongly_mitigated))
    )


@requires_advisories
def test_no_stale_mitigations():
    """Every MITIGATIONS key must name a real advisory.

    Catches typos, and mitigations kept for advisories that no longer exist.
    """
    known = {a["id"] for a in ADVISORIES["advisories"]}
    unknown = set(MITIGATIONS) - known
    assert not unknown, (
        "MITIGATIONS names advisories absent from the published file: "
        "{}".format(sorted(unknown))
    )


# =============================================================================
# The matching rule
# =============================================================================

def _advisory(*affects_specs, status="active"):
    return {"id": "test", "status": status, "affects": list(affects_specs)}


def test_affects_respects_per_product_fixed_in():
    """One defect can be fixed at different versions per variant.

    This is why fixed_in is per-product: tchip-whole-degrees was fixed in
    ORIGINAL fw03 and BL2 fw04, so a single top-level value would wrongly
    clear BL2 fw03.
    """
    advisory = _advisory(
        {"product_id": 0x10, "fw_version_min": 2, "fixed_in": 3},
        {"product_id": 0x11, "fw_version_min": 3, "fixed_in": 4},
    )
    assert affects(advisory, 0x10, 2)        # affected
    assert not affects(advisory, 0x10, 3)    # fixed here
    assert affects(advisory, 0x11, 3)        # still affected on BL2
    assert not affects(advisory, 0x11, 4)    # fixed here


def test_affects_open_ended_when_fixed_in_is_null():
    advisory = _advisory({"product_id": 0x10, "fw_version_min": 2, "fixed_in": None})
    assert affects(advisory, 0x10, 2)
    assert affects(advisory, 0x10, 99)


def test_affects_ignores_other_products_and_older_firmware():
    advisory = _advisory({"product_id": 0x10, "fw_version_min": 3, "fixed_in": None})
    assert not affects(advisory, 0x11, 3)    # different product
    assert not affects(advisory, 0x10, 2)    # predates the defect


def test_withdrawn_advisories_can_be_filtered_out():
    data = {"advisories": [
        _advisory({"product_id": 0x10, "fw_version_min": 2, "fixed_in": None}),
        dict(_advisory({"product_id": 0x10, "fw_version_min": 2, "fixed_in": None},
                       status="withdrawn"), id="gone"),
    ]}
    assert len(advisories_for(data, 0x10, 2)) == 2
    assert len(advisories_for(data, 0x10, 2, include_withdrawn=False)) == 1


# =============================================================================
# Specific advisories with a testable mitigation
# =============================================================================

@requires_advisories
def test_tchip_scaling_matches_the_advisory():
    """format_chip_temp must switch units at the versions the advisory names.

    The advisory's affects block is the source of truth for when the fix
    landed, so read the boundary from it rather than restating it here.
    """
    from benchlab_pycore.core.utils import format_chip_temp

    advisory = next(a for a in ADVISORIES["advisories"]
                    if a["id"] == "tchip-whole-degrees")
    for spec in advisory["affects"]:
        pid, fixed = spec["product_id"], spec["fixed_in"]
        assert fixed is not None, "advisory changed shape; update this test"

        # Affected firmware: whole degrees, so 38 means 38 degC.
        assert format_chip_temp(38, pid, fixed - 1) == 38.0
        # Fixed firmware: deci-degrees, so 380 means 38 degC.
        assert format_chip_temp(380, pid, fixed) == 38.0
        # And the old scale on new firmware would have been discarded by the
        # range guard -- the failure this advisory prevents.
        assert format_chip_temp(380) is None
