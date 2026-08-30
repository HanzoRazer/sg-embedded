"""T01-T09: provenance vocabulary, quantity validation, and unknowns.

These tests exist to make one property hard to lose: a number and the evidence
behind it are a single engineering fact, and no path through the system turns
a suggestion into evidence or an unknown into a default.
"""

import math
from dataclasses import FrozenInstanceError

import pytest

from acquisition.models import ClockSpec, ConverterSpec
from acquisition.provenance import (
    Provenance,
    Quantity,
    canonical_json,
    is_traceable,
    provenance_of,
    require_unit,
    value_of,
)

# ---------------------------------------------------------------------------
# T01 - provenance vocabulary is exact
# ---------------------------------------------------------------------------


def test_t01_provenance_vocabulary_is_exactly_five_members() -> None:
    """No accidental aliases, no spare members, no renamed values.

    The serialized values are an evidence-record format. A sixth member or a
    changed string would silently reinterpret every record already written.
    """
    assert [member.value for member in Provenance] == [
        "proposed",
        "assumed",
        "datasheet",
        "derived",
        "measured",
    ]
    assert len(Provenance) == 5


def test_t01_provenance_names_match_their_values() -> None:
    for member in Provenance:
        assert member.name.lower() == member.value


# ---------------------------------------------------------------------------
# T02 - a finite quantity is accepted intact
# ---------------------------------------------------------------------------


def test_t02_finite_quantity_is_accepted_and_preserved() -> None:
    quantity = Quantity(
        value=50.0,
        unit="ps",
        provenance=Provenance.MEASURED,
        source="bench test",
        evidence_ref="EVT-CLK-001",
    )
    assert quantity.value == 50.0
    assert quantity.unit == "ps"
    assert quantity.provenance is Provenance.MEASURED
    assert quantity.source == "bench test"
    assert quantity.evidence_ref == "EVT-CLK-001"


def test_t02_optional_fields_default_without_inventing_evidence() -> None:
    quantity = Quantity(20.0, "dB", Provenance.PROPOSED)
    assert quantity.source == ""
    assert quantity.evidence_ref is None
    assert is_traceable(quantity) is False


def test_t02_integer_values_are_normalised_to_float() -> None:
    assert Quantity(24, "bit", Provenance.DATASHEET, source="x").value == 24.0


# ---------------------------------------------------------------------------
# T03 / T04 / T05 - non-finite values are rejected
# ---------------------------------------------------------------------------


def test_t03_nan_rejected() -> None:
    """NaN entering a calculation would propagate silently into a result."""
    with pytest.raises(ValueError, match="must not be NaN"):
        Quantity(math.nan, "s", Provenance.MEASURED, evidence_ref="EVT-1")
    with pytest.raises(ValueError, match="must not be NaN"):
        Quantity(float("nan"), "dB", Provenance.DATASHEET, source="x")


def test_t04_positive_infinity_rejected() -> None:
    with pytest.raises(ValueError, match="must not be infinite"):
        Quantity(math.inf, "s", Provenance.MEASURED, evidence_ref="EVT-1")
    with pytest.raises(ValueError, match="must not be infinite"):
        Quantity(float("inf"), "s", Provenance.MEASURED, evidence_ref="EVT-1")


def test_t05_negative_infinity_rejected() -> None:
    with pytest.raises(ValueError, match="must not be infinite"):
        Quantity(-math.inf, "s", Provenance.MEASURED, evidence_ref="EVT-1")
    with pytest.raises(ValueError, match="must not be infinite"):
        Quantity(float("-inf"), "s", Provenance.MEASURED, evidence_ref="EVT-1")


def test_field_types_are_enforced() -> None:
    with pytest.raises(TypeError, match="must be a real number"):
        Quantity("50", "s", Provenance.MEASURED)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must be a string"):
        Quantity(50.0, 5, Provenance.MEASURED)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must be a string"):
        Quantity(50.0, "s", Provenance.MEASURED, source=None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="bare strings are not promoted"):
        Quantity(50.0, "s", "measured")  # type: ignore[arg-type]


