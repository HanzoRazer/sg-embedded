"""Provenance-bearing engineering quantities.

The epistemic foundation of SGAQ. Every load-bearing engineering value in this
subsystem is a :class:`Quantity` or ``None``, never a bare ``float`` paired
with a side-channel provenance dictionary.

Governing decisions
-------------------
D-02
    Provenance travels with the number. A value and the evidence supporting it
    constitute one engineering fact, and they must not be able to drift
    independently.
D-03
    ``None`` means *no trustworthy engineering value is currently available*.
    It never means zero, typical, nominal, or ignored. Nothing in this module
    substitutes a default for an unknown.

This module classifies evidence. It does not decide qualification. A whole
profile's evidence grade is a decision-layer question and is deliberately not
answered here.
"""

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

__all__ = [
    "AUTHORITATIVE_PROVENANCE",
    "NON_AUTHORITATIVE_PROVENANCE",
    "Provenance",
    "Quantity",
    "blocker_for",
    "canonical_json",
    "collect_blockers",
    "is_traceable",
    "provenance_of",
    "require_unit",
    "value_of",
]


class Provenance(StrEnum):
    """Where an engineering quantity came from.

    Listed in order of increasing authority, though authority is deliberately
    not exposed as a comparison operator: a ``DERIVED`` value is not "better
    than" a ``DATASHEET`` value in any way arithmetic should exploit.
    """

    PROPOSED = "proposed"
    """An engineering suggestion. Carries no evidential weight whatsoever."""

    ASSUMED = "assumed"
    """A working assumption adopted to make analysis possible. Not evidence."""

    DATASHEET = "datasheet"
    """A manufacturer claim. Authoritative subject to source validity."""

    DERIVED = "derived"
    """Computed from other quantities. Authoritative if its inputs are."""

    MEASURED = "measured"
    """Observed on real hardware. Authoritative subject to evidence."""

    @property
    def is_authoritative(self) -> bool:
        """Whether this class of provenance can carry evidential weight.

        Intrinsic to the classification only. ``PROPOSED`` and ``ASSUMED``
        never can; the other three can, each subject to the condition named in
        its own docstring. This property answers "what kind of claim is this?"
        and nothing more.

        It must not be used on its own to decide whether hardware qualifies.
        That decision depends on traceability, on which fields are populated,
        and on requirements this module knows nothing about, and it belongs to
        the later decision layer.
        """
        return self in AUTHORITATIVE_PROVENANCE


AUTHORITATIVE_PROVENANCE: Final[frozenset[Provenance]] = frozenset(
    {Provenance.DATASHEET, Provenance.DERIVED, Provenance.MEASURED}
)
"""Provenance classes that can carry evidential weight."""

NON_AUTHORITATIVE_PROVENANCE: Final[frozenset[Provenance]] = frozenset(
    {Provenance.PROPOSED, Provenance.ASSUMED}
)
"""Provenance classes that never can.

Grouped for convenience only. ``PROPOSED`` and ``ASSUMED`` remain distinct
engineering statements and no helper here collapses them into a single
"unverified" representation.
"""


