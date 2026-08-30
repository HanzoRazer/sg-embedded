"""T10-T12: the minimal specs carry provenance structurally.

These tests prove the structural contract only: quantities go in intact,
unknowns stay unknown, and records cannot be edited after the fact. No
qualification semantics are exercised, because none exist yet.
"""

from dataclasses import FrozenInstanceError

import pytest

from acquisition.models import ClockSpec, ConverterSpec, FrontEndSpec
from acquisition.provenance import Provenance, Quantity, canonical_json


def datasheet(value: float, unit: str, source: str = "ACME-0001 rev B") -> Quantity:
    return Quantity(value, unit, Provenance.DATASHEET, source=source)


def measured(value: float, unit: str, evidence_ref: str = "EVT-CLK-001") -> Quantity:
    return Quantity(
        value, unit, Provenance.MEASURED, source="bench test", evidence_ref=evidence_ref
    )


# ---------------------------------------------------------------------------
# T10 - specs accept provenance-bearing quantities and preserve them intact
# ---------------------------------------------------------------------------


def test_t10_clock_spec_preserves_the_original_quantity() -> None:
    jitter = measured(50e-12, "s", evidence_ref="EVT-CLK-001")
    accuracy = datasheet(20.0, "ppm")
    clock = ClockSpec(name="local XO", rms_jitter_s=jitter, accuracy_ppm=accuracy)

    assert clock.rms_jitter_s is jitter
    assert clock.accuracy_ppm is accuracy
    assert clock.rms_jitter_s.evidence_ref == "EVT-CLK-001"
    assert clock.rms_jitter_s.provenance is Provenance.MEASURED
    assert clock.accuracy_ppm.source == "ACME-0001 rev B"


def test_t10_front_end_spec_preserves_the_original_quantities() -> None:
    noise = datasheet(10e-9, "V/rtHz")
    gain = datasheet(20.0, "dB")
    bandwidth = datasheet(50000.0, "Hz")
    front_end = FrontEndSpec(
        name="AFE",
        input_referred_noise_v_per_rthz=noise,
        gain_db=gain,
        bandwidth_hz=bandwidth,
    )

    assert front_end.input_referred_noise_v_per_rthz is noise
    assert front_end.gain_db is gain
    assert front_end.bandwidth_hz is bandwidth
    assert front_end.quantities().items() >= {
        "input_referred_noise_v_per_rthz": noise,
        "gain_db": gain,
        "bandwidth_hz": bandwidth,
    }.items()


def test_t10_converter_spec_preserves_the_original_quantities() -> None:
    converter = ConverterSpec(
        name="ADC",
        bits=datasheet(24.0, "bit"),
        full_scale_vrms=datasheet(1.0, "Vrms"),
        thermal_snr_db=datasheet(110.0, "dB"),
        aperture_jitter_s=measured(5e-12, "s", evidence_ref="EVT-ADC-002"),
        sample_rate_hz=datasheet(48000.0, "Hz"),
    )

    assert converter.bits is not None
    assert converter.bits.value == 24.0
    assert converter.aperture_jitter_s is not None
    assert converter.aperture_jitter_s.evidence_ref == "EVT-ADC-002"
    assert converter.as_dict()["bits"]["provenance"] == "datasheet"


def test_t10_bit_depth_carries_provenance_like_any_other_value() -> None:
    """Bit depth is discrete, but it is still load-bearing.

    It sets the ideal quantization floor, so a result computed from it should
    be able to say where the number came from.
    """
    converter = ConverterSpec(name="ADC", bits=datasheet(16.0, "bit"))
    assert isinstance(converter.bits, Quantity)
    assert converter.bits.provenance is Provenance.DATASHEET


def test_t10_specs_serialize_deterministically() -> None:
    def build() -> ConverterSpec:
        return ConverterSpec(
            name="ADC",
            bits=datasheet(24.0, "bit"),
            sample_rate_hz=datasheet(48000.0, "Hz"),
        )

    assert canonical_json(build().as_dict()) == canonical_json(build().as_dict())


# ---------------------------------------------------------------------------
# T11 - specs preserve unknowns
# ---------------------------------------------------------------------------


