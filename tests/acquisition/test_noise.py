"""T13-T25: the native mathematical kernel.

Every expected value here is either hand-derived in the comment above it or is
an exact closed form checkable without a calculator. The reference vectors
were computed independently of ``acquisition.noise`` and are quoted to ten
decimal places so an algebraic error cannot hide inside a loose tolerance.

No expected result in this file is sourced from another codebase, and no
parity test against one exists.
"""

import math

import pytest

from acquisition.noise import (
    combine_snr_db,
    front_end_noise_vrms,
    jitter_budget_s,
    jitter_snr_db,
    quantization_snr_db,
    rss,
    voltage_snr_db,
)

DB = 1e-9  # tolerance for values quoted to ten decimal places


# ---------------------------------------------------------------------------
# T13 / T14 - jitter equation reference vectors
# ---------------------------------------------------------------------------


def test_t13_jitter_reference_vector_20khz_1ns() -> None:
    """SNR = -20*log10(2*pi*f*t_j), hand-calculated.

        f = 20,000 Hz, t_j = 1 ns
        2*pi*f*t_j = 2*pi * 20000 * 1e-9 = 1.2566370614e-04
        log10(1.2566370614e-04)          = -3.9007901360
        SNR                              = 78.0158027196 dB
    """
    assert jitter_snr_db(20_000.0, 1e-9) == pytest.approx(78.0158027196, abs=DB)


def test_t14_jitter_reference_vector_20khz_50ps() -> None:
    """The same relation two decades of jitter away, which pins the scale.

        f = 20,000 Hz, t_j = 50 ps
        2*pi*f*t_j = 2*pi * 20000 * 50e-12 = 6.2831853072e-06
        log10(6.2831853072e-06)            = -5.2018201316
        SNR                                = 104.0364026328 dB

    T13 and T14 differ by a factor of 20 in jitter, so they must differ by
    exactly 20*log10(20) = 26.0206 dB. A unit-scale error in the
    implementation cannot satisfy both.
    """
    assert jitter_snr_db(20_000.0, 50e-12) == pytest.approx(104.0364026328, abs=DB)
    assert jitter_snr_db(20_000.0, 50e-12) - jitter_snr_db(20_000.0, 1e-9) == (
        pytest.approx(20.0 * math.log10(20.0), abs=DB)
    )


def test_t13_closed_form_anchors_need_no_decimal_expansion() -> None:
    """When 2*pi*f*t_j == 1 the error RMS equals the signal RMS: 0 dB exactly.

    When the product is 0.1 the ratio is exactly 10, so the answer is exactly
    20 dB. These pin the formula's scale and sign with no logarithm table.
    """
    unity = 1.0 / (2.0 * math.pi * 20_000.0)
    assert jitter_snr_db(20_000.0, unity) == pytest.approx(0.0, abs=1e-12)
    assert jitter_snr_db(20_000.0, unity / 10.0) == pytest.approx(20.0, abs=1e-12)


def test_t13_doubling_frequency_or_jitter_costs_exactly_6_0206_db() -> None:
    """SNR depends on the product f*t_j, so either doubling costs the same."""
    six_db = 20.0 * math.log10(2.0)
    base = jitter_snr_db(20_000.0, 100e-12)
    assert jitter_snr_db(40_000.0, 100e-12) == pytest.approx(base - six_db, abs=DB)
    assert jitter_snr_db(20_000.0, 200e-12) == pytest.approx(base - six_db, abs=DB)


# ---------------------------------------------------------------------------
# T15 - jitter inverse
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("f_in_hz", [82.41, 1_000.0, 5_000.0, 20_000.0])
@pytest.mark.parametrize("target_snr_db", [60.0, 96.0, 110.0, 120.0])
def test_t15_jitter_budget_round_trips_to_the_target(
    f_in_hz: float, target_snr_db: float
) -> None:
    """U-02 must invert U-01 exactly.

    Any scale error in either direction -- an amplitude factor, a 10-versus-20
    log confusion -- breaks the round trip.
    """
    budget = jitter_budget_s(f_in_hz, target_snr_db)
    assert jitter_snr_db(f_in_hz, budget) == pytest.approx(target_snr_db, abs=1e-9)


