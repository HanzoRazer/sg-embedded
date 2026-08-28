# sg-embedded
Smart Guitar Embedded Systems Authority repository
# sg-embedded

**Smart Guitar Embedded Systems Authority**

`sg-embedded` is the authoritative engineering repository for the
embedded electronics, hardware-control, audio-acquisition qualification,
and physical-runtime boundary of the **String Master Digi-Tec Guitar**
and **String Master Smart Guitar**.

The repository exists to answer one fundamental question:

> **Is the physical Smart Guitar platform trustworthy enough for the
> musical software to use?**

It does **not** own musical truth, curriculum, coaching, generative
harmony, or AI musical judgment. Those responsibilities remain with the
other repositories in the String Master ecosystem.

------------------------------------------------------------------------

## Status

**Bootstrap / pre-hardware-validation**

This repository establishes a new authority boundary. It is not a
declaration that the current Smart Guitar electronics are
production-qualified.

At bootstrap:

-   hardware values may be `PROPOSED`, `ASSUMED`, `DATASHEET`,
    `DERIVED`, or `MEASURED`;
-   proposed or assumed values must never be presented as measured
    evidence;
-   current board, clock, latency, noise, thermal, battery, and
    reliability claims remain unqualified until supported by evidence;
-   the first major subsystem is **Smart Guitar Audio Acquisition
    Qualification (SGAQ)**.

The repository must preserve the distinction between **design intent**
and **demonstrated hardware behavior**.

------------------------------------------------------------------------

# 1. Product Context

The String Master program contains two related instrument products.

## 1.1 String Master Digi-Tec Guitar

Digi-Tec is the lower-complexity product and should remain capable of
shipping without the full AI Smart Guitar stack.

Its embedded platform may include:

-   conventional guitar pickups and passive controls;
-   high-impedance audio input;
-   ADC/DAC or audio codec;
-   Raspberry Pi 5;
-   Master All Strings;
-   display;
-   Wi-Fi and Bluetooth;
-   battery power;
-   active cooling where required;
-   wired and other validated audio outputs.

Digi-Tec does **not** require Hailo, a local LLM, or a dedicated
real-time MCU merely to satisfy the architecture.

Commercial/off-the-shelf hardware may serve as the first reference
implementation.

## 1.2 String Master Smart Guitar

The Smart Guitar extends the Digi-Tec foundation with a stronger
embedded-control and intelligence architecture.

Expected responsibilities may include:

-   dedicated MCU/Teensy-class real-time control;
-   autonomous watchdog behavior;
-   fail-safe audio bypass;
-   thermal and fan authority;
-   power sequencing and battery telemetry;
-   hardware fault reporting;
-   dedicated AI acceleration;
-   local Musical Servant capabilities;
-   richer sensing and hardware telemetry.

The MCU is intended to provide **deterministic hardware authority**, not
musical intelligence.

The Pi hosts the musical application environment.

AI remains downstream of established hardware, performance, and musical
facts.

------------------------------------------------------------------------

# 2. Repository Authority

`sg-embedded` owns the engineering implementation and evidence
associated with the physical embedded platform.

Its authority includes:

## Audio acquisition

-   pickup loading and Hi-Z input requirements;
-   analog front-end behavior;
-   gain structure and headroom;
-   anti-alias filtering;
-   ADC/DAC and codec qualification;
-   audio clock topology;
-   jitter budgets;
-   clock-spur qualification;
-   noise budgets;
-   muted-input noise-floor testing;
-   acquisition-health evaluation;
-   hardware audio profiles.

## Embedded control

-   MCU responsibilities;
-   Pi-to-MCU communication;
-   heartbeat/watchdog behavior;
-   autonomous bypass;
-   control scanning;
-   hardware fault handling;
-   deterministic timing responsibilities assigned to the MCU.

## Power and thermal behavior

-   battery/BMS telemetry interfaces;
-   power-state reporting;
-   shutdown coordination;
-   power sequencing where implemented;
-   thermal sensing;
-   cooling/fan control;
-   thermal fault policy.

Battery-cell charging circuitry does not automatically belong on the
audio/controller PCB. Charging architecture must be treated as a
separate electrical design decision and qualified for safety, heat, and
noise.

## Hardware qualification

-   engineering profiles;
-   test fixtures;
-   EVT evidence;
-   DVT evidence;
-   production acceptance criteria;
-   boot/self-test behavior;
-   hardware revision traceability;
-   qualification artifacts.

------------------------------------------------------------------------

# 3. What This Repository Does Not Own

Authority boundaries are deliberate.

### Master All Strings

Master All Strings owns the musical application and lightweight
performance environment, including its Musical Core, educational
behavior, spatial mapping, scrolling fretboard, transport/capture
behavior, and Performance Engine.

