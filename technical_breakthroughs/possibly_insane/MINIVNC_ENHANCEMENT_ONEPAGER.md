## Proposal: “RDP-like” performance upgrades for MiniVNC (without breaking VNC compatibility)

MiniVNC is already impressively fast on vintage Macs by keeping memory low and avoiding heavyweight screen tracking. The next leap isn’t “more compression” — it’s **stop treating the screen like a mystery**.

Classic Mac OS gives us high-quality signals about what changed (QuickDraw + Window Manager activity). If we harvest those signals, we can send **less** and send **smarter**, making MiniVNC *feel* like a modern remote desktop: lower latency, fewer bytes, fewer stalls.

### What we want to add (high ROI, low scope creep)

**1) CopyRect acceleration (the big win)**
VNC/RFB supports **CopyRect**: “copy pixels from A to B” on the client with *no* pixel payload.
That’s the closest thing VNC has to RDP’s blit/scroll optimizations, and it maps perfectly to classic Mac UI patterns:
- `ScrollRect` (scrolling lists/text)
- screen-to-screen `CopyBits` (window moves / UI blits)

**Impact:** scrolling becomes “client-side blit + tiny exposed strip,” not “re-encode the whole window.”

**2) Event-driven damage tracking (send only what changed)**
Instead of scanning/diffing large portions of the framebuffer, maintain a compact **damage model**:
- accumulate dirty rectangles/tiles from update regions and drawing activity
- coalesce tiles into efficient rectangles at send time
- keep current diff/sweep as a safety net for apps that bypass QuickDraw

**Impact:** fewer tiles encoded, fewer bytes sent, fewer missed updates.

**3) Adaptive scheduling + backpressure (no more death spirals)**
Introduce per-cycle budgets (tiles/bytes/time) and a “freshness-first” policy:
- if the client/network is slow, **drop intermediate frames** and send the latest state
- interactive mode favors latency; idle mode favors batching/compression

**Impact:** MiniVNC stays responsive under load instead of falling behind forever.

### Safety and stability: our hard rules
- Hooks/patches do *minimal work*: record rects/copies into a fixed ring buffer and return.
- No allocations, no heavy Region math, no network I/O in hot paths.
- Preallocate buffers to avoid fragmentation and long-session instability.

### Roadmap (incremental, shippable steps)
1. **Foundation:** event queue + tile damage grid + scheduler budgets + instrumentation counters
2. **ScrollRect → CopyRect:** huge win, easy to validate
3. **Update region harvesting:** reduce scanning reliance
4. **Conservative CopyBits → CopyRect:** strict rules + fallback
5. **Tuning:** adaptive modes, behind-recovery, optional safety sweep

### Success looks like
- Text/list scrolling sends mostly CopyRect + thin edge updates.
- Window dragging feels smoother and doesn’t spike CPU into unusable territory.
- Slow clients don’t cause runaway backlog; MiniVNC remains controllable.
- Works with mainstream VNC clients unchanged.

**Bottom line:** This is the “RDP feel” path that keeps MiniVNC compatible, stable, and fast on real vintage hardware.
