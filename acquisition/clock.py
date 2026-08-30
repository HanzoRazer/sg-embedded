"""Audio clock topology and clock qualification.

STAGED FOR 001B. Not part of the 001A gate.

The clock is modelled as a topology plus its evidence, not as a single jitter
number. A fractional-N synthesiser and a local crystal oscillator can quote the
same RMS jitter and behave completely differently in the audio band, because
RMS jitter is a Gaussian summary and fractional-N misbehaviour is discrete.
Collapsing the two into one figure would hide exactly the risk this dimension
exists to surface.

Jitter is not latency. This module reasons about variation in sample timing and
its effect on fidelity. Elapsed time through the acquisition path is a separate
concern with separate evidence, and the two must never be folded into one
metric.
"""

from dataclasses import dataclass
from typing import Any, Final

from .models import ClockSpec, ClockTopology, QualificationState, worst_state
from .provenance import Provenance, Quantity, blocker_for

__all__ = [
    "ClockEvaluation",
    "ClockTopology",
    "clock_topology_note",
    "evaluate_clock",
    "requires_spur_analysis",
]

_TOPOLOGY_NOTES: Final[dict[ClockTopology, str]] = {
    ClockTopology.LOCAL_XO: (
        "Local audio-grade oscillator with the codec as clock master. Jitter is "
        "dominated by the oscillator itself and is reasonably described by an "
        "RMS figure. This is a design hypothesis for the Smart Guitar, not a "
        "proven production requirement."
    ),
    ClockTopology.HOST_FRACTIONAL_N: (
        "Host-synthesised clock (for example Raspberry Pi I2S master). "
        "Fractional-N synthesis produces discrete spurious content that RMS "
        "jitter does not describe. This topology must not be rejected from "
        "assumption, but it cannot be qualified on an RMS figure alone: it "
        "requires measured spur evidence in the audio band."
    ),
    ClockTopology.CLEANUP_PLL: (
        "Upstream clock re-timed by a jitter-attenuating PLL. Qualification "
        "depends on the PLL loop bandwidth relative to the upstream noise "
        "spectrum; a cleanup PLL narrows but does not automatically eliminate "
        "inherited spurious content."
    ),
    ClockTopology.EXTERNAL_AUDIO_CLOCK: (
        "Clock supplied from outside the acquisition assembly. Its integrity is "
        "a property of equipment this profile does not describe, so evidence "
        "must accompany the external source."
    ),
    ClockTopology.UNKNOWN: (
        "Clock topology has not been established. An unknown topology is not a "
        "neutral condition: it means the dominant failure mode of the clock is "
        "unidentified."
    ),
}


def clock_topology_note(topology: ClockTopology) -> str:
    """Engineering note explaining what a topology implies for qualification."""
    return _TOPOLOGY_NOTES[topology]


def requires_spur_analysis(topology: ClockTopology, spurious: bool) -> bool:
    """Whether this clock needs measured spur evidence to be qualified.

    True when the clock is declared spurious, and true for
    ``HOST_FRACTIONAL_N`` regardless of the declaration.

    The dev order requires ``REVIEW_REQUIRED`` for fractional-N declared
    ``spurious=True`` with no measured evidence. This implementation is
    deliberately one step stricter: a fractional-N clock declared
    ``spurious=False`` is making a claim about discrete spectral content that an
    RMS jitter figure cannot support, and accepting that claim unmeasured would
    let an assumption qualify hardware. The stricter reading is flagged for
    review at the Tranche 1 gate.
    """
    return spurious or topology is ClockTopology.HOST_FRACTIONAL_N