def test_t11_omitted_fields_remain_none_on_every_spec() -> None:
    """Every declared quantity of an undescribed spec is None.

    Asserted over whatever quantities each spec declares rather than against a
    frozen field list, so the property keeps holding as fields are added. What
    matters is that no field acquires a value nobody supplied, not that the
    field set never grows.
    """
    for spec in (
        FrontEndSpec(name="AFE"),
        ClockSpec(name="clock"),
        ConverterSpec(name="ADC"),
    ):
        quantities = spec.quantities()
        assert quantities, f"{type(spec).__name__} declares no quantities"
        assert all(q is None for q in quantities.values())

    assert set(FrontEndSpec(name="AFE").quantities()) >= {
        "input_referred_noise_v_per_rthz",
        "gain_db",
        "bandwidth_hz",
    }
    assert set(ClockSpec(name="clock").quantities()) >= {
        "rms_jitter_s",
        "accuracy_ppm",
    }
    assert set(ConverterSpec(name="ADC").quantities()) >= {
        "bits",
        "full_scale_vrms",
        "thermal_snr_db",
        "aperture_jitter_s",
        "sample_rate_hz",
    }


def test_t11_an_explicit_none_is_kept_as_none() -> None:
    clock = ClockSpec(name="clock", rms_jitter_s=None, accuracy_ppm=None)
    assert clock.rms_jitter_s is None
    assert clock.accuracy_ppm is None


# ---------------------------------------------------------------------------
# T12 - frozen model behavior
# ---------------------------------------------------------------------------


def test_t12_specs_cannot_be_mutated_in_place() -> None:
    """Evidence records must not be edited after they are stated."""
    clock = ClockSpec(name="local XO", rms_jitter_s=measured(50e-12, "s"))
    with pytest.raises(FrozenInstanceError):
        clock.rms_jitter_s = None  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        clock.name = "renamed"  # type: ignore[misc]

    front_end = FrontEndSpec(name="AFE")
    with pytest.raises(FrozenInstanceError):
        front_end.gain_db = datasheet(20.0, "dB")  # type: ignore[misc]

    converter = ConverterSpec(name="ADC")
    with pytest.raises(FrozenInstanceError):
        converter.bits = datasheet(24.0, "bit")  # type: ignore[misc]


def test_t12_specs_reject_unknown_attributes() -> None:
    """A typo must not quietly attach a field that nothing reads.

    Note the decorator this depends on. ``frozen=True`` alone raises
    ``FrozenInstanceError`` for any attribute name; adding ``slots=True``
    breaks that, because the generated ``__setattr__`` closes over the
    pre-slots class object and an unknown name falls through to a confusing
    ``TypeError`` instead. The specs therefore use plain ``frozen=True``.
    """
    clock = ClockSpec(name="local XO")
    with pytest.raises(FrozenInstanceError):
        clock.rms_jitter = measured(50e-12, "s")  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Unit discipline at the model boundary
# ---------------------------------------------------------------------------


def test_canonical_units_are_enforced_without_conversion() -> None:
    """50 ps is a valid Quantity but not a valid value for a field in seconds.

    The README's own worked example. The field name cannot enforce a unit, so
    the model boundary does, and it rejects rather than rescales.
    """
    with pytest.raises(ValueError, match="must be expressed in 's'"):
        ClockSpec(name="clock", rms_jitter_s=measured(50.0, "ps"))
    with pytest.raises(ValueError, match="must be expressed in 'Hz'"):
        FrontEndSpec(name="AFE", bandwidth_hz=datasheet(50.0, "kHz"))
    with pytest.raises(ValueError, match="must be expressed in 'dB'"):
        ConverterSpec(name="ADC", thermal_snr_db=datasheet(110.0, "dBFS"))

    ClockSpec(name="clock", rms_jitter_s=measured(50e-12, "s"))


def test_physically_impossible_values_are_rejected() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        ClockSpec(name="clock", rms_jitter_s=measured(-1e-12, "s"))
    with pytest.raises(ValueError, match="must not be negative"):
        ConverterSpec(name="ADC", aperture_jitter_s=measured(-1e-12, "s"))
    with pytest.raises(ValueError, match="whole number of bits"):
        ConverterSpec(name="ADC", bits=datasheet(16.5, "bit"))
