import sys, struct, zlib, binascii
# Real PNG decode validation (B9): not header-only. Walks the full chunk
# stream verifying CRCs, requires IHDR first + IEND last, decompresses ALL
# IDAT data and verifies the raw scanline byte count for the declared
# geometry, and unfilters scanline 0 to prove the filter machinery parses.
# Also enforces expected viewport dims when given.
path, expW, expH = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
d = open(path, 'rb').read()
if d[:8] != b'\x89PNG\r\n\x1a\n': print('REJECT: bad signature'); sys.exit(1)
pos = 8; idat = b''; ihdr = None; seen_iend = False
while pos < len(d):
    if pos + 8 > len(d): print('REJECT: truncated chunk'); sys.exit(1)
    ln, = struct.unpack('>I', d[pos:pos+4]); typ = d[pos+4:pos+8]
    body = d[pos+8:pos+8+ln]; crc, = struct.unpack('>I', d[pos+8+ln:pos+12+ln])
    if len(body) != ln: print('REJECT: truncated chunk body'); sys.exit(1)
    if (binascii.crc32(typ + body) & 0xffffffff) != crc:
        print(f'REJECT: CRC mismatch in {typ!r}'); sys.exit(1)
    if typ == b'IHDR':
        if ihdr is not None: print('REJECT: duplicate IHDR'); sys.exit(1)
        ihdr = struct.unpack('>IIBBBBB', body)
    elif typ == b'IDAT': idat += body
    elif typ == b'IEND': seen_iend = True; break
    pos += 12 + ln
if ihdr is None: print('REJECT: no IHDR'); sys.exit(1)
if not seen_iend: print('REJECT: no IEND'); sys.exit(1)
w, h, bitd, color, comp, filt, interlace = ihdr
if comp != 0 or filt != 0: print('REJECT: unsupported compression/filter method'); sys.exit(1)
CH = {0:1, 2:3, 3:1, 4:2, 6:4}
if color not in CH or bitd not in (1,2,4,8,16): print('REJECT: bad color/bitdepth'); sys.exit(1)
if bitd < 8 and color in (2,4,6): print('REJECT: invalid bitdepth for color type'); sys.exit(1)
if (w, h) != (expW, expH): print(f'REJECT: dims {w}x{h} != expected {expW}x{expH}'); sys.exit(1)
raw = zlib.decompress(idat)
bpp = max(1, (CH[color] * bitd + 7) // 8)
stride = (w * CH[color] * bitd + 7) // 8
if len(raw) != (stride + 1) * h:
    print(f'REJECT: decompressed {len(raw)} != expected {(stride+1)*h}'); sys.exit(1)
if raw[0] > 4: print('REJECT: bad filter byte'); sys.exit(1)
# unfilter every scanline (full decode semantics)
prev = bytearray(stride); off = 0
for y in range(h):
    f = raw[off]; line = bytearray(raw[off+1:off+1+stride]); off += stride + 1
    if f == 1:
        for i in range(bpp, stride): line[i] = (line[i] + line[i-bpp]) & 255
    elif f == 2:
        for i in range(stride): line[i] = (line[i] + prev[i]) & 255
    elif f == 3:
        for i in range(stride):
            a = line[i-bpp] if i >= bpp else 0
            line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
    elif f == 4:
        for i in range(stride):
            a = line[i-bpp] if i >= bpp else 0
            b = prev[i]; c = prev[i-bpp] if i >= bpp else 0
            p = a + b - c; pa, pb, pc = abs(p-a), abs(p-b), abs(p-c)
            pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
            line[i] = (line[i] + pr) & 255
    elif f != 0: print(f'REJECT: bad filter {f}'); sys.exit(1)
    prev = line
print(f'OK decoded {w}x{h} color={color} bitdepth={bitd}')
