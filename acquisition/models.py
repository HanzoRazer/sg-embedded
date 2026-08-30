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

from dataclasses import dataclass
from typing import Any

from .provenance import Quantity, require_unit

__all__ = [
    "ClockSpec",
    "ConverterSpec",
    "FrontEndSpec",
]


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

    def __post_init__(self) -> None:
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

    def __post_init__(self) -> None:
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
        }

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, **_quantities_as_dict(self.quantities())}


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
        return {"name": self.name, **_quantities_as_dict(self.quantities())}