`sg-embedded` may report hardware readiness to Master All Strings.

It does not decide musical meaning.

### sg-spec

`sg-spec` owns shared, portable contracts used across repositories.

Where embedded state must cross a repository boundary, the schema
belongs in `sg-spec`; the measurement and qualification implementation
belongs here.

Examples may include:

-   `AudioAcquisitionHealthV1`
-   embedded device status contracts;
-   versioned Pi/MCU messages where they become cross-system contracts.

### sg-agentd

`sg-agentd` owns service/orchestration behavior. It is not hardware
authority.

### sg-curriculum

`sg-curriculum` owns curricular structure and progression. It is not
hardware authority.

### sg-coach

`sg-coach` represents the coaching/evaluation lineage. It is not
electrical or embedded authority.

### sg-ai

`sg-ai` owns AI-layer implementation within its defined boundaries. AI
must not determine whether unsafe or unqualified hardware should be
trusted.

### string_master_v.4.0

The String Master musical-generation/theory system remains separate from
embedded hardware qualification.

------------------------------------------------------------------------

# 4. Architectural Boundary

The intended high-level relationship is:

``` text
PHYSICAL GUITAR
      |
      v
PICKUPS / CONTROLS
      |
      v
AFE / CODEC / ADC-DAC
      |
      |  qualified by sg-embedded
      v
TRUSTED DIGITAL SIGNAL
      |
      v
MASTER ALL STRINGS
Performance Engine
      |
      v
MUSICAL CORE
      |
      v
EDUCATIONAL / COACHING / PLAYER EXPERIENCE
```

For the full Smart Guitar, the control plane may evolve toward:

``` text
                         AI ACCELERATOR
                              |
                              v
                         RASPBERRY PI 5
                              |
                       MASTER ALL STRINGS
                              |
                     versioned interface
                              |
                              v
                         MCU / TEENSY
                    _________|_________
                   |         |         |
                watchdog   thermal    power
                   |         |         |
                bypass      fan     telemetry
                   |
                   v
              AUDIO HARDWARE
                   |
                   v
                  AFE
                   |
                   v
                PICKUPS
```

This diagram expresses responsibility, not a frozen PCB design.

------------------------------------------------------------------------

# 5. Smart Guitar Audio Acquisition Qualification (SGAQ)

SGAQ is the first major engineering subsystem of `sg-embedded`.

Its purpose is to determine whether the signal-acquisition chain is
sufficiently characterized and qualified for use by the Smart Guitar
system.

The acquisition path includes:

``` text
Pickup
  -> Hi-Z input
  -> analog front end
  -> anti-alias filter
  -> ADC / codec
  -> audio clock
  -> digital audio interface
  -> Pi / Master All Strings
```

SGAQ must support engineering questions such as:

-   Is pickup loading acceptable?
-   Is analog headroom adequate?
-   What limits system SNR?
-   Is the clock topology acceptable?
-   What RMS jitter budget corresponds to the target?
-   Are fractional-N clock spurs a separate concern?
-   Is anti-alias behavior specified?
-   Is the measured noise floor acceptable?
-   Which evidence is measured and which remains assumed?
-   Is this hardware revision qualified, degraded, failed, or
    unvalidated?

SGAQ is **not** a per-sample DSP component.

Qualification calculations must not be placed in the real-time audio
callback or musical control loop.

------------------------------------------------------------------------

# 6. Jitter Is Not Latency

The project must preserve this distinction.

**Clock jitter** concerns variation in sample timing and its effect on
signal fidelity.

**Audio latency** concerns elapsed time through acquisition, buffering,
operating system, processing, synthesis, and output.

A low-jitter system can still have unacceptable latency.

A low-latency system can still have poor clock integrity.

The two may share evidence infrastructure, but they must not be
conflated into one metric.

------------------------------------------------------------------------

# 7. Clock Topology

SGAQ must explicitly model clock topology rather than hiding clock
behavior behind a single jitter number.

Initial topology vocabulary should include concepts equivalent to:

``` text
LOCAL_XO
HOST_FRACTIONAL_N
CLEANUP_PLL
UNKNOWN
```

A local audio-grade oscillator or codec-master architecture is currently
a **design hypothesis**, not a proven production requirement.

Likewise, Pi-master I2S must not be rejected merely from assumption.

Both architectures should be characterized against measured
requirements.

Fractional-N/spurious behavior must not be represented as if it were
completely described by Gaussian RMS jitter.

------------------------------------------------------------------------

# 8. Evidence and Provenance

Engineering quantities must carry provenance.

Initial provenance classes:

