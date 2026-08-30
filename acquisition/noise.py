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
from typing import Final

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
