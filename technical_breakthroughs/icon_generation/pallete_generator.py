#!/usr/bin/env python3
# make_mac_icon_palette_pngs.py
#
# Generates two "canonical palette source PNGs" suitable for scripts that expect
# a paletted PNG (mode "P") as the palette authority:
#
#   1) mac_clut8_palette256.png  (16x16, 256 entries)  -> for icl8/ics8
#   2) mac_clut4_palette16.png   (16x16, 16 entries)   -> for icl4/ics4
#
# The pixel grid is just indices 0..255 laid out left-to-right, top-to-bottom,
# so you can visually inspect index ordering if you like. The important part is
# the embedded palette ordering in the PNG.
#
# Requires Pillow:
#     python3 -c "import PIL; print(PIL.__version__)"
#
# Run:
#     python3 make_mac_icon_palette_pngs.py --out-dir .
#
# Output:
#     ./mac_clut8_palette256.png
#     ./mac_clut4_palette16.png

import argparse
from pathlib import Path
from PIL import Image


def clut8_rgb(index: int) -> tuple[int, int, int]:
    """
    Classic Macintosh CLUT #8 palette generator used for "system icon" 8-bit indices.

    Returns (R,G,B) in 0..255 for an index 0..255.

    Notes:
    - 0..214: 6x6x6 color cube (inverted order vs typical web-safe cube)
    - 215..254: ramps (R, G, B, Gray), 10 steps each (non-multiples of 3 from 0..15)
    - 255: black
    """
    x = index & 0xFF

    if x < 215:
        # Inverted 6x6x6 cube:
        # r changes slowest, b fastest; 0 is white-ish, 214 is near-black-ish.
        r = (5 - (x // 36)) / 5.0
        g = (5 - ((x // 6) % 6)) / 5.0
        b = (5 - (x % 6)) / 5.0
        return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))

    if x == 255:
        return (0, 0, 0)

    # 215..254: 4 groups of 10 values:
    # group 0: red ramp, group 1: green ramp, group 2: blue ramp, group 3: gray ramp
    # values are (15..0) excluding multiples of 3, scaled to 0..255
    values = [v / 15.0 for v in reversed(range(16)) if v % 3 != 0]  # 10 entries
    which = int((x - 215) % 10)
    group = int((x - 215) // 10)
    v = int(round(values[which] * 255))

    if group == 0:
        return (v, 0, 0)
    if group == 1:
        return (0, v, 0)
    if group == 2:
        return (0, 0, v)
    if group == 3:
        return (v, v, v)

    # Should never happen
    return (255, 0, 255)


def clut4_rgb(index: int) -> tuple[int, int, int]:
    """
    Default Macintosh 16-color palette (often referred to as CLUT ID 4).

    This matches the classic "basic" Mac 16 colors used commonly by 4-bit icons.
    """
    # 16 entries as RGB hex.
    # Order:
    # 0 white, 1 yellow, 2 orange, 3 red, 4 magenta, 5 purple, 6 blue, 7 cyan,
    # 8 green, 9 dark green, 10 brown, 11 tan, 12 light gray, 13 gray, 14 dark gray, 15 black
    hexes = [
        "FFFFFF", "FCF305", "FF6402", "DD0806",
        "F20884", "4600A5", "0000D4", "02ABEA",
        "1FB714", "006411", "562C05", "90713A",
        "C0C0C0", "808080", "404040", "000000",
    ]
    h = hexes[index & 0x0F]
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def make_palette_png_256(out_path: Path) -> None:
    # 16x16 indices 0..255
    img = Image.new("P", (16, 16))
    img.putdata(list(range(256)))

    # Build palette bytes [R0,G0,B0,...]
    pal = []
    for i in range(256):
        r, g, b = clut8_rgb(i)
        pal.extend([r, g, b])
    img.putpalette(pal)

    img.save(out_path)


def make_palette_png_16(out_path: Path) -> None:
    # Still make it 16x16 (to satisfy scripts that insist on 16x16 paletted PNGs)
    img = Image.new("P", (16, 16))
    img.putdata(list(range(256)))  # pixels are indices; only first 16 matter visually

    # First 16 entries are the palette; pad the rest to 256 entries (required by PNG paletted format)
    pal = []
    for i in range(16):
        r, g, b = clut4_rgb(i)
        pal.extend([r, g, b])
    pal.extend([0, 0, 0] * (256 - 16))  # pad remaining entries

    img.putpalette(pal)
    img.save(out_path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=Path("."), help="Directory for output PNGs")
    args = ap.parse_args()

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    p256 = out_dir / "mac_clut8_palette256.png"
    p16 = out_dir / "mac_clut4_palette16.png"

    make_palette_png_256(p256)
    make_palette_png_16(p16)

    print("Wrote:")
    print(f"  {p256}")
    print(f"  {p16}")
    print("")
    print("Use with your generator like:")
    print("  --palette-source mac_clut8_palette256.png --palette4-source mac_clut4_palette16.png")


if __name__ == "__main__":
    main()
