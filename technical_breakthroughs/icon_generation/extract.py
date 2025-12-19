#!/usr/bin/env python3
# extract.py
#
# Parse a classic Mac OS resource fork (raw bytes) and list/extract resources.
#
# Usage:
#     python3 extract.py Untitled
#     python3 extract.py Untitled --extract icl8 128 newton_icl8_128.bin
#     python3 extract.py Untitled --extract ICN# 128 newton_ICN_128.bin
#     python3 extract.py Untitled --extract ics8 128 newton_ics8_128.bin

import argparse
import struct
import sys
from dataclasses import dataclass
from typing import List, Tuple

def be_u16(b: bytes, off: int) -> int:
    return struct.unpack_from(">H", b, off)[0]

def be_s16(b: bytes, off: int) -> int:
    return struct.unpack_from(">h", b, off)[0]

def be_u32(b: bytes, off: int) -> int:
    return struct.unpack_from(">I", b, off)[0]

def read_pstr(b: bytes, off: int) -> str:
    if off < 0 or off >= len(b):
        return ""
    n = b[off]
    end = off + 1 + n
    if end > len(b):
        return ""
    data = b[off + 1:end]
    try:
        return data.decode("mac_roman", errors="replace")
    except LookupError:
        return data.decode("latin-1", errors="replace")

def type_to_str(t: bytes) -> str:
    try:
        return t.decode("latin-1")
    except Exception:
        return "".join(chr(x) if 32 <= x <= 126 else "." for x in t)

@dataclass
class ResourceEntry:
    rtype: str
    rid: int
    name: str
    attrs: int
    data_off: int
    data_len: int

def parse_resource_fork(path: str) -> Tuple[bytes, List[ResourceEntry]]:
    blob = open(path, "rb").read()
    if len(blob) < 16:
        raise ValueError("File too small to be a resource fork")

    data_off = be_u32(blob, 0)
    map_off  = be_u32(blob, 4)
    data_len = be_u32(blob, 8)
    map_len  = be_u32(blob, 12)

    if data_off + data_len > len(blob) or map_off + map_len > len(blob):
        raise ValueError("Header offsets/lengths exceed file size")

    data_area = blob[data_off:data_off + data_len]
    map_area  = blob[map_off:map_off + map_len]

    # Map header is at least 28 bytes:
    # 0..15  copy of resource header
    # 16..19 handleNextMap
    # 20..21 fileRefNum
    # 22..23 attrs
    # 24..25 typeListOff
    # 26..27 nameListOff
    if len(map_area) < 28:
        raise ValueError("Resource map too small")

    type_list_off = be_u16(map_area, 24)
    name_list_off = be_u16(map_area, 26)

    # Offsets are relative to start of map. Name list may legitimately be empty
    # and then name_list_off can be == map_len.
    if type_list_off >= len(map_area):
        raise ValueError("Type list offset out of range")
    if name_list_off > len(map_area):
        raise ValueError("Name list offset out of range")

    type_list_base = type_list_off
    name_list_base = name_list_off
    name_list_exists = (name_list_base < len(map_area))

    # Type list:
    # u16 numTypesMinus1
    # entries:
    #   4 bytes type
    #   u16 numResMinus1
    #   u16 refListOff (from start of type list)
    tl = map_area
    if type_list_base + 2 > len(tl):
        raise ValueError("Truncated type list header")

    num_types = be_u16(tl, type_list_base) + 1
    pos = type_list_base + 2

    entries: List[ResourceEntry] = []

    for _ in range(num_types):
        if pos + 8 > len(tl):
            raise ValueError("Truncated type list entry")

        rtype_bytes = tl[pos:pos + 4]
        rtype = type_to_str(rtype_bytes)

        num_res = be_u16(tl, pos + 4) + 1
        ref_off = be_u16(tl, pos + 6)
        pos += 8

        ref_list_pos = type_list_base + ref_off

        # Each ref is 12 bytes:
        # s16 id
        # s16 nameOff (from start of name list; -1 = none)
        # u8 attrs
        # u24 dataOff (from start of data area)
        # u32 handle (ignored)
        for _r in range(num_res):
            if ref_list_pos + 12 > len(tl):
                raise ValueError(f"Truncated reference list for type {rtype}")

            rid = be_s16(tl, ref_list_pos + 0)
            name_off = be_s16(tl, ref_list_pos + 2)
            attrs = tl[ref_list_pos + 4]

            d0, d1, d2 = tl[ref_list_pos + 5], tl[ref_list_pos + 6], tl[ref_list_pos + 7]
            doff = (d0 << 16) | (d1 << 8) | d2

            ref_list_pos += 12

            name = ""
            if name_list_exists and name_off != -1:
                # name_off is relative to name list base
                name = read_pstr(tl, name_list_base + name_off)

            # Data area: [u32 length][bytes...]
            if doff + 4 > len(data_area):
                raise ValueError(f"Bad data offset for {rtype} {rid}: {doff}")
            rlen = be_u32(data_area, doff)
            rdat_start = doff + 4
            rdat_end = rdat_start + rlen
            if rdat_end > len(data_area):
                raise ValueError(f"Bad data length for {rtype} {rid}: {rlen}")

            entries.append(ResourceEntry(
                rtype=rtype,
                rid=rid,
                name=name,
                attrs=attrs,
                data_off=rdat_start,
                data_len=rlen
            ))

    entries.sort(key=lambda e: (e.rtype, e.rid))
    return data_area, entries

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help="Raw resource fork file (e.g. Basilisk .rsrc sidecar)")
    ap.add_argument("--extract", nargs=3, metavar=("TYPE", "ID", "OUT"),
                    help="Extract resource TYPE and ID to OUT")
    args = ap.parse_args()

    data_area, entries = parse_resource_fork(args.file)

    if args.extract:
        t, sid, outp = args.extract
        rid = int(sid, 10)
        hit = None
        for e in entries:
            if e.rtype == t and e.rid == rid:
                hit = e
                break
        if not hit:
            print(f"Not found: {t} ({rid})", file=sys.stderr)
            return 2
        blob = data_area[hit.data_off:hit.data_off + hit.data_len]
        with open(outp, "wb") as f:
            f.write(blob)
        print(f"Wrote {outp}: type={hit.rtype} id={hit.rid} size={hit.data_len}")
        return 0

    print(f"Found {len(entries)} resources in {args.file}")
    for e in entries:
        nm = f' "{e.name}"' if e.name else ""
        print(f"{e.rtype:4s} ({e.rid:6d})  size={e.data_len:6d}  attrs=0x{e.attrs:02X}{nm}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

# Commands:
#     python3 extract.py Untitled
#     python3 extract.py Untitled --extract icl8 128 newton_icl8_128.bin
#     python3 extract.py Untitled --extract ICN# 128 newton_ICN_128.bin
#     python3 extract.py Untitled --extract ics8 128 newton_ics8_128.bin
#     wc -c newton_icl8_128.bin newton_ics8_128.bin newton_ICN_128.bin