def test_t15_jitter_budget_reference_vector() -> None:
    """f = 20 kHz, target 104.0364026328 dB reproduces T14's 50 ps.

        t_j = 10**(-104.0364026328/20) / (2*pi*20000)
            = 50.0 ps
    """
    assert jitter_budget_s(20_000.0, 104.0364026328) == pytest.approx(
        50e-12, rel=1e-9
    )


def test_t15_budget_tightens_in_proportion_to_frequency() -> None:
    """Ten times the frequency allows one tenth the jitter for a given SNR."""
    low = jitter_budget_s(2_000.0, 100.0)
    high = jitter_budget_s(20_000.0, 100.0)
    assert high == pytest.approx(low / 10.0, rel=1e-12)


# ---------------------------------------------------------------------------
# T16 / T17 - invalid jitter inputs are rejected, never clamped
# ---------------------------------------------------------------------------


def test_t16_invalid_frequency_rejected() -> None:
    for bad in (0.0, -1.0, -20_000.0):
        with pytest.raises(ValueError, match="f_in_hz must be positive"):
            jitter_snr_db(bad, 50e-12)
        with pytest.raises(ValueError, match="f_in_hz must be positive"):
            jitter_budget_s(bad, 100.0)


def test_t17_invalid_jitter_rejected() -> None:
    """Zero jitter would return infinity and silently poison a consumer."""
    for bad in (0.0, -1e-12, -1.0):
        with pytest.raises(ValueError, match="tj_rms_s must be positive"):
            jitter_snr_db(20_000.0, bad)


def test_t16_t17_non_finite_jitter_inputs_rejected() -> None:
    with pytest.raises(ValueError, match="must be finite"):
        jitter_snr_db(math.inf, 50e-12)
    with pytest.raises(ValueError, match="must be finite"):
        jitter_snr_db(20_000.0, math.nan)
    with pytest.raises(ValueError, match="must be finite"):
        jitter_budget_s(20_000.0, math.nan)


# ---------------------------------------------------------------------------
# T18 / T19 / T20 - ideal quantization SNR
# ---------------------------------------------------------------------------


def test_t18_ideal_16_bit_quantization_snr() -> None:
    """Hand-derived from SNR = 2**N * sqrt(3/2).

        N = 16: ratio = 65536 * 1.2247448714 = 80264.8809188
                SNR   = 20*log10(80264.8809188) = 98.0905112030 dB

    The textbook shorthand 6.02*16 + 1.76 = 98.08 dB is the same equation with
    its coefficients rounded to two decimals; it is 0.0105 dB low. The kernel
    returns the exact value.
    """
    assert quantization_snr_db(16) == pytest.approx(98.0905112030, abs=DB)
    assert quantization_snr_db(16) == pytest.approx(98.08, abs=0.011)


def test_t19_ideal_24_bit_quantization_snr() -> None:
    """N = 24: SNR = 20*log10(16777216 * 1.2247448714) = 146.2553105093 dB.

    The textbook shorthand gives 146.24 dB, 0.0153 dB low.
    """
    assert quantization_snr_db(24) == pytest.approx(146.2553105093, abs=DB)
    assert quantization_snr_db(24) == pytest.approx(146.24, abs=0.016)


def test_t18_t19_recomputed_from_the_ratio_form() -> None:
    """Check the dB coefficients against the derivation they come from.

    ``2**N * sqrt(3/2)`` is the derivation; ``6.0206*N + 1.7609`` is its
    logarithm. Checking one against the other catches a mistranscribed
    coefficient that a self-consistent implementation would hide.
    """
    for bits in (1, 8, 12, 16, 20, 24, 32):
        ratio = (2.0**bits) * math.sqrt(1.5)
        assert quantization_snr_db(bits) == pytest.approx(
            20.0 * math.log10(ratio), abs=1e-12
        )


def test_t18_t19_exactly_6_0206_db_per_bit() -> None:
    per_bit = 20.0 * math.log10(2.0)
    assert per_bit == pytest.approx(6.0205999133, abs=1e-10)
    for bits in range(1, 32):
        step = quantization_snr_db(bits + 1) - quantization_snr_db(bits)
        assert step == pytest.approx(per_bit, abs=1e-12)


