import sys
import fontforge
import psMat

inp = sys.argv[1]
out = sys.argv[2]
new_family = sys.argv[3]
probe = sys.argv[4] if len(sys.argv) > 4 else "0"   # "0" or "n" are good probes

f = fontforge.open(inp)

# Optional cleanup (helps some fonts generate cleanly)
try:
    f.selection.all()
    f.removeOverlap()
    f.correctDirection()
except Exception:
    pass

# Decide target cell width from a "typical" glyph instead of the widest glyph
probe_cp = ord(probe[0])
target = 0
try:
    g = f[probe_cp]
    if g is not None and g.width > 0:
        target = g.width
except Exception:
    pass

if target <= 0:
    # fallback: median-ish of ASCII widths
    widths = []
    for cp in range(32, 127):
        try:
            gg = f[cp]
            if gg is not None and gg.width > 0:
                widths.append(gg.width)
        except Exception:
            pass
    widths.sort()
    target = widths[len(widths)//2] if widths else f.em

# Force uniform width.
# If a glyph is too wide, scale its outline horizontally to fit target.
for g in f.glyphs():
    if g is None or g.width <= 0:
        continue

    w = g.width

    if w > target:
        sx = float(target) / float(w)
        # scale outline about origin; then we'll re-center it
        g.transform(psMat.scale(sx, 1.0))
        w = target  # after scaling, treat it as target for centering

    # Center current outline into the target cell
    dx = (target - g.width) / 2.0
    if dx != 0:
        g.transform(psMat.translate(dx, 0))

    g.width = target

# Rename so it doesn't collide with the original
f.familyname = new_family
f.fullname = new_family
f.fontname = new_family.replace(" ", "")
try:
    f.isFixedPitch = 1
except Exception:
    pass

f.generate(out)
