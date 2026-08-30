"""Minimal Smart Guitar acquisition specs.

Only the types needed to prove that provenance-bearing fields work
structurally. This is not the SGAQ model; it is the smallest set of native
dataclasses on which the qualification model can later be built.

Deliberately absent, because their semantics are not exercised yet: clock
topology, spurious-content declarations, SFDR, THD+N, anti-alias disposition,
AC coupling, high-pass corner, pickup loading, power-state observations,
acquisition profiles, requirements, and any disposition vocabulary. Adding a
field here before anything reasons about it would record an engineering claim
no code examines.

Field typing rule
-----------------
An engineering value that may eventually affect qualification is
``Quantity | None`` (D-02), including converter bit depth. Bit depth is
discrete and architectural rather than measured, so a bare ``int`` was
tempting, but it is load-bearing -- it sets the ideal quantization floor -- and
a value that feeds a noise result should be able to say where it came from.
Uniformity also means no later field has to be argued about individually.

Categorical identity, such as a part name, stays a plain ``str``.

Unit discipline
---------------
Each field declares one canonical SI unit and construction fails on a
mismatch. Nothing is converted: a jitter figure in ``ps`` is rejected by a
field declared in ``s``, never rescaled. A
:class:`~acquisition.provenance.Quantity` may still hold ``50 ps`` perfectly
legitimately; it simply does not belong in that field.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final

from .provenance import Provenance, Quantity, collect_blockers, require_unit

__all__ = [
    "AntiAliasDisposition",
    "AudioAcquisitionProfile",
    "AudioQualificationRequirements",
    "ClockSpec",
    "ClockTopology",
    "ConverterSpec",
    "FrequencyBand",
    "FrontEndSpec",
    "PickupInterfaceSpec",
    "PowerCondition",
    "PowerNoiseObservation",
    "QualificationState",
    "worst_state",
]


# ---------------------------------------------------------------------------
# STAGED FOR 001B -- deferred vocabulary.
#
# None of the following is part of the 001A gate. It is written, tested and
# parked here so that the domain-semantics tranche starts from something
# reviewable rather than from a blank file. Nothing in the 001A surface
# depends on any of it.
# ---------------------------------------------------------------------------


class QualificationState(StrEnum):
    """Disposition vocabulary for a qualification dimension or a whole path."""

    PASS = "pass"
    """The dimension meets its requirement on the evidence available."""

    FAIL = "fail"
    """The dimension violates its requirement. A positive, load-bearing no."""

    REVIEW_REQUIRED = "review_required"
    """A human engineering judgement is required before this can be settled."""

    UNVALIDATED = "unvalidated"
    """Not enough is known to say anything. Never read this as a soft pass."""


_STATE_PRECEDENCE: Final[Mapping[QualificationState, int]] = {
    QualificationState.PASS: 0,
    QualificationState.UNVALIDATED: 1,
    QualificationState.REVIEW_REQUIRED: 2,
    QualificationState.FAIL: 3,
}
"""Disposition precedence: FAIL > REVIEW_REQUIRED > UNVALIDATED > PASS.