``` text
PROPOSED
ASSUMED
DATASHEET
DERIVED
MEASURED
```

The system must make it difficult to accidentally promote an assumption
into evidence.

Example:

``` text
clock_jitter_rms:
  value: 50
  unit: ps
  provenance: ASSUMED
```

is fundamentally different from:

``` text
clock_jitter_rms:
  value: 50
  unit: ps
  provenance: MEASURED
  evidence_ref: EVT-AUDIO-CLK-0042
```

Qualification disposition must take evidence quality into account.

A mathematically passing design based entirely on assumptions is not
necessarily evidence-qualified hardware.

------------------------------------------------------------------------

# 9. Qualification States

The initial SGAQ decision vocabulary should distinguish at least:

``` text
PASS
FAIL
REVIEW_REQUIRED
UNVALIDATED
```

A separate lightweight runtime health contract may expose states
appropriate to consumers, for example:

``` text
QUALIFIED
DEGRADED
FAILED
UNKNOWN
```

The detailed engineering record remains in `sg-embedded`.

Master All Strings should normally consume the simplified health result
rather than jitter calculations, noise-budget internals, or electrical
design assumptions.

------------------------------------------------------------------------

# 10. Digi-Tec Reference Hardware

The first real hardware profile should be the **Digi-Tec reference audio
interface**, not an imaginary final custom PCB.

The sequence is:

1.  select the actual commercial Hi-Z ADC/DAC/interface used by the
    Digi-Tec prototype;
2.  record its datasheet claims;
3.  establish its clock topology where possible;
4.  measure the real device;
5.  characterize noise, latency, stability, and relevant acquisition
    behavior;
6.  create an evidence-backed reference profile;
7.  use that profile as a baseline for later custom electronics.

This gives the future custom Smart Guitar board a real reference target.

The custom board should have to demonstrate why it is at least adequate
for the intended product rather than being accepted because it is
custom.

------------------------------------------------------------------------

# 11. Boot and Production Self-Test

SGAQ should eventually support a lightweight self-test seam.

Possible runtime checks include:

-   muted-input noise floor;
-   codec presence;
-   expected clock mode;
-   hardware revision;
-   MCU heartbeat;
-   thermal state;
-   battery/power state;
-   bypass state;
-   selected critical faults.

The full engineering qualification calculation is not required at every
boot.

Instead:

``` text
DEVELOPMENT / LAB
    |
    v
full qualification + evidence
    |
    v
approved hardware profile
    |
    v
derived self-test policy
    |
    v
BOOT / PRODUCTION TEST
    |
    v
small deterministic health check
```

Production thresholds must ultimately be based on measured EVT/DVT
populations and manufacturing evidence, not theoretical values alone.

------------------------------------------------------------------------

# 12. Proposed Repository Structure

The initial repository may evolve toward:

``` text
sg-embedded/
|
|-- README.md
|
|-- docs/
|   |-- architecture/
|   |   |-- ELECTRICAL_STACK_CURRENT.md
|   |   |-- RESPONSIBILITY_MODEL.md
|   |   |-- DIGITEC_STACK.md
|   |   `-- SMART_GUITAR_AI_STACK.md
|   |
|   |-- decisions/
|   |-- engineering/
|   `-- historical/
|
|-- acquisition/
|   |-- quantities.py
|   |-- models.py
|   |-- noise.py
|   |-- clock.py
|   |-- qualification.py
|   |-- profiles.py
|   |-- self_test.py
|   |-- report.py
|   `-- cli.py
|
|-- hardware/
|   |-- audio/
|   |-- interfaces/
|   |-- power/
|   |-- thermal/
|   `-- profiles/
|
|-- protocol/
|   `-- pi_mcu/
|
|-- evidence/
|   |-- bench/
|   |-- evt/
|   |-- dvt/
|   `-- production/
|
|-- schemas/
|
|-- tests/
|   |-- acquisition/
|   |-- hardware_profiles/
|   `-- protocol/
|
`-- tools/
```

This tree is a bootstrap direction, not permission to create empty
architecture for its own sake.

Directories should be introduced when their first governed artifact is
ready.

------------------------------------------------------------------------

# 13. Historical Material

Old Smart Guitar concepts are valuable engineering evidence but are not
automatically current authority.

Historical designs may include earlier:

-   Raspberry Pi configurations;
-   Arduino concepts;
-   Teensy arrangements;
-   amplifier boards;
-   audio interfaces;
-   PCB concepts;
-   power architecture;
-   cooling assumptions;
-   DAW integration strategies.

When imported, historical material must be classified rather than
silently restored.

Recommended states:

``` text
HISTORICAL
SUPERSEDED
EXPERIMENTAL
CURRENT
```