def test_unit_must_not_be_blank() -> None:
    with pytest.raises(ValueError, match="unit must be"):
        Quantity(50.0, "", Provenance.MEASURED, evidence_ref="EVT-1")
    with pytest.raises(ValueError, match="unit must be"):
        Quantity(50.0, "   ", Provenance.MEASURED, evidence_ref="EVT-1")


def test_no_auto_promotion_of_a_bare_float() -> None:
    """No constructor turns a number into evidence by itself."""
    with pytest.raises(TypeError):
        Quantity(50.0)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        Quantity(50.0, "s")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# T06 - a measured evidence reference survives intact
# ---------------------------------------------------------------------------


def test_t06_measured_evidence_reference_survives_serialization() -> None:
    """The reference must still be attached after the record is written out.

    This is the property that makes an evidence trail usable: a number
    arriving at a later report must still be able to name the artifact that
    produced it.

    Note the unit. A Quantity may legitimately hold 50 ps; it records the unit
    it was given and converts nothing. Whether a particular model field will
    accept picoseconds is a separate question, settled at the model boundary.
    """
    quantity = Quantity(
        value=50.0,
        unit="ps",
        provenance=Provenance.MEASURED,
        source="bench test",
        evidence_ref="EVT-CLK-001",
    )
    assert quantity.as_dict() == {
        "value": 50.0,
        "unit": "ps",
        "provenance": "measured",
        "source": "bench test",
        "evidence_ref": "EVT-CLK-001",
    }
    assert "EVT-CLK-001" in canonical_json(quantity.as_dict())
    assert "EVT-CLK-001" in str(quantity)


def test_t06_empty_evidence_ref_is_rejected_rather_than_stored() -> None:
    """An empty string would read as "referenced" while referencing nothing."""
    with pytest.raises(ValueError, match="never an empty string"):
        Quantity(50.0, "ps", Provenance.MEASURED, evidence_ref="")


def test_t06_traceability_requires_something_to_follow() -> None:
    """An authoritative class alone does not make a quantity traceable.

    A measurement with no evidence reference is an anecdote, and a datasheet
    claim with no stated source cannot be checked against the datasheet.
    """
    assert is_traceable(Quantity(50.0, "ps", Provenance.MEASURED)) is False
    assert is_traceable(Quantity(1e6, "ohm", Provenance.DATASHEET)) is False
    assert (
        is_traceable(
            Quantity(50.0, "ps", Provenance.MEASURED, evidence_ref="EVT-CLK-001")
        )
        is True
    )
    assert (
        is_traceable(Quantity(1e6, "ohm", Provenance.DATASHEET, source="ACME rev B"))
        is True
    )


# ---------------------------------------------------------------------------
# T07 - deterministic serialization
# ---------------------------------------------------------------------------


def test_t07_equal_quantities_serialize_identically() -> None:
    first = Quantity(50.0, "ps", Provenance.MEASURED, "bench", "EVT-CLK-001")
    second = Quantity(50.0, "ps", Provenance.MEASURED, "bench", "EVT-CLK-001")
    assert first == second
    assert first.as_dict() == second.as_dict()
    assert canonical_json(first.as_dict()) == canonical_json(second.as_dict())


def test_t07_key_set_is_stable_whether_or_not_evidence_exists() -> None:
    """Measured and unmeasured records must have the same shape.

    Omitting a key on falsiness would let structural drift creep between the
    two, which is what makes an evidence trail unreadable later.
    """
    measured = Quantity(50.0, "ps", Provenance.MEASURED, "bench", "EVT-CLK-001")
    proposed = Quantity(50.0, "ps", Provenance.PROPOSED)
    assert measured.as_dict().keys() == proposed.as_dict().keys()
    assert proposed.as_dict()["evidence_ref"] is None
    assert '"evidence_ref":null' in canonical_json(proposed.as_dict())


def test_t07_serialization_emits_the_enum_value_not_its_repr() -> None:
    payload = Quantity(50.0, "ps", Provenance.ASSUMED).as_dict()
    assert payload["provenance"] == "assumed"


# ---------------------------------------------------------------------------
# T08 - assumed and proposed remain distinguishable
# ---------------------------------------------------------------------------


