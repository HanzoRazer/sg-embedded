"""STAGED FOR 001B: clock topology qualification.

Not part of the 001A gate.

The clock dimension answers two separable questions: is enough known about the
clock, and does what is known raise a concern an RMS jitter figure cannot
settle? Evidence grade is reported alongside, not folded in.
"""

import pytest

from acquisition.clock import (
    ClockTopology,
    clock_topology_note,
    evaluate_clock,
    requires_spur_analysis,
)
from acquisition.models import ClockSpec, QualificationState
from acquisition.provenance import Provenance

from .conftest import assumed, datasheet, measured, proposed

# ---------------------------------------------------------------------------
# T20 - an adequately evidenced local oscillator may qualify
# ---------------------------------------------------------------------------


def test_t20_evidenced_local_xo_passes() -> None:
    clock = ClockSpec(
        name="local audio XO",
        rms_jitter_s=measured(50e-12, "s", evidence_ref="EVT-AUDIO-CLK-0042"),
        accuracy_ppm=datasheet(20.0, "ppm"),
        topology=ClockTopology.LOCAL_XO,
        spurious=False,
    )
    evaluation = evaluate_clock(clock)

    assert evaluation.state is QualificationState.PASS
    assert evaluation.spur_analysis_required is False
    assert evaluation.jitter_provenance is Provenance.MEASURED
    assert evaluation.blockers == ()


def test_t20_local_xo_passes_the_dimension_even_on_a_proposed_jitter_figure() -> None:
    """Engineering adequacy and evidence grade are separate axes.

    A proposed jitter figure is not an engineering concern in itself -- the
    number may be entirely reasonable -- but it can never support an
    evidence-grade disposition. The dimension reports the concern (none) and
    the blocker (one) separately, and the qualification layer applies the
    evidence gate. Folding them together here would either hide real concerns
    or manufacture false ones.
    """
    clock = ClockSpec(
        name="proposed local XO",
        rms_jitter_s=proposed(50e-12, "s"),
        accuracy_ppm=assumed(20.0, "ppm"),
        topology=ClockTopology.LOCAL_XO,
    )
    evaluation = evaluate_clock(clock)

    assert evaluation.state is QualificationState.PASS
    assert evaluation.jitter_provenance is Provenance.PROPOSED
    assert evaluation.blockers == (
        "clock.rms_jitter_s is PROPOSED",
        "clock.accuracy_ppm is ASSUMED",
    )


def test_t20_local_xo_without_a_jitter_figure_is_unvalidated() -> None:
    """Being the preferred topology does not substitute for knowing anything."""
    clock = ClockSpec(
        name="undescribed local XO",
        rms_jitter_s=None,
        topology=ClockTopology.LOCAL_XO,
    )
    evaluation = evaluate_clock(clock)

    assert evaluation.state is QualificationState.UNVALIDATED
    assert evaluation.jitter_provenance is None
    assert any("No RMS jitter figure" in note for note in evaluation.notes)


# ---------------------------------------------------------------------------
# T21 - fractional-N without measured spur evidence
# ---------------------------------------------------------------------------


def test_t21_fractional_n_without_spur_evidence_requires_review() -> None:
    """RMS jitter cannot describe discrete spurious content.

    The clock may well be fine. The point is that the available evidence
    cannot establish it, and the honest disposition for that is a review, not
    a pass and not a failure.
    """
    clock = ClockSpec(
        name="Pi I2S master",
        rms_jitter_s=datasheet(200e-12, "s", source="SoC datasheet rev 1"),
        topology=ClockTopology.HOST_FRACTIONAL_N,
        spurious=True,
    )
    evaluation = evaluate_clock(clock, has_measured_spur_evidence=False)

    assert evaluation.state is QualificationState.REVIEW_REQUIRED
    assert evaluation.spur_analysis_required is True
    assert any("spur evidence" in note for note in evaluation.notes)


def test_t21_fractional_n_with_measured_spur_evidence_may_pass() -> None:
    """Pi-master I2S must not be rejected from assumption either.

    Given measured in-band spur evidence, the topology carries no unresolved
    concern of its own and the spectral dimension holds the verdict.
    """
    clock = ClockSpec(
        name="Pi I2S master",
        rms_jitter_s=measured(200e-12, "s", evidence_ref="EVT-AUDIO-CLK-0101"),
        topology=ClockTopology.HOST_FRACTIONAL_N,
        spurious=True,
    )
    evaluation = evaluate_clock(clock, has_measured_spur_evidence=True)

    assert evaluation.state is QualificationState.PASS
    assert evaluation.spur_analysis_required is True
    assert evaluation.has_measured_spur_evidence is True