def _finite_float(value: object, field: str) -> float:
    """Coerce ``value`` to a finite float, or raise.

    Accepts ``object`` rather than ``float`` so the runtime guards stay
    reachable under ``mypy --strict`` with ``warn_unreachable``.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be a real number, got {type(value).__name__!r}")
    coerced = float(value)
    if math.isnan(coerced):
        raise ValueError(f"{field} must not be NaN")
    if math.isinf(coerced):
        raise ValueError(f"{field} must not be infinite")
    return coerced


def _require_provenance(value: object) -> Provenance:
    if not isinstance(value, Provenance):
        raise TypeError(
            "provenance must be a Provenance member, got "
            f"{type(value).__name__!r}; bare strings are not promoted"
        )
    return value


def _require_str(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string, got {type(value).__name__!r}")
    return value


@dataclass(frozen=True)
class Quantity:
    """A number that knows where it came from.

    Parameters
    ----------
    value:
        The magnitude. Must be finite: NaN and infinity are rejected at
        construction so no unusable number can enter a calculation and
        silently poison a result.
    unit:
        The unit the magnitude is expressed in, as a bare string. A
        :class:`Quantity` may legitimately hold ``50`` with unit ``"ps"``; it
        records what it was given and converts nothing. Whether a particular
        model field will accept that unit is a separate question, answered at
        the model boundary by :func:`require_unit`.
    provenance:
        How the value was obtained. See :class:`Provenance`.
    source:
        Free text identifying the origin: a datasheet part number and
        revision, a derivation reference, a bench log.
    evidence_ref:
        A traceable evidence artifact identifier, for example
        ``"EVT-CLK-001"``, or ``None``.

    This class performs no unit conversion and is not a dimensional-analysis
    framework. It carries a number, its unit as stated, and its evidence.
    """

    value: float
    unit: str
    provenance: Provenance
    source: str = ""
    evidence_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _finite_float(self.value, "value"))
        object.__setattr__(self, "provenance", _require_provenance(self.provenance))
        object.__setattr__(self, "unit", _require_str(self.unit, "unit"))
        object.__setattr__(self, "source", _require_str(self.source, "source"))
        if not self.unit.strip():
            raise ValueError("unit must be a non-empty string")
        if self.evidence_ref is not None:
            _require_str(self.evidence_ref, "evidence_ref")
            if not self.evidence_ref.strip():
                raise ValueError(
                    "evidence_ref must be a non-empty string or None, "
                    "never an empty string"
                )

    @property
    def is_traceable(self) -> bool:
        """Whether this quantity can be followed back to its origin."""
        return is_traceable(self)

    def as_dict(self) -> dict[str, Any]:
        """Deterministic, JSON-ready representation.

        Every key is always emitted, including ``evidence_ref`` when it is
        ``None``. Omitting keys on falsiness would give measured and unmeasured
        records different shapes, and structural drift between them is exactly
        what makes an evidence trail unreadable later.

        Key order is fixed here and the enum is emitted as its value, so the
        result depends on neither dataclass field iteration order nor the JSON
        encoder's handling of ``str`` subclasses.
        """
        return {
            "value": self.value,
            "unit": self.unit,
            "provenance": self.provenance.value,
            "source": self.source,
            "evidence_ref": self.evidence_ref,
        }

    def __str__(self) -> str:
        tail = f" [{self.evidence_ref}]" if self.evidence_ref else ""
        return f"{self.value:g} {self.unit} ({self.provenance.value}){tail}"


def value_of(quantity: Quantity | None) -> float | None:
    """Unwrap the magnitude, preserving ``None`` for an unknown quantity.

    Deliberately explicit. Arithmetic on evidence-bearing values should look
    different from generic arithmetic at the call site, and an unknown must
    never acquire a default on its way into a calculation.
    """
    return None if quantity is None else quantity.value


def provenance_of(quantity: Quantity | None) -> Provenance | None:
    """Return the provenance of a quantity, or ``None`` if it is unknown."""
    return None if quantity is None else quantity.provenance


def is_traceable(quantity: Quantity | None) -> bool:
    """Whether ``quantity`` can be followed back to a stated origin.

    Traceability is a property of the individual quantity: an authoritative
    provenance class plus something to follow.

    * ``MEASURED`` requires an ``evidence_ref`` -- a measurement with nothing
      to trace it back to is an anecdote;
    * ``DATASHEET`` and ``DERIVED`` require a ``source``.

    This is intrinsic evidence quality, not a verdict. Whether a profile as a
    whole is evidence-grade depends on which fields matter, which are
    populated, and what the requirements demand, and is decided later.
    """
    if quantity is None:
        return False
    if not quantity.provenance.is_authoritative:
        return False
    if quantity.provenance is Provenance.MEASURED:
        return quantity.evidence_ref is not None
    return bool(quantity.source.strip())


def require_unit(quantity: Quantity | None, unit: str, field: str) -> None:
    """Raise if ``quantity`` is present but not expressed in ``unit``.

    Model boundaries declare a canonical SI unit per field and this compares
    against it. No conversion is performed or implied: a value in the wrong
    unit is rejected, never rescaled.

    The guard exists because the field name alone cannot enforce a unit, and
    the README's own worked example is precisely that trap -- ``50`` is a
    different engineering fact in ``ps`` than in ``s``.
    """
    if quantity is None:
        return
    if quantity.unit != unit:
        raise ValueError(
            f"{field} must be expressed in {unit!r}, got {quantity.unit!r}"
        )


def canonical_json(payload: Any) -> str:
    """Serialize ``payload`` deterministically.

    Sorted keys, no incidental whitespace, and ``allow_nan=False`` so a
    non-finite number raises rather than emitting non-standard JSON. Identical
    inputs always produce a byte-identical string.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# STAGED FOR 001B -- evidence blocker reporting (utility U-05).
#
# Not part of the 001A gate. These turn traceability into decision-support
# text, which is a qualification-layer concern rather than a property of a
# quantity.
# ---------------------------------------------------------------------------


def blocker_for(name: str, quantity: Quantity | None) -> str | None:
    """Return a human-readable evidence blocker for ``name``, or ``None``.

    The strings are stable enough to assert against and are the raw material a
    later report renders.
    """
    if quantity is None:
        return f"{name} is missing (no value declared)"
    if not quantity.provenance.is_authoritative:
        return f"{name} is {quantity.provenance.value.upper()}"
    if quantity.provenance is Provenance.MEASURED and quantity.evidence_ref is None:
        return f"{name} is MEASURED but has no evidence reference"
    if not quantity.source.strip():
        return (
            f"{name} is {quantity.provenance.value.upper()} "
            "but has no evidence source"
        )
    return None


def collect_blockers(fields: Mapping[str, Quantity | None]) -> tuple[str, ...]:
    """Evidence blockers for a mapping of field path to quantity.

    Order follows the mapping's own iteration order, which the model layer
    fixes explicitly, so the result is deterministic.
    """
    blockers = (blocker_for(name, q) for name, q in fields.items())
    return tuple(b for b in blockers if b is not None)
