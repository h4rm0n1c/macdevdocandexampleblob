# MiniVNC “RDP-Like” Performance Enhancements for Classic Mac OS  
## A proposal for event-driven damage tracking, CopyRect acceleration, and adaptive scheduling (without breaking VNC compatibility)

**Status:** Proposal / design notes  
**Audience:** MiniVNC maintainers + contributors building for System 7–9 era hardware (68k + PPC)  
**Motivation:** Make MiniVNC *feel* more like a modern remote desktop: lower latency, fewer bytes, fewer stalls, fewer glitches—by sending *less* and sending *smarter*.

---

## 0. Executive summary (what this is, in one breath)

MiniVNC is already fast because it avoids heavyweight structures and tries to be clever with limited CPU/RAM. The next big leap isn’t “more compression.” It’s **stop treating the screen like a mystery**.

Classic Mac OS exposes strong low-level “signals” about what changed (QuickDraw ops, update regions, scroll operations). We can harvest those signals to build a **high-confidence damage model**, then exploit the single most “RDP-like” primitive that stock VNC already supports—**CopyRect**—to accelerate scrolling and window movement dramatically.

This proposal defines a conservative, stability-first plan that:
- remains compatible with standard VNC viewers,
- minimizes risky work in interrupt/callback contexts,
- adds adaptive work budgeting to prevent “fall behind forever” scenarios,
- and keeps a fallback path for apps that bypass QuickDraw.

**Result:** Lower encode cost, lower bandwidth, higher interactivity, better stability.

---

## 1. Problem statement

### 1.1 What hurts today (typical symptoms)
Even with good encodings, classic “framebuffer thinking” wastes work:

- **Scrolling a text view** triggers large updates when the correct answer is “copy most pixels down and paint a thin strip.”
- **Dragging windows** or moving list selections can cause excessive encoding churn.
- **High activity bursts** (menus, typing, mouse moves) can cause backlog if the server produces too much too late.
- **Inexact change detection** can miss changes or require periodic heavy refresh.

### 1.2 Why “just compress harder” doesn’t solve it
Compression (ZRLE/Hextile/etc.) trades CPU for bandwidth. On 68k, CPU is the currency you can’t print. The best win is to **avoid producing pixels** in the first place.

---

## 2. Goals and constraints

### 2.1 Goals (ranked)
1. **Perceived responsiveness:** interactive operations should feel immediate.
2. **Stability:** avoid lockups, re-entrancy bugs, memory churn, and pathological backlog.
3. **Efficiency:** reduce bytes sent and CPU spent encoding.
4. **Compatibility:** work with mainstream VNC clients out-of-the-box.

### 2.2 Constraints (reality checks)
- Some apps draw *outside* QuickDraw (direct VRAM writes, games, demos).
- Hooking system calls is powerful, but **dangerous** if done in the wrong context.
- VNC clients expect RFB semantics; we can’t require a custom viewer (in this phase).

---

## 3. Core idea: “RDP feel” using VNC-native primitives

RDP gets huge wins by shipping *operations* (orders), not pixels. We can’t send arbitrary QuickDraw orders to stock VNC clients. But we *can* do the next best thing:

### 3.1 Event-driven damage model
Instead of guessing what changed by scanning the framebuffer, build a **damage accumulator** from OS-level drawing/update signals:
- Update regions (Window Manager style redraw)
- Drawing calls (QuickDraw primitives)
- Copy/move operations (ScrollRect / CopyBits patterns)

### 3.2 CopyRect as the “poor man’s draw call”
RFB includes **CopyRect**, which instructs the client:  
> “Copy pixels from source rect to destination rect.”

This is essentially a client-side blit—exactly what you want for:
- scrolling list/text areas,
- window moves,
- certain UI animations.

**CopyRect is the single biggest “RDP-like” win available without a custom client.**

---

## 4. Proposed system architecture

### 4.1 High-level pipeline
1. **Hook layer** observes OS drawing activity and records cheap events.
2. **Event queue** collects `DIRTY_RECT` and `COPY_RECT` records.
3. **Damage accumulator** merges/coalesces into a compact “what needs updating” representation.
4. **Scheduler** decides what to send this cycle, with budgets/backpressure control.
5. **Encoder** emits CopyRect where valid, then pixel tiles for the remainder.

### 4.2 The “do no harm” rule
Hooks must be minimal and safe:
- **No allocations**
- **No toolbox calls that can re-enter or block**
- **No heavy Region math**
- **No network I/O**
- Just record intent, then return.

