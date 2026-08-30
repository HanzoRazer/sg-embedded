"""Native mathematical kernel: jitter, quantization, and noise combination.

Pure first-principles engineering mathematics on plain floats. Every relation
is derived in its own docstring and validated against hand-calculated
reference vectors in ``tests/acquisition/test_noise.py``. Correctness is
established by derivation and independent arithmetic; there is no parity gate
against any other codebase, and none is intended.

This module holds no policy and no domain semantics. It does not decide which
bandwidth to integrate over, what to do about a missing value, which term
limits a design, or whether any result is acceptable. Invalid engineering
input raises; nothing is silently clamped, defaulted, or discarded.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

__all__ = [
    "combine_snr_db",
    "front_end_noise_vrms",
    "jitter_budget_s",
    "jitter_snr_db",
    "quantization_snr_db",
    "rss",
    "voltage_snr_db",
]

_DB_PER_BIT: Final[float] = 20.0 * math.log10(2.0)
"""6.020599913... dB. Derived, not a remembered constant."""

_QUANTIZATION_OFFSET_DB: Final[float] = 20.0 * math.log10(math.sqrt(1.5))
"""1.760912591... dB, i.e. 20*log10(sqrt(3/2)). See :func:`quantization_snr_db`."""


def _positive(value: float, name: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")
    if value <= 0.0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return value


def _finite(value: float, name: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return value


def rss(*values: float) -> float:
    """Root sum of squares.

    The combination rule for independent random contributions: uncorrelated
    quantities add in power, so their amplitudes add in quadrature.

    ``rss(3, 4) == 5``.

    With no arguments this returns ``0.0``, the natural identity: the root sum
    of squares of no contributors is zero, and that value composes correctly
    with any subsequent combination. This is an identity, not a substituted
    default -- an *unknown* contributor is still an error and must never be
    passed as an absent one.
    """
    return math.sqrt(sum(_finite(v, "value") ** 2 for v in values))


def jitter_snr_db(f_in_hz: float, tj_rms_s: float) -> float:
    """Jitter-limited SNR of a sampled sinusoid, in dB (utility U-01).

    Derivation
    ----------
    Sample a sinusoid ``v(t) = A*sin(2*pi*f*t)`` at times carrying an
    independent random error ``dt`` of RMS ``t_j``. For small ``dt`` the
    amplitude error is the slope times the timing error::

        dv = dt * dv/dt = dt * A*2*pi*f*cos(2*pi*f*t)

    The cosine contributes an RMS factor of ``1/sqrt(2)`` over the cycle, and
    the timing error is independent of signal phase, so::

        error_rms  = A * 2*pi*f * t_j / sqrt(2)
        signal_rms = A / sqrt(2)

    The amplitude ``A`` and the ``sqrt(2)`` both cancel::

        SNR = signal_rms / error_rms = 1 / (2*pi*f*t_j)

    and therefore::

        SNR_dB = -20*log10(2*pi*f*t_j)

    The result is independent of amplitude: jitter degrades a full-scale
    signal and a quiet one by the same ratio.

    Zero jitter is rejected rather than returning infinity. A clock with
    literally no jitter is not a physical claim, and an infinity would
    propagate silently into whatever consumed it.
    """
    _positive(f_in_hz, "f_in_hz")
    _positive(tj_rms_s, "tj_rms_s")
    return -20.0 * math.log10(2.0 * math.pi * f_in_hz * tj_rms_s)


def jitter_budget_s(f_in_hz: float, target_snr_db: float) -> float:
    """RMS jitter corresponding to a jitter-limited SNR, in seconds (U-02).

    The exact inverse of :func:`jitter_snr_db`. From
    ``SNR_dB = -20*log10(2*pi*f*t_j)``::

        t_j = 10**(-SNR_dB/20) / (2*pi*f)

    This answers the pure mathematical question only: what RMS jitter
    corresponds to this jitter-limited SNR at this frequency? It allocates
    nothing against converter noise or any other contributor; budget
    allocation across a real design is a later concern.
    """
    _positive(f_in_hz, "f_in_hz")
    _finite(target_snr_db, "target_snr_db")
    return float(10.0 ** (-target_snr_db / 20.0)) / (2.0 * math.pi * f_in_hz)


def quantization_snr_db(bits: int) -> float:
    """Ideal quantization SNR for a full-scale sine, in dB (utility U-03).

    Derivation
    ----------
    An ideal ``N``-bit uniform quantizer covering a full-scale range ``FS``
    has step size ``q = FS / 2**N``. Quantization error is uniformly
    distributed over one step, so its variance is ``q**2/12`` and its RMS is
    ``q/sqrt(12)``.

    A full-scale sine spans the range peak to peak, so its amplitude is
    ``FS/2`` and its RMS is ``FS/(2*sqrt(2))``. Therefore::

        SNR = [FS/(2*sqrt(2))] / [FS/(2**N * sqrt(12))]
            = 2**N * sqrt(12) / (2*sqrt(2))
            = 2**N * sqrt(3/2)

    In dB::

        SNR_dB = N*20*log10(2) + 20*log10(sqrt(3/2))

    The exact coefficients are ``20*log10(2) = 6.020599913...`` and
    ``20*log10(sqrt(3/2)) = 1.760912591...``, and this function uses them,
    yielding 98.090511 dB at 16 bits and 146.255311 dB at 24 bits.

    The familiar ``6.02N + 1.76`` giving 98.08 and 146.24 is textbook
    shorthand: the same equation with its coefficients rounded to two
    decimals. It is documented here for recognition and is not what the kernel
    returns. Carrying a rounding error into an evidence record would be a
    small dishonesty with no benefit.

    This is a ceiling for an ideal converter, not a claim about any real part.
    """
    if isinstance(bits, bool) or not isinstance(bits, int):
        raise TypeError(f"bits must be an int, got {type(bits).__name__!r}")
    if bits <= 0:
        raise ValueError(f"bits must be positive, got {bits!r}")
    return _DB_PER_BIT * bits + _QUANTIZATION_OFFSET_DB


def combine_snr_db(*snr_db: float) -> float:
    """Combine independent SNR contributions sharing one signal reference (U-04).

    Derivation
    ----------
    Each contribution states a signal-to-noise ratio against the same signal
    reference, so each implies a noise power relative to that reference::

        p_i = 10**(-SNR_i/10)

    Independent noise sources add in power, so the total relative noise power
    is ``sum(p_i)`` and::

        SNR_total_dB = -10*log10(sum(10**(-SNR_i/10)))

    Two equal contributions therefore combine to exactly ``10*log10(2)`` =
    3.0103 dB worse than either.

    This is noise-power addition, not any of the shortcuts that resemble it:
    dB values are never averaged, never added, and the result is not the
    minimum term. The minimum is only approached when one term dominates.

    Every supplied term must be finite. An invalid term is an error, not
    something to discard quietly -- silently dropping one would improve the
    reported SNR, which is the most dangerous direction for a mistake to go.
    Empty input is rejected: there is no meaningful SNR of nothing, and unlike
    :func:`rss` there is no identity element to fall back on.

    All terms must already be referenced to the same signal level. This
    function cannot check that and does not try.
    """
    if not snr_db:
        raise ValueError("combine_snr_db requires at least one contribution")
    total_noise_power = sum(10.0 ** (-_finite(s, "snr_db") / 10.0) for s in snr_db)
    if total_noise_power <= 0.0:
        raise ValueError("combined noise power underflowed to zero")
    return -10.0 * math.log10(total_noise_power)


def front_end_noise_vrms(
    input_referred_noise_v_per_rthz: float,
    bandwidth_hz: float,
    gain_db: float,
) -> float:
    """Output-referred front-end noise, in Vrms.

    For a white (frequency-flat) input-referred density ``e_n`` in V/sqrt(Hz),
    the noise power in a band of width ``B`` is ``e_n**2 * B``, so the
    input-referred RMS voltage is ``e_n * sqrt(B)``. Gain amplifies the front
    end's own noise along with the signal::

        v_out = e_n * sqrt(B) * 10**(gain_db/20)

    ``bandwidth_hz`` is an equivalent noise bandwidth and the caller supplies
    it deliberately. This function does not assume a quoted -3 dB bandwidth is
    a noise bandwidth (for a single-pole roll-off the noise bandwidth is about
    1.57 times the corner), and it does not decide whether out-of-band noise
    is removed by an anti-alias filter or folded back by the sampler. Those
    are qualification-layer questions.
    """
    _positive(input_referred_noise_v_per_rthz, "input_referred_noise_v_per_rthz")
    _positive(bandwidth_hz, "bandwidth_hz")
    _finite(gain_db, "gain_db")
    gain_linear = float(10.0 ** (gain_db / 20.0))
    return input_referred_noise_v_per_rthz * math.sqrt(bandwidth_hz) * gain_linear


def voltage_snr_db(signal_vrms: float, noise_vrms: float) -> float:
    """Signal-to-noise ratio of two RMS voltages, in dB.

    ``SNR_dB = 20*log10(signal_vrms / noise_vrms)``, the ratio of two
    amplitudes rather than two powers, hence 20 rather than 10.

    Both voltages must be referred to the same point in the signal chain. This
    function takes two numbers and cannot verify that; choosing a consistent
    reference is the caller's responsibility.
    """
    _positive(signal_vrms, "signal_vrms")
    _positive(noise_vrms, "noise_vrms")
    return 20.0 * math.log10(signal_vrms / noise_vrms)


# ---------------------------------------------------------------------------
# STAGED FOR 001B -- broadband noise budget and dominant-limiter analysis.
#
# Not part of the 001A gate. This assembles the primitives above into a design
# result, which is a qualification-layer act rather than a mathematical one.
# Nothing in the 001A surface depends on any of it.
# ---------------------------------------------------------------------------

FRONT_END: Final = "front_end"
CONVERTER_THERMAL: Final = "converter_thermal"
QUANTIZATION: Final = "quantization"
JITTER: Final = "jitter"

CONTRIBUTORS: Final[tuple[str, ...]] = (
    FRONT_END,
    CONVERTER_THERMAL,
    QUANTIZATION,
    JITTER,
)
"""The broadband noise contributors, in a fixed order.