def test_t08_assumed_and_proposed_are_never_collapsed() -> None:
    """Two different engineering statements, and they must stay different.

    "We suggest 50 ps" and "we are assuming 50 ps to proceed" carry different
    weight and different follow-up actions. No helper may flatten them into a
    single "unverified" representation.
    """
    proposed = Quantity(50.0, "ps", Provenance.PROPOSED)
    assumed = Quantity(50.0, "ps", Provenance.ASSUMED)

    assert proposed.provenance is not assumed.provenance
    assert proposed != assumed
    assert proposed.as_dict()["provenance"] == "proposed"
    assert assumed.as_dict()["provenance"] == "assumed"
    assert canonical_json(proposed.as_dict()) != canonical_json(assumed.as_dict())


def test_t08_neither_is_authoritative_but_both_keep_their_identity() -> None:
    assert Provenance.PROPOSED.is_authoritative is False
    assert Provenance.ASSUMED.is_authoritative is False
    assert Provenance.DATASHEET.is_authoritative is True
    assert Provenance.DERIVED.is_authoritative is True
    assert Provenance.MEASURED.is_authoritative is True


# ---------------------------------------------------------------------------
# T09 - unknown remains structurally None
# ---------------------------------------------------------------------------


def test_t09_missing_quantity_stays_none_on_a_spec() -> None:
    """No default engineering value may appear in place of an unknown."""
    clock = ClockSpec(name="undescribed clock")
    assert clock.rms_jitter_s is None
    assert clock.accuracy_ppm is None
    assert clock.quantities() == {"rms_jitter_s": None, "accuracy_ppm": None}


def test_t09_unknown_serializes_as_explicit_null_not_zero() -> None:
    """An unknown must serialize as null, never as a substituted zero.

    Checked per declared quantity rather than by scanning every value in the
    payload: a spec may legitimately carry a categorical field whose value is
    False, and ``False == 0`` in Python would make a blanket scan report a
    violation that is not one.
    """
    spec = ConverterSpec(name="undescribed ADC")
    payload = spec.as_dict()
    for name in spec.quantities():
        assert payload[name] is None, f"{name} did not serialize as null"
    assert "null" in canonical_json(payload)
    assert 0.0 not in [payload[name] for name in spec.quantities()]


def test_t09_unwrapping_preserves_the_unknown() -> None:
    """value_of(None) is None, not 0.0. The distinction is the whole point."""
    assert value_of(None) is None
    assert provenance_of(None) is None
    assert is_traceable(None) is False

    known = Quantity(50.0, "ps", Provenance.MEASURED, evidence_ref="EVT-CLK-001")
    assert value_of(known) == 50.0
    assert provenance_of(known) is Provenance.MEASURED


def test_t09_partial_knowledge_does_not_fill_in_the_rest() -> None:
    clock = ClockSpec(
        name="half-described clock",
        rms_jitter_s=Quantity(50e-12, "s", Provenance.DATASHEET, source="XO rev A"),
    )
    assert clock.rms_jitter_s is not None
    assert clock.accuracy_ppm is None


# ---------------------------------------------------------------------------
# Immutability and unit discipline
# ---------------------------------------------------------------------------


def test_quantity_is_immutable() -> None:
    """Evidence must not be edited in place after it is stated."""
    quantity = Quantity(50.0, "ps", Provenance.MEASURED, evidence_ref="EVT-CLK-001")
    with pytest.raises(FrozenInstanceError):
        quantity.value = 1.0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        quantity.evidence_ref = "EVT-OTHER"  # type: ignore[misc]


def test_require_unit_rejects_rather_than_converts() -> None:
    """A wrong unit is an error, never something to rescale silently."""
    picoseconds = Quantity(50.0, "ps", Provenance.MEASURED, evidence_ref="EVT-CLK-001")
    with pytest.raises(ValueError, match="must be expressed in 's'"):
        require_unit(picoseconds, "s", "rms_jitter_s")

    seconds = Quantity(50e-12, "s", Provenance.MEASURED, evidence_ref="EVT-CLK-001")
    require_unit(seconds, "s", "rms_jitter_s")
    require_unit(None, "s", "rms_jitter_s")
    assert seconds.value == 50e-12