@dataclass(frozen=True)
class ClockEvaluation:
    """The clock dimension's contribution to acquisition qualification.

    ``state`` reports engineering adequacy: is enough known about this clock,
    and does what is known raise a concern? It is deliberately separate from
    evidence grade, which is reported through ``jitter_provenance`` and
    ``blockers`` and applied by the qualification layer. A clock whose jitter
    figure is merely ``PROPOSED`` is not an engineering concern in itself -- the
    number may be perfectly reasonable -- but it can never support an
    evidence-grade disposition, and conflating the two would either hide real
    concerns or manufacture false ones.
    """

    topology: ClockTopology
    state: QualificationState
    rms_jitter_s: Quantity | None
    accuracy_ppm: Quantity | None
    spur_analysis_required: bool
    has_measured_spur_evidence: bool
    jitter_provenance: Provenance | None
    notes: tuple[str, ...]
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "topology": self.topology.value,
            "state": self.state.value,
            "rms_jitter_s": (
                None if self.rms_jitter_s is None else self.rms_jitter_s.as_dict()
            ),
            "accuracy_ppm": (
                None if self.accuracy_ppm is None else self.accuracy_ppm.as_dict()
            ),
            "spur_analysis_required": self.spur_analysis_required,
            "has_measured_spur_evidence": self.has_measured_spur_evidence,
            "jitter_provenance": (
                None if self.jitter_provenance is None else self.jitter_provenance.value
            ),
            "notes": list(self.notes),
            "blockers": list(self.blockers),
        }


def evaluate_clock(
    clock: ClockSpec, *, has_measured_spur_evidence: bool = False
) -> ClockEvaluation:
    """Evaluate the clock dimension of a Smart Guitar acquisition path.

    Rules
    -----
    * ``UNKNOWN`` topology yields ``UNVALIDATED``.
    * A missing RMS jitter figure yields ``UNVALIDATED``.
    * A clock needing spur analysis with no measured spur evidence yields
      ``REVIEW_REQUIRED``.
    * Otherwise ``PASS``: the clock is adequately described and raises no
      concern that this dimension can settle on its own.

    Where more than one rule fires, the governing disposition follows the
    standard precedence, so an unknown-topology clock that is also declared
    spurious surfaces as ``REVIEW_REQUIRED`` rather than losing the spur
    concern behind the unknown.

    ``has_measured_spur_evidence`` is supplied by the caller because the
    evidence itself lives in the spectral dimension. The clock dimension
    decides whether that evidence is *required*; it does not hold it.
    """
    states: list[QualificationState] = []
    notes: list[str] = [clock_topology_note(clock.topology)]

    if clock.topology is ClockTopology.UNKNOWN:
        states.append(QualificationState.UNVALIDATED)
        notes.append("Clock topology is UNKNOWN; the clock cannot be qualified.")

    if clock.rms_jitter_s is None:
        states.append(QualificationState.UNVALIDATED)
        notes.append("No RMS jitter figure is declared for this clock.")

    spur_required = requires_spur_analysis(clock.topology, clock.spurious)
    if spur_required and not has_measured_spur_evidence:
        states.append(QualificationState.REVIEW_REQUIRED)
        notes.append(
            "This clock requires measured in-band spur evidence, which is not "
            "available. RMS jitter alone cannot describe discrete spurious "
            "content, so an engineering review is required."
        )
    elif spur_required:
        notes.append(
            "Spur analysis is required for this topology and measured spur "
            "evidence is available; the spectral dimension carries the verdict."
        )

    if not states:
        states.append(QualificationState.PASS)

    blockers = tuple(
        blocker
        for blocker in (
            blocker_for("clock.rms_jitter_s", clock.rms_jitter_s),
            blocker_for("clock.accuracy_ppm", clock.accuracy_ppm),
        )
        if blocker is not None
    )

    return ClockEvaluation(
        topology=clock.topology,
        state=worst_state(states),
        rms_jitter_s=clock.rms_jitter_s,
        accuracy_ppm=clock.accuracy_ppm,
        spur_analysis_required=spur_required,
        has_measured_spur_evidence=has_measured_spur_evidence,
        jitter_provenance=(
            None if clock.rms_jitter_s is None else clock.rms_jitter_s.provenance
        ),
        notes=tuple(notes),
        blockers=blockers,
    )