A historical design becoming useful again requires an explicit
engineering decision.

------------------------------------------------------------------------

# 14. Safety and Fail-Safe Principle

The Smart Guitar must retain conventional instrument usefulness when
practical and must not make AI responsible for physical safety.

For the advanced Smart Guitar, hardware-control design should favor
autonomous handling of critical functions such as:

-   watchdog timeout;
-   thermal protection;
-   controlled shutdown;
-   fail-safe bypass;
-   critical power faults.

The Pi, Master All Strings, network services, and AI layer must not be
the sole authority for these functions.

AI recommendations may inform a user.

AI must not be the only mechanism protecting the instrument.

------------------------------------------------------------------------

# 15. Integration Principle

Cross-repository integration should be deliberately narrow.

A preferred relationship is:

``` text
sg-embedded
    |
    | produces hardware state/evidence
    v
sg-spec contract
    |
    v
Master All Strings
```

For example, a future portable acquisition-health record might
communicate:

``` json
{
  "schema": "AudioAcquisitionHealthV1",
  "profile_id": "DIGITEC_REFERENCE_AUDIO_V1",
  "hardware_revision": "prototype",
  "state": "QUALIFIED",
  "evidence_grade": true,
  "capture_allowed": true,
  "warnings": []
}
```

The exact contract is **not frozen by this README**.

It should be designed and versioned through `sg-spec`.

------------------------------------------------------------------------

# 16. Development Discipline

Early development should follow these rules:

1.  **Measure before freezing.**
2.  **Label assumptions.**
3.  **Preserve provenance.**
4.  **Separate calculation from evidence.**
5.  **Separate hardware health from musical meaning.**
6.  **Keep engineering qualification out of real-time audio callbacks.**
7.  **Do not force AI-Smart-Guitar complexity into Digi-Tec.**
8.  **Do not allow AI to become hardware safety authority.**
9.  **Prefer versioned, narrow cross-repository contracts.**
10. **Treat custom hardware as something to qualify, not something to
    trust by default.**

------------------------------------------------------------------------

# 17. Initial Development Sequence

The initial repository build should proceed in controlled stages.

### Phase 0 --- Authority bootstrap

Establish:

-   repository charter;
-   authority boundaries;
-   provenance vocabulary;
-   evidence conventions;
-   current-vs-historical classification.

### Phase 1 --- SGAQ mathematical kernel

Migrate and test:

-   jitter SNR calculation;
-   jitter budget calculation;
-   quantization SNR;
-   independent SNR combination;
-   front-end noise calculation;
-   dominant-limiter identification.

No hardware truth is established merely by completing this phase.

### Phase 2 --- Smart Guitar qualification layer

Add:

-   Smart Guitar-specific acquisition profiles;
-   clock topology;
-   evidence gating;
-   qualification disposition;
-   deterministic report artifacts.

### Phase 3 --- Consumer contract

Work with `sg-spec` to establish the smallest portable hardware-health
contract needed by Master All Strings.

### Phase 4 --- Digi-Tec reference qualification

Characterize the actual Digi-Tec commercial audio hardware.

This is the first major opportunity to replace assumptions with
measurements.

### Phase 5 --- Master All Strings seam

Allow the Performance Engine to consume acquisition readiness without
taking ownership of electrical engineering.

### Phase 6 --- Advanced Smart Guitar control plane

When required by the product, introduce:

-   MCU authority;
-   Pi/MCU protocol;
-   watchdog;
-   bypass;
-   thermal/fan behavior;
-   power telemetry.

### Phase 7 --- Custom electronics

Use the accumulated evidence and reference profiles to specify and
qualify the custom Smart Guitar electronics.

------------------------------------------------------------------------

# 18. First Milestone

The first repository milestone is:

> **SG-EMBEDDED-BOOTSTRAP-001**

It is complete when:

-   the repository authority is explicit;
-   SGAQ has a defined home;
-   engineering provenance is enforced;
-   no assumed value is represented as measured;
-   the Digi-Tec and AI Smart Guitar boundaries are distinct;
-   the `sg-spec` boundary is documented;
-   the Master All Strings boundary is documented;
-   the first acquisition calculations have deterministic tests;
-   no real-time audio behavior has been modified merely to establish
    qualification infrastructure.

------------------------------------------------------------------------

# 19. Guiding Principle

The Smart Guitar software stack can only reason correctly about a
performance if the physical system first acquires and reports that
performance truthfully.

Therefore:

> **The embedded layer establishes physical trust.\
> Master All Strings establishes musical truth.\
> The educational systems establish instructional meaning.\
> The Musical Servant assists only after those authorities have
> spoken.**

That separation is the foundation of `sg-embedded`.
