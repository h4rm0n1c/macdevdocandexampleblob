"""Generate a Rez .r file for MacVox68 icons from PNG sources.

The script expects six input PNGs:
- 32x32 256-color icon
- 16x16 256-color icon
- 32x32 black and white icon (1-bit)
- 16x16 black and white icon (1-bit)
- 32x32 mask (black=opaque, white=transparent)
- 16x16 mask (black=opaque, white=transparent)

Outputs a Rez source file containing 'icl8', 'ics8', 'icl4', 'ics4',
'ICN#', and 'ics#' resources that share the same resource ID and name.

The generator uses internally defined Classic Mac CLUT8/CLUT4 palettes to
map RGB pixels to icon indices, so no external palette PNGs are required.

Example:
    python docs/generate_icon_r.py \
        --name "MacVox68" \
        --res-id 128 \
        --color32 macvox68_32.png \
        --color16 macvox68_16.png \
        --bw32 macvox68_bw32.png \
        --bw16 macvox68_bw16.png \
        --mask32 macvox68_mask32.png \
        --mask16 macvox68_mask16.png \
        --output macvox68_icon.r

Requires Pillow for PNG decoding.
"""

import argparse
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from PIL import Image


DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "macvox68_icon.r"


def _pad_image(
    image: Image.Image, expected_size: tuple[int, int], *, fill_color: int | tuple[int, ...]
) -> Image.Image:
    if image.size == expected_size:
        return image
    width, height = image.size
    expected_width, expected_height = expected_size
    if width > expected_width or height > expected_height:
        raise ValueError(f"Expected image size {expected_size}, got {image.size}")
    padded = Image.new(image.mode, expected_size, fill_color)
    if image.mode == "P":
        palette = image.getpalette()
        if palette:
            padded.putpalette(palette)
    padded.paste(image, (0, 0))
    return padded


def _ensure_color_image(image: Image.Image, expected_size: tuple[int, int]) -> Image.Image:
    if image.mode not in {"P", "RGB", "RGBA"}:
        raise ValueError(
            "Color icons must be RGB/RGBA or paletted PNGs "
            f"(got {image.mode})."
        )
    if image.size != expected_size:
        if image.mode == "P":
            return _pad_image(image, expected_size, fill_color=0)
        rgb_image = image.convert("RGB")
        return _pad_image(rgb_image, expected_size, fill_color=(255, 255, 255))
    return image


def _ensure_one_bit(image: Image.Image, expected_size: tuple[int, int]) -> Image.Image:
    if image.size != expected_size:
        bit_image = image.convert("1")
        return _pad_image(bit_image, expected_size, fill_color=1)
    return image.convert("1")


def _pack_bits(rows: Iterable[Iterable[bool]]) -> bytes:
    packed = bytearray()
    for row in rows:
        byte = 0
        bit_count = 0
        for pixel_on in row:
            byte = (byte << 1) | (1 if pixel_on else 0)
            bit_count += 1
            if bit_count == 8:
                packed.append(byte)
                byte = 0
                bit_count = 0
        if bit_count:
            packed.append(byte << (8 - bit_count))
    return bytes(packed)


def _bool_rows_from_1bit(image: Image.Image, invert: bool = False) -> List[List[bool]]:
    pixels = list(image.getdata())
    rows: List[List[bool]] = []
    width, height = image.size
    for y in range(height):
        row = []
        for x in range(width):
            value = pixels[y * width + x]
            is_black = value == 0
            row.append(not is_black if invert else is_black)
        rows.append(row)
    return rows


def _pack_nibbles(index_bytes: bytes) -> bytes:
    if len(index_bytes) % 2:
        raise ValueError("4-bit icon data must have an even pixel count for nibble packing.")
    packed = bytearray()
    for i in range(0, len(index_bytes), 2):
        high = index_bytes[i] & 0x0F
        low = index_bytes[i + 1] & 0x0F
        packed.append((high << 4) | low)
    return bytes(packed)