def test_t21_fractional_n_declared_non_spurious_still_requires_evidence() -> None:
    """Deliberately stricter than the dev order's literal rule.

    A fractional-N clock declared ``spurious=False`` is making a claim about
    discrete spectral content that an RMS jitter figure cannot support.
    Accepting the declaration unmeasured would let an assumption qualify
    hardware, which is the failure mode this repository exists to prevent.
    Flagged for the Tranche 1 review gate.
    """
    clock = ClockSpec(
        name="Pi I2S master, declared clean",
        rms_jitter_s=datasheet(200e-12, "s", source="SoC datasheet rev 1"),
        topology=ClockTopology.HOST_FRACTIONAL_N,
        spurious=False,
    )
    assert requires_spur_analysis(ClockTopology.HOST_FRACTIONAL_N, False) is True
    assert evaluate_clock(clock).state is QualificationState.REVIEW_REQUIRED


def test_any_topology_declared_spurious_requires_spur_analysis() -> None:
    for topology in ClockTopology:
        assert requires_spur_analysis(topology, True) is True


def test_local_xo_and_cleanup_pll_do_not_require_spur_analysis_by_default() -> None:
    assert requires_spur_analysis(ClockTopology.LOCAL_XO, False) is False
    assert requires_spur_analysis(ClockTopology.CLEANUP_PLL, False) is False


# ---------------------------------------------------------------------------
# T22 - unknown topology
# ---------------------------------------------------------------------------


def test_t22_unknown_topology_is_unvalidated() -> None:
    """An unknown topology means the dominant failure mode is unidentified."""
    clock = ClockSpec(
        name="unspecified clock",
        rms_jitter_s=measured(50e-12, "s", evidence_ref="EVT-AUDIO-CLK-0007"),
        accuracy_ppm=datasheet(20.0, "ppm"),
        topology=ClockTopology.UNKNOWN,
        spurious=False,
    )
    evaluation = evaluate_clock(clock)

    assert evaluation.state is QualificationState.UNVALIDATED
    assert evaluation.blockers == ()
    assert any("UNKNOWN" in note for note in evaluation.notes)


def test_t22_unknown_topology_defaults_when_unspecified() -> None:
    """The default must be UNKNOWN, never a convenient assumption."""
    assert ClockSpec(name="bare clock").topology is ClockTopology.UNKNOWN


def test_unknown_and_spurious_surfaces_the_review_not_just_the_unknown() -> None:
    """Disposition precedence: REVIEW_REQUIRED outranks UNVALIDATED.

    A clock that is both undescribed and known to be spurious must not lose
    the spur concern behind the unknown topology.
    """
    clock = ClockSpec(
        name="unknown spurious clock",
        rms_jitter_s=datasheet(200e-12, "s", source="vendor note"),
        topology=ClockTopology.UNKNOWN,
        spurious=True,
    )
    assert evaluate_clock(clock).state is QualificationState.REVIEW_REQUIRED


# ---------------------------------------------------------------------------
# Topology notes and serialization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology", list(ClockTopology))
def test_every_topology_has_an_engineering_note(topology: ClockTopology) -> None:
    note = clock_topology_note(topology)
    assert note.strip()
    assert len(note) > 40


def test_evaluation_serializes_deterministically() -> None:
    clock = ClockSpec(
        name="local audio XO",
        rms_jitter_s=measured(50e-12, "s", evidence_ref="EVT-AUDIO-CLK-0042"),
        topology=ClockTopology.LOCAL_XO,
    )
    payload = evaluate_clock(clock).as_dict()

    assert payload["topology"] == "local_xo"
    assert payload["state"] == "pass"
    assert payload["jitter_provenance"] == "measured"
    assert payload["rms_jitter_s"]["evidence_ref"] == "EVT-AUDIO-CLK-0042"


def test_negative_jitter_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        ClockSpec(
            name="impossible clock",
            rms_jitter_s=measured(-1e-12, "s"),
            topology=ClockTopology.LOCAL_XO,
        )