A hard measured failure must never be hidden behind an unrelated unknown.
"""


def worst_state(states: Iterable[QualificationState]) -> QualificationState:
    """Fold ``states`` down to the governing disposition.

    An empty input yields ``UNVALIDATED``: evaluating nothing is not a pass.
    """
    ranked = sorted(states, key=lambda s: _STATE_PRECEDENCE[s], reverse=True)
    return ranked[0] if ranked else QualificationState.UNVALIDATED


class ClockTopology(StrEnum):
    """How the audio sample clock is generated.

    Modelled explicitly rather than hidden behind a single jitter number,
    because Gaussian RMS jitter does not describe fractional-N spur behavior.
    """

    LOCAL_XO = "local_xo"
    """A local audio-grade oscillator; the codec is clock master."""

    HOST_FRACTIONAL_N = "host_fractional_n"
    """The host, for example a Pi acting as I2S master, synthesises the clock."""

    CLEANUP_PLL = "cleanup_pll"
    """An upstream clock re-timed by a jitter-attenuating PLL."""

    EXTERNAL_AUDIO_CLOCK = "external_audio_clock"
    """A clock supplied from outside the acquisition assembly."""

    UNKNOWN = "unknown"
    """Topology not established. Not the same as "probably fine"."""


class AntiAliasDisposition(StrEnum):
    """What is known about anti-alias filtering ahead of the converter."""

    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class PowerCondition(StrEnum):
    """Platform activity states under which acquisition noise is observed.

    Evidence slots only. No automated capture hardware is required for the
    vocabulary to exist before the measurements do.
    """

    BASELINE = "baseline"
    PI_IDLE = "pi_idle"
    PI_CPU_LOAD = "pi_cpu_load"
    DISPLAY_ACTIVE = "display_active"
    WIFI_ACTIVE = "wifi_active"
    BLUETOOTH_ACTIVE = "bluetooth_active"
    FAN_ACTIVE = "fan_active"
    BATTERY_CHARGING = "battery_charging"
    AI_ACCELERATOR_ACTIVE = "ai_accelerator_active"


def _quantities_as_dict(
    quantities: dict[str, Quantity | None],
) -> dict[str, Any]:
    """Serialize a quantity mapping, preserving unknowns as ``null``.

    An unknown serializes as an explicit ``null``, never as a substituted
    default and never by omitting the key (D-03).
    """
    return {
        name: (None if quantity is None else quantity.as_dict())
        for name, quantity in quantities.items()
    }


@dataclass(frozen=True)
class FrontEndSpec:
    """The analog front end between the input node and the converter."""

    name: str
    input_referred_noise_v_per_rthz: Quantity | None = None
    gain_db: Quantity | None = None
    bandwidth_hz: Quantity | None = None
    max_input_vrms: Quantity | None = None  # staged for 001B
    thdn_db: Quantity | None = None  # staged for 001B

    def __post_init__(self) -> None:
        require_unit(self.max_input_vrms, "Vrms", "max_input_vrms")
        require_unit(self.thdn_db, "dB", "thdn_db")
        require_unit(
            self.input_referred_noise_v_per_rthz,
            "V/rtHz",
            "input_referred_noise_v_per_rthz",
        )
        require_unit(self.gain_db, "dB", "gain_db")
        require_unit(self.bandwidth_hz, "Hz", "bandwidth_hz")

    def quantities(self) -> dict[str, Quantity | None]:
        """Every load-bearing quantity, in fixed order."""
        return {
            "input_referred_noise_v_per_rthz": self.input_referred_noise_v_per_rthz,
            "gain_db": self.gain_db,
            "bandwidth_hz": self.bandwidth_hz,
            "max_input_vrms": self.max_input_vrms,
            "thdn_db": self.thdn_db,
        }

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, **_quantities_as_dict(self.quantities())}


@dataclass(frozen=True)
class ConverterSpec:
    """The ADC or codec at the end of the analog chain."""

    name: str
    bits: Quantity | None = None
    full_scale_vrms: Quantity | None = None
    thermal_snr_db: Quantity | None = None
    aperture_jitter_s: Quantity | None = None
    sample_rate_hz: Quantity | None = None
    thdn_db: Quantity | None = None  # staged for 001B
    sfdr_db: Quantity | None = None  # staged for 001B
    ac_coupled: bool = False  # staged for 001B
    hp_corner_hz: Quantity | None = None  # staged for 001B
    anti_alias_disposition: AntiAliasDisposition = AntiAliasDisposition.UNKNOWN

    def __post_init__(self) -> None:
        require_unit(self.thdn_db, "dB", "thdn_db")
        require_unit(self.sfdr_db, "dB", "sfdr_db")
        require_unit(self.hp_corner_hz, "Hz", "hp_corner_hz")
        require_unit(self.bits, "bit", "bits")
        require_unit(self.full_scale_vrms, "Vrms", "full_scale_vrms")
        require_unit(self.thermal_snr_db, "dB", "thermal_snr_db")
        require_unit(self.aperture_jitter_s, "s", "aperture_jitter_s")
        require_unit(self.sample_rate_hz, "Hz", "sample_rate_hz")
        if self.bits is not None and not self.bits.value.is_integer():
            raise ValueError("bits must be a whole number of bits")
        if self.aperture_jitter_s is not None and self.aperture_jitter_s.value < 0.0:
            raise ValueError("aperture_jitter_s must not be negative")

    def quantities(self) -> dict[str, Quantity | None]:
        """Every load-bearing quantity, in fixed order."""
        return {
            "bits": self.bits,
            "full_scale_vrms": self.full_scale_vrms,
            "thermal_snr_db": self.thermal_snr_db,
            "aperture_jitter_s": self.aperture_jitter_s,
            "sample_rate_hz": self.sample_rate_hz,
            "thdn_db": self.thdn_db,
            "sfdr_db": self.sfdr_db,
            "hp_corner_hz": self.hp_corner_hz,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ac_coupled": self.ac_coupled,
            "anti_alias_disposition": self.anti_alias_disposition.value,
            **_quantities_as_dict(self.quantities()),
        }


@dataclass(frozen=True)
class ClockSpec:
    """The audio sample clock.

    Topology and spurious-content behavior are not modelled yet. Neither is
    describable by an RMS jitter figure, and nothing in this tranche reasons
    about them.
    """

    name: str
    rms_jitter_s: Quantity | None = None
    accuracy_ppm: Quantity | None = None
    topology: ClockTopology = ClockTopology.UNKNOWN
    spurious: bool = False  # staged for 001B

    def __post_init__(self) -> None:
        require_unit(self.rms_jitter_s, "s", "rms_jitter_s")
        require_unit(self.accuracy_ppm, "ppm", "accuracy_ppm")
        if self.rms_jitter_s is not None and self.rms_jitter_s.value < 0.0:
            raise ValueError("rms_jitter_s must not be negative")

    def quantities(self) -> dict[str, Quantity | None]:
        """Every load-bearing quantity, in fixed order."""
        return {
            "rms_jitter_s": self.rms_jitter_s,
            "accuracy_ppm": self.accuracy_ppm,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "topology": self.topology.value,
            "spurious": self.spurious,
            **_quantities_as_dict(self.quantities()),
        }


@dataclass(frozen=True)
class FrequencyBand:
    """A declared frequency band, both edges evidence-bearing."""

    low_hz: Quantity
    high_hz: Quantity

    def __post_init__(self) -> None:
        require_unit(self.low_hz, "Hz", "low_hz")
        require_unit(self.high_hz, "Hz", "high_hz")
        if self.low_hz.value <= 0.0:
            raise ValueError("low_hz must be positive")
        if self.high_hz.value <= self.low_hz.value:
            raise ValueError("high_hz must be greater than low_hz")

    def as_dict(self) -> dict[str, Any]:
        return {
            "low_hz": self.low_hz.as_dict(),
            "high_hz": self.high_hz.as_dict(),
        }


@dataclass(frozen=True)
class PickupInterfaceSpec:
    """The pickup and the instrument-input node it drives.

    Loading only. A full pickup RLC resonance model is a later concern;
    ``input_capacitance_pf`` is carried so the refinement has somewhere to land.
    """

    name: str
    pickup_type: str
    input_impedance_ohm: Quantity | None = None
    input_capacitance_pf: Quantity | None = None

    def __post_init__(self) -> None:
        require_unit(self.input_impedance_ohm, "ohm", "input_impedance_ohm")
        require_unit(self.input_capacitance_pf, "pF", "input_capacitance_pf")

    def quantities(self) -> dict[str, Quantity | None]:
        return {
            "input_impedance_ohm": self.input_impedance_ohm,
            "input_capacitance_pf": self.input_capacitance_pf,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "pickup_type": self.pickup_type,
            **_quantities_as_dict(self.quantities()),
        }


@dataclass(frozen=True)
class PowerNoiseObservation:
    """Acquisition noise observed under one platform power/activity condition.

    Observation-level ``provenance`` describes how the observation as a whole
    was obtained, and construction requires every quantity in it to agree, so
    the two levels cannot drift apart.
    """

    condition: PowerCondition
    noise_floor_dbfs: Quantity | None = None
    largest_spur_dbfs: Quantity | None = None
    largest_spur_hz: Quantity | None = None
    provenance: Provenance = Provenance.PROPOSED
    source: str = ""

    def __post_init__(self) -> None:
        require_unit(self.noise_floor_dbfs, "dBFS", "noise_floor_dbfs")
        require_unit(self.largest_spur_dbfs, "dBFS", "largest_spur_dbfs")
        require_unit(self.largest_spur_hz, "Hz", "largest_spur_hz")
        for name, quantity in self.quantities().items():
            if quantity is not None and quantity.provenance is not self.provenance:
                raise ValueError(
                    f"{name} provenance {quantity.provenance.value!r} disagrees "
                    f"with observation provenance {self.provenance.value!r}"
                )

    def quantities(self) -> dict[str, Quantity | None]:
        return {
            "noise_floor_dbfs": self.noise_floor_dbfs,
            "largest_spur_dbfs": self.largest_spur_dbfs,
            "largest_spur_hz": self.largest_spur_hz,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "condition": self.condition.value,
            "provenance": self.provenance.value,
            "source": self.source,
            **_quantities_as_dict(self.quantities()),
        }


@dataclass(frozen=True)
class AudioAcquisitionProfile:
    """A complete description of one Smart Guitar audio acquisition path.

    A profile is a description, not a verdict. It says what is believed about a
    hardware configuration and how well each belief is supported; whether that
    configuration qualifies is decided elsewhere.
    """

    profile_id: str
    profile_version: str
    pickup_interface: PickupInterfaceSpec
    front_end: FrontEndSpec
    converter: ConverterSpec
    clock: ClockSpec
    declared_audio_band_hz: FrequencyBand
    power_noise_observations: tuple[PowerNoiseObservation, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError("profile_id must be a non-empty string")
        if not self.profile_version.strip():
            raise ValueError("profile_version must be a non-empty string")
        seen: set[PowerCondition] = set()
        for observation in self.power_noise_observations:
            if observation.condition in seen:
                raise ValueError(
                    "duplicate power noise observation for condition "
                    f"{observation.condition.value!r}"
                )
            seen.add(observation.condition)

    def quantities(self) -> dict[str, Quantity | None]:
        """Every load-bearing quantity in the profile, by dotted field path.

        Insertion order is fixed, so any walk over this mapping is
        deterministic.
        """
        collected: dict[str, Quantity | None] = {}
        sections: Sequence[tuple[str, Mapping[str, Quantity | None]]] = (
            ("pickup_interface", self.pickup_interface.quantities()),
            ("front_end", self.front_end.quantities()),
            ("converter", self.converter.quantities()),
            ("clock", self.clock.quantities()),
        )
        for prefix, section in sections:
            for name, quantity in section.items():
                collected[f"{prefix}.{name}"] = quantity
        for observation in self.power_noise_observations:
            prefix = f"power_noise[{observation.condition.value}]"
            for name, quantity in observation.quantities().items():
                collected[f"{prefix}.{name}"] = quantity
        return collected

    def evidence_blockers(self) -> tuple[str, ...]:
        """Every reason this profile is not yet evidence-grade (utility U-05).

        Power noise observations are excluded: their absence is reported by the
        power contamination dimension, which knows which conditions matter,
        rather than by a blanket pass over whichever observations happen to
        have been recorded.
        """
        core = {
            name: quantity
            for name, quantity in self.quantities().items()
            if not name.startswith("power_noise[")
        }
        return collect_blockers(core)

    def observation(self, condition: PowerCondition) -> PowerNoiseObservation | None:
        """Return the observation recorded for ``condition``, if any."""
        for observation in self.power_noise_observations:
            if observation.condition is condition:
                return observation
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "pickup_interface": self.pickup_interface.as_dict(),
            "front_end": self.front_end.as_dict(),
            "converter": self.converter.as_dict(),
            "clock": self.clock.as_dict(),
            "declared_audio_band_hz": self.declared_audio_band_hz.as_dict(),
            "power_noise_observations": [
                observation.as_dict() for observation in self.power_noise_observations
            ],
        }


@dataclass(frozen=True)
class AudioQualificationRequirements:
    """The thresholds a Smart Guitar acquisition path is judged against.

    Authored requirements, not hardware claims, so plain floats rather than
    quantities: there is no evidence to attach to a number we chose. Where a
    threshold originates in measured population data, that provenance belongs
    to the document that sets it.

    ``min_interstage_margin_db`` is deliberately not called headroom. The
    margin evaluated is inter-stage gain-staging margin, not player or source
    headroom; a ``min_source_headroom_db`` requirement arrives only with
    measured pickup levels.
    """

    min_input_impedance_ohm: float
    min_combined_snr_db: float
    min_sfdr_db: float
    max_thdn_db: float
    min_interstage_margin_db: float
    require_anti_alias: bool = True
    require_known_hp_corner: bool = True
    require_evidence_grade: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "min_input_impedance_ohm": self.min_input_impedance_ohm,
            "min_combined_snr_db": self.min_combined_snr_db,
            "min_sfdr_db": self.min_sfdr_db,
            "max_thdn_db": self.max_thdn_db,
            "min_interstage_margin_db": self.min_interstage_margin_db,
            "require_anti_alias": self.require_anti_alias,
            "require_known_hp_corner": self.require_known_hp_corner,
            "require_evidence_grade": self.require_evidence_grade,
        }