def test_t20_invalid_bit_depth_rejected() -> None:
    for bad in (0, -1, -16):
        with pytest.raises(ValueError, match="bits must be positive"):
            quantization_snr_db(bad)
    with pytest.raises(TypeError, match="bits must be an int"):
        quantization_snr_db(16.5)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="bits must be an int"):
        quantization_snr_db(True)


def test_t20_no_arbitrary_bit_depth_restriction() -> None:
    """Non-standard depths are legitimate; only nonsense is rejected."""
    for bits in (1, 12, 18, 20, 32):
        assert quantization_snr_db(bits) > 0.0


# ---------------------------------------------------------------------------
# T21 / T22 / T23 - independent noise-power combination
# ---------------------------------------------------------------------------


def test_t21_two_equal_100_db_terms_combine_to_96_9897_db() -> None:
    """Two equal independent noise sources double the noise power.

        total power = 2 * 10**(-10) = 2e-10
        SNR         = -10*log10(2e-10) = 96.9897000434 dB

    Exactly 10*log10(2) = 3.0103 dB worse than either term. This is the test
    that proves powers are being summed rather than dB values manipulated.
    """
    assert combine_snr_db(100.0, 100.0) == pytest.approx(96.9897000434, abs=DB)
    assert combine_snr_db(100.0, 100.0) == pytest.approx(
        100.0 - 10.0 * math.log10(2.0), abs=1e-12
    )


def test_t21_n_equal_terms_lose_exactly_10_log10_n() -> None:
    for count in (2, 3, 4, 8):
        expected = 100.0 - 10.0 * math.log10(count)
        assert combine_snr_db(*([100.0] * count)) == pytest.approx(expected, abs=1e-12)


def test_t22_unequal_terms_are_not_simply_the_minimum() -> None:
    """Hand-calculated by summing 10**(-SNR/10) and taking -10*log10.

        [100, 110]          -> 99.5860731484 dB
        [96, 96, 96]        -> 91.2287874528 dB
        [120, 100, 105, 98] -> 95.3593974904 dB

    Each result is strictly below the smallest input, which a ``min()``
    implementation could never produce. The 100/110 case is the sharpest: a
    term 10 dB quieter still costs 0.414 dB, and picking the minimum would
    report 100 dB exactly.
    """
    assert combine_snr_db(100.0, 110.0) == pytest.approx(99.5860731484, abs=DB)
    assert combine_snr_db(96.0, 96.0, 96.0) == pytest.approx(91.2287874528, abs=DB)
    assert combine_snr_db(120.0, 100.0, 105.0, 98.0) == pytest.approx(
        95.3593974904, abs=DB
    )

    for terms in ((100.0, 110.0), (96.0, 96.0, 96.0), (120.0, 100.0, 105.0, 98.0)):
        assert combine_snr_db(*terms) < min(terms)


def test_t22_not_a_db_average_and_not_a_db_sum() -> None:
    """Rule out the two arithmetic shortcuts that resemble the right answer."""
    combined = combine_snr_db(100.0, 110.0)
    assert combined != pytest.approx(105.0, abs=0.1)  # not the mean
    assert combined != pytest.approx(210.0, abs=0.1)  # not the sum


def test_t22_combination_is_order_independent() -> None:
    assert combine_snr_db(100.0, 110.0) == pytest.approx(
        combine_snr_db(110.0, 100.0), abs=1e-12
    )


def test_t22_a_far_quieter_term_is_almost_irrelevant() -> None:
    """A term 20 dB quieter adds 10*log10(1.01) = 0.0432137378 dB."""
    assert combine_snr_db(100.0, 120.0) == pytest.approx(
        100.0 - 0.0432137378, abs=DB
    )


def test_t22_a_single_term_combines_to_itself() -> None:
    assert combine_snr_db(98.0905112030) == pytest.approx(98.0905112030, abs=1e-12)


def test_t23_empty_snr_input_rejected() -> None:
    """There is no meaningful SNR of nothing, and no identity to fall back on."""
    with pytest.raises(ValueError, match="at least one contribution"):
        combine_snr_db()


