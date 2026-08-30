"""Smart Guitar Audio Acquisition Qualification (SGAQ).

A native ``sg-embedded`` subsystem. At this tranche it is a provenance model
and a mathematical kernel, not yet a qualifier: it can say what a jitter
figure implies and where a number came from, but it cannot yet say whether any
hardware is fit to use.

SGAQ is a design-time, qualification-time, diagnostic and manufacturing
subsystem. Nothing here belongs in an audio callback, in sample processing, in
transport timing, in lesson control, or in fretboard rendering.

Native implementation, carrying no implementation or semantic dependency on
any other analysis codebase.

Modules
-------
:mod:`acquisition.provenance`
    Provenance classification and the evidence-bearing ``Quantity``.
:mod:`acquisition.models`
    Minimal front-end, converter and clock specs.
:mod:`acquisition.noise`
    Jitter, quantization and noise-combination mathematics.

Only the foundation types are re-exported here. The mathematical helpers are
imported from :mod:`acquisition.noise` directly, so that this tranche does not
prematurely declare them permanent public API.
"""

from .models import ClockSpec, ConverterSpec, FrontEndSpec
from .provenance import Provenance, Quantity

__all__ = [
    "ClockSpec",
    "ConverterSpec",
    "FrontEndSpec",
    "Provenance",
    "Quantity",
]