Fixed so limiter selection stays deterministic when two contributors are
exactly equal.
"""


@dataclass(frozen=True)
class NoiseBudget:
    """The result of a broadband noise budget.

    Attributes
    ----------
    contributions:
        Per-contributor SNR in dB, referenced to converter full scale, in the
        fixed :data:`CONTRIBUTORS` order.
    combined_snr_db:
        All contributions combined by noise-power addition.
    limiter:
        The contributor carrying the largest share of total noise power, i.e.
        the term that actually limits the path. Ties break by
        :data:`CONTRIBUTORS` order.
    limiter_share:
        The limiter's fraction of total noise power, in ``(0, 1]``. A share
        near 0.25 means all four terms are comparable and no single fix helps.
    jitter_headroom_db:
        How far the jitter-limited SNR sits above the combined SNR of every
        other contributor. Positive means the clock is quieter than the rest of
        the path put together, so clock improvements cannot help much. This is
        a diagnostic against the design as it stands, distinct from
        :func:`jitter_budget_s`, which allocates against an external target.
    total_jitter_s:
        Clock RMS jitter and converter aperture jitter combined in quadrature.
    signal_reference:
        The declared reference for every SNR reported here.
    """

    contributions: Mapping[str, float]
    combined_snr_db: float
    limiter: str
    limiter_share: float
    jitter_headroom_db: float
    total_jitter_s: float
    signal_reference: str = "converter_full_scale"

    def as_dict(self) -> dict[str, Any]:
        return {
            "contributions": {
                name: self.contributions[name]
                for name in CONTRIBUTORS
                if name in self.contributions
            },
            "combined_snr_db": self.combined_snr_db,
            "limiter": self.limiter,
            "limiter_share": self.limiter_share,
            "jitter_headroom_db": self.jitter_headroom_db,
            "total_jitter_s": self.total_jitter_s,
            "signal_reference": self.signal_reference,
        }


def _noise_power(snr_db: float) -> float:
    return float(10.0 ** (-snr_db / 10.0))


def dominant_limiter(contributions: Mapping[str, float]) -> tuple[str, float]:
    """Return the limiting contributor and its share of total noise power.

    The limiter is the contributor with the *lowest* SNR, which is the one
    contributing the *most* noise power. Reporting the share as well as the
    name matters: naming a limiter that carries 26% of the noise invites an
    engineering effort that cannot pay off.
    """
    if not contributions:
        raise ValueError("dominant_limiter requires at least one contribution")
    ordered = [name for name in CONTRIBUTORS if name in contributions]
    ordered += [name for name in contributions if name not in CONTRIBUTORS]
    powers = {name: _noise_power(contributions[name]) for name in ordered}
    total = sum(powers.values())
    if total <= 0.0:
        raise ValueError("total noise power underflowed to zero")
    limiter = max(ordered, key=lambda name: powers[name])
    return limiter, powers[limiter] / total


def broadband_noise_budget(
    *,
    test_frequency_hz: float,
    front_end_noise_density_v_per_rthz: float,
    noise_bandwidth_hz: float,
    gain_db: float,
    full_scale_vrms: float,
    converter_thermal_snr_db: float,
    bits: int,
    clock_rms_jitter_s: float,
    aperture_jitter_s: float,
) -> NoiseBudget:
    """Combine the four broadband contributors into one budget.

    The contributors are the front end, the converter's own thermal noise, the
    ideal quantization floor, and clock jitter. All four are referenced to
    converter full scale and combined by noise-power addition.

    Clock jitter and converter aperture jitter are independent timing errors,
    so they combine in quadrature into a single effective timing uncertainty
    before being converted to an SNR.

    Every argument is a plain float and required. Missing values are the
    qualification layer's problem: a budget computed from a default would be a
    fabricated number wearing the appearance of a result.
    """
    total_jitter = rss(
        _positive(clock_rms_jitter_s, "clock_rms_jitter_s"),
        _positive(aperture_jitter_s, "aperture_jitter_s"),
    )
    front_end_noise = front_end_noise_vrms(
        front_end_noise_density_v_per_rthz, noise_bandwidth_hz, gain_db
    )
    contributions: dict[str, float] = {
        FRONT_END: voltage_snr_db(full_scale_vrms, front_end_noise),
        CONVERTER_THERMAL: _finite(
            converter_thermal_snr_db, "converter_thermal_snr_db"
        ),
        QUANTIZATION: quantization_snr_db(bits),
        JITTER: jitter_snr_db(test_frequency_hz, total_jitter),
    }
    combined = combine_snr_db(*(contributions[name] for name in CONTRIBUTORS))
    limiter, share = dominant_limiter(contributions)
    others = combine_snr_db(
        *(contributions[name] for name in CONTRIBUTORS if name != JITTER)
    )
    return NoiseBudget(
        contributions=contributions,
        combined_snr_db=combined,
        limiter=limiter,
        limiter_share=share,
        jitter_headroom_db=contributions[JITTER] - others,
        total_jitter_s=total_jitter,
    )
