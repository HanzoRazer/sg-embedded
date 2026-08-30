"""STAGED FOR 001B: profile-level evidence blockers.

Not part of the 001A gate. Quantity-level traceability is gated in
``test_provenance.py``; what is exercised here is aggregating that into a
statement about a whole profile, which is a decision-layer concern.
"""

from dataclasses import replace

from acquisition.models import (
    AudioAcquisitionProfile,
    PowerCondition,
    PowerNoiseObservation,
)
from acquisition.provenance import (
    Provenance,
    Quantity,
    blocker_for,
    canonical_json,
    collect_blockers,
)

from .conftest import assumed, datasheet, fully_evidenced_profile, measured, proposed


def test_a_fully_evidenced_profile_has_no_blockers() -> None:
    profile = fully_evidenced_profile()
    assert profile.evidence_blockers() == ()


def test_one_proposed_value_holds_back_the_whole_profile() -> None:
    profile = fully_evidenced_profile()
    degraded = replace(
        profile,
        clock=replace(profile.clock, rms_jitter_s=proposed(50e-12, "s")),
    )
    assert "clock.rms_jitter_s is PROPOSED" in degraded.evidence_blockers()


def test_one_assumed_value_holds_back_the_whole_profile() -> None:
    profile = fully_evidenced_profile()
    degraded = replace(
        profile,
        converter=replace(profile.converter, hp_corner_hz=assumed(10.0, "Hz")),
    )
    assert "converter.hp_corner_hz is ASSUMED" in degraded.evidence_blockers()


def test_a_missing_value_is_reported_as_missing_not_as_zero() -> None:
    profile = fully_evidenced_profile()
    degraded = replace(profile, converter=replace(profile.converter, sfdr_db=None))
    assert (
        "converter.sfdr_db is missing (no value declared)"
        in degraded.evidence_blockers()
    )


def test_blockers_are_deterministic_and_ordered() -> None:
    fields = {
        "clock.rms_jitter_s": proposed(50e-12, "s"),
        "converter.sfdr_db": None,
        "converter.hp_corner_hz": assumed(10.0, "Hz"),
        "front_end.gain_db": datasheet(20.0, "dB"),
    }
    assert collect_blockers(fields) == (
        "clock.rms_jitter_s is PROPOSED",
        "converter.sfdr_db is missing (no value declared)",
        "converter.hp_corner_hz is ASSUMED",
    )


def test_untraceable_authoritative_values_are_still_blockers() -> None:
    untraceable = Quantity(50e-12, "s", Provenance.MEASURED)
    assert blocker_for("clock.rms_jitter_s", untraceable) == (
        "clock.rms_jitter_s is MEASURED but has no evidence reference"
    )
    sourceless = Quantity(1.0e6, "ohm", Provenance.DATASHEET)
    assert blocker_for("pickup.input_impedance_ohm", sourceless) == (
        "pickup.input_impedance_ohm is DATASHEET but has no evidence source"
    )


def test_evidence_ref_survives_the_profile_walk() -> None:
    profile = fully_evidenced_profile()
    walked = profile.quantities()["clock.rms_jitter_s"]
    assert walked is not None
    assert walked.evidence_ref == "EVT-AUDIO-CLK-0042"

    serialized = profile.as_dict()
    assert serialized["clock"]["rms_jitter_s"]["evidence_ref"] == "EVT-AUDIO-CLK-0042"


def test_profile_serialization_is_deterministic() -> None:
    first = canonical_json(fully_evidenced_profile().as_dict())
    second = canonical_json(fully_evidenced_profile().as_dict())
    assert first == second
    assert '"provenance":"datasheet"' in first


def test_power_observation_provenance_cannot_drift_from_its_quantities() -> None:
    import pytest

    with pytest.raises(ValueError, match="disagrees with observation provenance"):
        PowerNoiseObservation(
            condition=PowerCondition.WIFI_ACTIVE,
            noise_floor_dbfs=measured(-120.0, "dBFS"),
            provenance=Provenance.ASSUMED,
        )


def test_profile_rejects_duplicate_power_conditions() -> None:
    import pytest

    profile = fully_evidenced_profile()
    observation = PowerNoiseObservation(
        condition=PowerCondition.BASELINE,
        noise_floor_dbfs=measured(-120.0, "dBFS"),
        provenance=Provenance.MEASURED,
        source="bench log",
    )
    with pytest.raises(ValueError, match="duplicate power noise observation"):
        AudioAcquisitionProfile(
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            pickup_interface=profile.pickup_interface,
            front_end=profile.front_end,
            converter=profile.converter,
            clock=profile.clock,
            declared_audio_band_hz=profile.declared_audio_band_hz,
            power_noise_observations=(observation, observation),
        )