def _clut8_rgb(index: int) -> Tuple[int, int, int]:
    """Classic Macintosh CLUT #8 palette (system icon 8-bit indices)."""
    x = index & 0xFF
    if x < 215:
        r = (5 - (x // 36)) / 5.0
        g = (5 - ((x // 6) % 6)) / 5.0
        b = (5 - (x % 6)) / 5.0
        return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))
    if x == 255:
        return (0, 0, 0)
    values = [v / 15.0 for v in reversed(range(16)) if v % 3 != 0]
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
    return (255, 0, 255)


def _clut4_rgb(index: int) -> Tuple[int, int, int]:
    """Default Macintosh 16-color palette (often referred to as CLUT ID 4)."""
    hexes = [
        "FFFFFF",
        "FCF305",
        "FF6402",
        "DD0806",
        "F20884",
        "4600A5",
        "0000D4",
        "02ABEA",
        "1FB714",
        "006411",
        "562C05",
        "90713A",
        "C0C0C0",
        "808080",
        "404040",
        "000000",
    ]
    h = hexes[index & 0x0F]
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _build_clut8_palette() -> List[Tuple[int, int, int]]:
    return [_clut8_rgb(i) for i in range(256)]


def _build_clut4_palette() -> List[Tuple[int, int, int]]:
    return [_clut4_rgb(i) for i in range(16)]


def _nearest_palette_index(
    rgb: Tuple[int, int, int], palette: Sequence[Tuple[int, int, int]]
) -> int:
    r, g, b = rgb
    best_index = 0
    best_distance = None
    for idx, (pr, pg, pb) in enumerate(palette):
        dr = r - pr
        dg = g - pg
        db = b - pb
        distance = dr * dr + dg * dg + db * db
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_index = idx
    return best_index


def _index_image_to_palette(
    image: Image.Image, palette: Sequence[Tuple[int, int, int]]
) -> bytes:
    base = image.convert("RGB")
    pixels = list(base.getdata())
    lookup = {rgb: idx for idx, rgb in enumerate(palette)}
    indices = bytearray(len(pixels))
    for i, rgb in enumerate(pixels):
        if rgb in lookup:
            indices[i] = lookup[rgb]
        else:
            indices[i] = _nearest_palette_index(rgb, palette)
    return bytes(indices)


def _index_paletted_image_to_palette(
    image: Image.Image, palette: Sequence[Tuple[int, int, int]]
) -> bytes:
    raw_palette = image.getpalette() or []
    input_palette = []
    for idx in range(0, min(len(raw_palette), 768), 3):
        input_palette.append((raw_palette[idx], raw_palette[idx + 1], raw_palette[idx + 2]))
    if not input_palette:
        return _index_image_to_palette(image, palette)
    mapping = [
        _nearest_palette_index(rgb, palette) for rgb in input_palette
    ]
    pixels = list(image.getdata())
    indices = bytearray(len(pixels))
    for i, pixel in enumerate(pixels):
        if pixel < len(mapping):
            indices[i] = mapping[pixel]
        else:
            indices[i] = 0
    return bytes(indices)


def _clut8_indices(image: Image.Image, palette: Sequence[Tuple[int, int, int]]) -> bytes:
    if image.mode == "P":
        return _index_paletted_image_to_palette(image, palette)
    return _index_image_to_palette(image, palette)


def _remap_indices(
    indices: bytes,
    source_palette: Sequence[Tuple[int, int, int]],
    target_palette: Sequence[Tuple[int, int, int]],
) -> bytes:
    mapping = [
        _nearest_palette_index(rgb, target_palette) for rgb in source_palette
    ]
    remapped = bytearray(len(indices))
    for i, value in enumerate(indices):
        if value < len(mapping):
            remapped[i] = mapping[value]
        else:
            remapped[i] = 0
    return bytes(remapped)


def _format_hex_lines(data: bytes, indent: str = "    ", bytes_per_line: int = 16) -> List[str]:
    lines: List[str] = []
    for offset in range(0, len(data), bytes_per_line):
        chunk = data[offset : offset + bytes_per_line]
        hex_chunk = " ".join(f"{byte:02X}" for byte in chunk)
        lines.append(f"{indent}$\"{hex_chunk}\"")
    return lines


def _resource_block(res_type: str, res_id: int, data: bytes) -> str:
    lines = [f"resource '{res_type}' ({res_id}, purgeable) {{"]
    lines.extend(_format_hex_lines(data))
    lines.append("};\n")
    return "\n".join(lines)


def _resource_block_array(res_type: str, res_id: int, elements: Sequence[bytes]) -> str:
    lines = [f"resource '{res_type}' ({res_id}, purgeable) {{", "    {    /* array: 2 elements */"]
    for index, element in enumerate(elements, start=1):
        lines.append(f"        /* [{index}] */")
        lines.extend(_format_hex_lines(element, indent="        ", bytes_per_line=16))
        if index < len(elements):
            lines[-1] = f"{lines[-1]},"
    lines.append("    }")
    lines.append("};\n")
    return "\n".join(lines)


def _bundle_block(
    creator: str, bundle_id: int, icon_res_id: int, name: str, file_type: str
) -> str:
    mappings = [
        "        'ICN#', { 0, %d }," % icon_res_id,
        "        'icl8', { 0, %d }," % icon_res_id,
        "        'icl4', { 0, %d }," % icon_res_id,
        "        'ics#', { 0, %d }," % icon_res_id,
        "        'ics8', { 0, %d }," % icon_res_id,
        "        'ics4', { 0, %d }," % icon_res_id,
        "        'FREF', { 0, %d }" % bundle_id,
    ]
    return "\n".join(
        [
            f"resource 'BNDL' ({bundle_id}, purgeable) {{",
            f"    '{creator}',",
            "    0,",
            "    {",
            "        " + "\n        ".join(mappings),
            "    }",
            "};\n",
            f"resource 'FREF' ({bundle_id}, purgeable) {{",
            f"    '{file_type}',",
            "    0,",
            f"    \"{name}\"",
            "};\n",
        ]
    )


def generate_rez(
    name: str,
    res_id: int,
    paths: dict[str, Path],
    *,
    creator: str,
    file_type: str,
    include_bundle: bool,
    bundle_id: int,
) -> str:
    color32 = _ensure_color_image(Image.open(paths["color32"]), (32, 32))
    color16 = _ensure_color_image(Image.open(paths["color16"]), (16, 16))
    bw32 = _ensure_one_bit(Image.open(paths["bw32"]), (32, 32))
    bw16 = _ensure_one_bit(Image.open(paths["bw16"]), (16, 16))
    mask32 = _ensure_one_bit(Image.open(paths["mask32"]), (32, 32))
    mask16 = _ensure_one_bit(Image.open(paths["mask16"]), (16, 16))

    clut8_palette = _build_clut8_palette()
    clut4_palette = _build_clut4_palette()

    icl8_data = _clut8_indices(color32, clut8_palette)
    ics8_data = _clut8_indices(color16, clut8_palette)

    icl4_bytes = _remap_indices(icl8_data, clut8_palette, clut4_palette)
    ics4_bytes = _remap_indices(ics8_data, clut8_palette, clut4_palette)
    icl4_data = _pack_nibbles(icl4_bytes)
    ics4_data = _pack_nibbles(ics4_bytes)

    icn_icon = _pack_bits(_bool_rows_from_1bit(bw32))
    icn_mask = _pack_bits(_bool_rows_from_1bit(mask32, invert=True))
    ics_icon = _pack_bits(_bool_rows_from_1bit(bw16))
    ics_mask = _pack_bits(_bool_rows_from_1bit(mask16, invert=True))

    sections = [
        _resource_block("icl8", res_id, icl8_data),
        _resource_block("icl4", res_id, icl4_data),
        _resource_block("ics8", res_id, ics8_data),
        _resource_block("ics4", res_id, ics4_data),
        _resource_block_array("ICN#", res_id, [icn_icon, icn_mask]),
        _resource_block_array("ics#", res_id, [ics_icon, ics_mask]),
    ]
    if include_bundle:
        sections.append(_bundle_block(creator, bundle_id, res_id, name, file_type))
    header = [
        "/* Generated by generate_icon_r.py. */",
        "/* Resource types: 'icl8', 'icl4', 'ics8', 'ics4', 'ICN#', 'ics#', optional 'BNDL' + 'FREF'. */",
        '#include "Types.r"',
        '#include "SysTypes.r"',
        '#include "Icons.r"',
        '#include "Finder.r"',
        "",
    ]
    return "\n".join(header + sections)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Rez .r file for MacVox68 icons.")
    parser.add_argument("--name", default="MacVox68", help="Resource name used for all icon variants.")
    parser.add_argument("--res-id", type=int, default=128, help="Resource ID used for all icon variants.")
    parser.add_argument("--color32", type=Path, required=True, help="Path to 32x32 8-bit color PNG.")
    parser.add_argument("--color16", type=Path, required=True, help="Path to 16x16 8-bit color PNG.")
    parser.add_argument("--bw32", type=Path, required=True, help="Path to 32x32 1-bit PNG.")
    parser.add_argument("--bw16", type=Path, required=True, help="Path to 16x16 1-bit PNG.")
    parser.add_argument("--mask32", type=Path, required=True, help="Path to 32x32 mask PNG (black=opaque).")
    parser.add_argument("--mask16", type=Path, required=True, help="Path to 16x16 mask PNG (black=opaque).")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=(
            "Destination Rez source file (defaults to macvox68_icon.r in the project root)."
        ),
    )
    parser.add_argument(
        "--creator",
        default="MV68",
        help="Creator code used in the bundle (defaults to MV68).",
    )
    parser.add_argument(
        "--file-type", default="APPL", help="File type used in the FREF (defaults to APPL)."
    )
    parser.add_argument(
        "--bundle-id",
        type=int,
        default=None,
        help="Resource ID for BNDL/FREF (defaults to res-id when omitted).",
    )
    parser.add_argument(
        "--no-bundle",
        action="store_true",
        help="Skip emitting BNDL/FREF resources (icons only).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = {
        "color32": args.color32,
        "color16": args.color16,
        "bw32": args.bw32,
        "bw16": args.bw16,
        "mask32": args.mask32,
        "mask16": args.mask16,
    }
    bundle_id = args.bundle_id if args.bundle_id is not None else args.res_id
    rez_text = generate_rez(
        args.name,
        args.res_id,
        paths,
        creator=args.creator,
        file_type=args.file_type,
        include_bundle=not args.no_bundle,
        bundle_id=bundle_id,
    )
    args.output.write_text(rez_text, encoding="utf-8")


if __name__ == "__main__":
    main()