All expensive work happens in a known-safe context (main loop / cooperative task).

---

## 5. Enhancements (detailed)

### 5.1 CopyRect acceleration (Phase 1: ScrollRect)
**Deliverable:** Detect ScrollRect-driven motion and emit CopyRect + exposed damage slivers.

**Mechanism:**
- Intercept `ScrollRect(rect, dh, dv, updateRgn)` (or equivalent signal)
- Derive:
  - `srcRect = rect shifted opposite (dh,dv)`
  - `dstRect = rect`
  - `exposed = rect - shifted(rect)` (the newly uncovered strip)
- Enqueue:
  - `COPY_RECT(srcRect, dstRect)`
  - `DIRTY(exposed)`

**Why it’s safe and huge:** Scrolling becomes a client-side blit + tiny repaint.

**Correctness guardrails:**
- Only emit CopyRect when scroll deltas are small and operation is clearly within screen bounds.
- If ambiguity exists, downgrade to pixel update.

---

### 5.2 CopyRect acceleration (Phase 2: screen-to-screen CopyBits)
**Deliverable:** Identify on-screen blits via CopyBits patterns and convert to CopyRect where appropriate.

**Mechanism:**
- Intercept/observe `CopyBits(srcBits, dstBits, srcRect, dstRect, mode, maskRgn)`
- Conservatively detect cases where:
  - src and dst refer to the visible screen (same port / same baseAddr semantics)
  - transfer mode is compatible (pure copy; avoid XOR/invert/alpha illusions)
  - maskRgn is null or simple enough
- Enqueue:
  - `COPY_RECT(srcRect, dstRect)`
  - `DIRTY(dstRect minus copied area if needed)` (depending on overlap/clip)

**Why it matters:** Window moves/drags and UI blits stop becoming full repaints.

**Risk mitigation:**
- Start strict; loosen rules only after proving correctness.

---

### 5.3 Event-driven dirty tracking (tile-based accumulator)
**Deliverable:** A deterministic, low-cost representation of screen damage that replaces “scan everything.”

**Preferred representation:** **tile bitset grid**
- Choose a tile size tuned to 68k (e.g., 16×16 or 32×16)
- When a dirty rect is recorded, mark intersecting tiles “dirty”
- When sending updates, coalesce dirty tiles into rectangles (greedy merge)

**Why tile bitset instead of Regions everywhere:**
- Regions can get expensive and fragmented.
- Bitsets are stable, predictable, and faster for coalescing.

**Inputs to damage model:**
- Update regions from Window Manager (best “truth” about redraw intent)
- QuickDraw primitives (optional expansion; see §5.6)
- Exposed edges from scroll/move ops

**Fallback path:**
- Keep the current sum/diff method as a periodic verifier or as a “sweep” mode.

---

### 5.4 Adaptive scheduler & work budgeting (anti-backlog engine)
**Deliverable:** MiniVNC should never enter a death spiral where it’s encoding yesterday’s frame forever.

**Core policy:** Always prefer **freshness** over completeness under load.

**Budgets (per cycle):**
- max tiles encoded
- max bytes produced
- max time spent encoding (coarse via TickCount delta)
- max outstanding bytes queued to MacTCP

**Backpressure signals:**
- send queue length / outstanding write count
- repeated send failures / EWOULDBLOCK-like conditions
- time since last successful flush

**Behavior:**
- If behind: drop intermediate dirty states and keep only the latest damage model.
- If interactive: prioritize small updates with minimal latency.
- If idle: batch more aggressively and compress harder.

**Outcome:** Better “feel” and fewer stalls, especially on slow links.

---

### 5.5 Cursor and menu fast paths
**Deliverable:** Prevent full-screen churn during “cursor-only” or menu-tracking phases.

**Mechanisms:**
- If only cursor moved: send pointer update (where protocol/viewer supports it).
- During menu tracking: prioritize small regions around menus and highlights.

**Why:** Lots of perceived lag happens during tiny UI operations that shouldn’t force full frame updates.

---

### 5.6 Optional expansion: Hooking key QuickDraw primitives for richer damage
Once stable, expand damage sources beyond update regions:

- `PaintRect`, `EraseRect`, `FillRect`, `InvertRect`
- text drawing entry points (careful; fonts/modes can be complex but dirty rect is enough)
- `StdBits` / bitmap draws