def test_t23_non_finite_terms_rejected_not_discarded() -> None:
    """Dropping a bad term would improve the reported SNR.

    That is the most dangerous direction for a mistake to go, so an invalid
    term is an error rather than something to skip.
    """
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="must be finite"):
            combine_snr_db(100.0, bad)


# ---------------------------------------------------------------------------
# T24 / T25 - RSS and remaining input validation
# ---------------------------------------------------------------------------


def test_t24_rss_3_4_5() -> None:
    assert rss(3.0, 4.0) == pytest.approx(5.0, abs=1e-12)


def test_t24_rss_combines_in_quadrature() -> None:
    assert rss(50e-12, 50e-12) == pytest.approx(math.sqrt(2.0) * 50e-12, rel=1e-12)
    assert rss(5.0) == pytest.approx(5.0, abs=1e-12)
    assert rss(3.0, 4.0, 12.0) == pytest.approx(13.0, abs=1e-12)


def test_t24_rss_of_no_contributors_is_the_zero_identity() -> None:
    """An identity, not a substituted default.

    The root sum of squares of no contributors is zero, and that value
    composes correctly with any further combination. An *unknown* contributor
    remains an error and must never be passed as an absent one.
    """
    assert rss() == 0.0
    assert rss(*[]) == 0.0
    assert rss(0.0, 3.0, 4.0) == pytest.approx(5.0, abs=1e-12)


def test_t25_rss_rejects_non_finite_input() -> None:
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="must be finite"):
            rss(3.0, bad)


def test_t25_front_end_noise_reference_vector() -> None:
    """10 nV/rtHz over 20 kHz with 20 dB of gain.

        sqrt(20000)          = 141.4213562373
        input-referred noise = 10e-9 * 141.4213562373 = 1.4142135624e-06 Vrms
        gain                 = 10**(20/20) = 10
        output noise         = 1.4142135624e-05 Vrms
    """
    assert front_end_noise_vrms(10e-9, 20_000.0, 20.0) == pytest.approx(
        1.4142135624e-05, rel=1e-9
    )
    assert front_end_noise_vrms(10e-9, 20_000.0, 0.0) == pytest.approx(
        1.4142135624e-06, rel=1e-9
    )


def test_t25_front_end_noise_rejects_invalid_input() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        front_end_noise_vrms(0.0, 20_000.0, 20.0)
    with pytest.raises(ValueError, match="must be positive"):
        front_end_noise_vrms(10e-9, 0.0, 20.0)
    with pytest.raises(ValueError, match="must be finite"):
        front_end_noise_vrms(10e-9, 20_000.0, math.nan)


def test_t25_voltage_snr_reference_vector() -> None:
    """1.0 Vrms signal against 1.4142135624e-05 Vrms of noise.

        SNR = 20*log10(1.0 / 1.4142135624e-05) = 96.9897000434 dB
    """
    assert voltage_snr_db(1.0, 1.4142135624e-05) == pytest.approx(
        96.9897000434, abs=DB
    )
    assert voltage_snr_db(1.0, 1.0) == pytest.approx(0.0, abs=1e-12)
    assert voltage_snr_db(10.0, 1.0) == pytest.approx(20.0, abs=1e-12)


def test_t25_gain_does_not_buy_snr_against_a_fixed_full_scale() -> None:
    """Gain amplifies the front end's own noise along with the signal.

    A real design consequence worth pinning: raising pre-converter gain helps
    reach full scale from a small source, but degrades front-end SNR against a
    fixed full scale by exactly the gain applied.
    """
    at_0_db = voltage_snr_db(1.0, front_end_noise_vrms(1e-6, 20_000.0, 0.0))
    at_20_db = voltage_snr_db(1.0, front_end_noise_vrms(1e-6, 20_000.0, 20.0))
    assert at_20_db == pytest.approx(at_0_db - 20.0, abs=1e-12)


def test_t25_voltage_snr_rejects_invalid_input() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        voltage_snr_db(1.0, 0.0)
    with pytest.raises(ValueError, match="must be positive"):
        voltage_snr_db(0.0, 1e-6)
    with pytest.raises(ValueError, match="must be finite"):
        voltage_snr_db(math.inf, 1e-6)
