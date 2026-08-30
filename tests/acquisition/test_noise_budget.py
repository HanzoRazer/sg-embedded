"""STAGED FOR 001B: broadband noise budget and dominant-limiter analysis.

Not part of the 001A gate. The primitives these compose are gated in
``test_noise.py``; what is exercised here is their assembly into a design
result, which is a qualification-layer act.
"""

import math

import pytest

from acquisition.noise import (
    CONTRIBUTORS,
    FRONT_END,
    JITTER,
    broadband_noise_budget,
    combine_snr_db,
    dominant_limiter,
)

DB = 1e-9


def test_jitter_is_the_dominant_limiter() -> None:
    """A synthetic path whose only weakness is its clock.

    24-bit converter (146.26 dB), 120 dB converter thermal noise, a very quiet
    front end, and 1 ns of clock jitter evaluated at 20 kHz:

        jitter SNR = -20*log10(2*pi*20000*1.0000005e-09) = 78.0155 dB

    Every other term is more than 40 dB quieter, so the jitter term must carry
    essentially all of the noise power.
    """
    budget = broadband_noise_budget(
        test_frequency_hz=20_000.0,
        front_end_noise_density_v_per_rthz=1e-9,
        noise_bandwidth_hz=20_000.0,
        gain_db=0.0,
        full_scale_vrms=1.0,
        converter_thermal_snr_db=120.0,
        bits=24,
        clock_rms_jitter_s=1e-9,
        aperture_jitter_s=1e-12,
    )
    assert budget.limiter == JITTER
    assert budget.limiter_share > 0.999
    assert budget.combined_snr_db == pytest.approx(
        budget.contributions[JITTER], abs=0.01
    )
    assert budget.jitter_headroom_db < 0.0


def test_front_end_is_the_dominant_limiter() -> None:
    """A synthetic path whose only weakness is its analog front end.

    1 uV/rtHz over 20 kHz with 40 dB of gain into a 1 Vrms full scale:

        noise_in     = 1e-6 * 141.4213562373 = 1.4142135624e-04 Vrms
        noise_at_adc = 1.4142135624e-02 Vrms
        SNR          = 20*log10(1/1.4142135624e-02) = 36.9897000434 dB

    against a 24-bit converter, 120 dB thermal noise, and 1 ps of jitter at
    1 kHz (164 dB). The front end must dominate.
    """
    budget = broadband_noise_budget(
        test_frequency_hz=1_000.0,
        front_end_noise_density_v_per_rthz=1e-6,
        noise_bandwidth_hz=20_000.0,
        gain_db=40.0,
        full_scale_vrms=1.0,
        converter_thermal_snr_db=120.0,
        bits=24,
        clock_rms_jitter_s=1e-12,
        aperture_jitter_s=1e-13,
    )
    assert budget.limiter == FRONT_END
    assert budget.limiter_share > 0.999
    assert budget.contributions[FRONT_END] == pytest.approx(36.9897000434, abs=DB)
    assert budget.combined_snr_db == pytest.approx(36.9897000434, abs=0.01)
    assert budget.jitter_headroom_db > 0.0


def test_budget_reports_all_four_contributors_and_combines_them() -> None:
    budget = broadband_noise_budget(
        test_frequency_hz=1_000.0,
        front_end_noise_density_v_per_rthz=10e-9,
        noise_bandwidth_hz=20_000.0,
        gain_db=20.0,
        full_scale_vrms=1.0,
        converter_thermal_snr_db=110.0,
        bits=24,
        clock_rms_jitter_s=50e-12,
        aperture_jitter_s=5e-12,
    )
    assert set(budget.contributions) == set(CONTRIBUTORS)
    assert budget.combined_snr_db == pytest.approx(
        combine_snr_db(*(budget.contributions[name] for name in CONTRIBUTORS)),
        abs=1e-12,
    )
    assert budget.combined_snr_db < min(budget.contributions.values())
    assert 0.0 < budget.limiter_share <= 1.0
    assert budget.signal_reference == "converter_full_scale"


def test_clock_and_aperture_jitter_combine_in_quadrature() -> None:
    """50 ps clock jitter and 50 ps aperture jitter give 70.71 ps total."""
    budget = broadband_noise_budget(
        test_frequency_hz=1_000.0,
        front_end_noise_density_v_per_rthz=10e-9,
        noise_bandwidth_hz=20_000.0,
        gain_db=20.0,
        full_scale_vrms=1.0,
        converter_thermal_snr_db=110.0,
        bits=24,
        clock_rms_jitter_s=50e-12,
        aperture_jitter_s=50e-12,
    )
    assert budget.total_jitter_s == pytest.approx(math.sqrt(2.0) * 50e-12, rel=1e-12)


def test_limiter_ties_break_deterministically() -> None:
    """Equal contributors must not produce an order-dependent limiter."""
    tied = dict.fromkeys(CONTRIBUTORS, 100.0)
    limiter, share = dominant_limiter(tied)
    assert limiter == CONTRIBUTORS[0]
    assert share == pytest.approx(0.25, abs=1e-12)


def test_budget_refuses_to_invent_missing_inputs() -> None:
    """A budget computed from a default would be a fabricated result."""
    with pytest.raises(TypeError):
        broadband_noise_budget(  # type: ignore[call-arg]
            test_frequency_hz=1_000.0,
            front_end_noise_density_v_per_rthz=10e-9,
            noise_bandwidth_hz=20_000.0,
            gain_db=20.0,
            full_scale_vrms=1.0,
            converter_thermal_snr_db=110.0,
            bits=24,
        )


def test_budget_serializes_with_contributors_in_fixed_order() -> None:
    budget = broadband_noise_budget(
        test_frequency_hz=1_000.0,
        front_end_noise_density_v_per_rthz=10e-9,
        noise_bandwidth_hz=20_000.0,
        gain_db=20.0,
        full_scale_vrms=1.0,
        converter_thermal_snr_db=110.0,
        bits=24,
        clock_rms_jitter_s=50e-12,
        aperture_jitter_s=5e-12,
    )
    payload = budget.as_dict()
    assert list(payload["contributions"]) == list(CONTRIBUTORS)
    assert payload["signal_reference"] == "converter_full_scale"