**Important:** We are not “sending draw calls.” We are only using them to *estimate what pixels became invalid*.

---

## 6. Correctness strategy: conservative first, fast later

### 6.1 Conservative CopyRect rules (initial)
Emit CopyRect only when:
- operation is clearly screen-to-screen
- transfer mode is plain copy
- no complex mask region
- rects are aligned and within bounds
- overlap behavior is well-defined

Otherwise: fall back to pixel updates for that area.

### 6.2 Periodic safety refresh
Because not all drawing is observed:
- On a timer (low cadence), run a lightweight verifier:
  - either a partial diff sweep,
  - or force-refresh a small rotating set of tiles.
This bounds worst-case “missed update” persistence without doing constant full scans.

---

## 7. Stability design notes (Classic Mac OS realities)

### 7.1 Hot-path safety
Hooks and callbacks must avoid:
- memory allocation
- calling into non-reentrant toolbox routines
- region math (especially handle-based regions)
- anything that can block

### 7.2 Event queue discipline
Use a fixed-size ring buffer with:
- overflow policy (“drop oldest dirty events” or “merge into a global dirty-all flag”)
- atomic/interrupt-safe indices where needed
- debug counters for overruns (instrumented but not chatty)

### 7.3 Memory strategy
Preallocate:
- tile grid bitset
- rectangle merge buffers
- encode scratch buffers
Avoid heap churn to prevent fragmentation and long-session instability.

---

## 8. Implementation plan (milestones)

### Milestone 1 — Foundation (1–2 PRs)
- Fixed-size event ring buffer (`DIRTY_RECT`, `COPY_RECT`)
- Tile-bitset damage accumulator + greedy coalescer
- Basic scheduler with per-cycle budgets
- Metrics counters (bytes, tiles, CopyRect count, overruns)

### Milestone 2 — ScrollRect → CopyRect
- Hook ScrollRect
- Emit CopyRect + exposed dirty strips
- Validate on scrolling-heavy apps (editors, lists)

### Milestone 3 — Update region harvesting
- Integrate Window Manager update signals as dirty inputs
- Reduce reliance on diff scanning

### Milestone 4 — CopyBits screen-to-screen → CopyRect (conservative)
- Add strict detection + fallback
- Validate window drag/move scenarios

### Milestone 5 — Tuning + Hardening
- Adaptive “interactive vs idle” mode switch
- Better behind-recovery behavior
- Optional periodic verifier sweep

---

## 9. Test plan (what proves this works)

### 9.1 Functional
- connect/disconnect loops (repeat 100×)
- long soak test (≥ 4 hours)
- heavy scrolling (text/list)
- window dragging + resizing
- menu tracking + rapid selection changes
- clipboard operations (if relevant)

### 9.2 Performance
Measure:
- median latency (input → visible response)
- bytes/sec for:
  - idle desktop
  - scrolling text view
  - window dragging
- CPU time spent in encode vs network
- CopyRect hit rate (% of motion resolved without pixels)

### 9.3 Compatibility
Test at least:
- RealVNC / TightVNC / TurboVNC (or representative set)
Verify:
- CopyRect negotiation support
- correct fallback when unsupported
- no client-specific glitches in mixed CopyRect + pixel updates

---

## 10. Future work: the “true RDP” fork in the road (optional)

If a custom viewer becomes acceptable, a second-track project could send **QuickDraw-like orders**:
- fills, text, blits, lines, patterns, etc.
- with resource sync (fonts/patterns) and pixel fallback

This can beat VNC by orders of magnitude on slow links—but it’s a different scope: custom client, resource management, and deep QuickDraw semantics.

For MiniVNC’s current mission (retro Macs + standard clients), the best ROI remains:
**CopyRect + event-driven damage + adaptive budgeting.**

---

## Appendix A: Success criteria (what “done” looks like)
- Scrolling in a text editor sends mostly CopyRect + tiny edge updates.
- Window dragging feels smooth and doesn’t spike CPU into unusable territory.
- Under slow clients, MiniVNC remains controllable and does not accumulate infinite backlog.
- No increase in crash rate; long sessions remain stable.
- Works with mainstream VNC clients unchanged.

---

## Appendix B: “GaN mode” design principles (the vibe)
- **Pixels are expensive. Don’t send them unless you must.**
- **Fresh > complete** under load.
- **Conservative correctness first**; optimize once proven.
- **Never do heavy work in the wrong context.**
- **Instrument everything** so tuning is science, not vibes.
