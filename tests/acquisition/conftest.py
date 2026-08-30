"""Shared builders for the STAGED 001B acquisition tests.

Not used by the 001A gate tests, which build what they need inline.

Deliberately explicit constructors rather than clever factories: a test that
asserts something about evidence should show, on the page, exactly what
evidence it was given.
"""

import pytest

from acquisition.models import (
    AntiAliasDisposition,
    AudioAcquisitionProfile,
    ClockSpec,
    ClockTopology,
    ConverterSpec,
    FrequencyBand,
    FrontEndSpec,
    PickupInterfaceSpec,
)
from acquisition.provenance import Provenance, Quantity


def datasheet(value: float, unit: str, source: str = "ACME-0001 rev B") -> Quantity:
    """A manufacturer claim with a source, so it is evidence-eligible."""
    return Quantity(value, unit, Provenance.DATASHEET, source=source)


def derived(
    value: float, unit: str, source: str = "SGAQ derivation note 1"
) -> Quantity:
    """A computed value with a stated derivation."""
    return Quantity(value, unit, Provenance.DERIVED, source=source)


def measured(
    value: float, unit: str, evidence_ref: str = "EVT-AUDIO-0001"
) -> Quantity:
    """A bench observation traceable to an evidence artifact."""
    return Quantity(
        value,
        unit,
        Provenance.MEASURED,
        source="bench log",
        evidence_ref=evidence_ref,
    )


def proposed(value: float, unit: str) -> Quantity:
    """An engineering suggestion carrying no evidential weight."""
    return Quantity(value, unit, Provenance.PROPOSED, source="architecture study")


def assumed(value: float, unit: str) -> Quantity:
    """A working assumption adopted to make analysis possible."""
    return Quantity(value, unit, Provenance.ASSUMED, source="architecture study")


def audio_band() -> FrequencyBand:
    return FrequencyBand(
        low_hz=datasheet(20.0, "Hz", source="declared audio band"),
        high_hz=datasheet(20000.0, "Hz", source="declared audio band"),
    )


def fully_evidenced_profile() -> AudioAcquisitionProfile:
    """A profile in which every core quantity is evidence-grade.

    Not a claim about any real hardware. It exists so that tests can ask what
    the system does when evidence is complete, without that question being
    answered accidentally by a missing field somewhere else.
    """
    return AudioAcquisitionProfile(
        profile_id="TEST_FULLY_EVIDENCED",
        profile_version="1",
        pickup_interface=PickupInterfaceSpec(
            name="test Hi-Z input",
            pickup_type="P-90",
            input_impedance_ohm=datasheet(1.0e6, "ohm"),
            input_capacitance_pf=datasheet(50.0, "pF"),
        ),
        front_end=FrontEndSpec(
            name="test AFE",
            input_referred_noise_v_per_rthz=datasheet(10.0e-9, "V/rtHz"),
            gain_db=datasheet(20.0, "dB"),
            bandwidth_hz=datasheet(50000.0, "Hz"),
            max_input_vrms=datasheet(0.1, "Vrms"),
            thdn_db=datasheet(-100.0, "dB"),
        ),
        converter=ConverterSpec(
            name="test ADC",
            bits=datasheet(24.0, "bit"),
            full_scale_vrms=datasheet(1.0, "Vrms"),
            thermal_snr_db=datasheet(110.0, "dB"),
            thdn_db=datasheet(-100.0, "dB"),
            sfdr_db=datasheet(105.0, "dB"),
            aperture_jitter_s=datasheet(5.0e-12, "s"),
            sample_rate_hz=datasheet(48000.0, "Hz"),
            ac_coupled=True,
            hp_corner_hz=datasheet(10.0, "Hz"),
            anti_alias_disposition=AntiAliasDisposition.PRESENT,
        ),
        clock=ClockSpec(
            name="test local XO",
            rms_jitter_s=measured(50.0e-12, "s", evidence_ref="EVT-AUDIO-CLK-0042"),
            accuracy_ppm=datasheet(20.0, "ppm"),
            topology=ClockTopology.LOCAL_XO,
            spurious=False,
        ),
        declared_audio_band_hz=audio_band(),
    )


@pytest.fixture
def evidenced_profile() -> AudioAcquisitionProfile:
    return fully_evidenced_profile()
