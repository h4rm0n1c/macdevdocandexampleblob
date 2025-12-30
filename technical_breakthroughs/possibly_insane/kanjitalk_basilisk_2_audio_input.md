# Proposal: SDL2 Sound Input (Microphone) Support via Deferred-Task Completion (Kanjitalk/Basilisk II Pattern)

## Summary

This proposal describes how to add **Sound Input (microphone capture)** support to a 68k Mac emulator in the style of Kanjitalk/Basilisk II, using the same completion model shown in `serial.cpp`:

- **Prime() requests are asynchronous**
- The emulator **never calls 68k code from host audio callbacks**
- Completion is signaled by **enqueuing a Deferred Task** that jumps to **JIODone**
- A periodic emulator-side “IRQ poll” checks whether pending requests are ready and completes them

The approach minimizes risk and matches how the existing serial driver avoids reentrancy and thread hazards.

---

## Goals

1. Provide working Sound Input for classic Mac OS software that uses the Sound Input driver.
2. Preserve emulator stability by avoiding 68k calls or guest memory access from SDL callback threads.
3. Integrate cleanly with the existing ROM patch / emul-op infrastructure (same pattern used for serial).

---

## Non-Goals

- Perfect hardware-accurate Sound Input timing
- Supporting every obscure Sound Manager/Sound Input edge case immediately
- Implementing full “SerialDMA” style multi-queue or multiple concurrent Prime requests

---

## Background & Rationale

### Observed pattern in `serial.cpp` (Kanjitalk/Basilisk II)

The serial driver demonstrates a safe, classic Mac OS-compliant async I/O completion strategy:

- In `Open()`:
  - Allocate Deferred Task structures (`NewPtrSysClear`)
  - Build a tiny 68k snippet inside the DT that jumps to `JIODone`
- In `Prime()`:
  - Mark request as pending (read or write)
- In the emulator’s periodic IRQ path:
  - If `pending && done`, enqueue the DT via `EnqueueMac(dt, 0xd92)`
  - DT runs on Mac side and calls `JIODone`, completing the PB/DCE request

**Key insight:** A host callback (SDL audio capture) should only buffer audio, never touch Mac memory or signal completion directly.

---

## Architecture Overview

### High-level data flow

1. **Mac app calls SoundIn Prime()** (asynchronous read request)
2. Emulator records request as **pending**
3. SDL2 capture callback pushes captured PCM into a **host ring buffer**
4. Emulator thread periodically checks:
   - Is a SoundIn request pending?
   - Do we have enough bytes to satisfy it (or enough for a partial completion rule)?
5. If yes:
   - Copy from ring buffer into **guest-provided buffer**
   - Set PB fields (ioActCount, ioResult, etc.)
   - Mark done
   - **Enqueue Deferred Task** to call `JIODone`

---

## Proposed Implementation Details

### 1) Add Sound Input driver state (similar to `SERDPort` usage)

Introduce a minimal global state (one channel initially):

- `is_open`
- `read_pending`
- `read_done`
- `dt` pointer (Mac address) for deferred completion
- ring buffer handle (host side)
- audio format configuration (sample rate, sample format, channels)

Example (conceptual):

- `SoundInState g_sndin;`

Only **one outstanding Prime read** is supported at a time initially (matching the “fatal if pending” behavior from serial).

---

### 2) Allocate and initialize a Deferred Task in SoundIn Open()

On `SoundInOpen(pb, dce)`:

- Allocate `SIZEOF_serdt` bytes using `NewPtrSysClear()` (trap `0xA71E`)
- Fill DT fields:
  - `qType = dtQType`
  - `dtAddr = dt + serdtCode`
  - `dtParam = dt + serdtResult`
- Write a 68k completion thunk identical to serial:

**DT param layout**
- `[0..3] result (int32)`
- `[4..7] dce (uint32)`

**DT 68k code**
- `move.l (a1)+,d0`  (result)
- `move.l (a1),a1`   (dce)
- `move.l JIODone,a0`
- `jmp (a0)`

This preserves the same semantics as serial: when the DT is executed, it completes the I/O request by calling `JIODone(dce, result)`.

---

### 3) Implement SoundIn Prime() as asynchronous read request

On `SoundInPrime(pb, dce)`:

- If driver not open: return `notOpenErr`
- If `read_pending == true`: return `readErr` (or a suitable error), matching serial’s “one request at a time” assumption
- Record the request context:
  - `read_pending = true`
  - `read_done = false`
  - Store any request parameters you need (or plan to read directly from PB later)
- Return `noErr` (request accepted; completion will occur later via DT)

**Important:** Do not complete the request synchronously unless you explicitly decide to support “immediate completion if enough data exists”. If you do allow immediate completion, still do it from emulator thread, not from SDL callback.

---

### 4) SDL2 capture callback: buffer only

In SDL2 audio capture callback:

- Do **not** touch Mac memory
- Do **not** invoke any 68k trap or emulator function that is not thread-safe
- Just push samples into a lock-protected or lock-free ring buffer

Preferred ring buffer properties:

- Bounded size (e.g., a few hundred ms of audio)
- Overrun policy:
  - drop oldest (common) or drop newest
  - log once if overruns occur frequently

---

### 5) Completion occurs in emulator-thread “IRQ poll”

Add a `SoundInInterrupt()` analogous to `SerialInterrupt()` and call it from the same periodic IRQ pathway used for serial:

Pseudo-logic:

- If `is_open && read_pending`:
  - Determine how many bytes requested in PB (`ioReqCount`)
  - If ring buffer has enough:
    - Copy bytes into guest buffer (`ioBuffer`)
    - Set `ioActCount` to the number of bytes copied
    - Set `ioResult` to `noErr` (or an error if applicable)
    - Set `read_done = true`
    - Write DT param payload:
      - `dtResult.result = ioResult`
      - `dtResult.dce = dce`
  - If `read_pending && read_done`:
    - `EnqueueMac(dt, 0xd92)`
    - clear `read_pending/read_done`

This ensures `JIODone` runs on the Mac side and completes the PB properly.

---

## Mac OS Integration Notes

### Driver installation approach

There are two likely integration strategies:

1. **Patch/install Sound Input driver in ROM**, similar to `.Sony`/SERD replacement:
   - Add a stub driver header in ROM
   - Map Open/Prime/Control/Status/Close to EMUL_OP handlers
2. **Hook existing Sound Input A-trap / driver entry** if present in ROM:
   - Replace trap address via `SetOSTrapAddress()` if applicable

The project should follow whichever mechanism the existing emulator already uses for other pseudo-drivers (serial, disk, etc.).

---

## Control/Status calls and minimal feature set

To support common apps, the initial Sound Input driver should implement at least:

### Status() basics
- Driver version query (return something plausible)
- Current format (sample rate, channels) if requested

### Control() basics
- Start/stop capture
- Set sample rate / format if feasible
- Buffer/latency configuration if requested

**Initial simplification:**
- Provide a fixed capture format (e.g., 8-bit mono or 16-bit mono) and perform conversion as needed in the emulator thread.

---

## Audio Format Handling

### Suggested initial format
Start with a format that is broadly compatible and easy to convert:

- 16-bit signed, mono
- 11025 Hz or 22050 Hz (depending on compatibility targets)

Conversion responsibilities:

- If Mac requests 8-bit unsigned, convert from signed 16-bit
- If Mac requests other rates, either:
  - resample (later improvement), or
  - clamp to a supported set and report it via Status()

---

## Threading & Safety Requirements

### Hard rule (copied from serial pattern intent)
- Never call into the 68k emulator core from the SDL callback thread
- Never read/write guest memory from SDL callback thread

All guest memory interactions must occur in the emulator’s main thread, typically during the same periodic “IRQ” servicing where serial completion is handled.

---

## Testing Plan

### Phase 1: Driver life-cycle sanity
- Open → Close works without leaks
- Re-open works
- No crashes if Prime called before Open (expect notOpenErr)

### Phase 2: Basic capture + completion
- Prime read completes and app receives non-zero data
- Repeated Prime calls succeed sequentially

### Phase 3: Real application tests
- Simple Sound Input control panel (if available)
- Third-party audio recording utilities that use Sound Input driver

### Logging & observability
- Add optional debug logs when:
  - ring buffer overruns
  - Prime called while pending
  - completion enqueued

---

## Milestones

1. **M1**: Add host ring buffer + SDL2 capture
2. **M2**: Add SoundIn driver skeleton (Open/Close/Prime) + deferred task completion
3. **M3**: Implement minimal Control/Status to satisfy common apps
4. **M4**: Improve format negotiation and conversion
5. **M5**: Optional resampling + better latency controls

---

## Risks & Mitigations

### Risk: Mac apps expect specific Control/Status behavior
- Mitigation: start with minimal, then iteratively add calls based on observed app behavior

### Risk: Timing/latency sensitivity
- Mitigation: tune ring buffer size; prefer stable completion over ultra-low latency initially

### Risk: ROM/driver hook complexity
- Mitigation: reuse existing driver replacement patterns (SERD/.Sony style), avoiding new mechanisms where possible

---

## Deliverables

- Sound Input driver implementation using:
  - Async Prime + deferred completion via `JIODone`
  - SDL2 capture ring buffer
- Documentation describing:
  - supported formats
  - known limitations
  - configuration options (device selection, latency)

---

## Appendix: Why Deferred Tasks (DT) are the correct mechanism

This is the same technique already proven by `serial.cpp`:

- The DT executes in the Mac OS environment
- It safely calls `JIODone` without reentrancy issues
- Completion is scheduled from the emulator thread
- It avoids crossing thread boundaries unsafely

This aligns Sound Input completion with existing emulator conventions and reduces integration risk.
