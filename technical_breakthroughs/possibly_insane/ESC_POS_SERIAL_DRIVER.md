# Proposal: ESC/POS Serial Printer Driver for Classic Mac OS 7 (Epson TM-T88IV)

> **Working title:** `ESC_POS_SERIAL_DRIVER.md`  
> **Status:** Proposal / design notes  
> **Target OS:** System 7.1–7.5.x (68k-first)  
> **Target printer:** Epson **TM-T88IV**

---

## 0. Executive summary (what this is)

Build a **Chooser-selectable, serial printer** for Classic Mac OS that shows up like an ImageWriter-style device, but outputs **ESC/POS** over the Mac’s serial port (RS-422 electrically, adapted to RS-232 for the printer). The concrete goal is: **Command-P → choose the “TM-T88IV ESC/POS” driver → print a receipt** (text-first, with optional bitmap logos and auto-cut).

This is *not* “just write bytes to a port.” A Classic Mac printer driver is a **Printing Manager** implementation packaged as a **Printer Resource File** (code/resources like `DRVR`, `PDEF`, `PACK`, `PREC`, dialogs, etc.).

---

## 1. Why this is plausibly doable

* The Mac’s Printing Manager was designed to route printing through a printer driver selected by the user, and it calls into that driver to do translation + output.
* There’s precedent for “simple serial text printers” implemented as Printer Resource Files (classic articles outline exactly the resource types and the low-level text streaming path).
* The TM-T88IV is explicitly a serial-capable POS printer, with selectable handshake (DTR/DSR or XON/XOFF) and common baud rates up through 115200 bps.
* ESC/POS cutting and (optionally) raster/bit-image commands are well-understood and documented in Epson’s reference materials for TM printers.

---

## 2. Goals

1. **Print receipts from any Mac app** that uses the Printing Manager: basic text output works immediately.
2. **Serial output path is solid:** correct baud/format + flow control; no dropped data.
3. **Receipt ergonomics:** optional “Cut after job,” “Open cash drawer pulse,” margins, and a fixed paper width preset (58mm/80mm-ish).
4. **Optional logo support:** print a small bitmap logo at top (via ESC/POS bit-image/raster modes).

---

## 3. Non-goals (at least initially)

* Perfect “LaserWriter-class” fidelity for arbitrary QuickDraw graphics/layout.
* Full proportional font mapping (we’ll start with monospace / rasterize later).
* Network printing / AppleTalk / LocalTalk.
* QuickDraw GX compatibility (this is a System 7 Printing Manager era driver).

---

## 4. Hardware + serial reality check

### 4.1 Physical layer
* Classic Mac serial ports are **RS-422**; the printer is **RS-232C**. You already have the special cabling/level conversion — great — but the driver design must assume proper level shifting and correct handshake wiring.
* TM-T88IV serial interface: selectable handshake (**DTR/DSR** or **XON/XOFF**), 7/8-bit, parity, and baud rates (DIP-select subset + command-select extended list).

### 4.2 Mac OS serial device names (important for code)
* Modem port drivers: **`.AIn` / `.AOut`**
* Printer port drivers: **`.BIn` / `.BOut`**

This matters because the printer driver will ultimately call into the Serial Driver (via Device Manager calls like PBWrite / PBControl).

---

## 5. Classic Mac printing architecture (what we’re actually building)

At a high level:

1. The **Printing Manager** dispatches printing operations to the **currently selected printer driver**.
2. A printer driver is packaged as a **Printer Resource File** containing code resources (notably `DRVR` and `PDEF`) plus dialogs/settings resources.

A practical decomposition:

* **`DRVR`**: “low-level” entry points + device control/status; often where the serial port is opened/configured and where raw bytes are sent.
* **`PDEF`**: “high-level” printing routines and printing dialogs (style/job UI).
* **`PACK -4096`** (optional): Chooser/installation UI logic (for device configuration).
* **`PREC`**: print record / private storage blobs persisted as resources.

**Important reality note:** writing Chooser-selectable printer drivers was historically under-documented and sometimes implemented in 68k assembly; but it’s still doable with references/skeletons.

---

## 6. Driver “shape” options

### Option A — “Serial printer, minimal UI” (`PRES`)
Make it a **serial printer** resource file (`PRES`) so Chooser handles port selection and stores choice in PRAM; the driver focuses on printing.

**Pros:** smallest surface area, fastest path to “it prints.”  
**Cons:** fewer custom settings in Chooser; may need clever defaults.

### Option B — “Non-serial printer with custom Chooser config” (`PRER` + `PACK`)
Use `PRER` so we can add a config UI for:
* baud rate / data format
* handshake mode (DTR/DSR vs XON/XOFF)
* cut mode / margins / code page

**Pros:** better user experience, fewer “why is it gibberish” failures.  
**Cons:** more work (dialogs + `PACK` logic).

**Recommendation:** start with **Option A** to validate end-to-end printing, then upgrade to **Option B** once the data path is proven.

---

## 7. What we print (ESC/POS strategy)

### 7.1 Text-first (phase 1)
Receipt printing is mostly text. ESC/POS gives us:
* Initialize printer (commonly `ESC @`)
* Line feeds / spacing
* Emphasis/double-width/double-height (model-dependent)
* Optional partial/full cut (`GS V …`)

We keep a conservative subset and focus on correctness + flow control.

### 7.2 Graphics (phase 2)
For logos and (later) rasterized pages:
* Use ESC/POS bit-image / raster image commands (`GS v 0 …` / `ESC * …` variants).

---

## 8. Paper geometry + resolution constraints (receipt reality)

TM-T88IV horizontal dot width (often cited as **512 dots**) is a key constraint for raster graphics width and for mapping a “page rectangle” concept into a roll printer world.

Driver design implication:
* Treat the receipt as a **fixed-width canvas** (e.g., 512 dots).
* Height is “infinite-ish” until job end; we stream lines and then cut.

---

## 9. Proposed implementation plan (phased)

### Phase 0 — prove the serial path with a tiny test app
Before touching Printing Manager complexity:
1. Write a tiny Mac app that opens `.BOut` (or `.AOut`) and writes:
   * init
   * “Hello receipt”
   * feed + cut
2. Validate:
   * baud rate
   * handshake choice (DTR/DSR vs XON/XOFF)
   * no dropped bytes under sustained output

### Phase 1 — “text-only printer driver” (draft-quality mindset)
Build a Printer Resource File that supports:
* minimal dialogs (or defaults)
* text streaming path to serial (classic low-level `iPrIOCtl` pattern)
* end-of-job cut sequence (configurable)

### Phase 2 — bitmap/logo support
Add:
* a resource-stored 1-bit logo bitmap (or load from file)
* convert to ESC/POS raster/bit-image and print at job start

### Phase 3 — rasterize “real” QuickDraw pages (optional insanity upgrade)
If we want arbitrary app output:
* Capture QuickDraw drawing into a bitmap per band/strip
* Dither to 1-bit
* Stream as ESC/POS raster bands

---

## 10. Risks / gotchas (known sharp edges)

* **Driver complexity:** Printer drivers are not like normal device drivers; lots of resource formats and call conventions.
* **Flow control is non-optional:** thermal printers can accept data fast until they can’t; without correct DTR/DSR or XON/XOFF you will drop bytes mid-job.
* **Character encoding/code pages:** receipts often need code page selection (e.g., CP437 / Katakana tables). Plan for a “code page” option early.
* **“Infinite page” vs page rectangles:** classic printing UI wants page sizes; receipt printers want continuous roll. We’ll likely expose a “Receipt (Roll)” page size and treat height as “stream until end.”

---

## 11. Test plan (practical, not theoretical)

1. Use printer diagnostic modes (e.g., hex dump / self-test, if available) to confirm exactly what bytes arrived.
2. Test matrices:
   * baud: 9600, 19200, 38400, 115200 (if stable)
   * handshake: DTR/DSR vs XON/XOFF
   * long receipt (>5KB) to stress flow control
3. Print from:
   * SimpleTeachText / text apps (baseline)
   * a few “receipt-ish” apps that print mostly text
4. Confirm:
   * cut triggers once (no double-cut)
   * no stalls / no partial lines

---

## 12. Stretch features (very on-brand for “possibly_insane”)

* **Cash drawer pulse** support surfaced as a checkbox in the job dialog.
* **Status polling** (paper out, cover open) if serial status commands are available/compatible; surface meaningful Mac errors.
* **“Receipt renderer” mode:** interpret common QuickDraw text ops as ESC/POS text (fast), and fall back to raster only when necessary.

---

## 13. References (starting points we will lean on)

* Apple Printing Manager documentation and driver structure notes.
* Epson TM-T88IV Technical Reference Guide: serial interface options, handshake, speeds, and device specs.
* Epson ESC/POS command references for TM printers (cut, raster, etc.).
* Inside Macintosh Serial Driver: device names and flow control fundamentals.
* Historic “How to Write a Printer Driver” examples and Apple technotes on printer drivers.
