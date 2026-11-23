#!/usr/bin/env python3
"""Numerically check analysis claims that can be computed without an HDL simulator.

Each check re-implements the relevant RTL arithmetic exactly as written in the
source (file/line noted per check) and compares it with an independent reference.

Usage:
  python3 tools/verify/verify_calcs.py <path-to-holoscan-sensor-bridge>
Prints one PASS/FAIL/RESULT block per check; exit code 1 if any check FAILs.
"""
import math
import random
import re
import sys
from pathlib import Path

random.seed(1)
FAILED = []


def report(name, ok, detail):
    tag = "PASS" if ok is True else ("FAIL" if ok is False else "RESULT")
    if ok is False:
        FAILED.append(name)
    print(f"[{tag}] {name}\n        {detail}")


def ones_sum(words):
    s = 0
    for w in words:
        s += w
        s = (s & 0xFFFF) + (s >> 16)
    return s


def ipv4_checksum(hdr_words):
    """RFC 791 checksum over 10 16-bit words with the checksum word = 0."""
    return (~ones_sum(hdr_words)) & 0xFFFF


def ipv4_valid(hdr_words):
    return ones_sum(hdr_words) == 0xFFFF


# ---------------------------------------------------------------------------
# 1. EEPROM CRC (sys_init/eeprom_info.sv L276-L322 vs script/eeprom/eeprom_utility.py)
# ---------------------------------------------------------------------------
def crc8_rtl_step(data, crc):          # nextCRC() in eeprom_info.sv
    for _ in range(8):
        odd = (data ^ crc) & 1
        crc >>= 1
        data >>= 1
        if odd:
            crc ^= 0x8C
    return crc


def crc8_utility(data_bytes):          # AddToCRC()/compute_crc() in eeprom_utility.py
    crc = 0
    for b in data_bytes[:255]:
        crc = crc8_rtl_step(b, crc)
    return crc


def crc8_reflected_generic(data, poly_reflected, init=0):
    crc = init
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ poly_reflected if crc & 1 else crc >> 1
    return crc


def check_eeprom_crc():
    check = crc8_reflected_generic(b"123456789", 0x8C)
    report("EEPROM CRC algorithm = CRC-8/MAXIM (poly 0x31, reflected 0x8C)",
           check == 0xA1, f"check value over '123456789' = 0x{check:02X} (CRC-8/MAXIM catalogue: 0xA1)")
    comment = crc8_reflected_generic(b"123456789", 0xB0)
    report("Header comment polynomial (0xB0) is a different CRC",
           comment != check, f"0xB0 reflected gives 0x{comment:02X} on the same input")

    flagged = 0
    trials = 10000
    for _ in range(trials):
        img = [random.randrange(256) for _ in range(255)]
        img.append(crc8_utility(img))      # byte 255 written by the utility
        # RTL: CRC over bytes 0..254 (byte 255 skipped), error = CRC != 0
        crc = 0
        for b in img[:255]:
            crc = crc8_rtl_step(b, crc)
        flagged += (crc != 0)
        assert crc == img[255]             # RTL value equals the stored CRC byte
    report("RTL flags correctly-programmed EEPROMs as CRC errors",
           None, f"{flagged}/{trials} random images written by eeprom_utility.py give "
                 f"eeprom_crc_err = 1 (expected ~255/256 = {trials*255/256:.0f}); "
                 f"RTL CRC always equals stored byte 255, so it should compare instead of test for 0")
    resid = 0
    for _ in range(trials):
        img = [random.randrange(256) for _ in range(255)]
        img.append(crc8_utility(img))
        crc = 0
        for b in img:                     # proposed fix: include byte 255 in the CRC
            crc = crc8_rtl_step(b, crc)
        resid += (crc != 0)
    report("Proposed fix: CRC over bytes 0..255 leaves residue 0 for valid images", resid == 0,
           f"{resid}/{trials} valid images give a non-zero residue (reflected CRC, init 0, no xorout)")


# ---------------------------------------------------------------------------
# 2. IPv4 checksum constant 0xC52D (dp_pkt_top.sv L1173-L1188, rx_ls_parser.sv L499-L514)
# ---------------------------------------------------------------------------
def check_c52d():
    report("0xC52D = 0x4500 + 0x4000 + 0x4011 + 28", 0x4500 + 0x4000 + 0x4011 + 28 == 0xC52D,
           f"sum = 0x{0x4500 + 0x4000 + 0x4011 + 28:04X}")
    bad = 0
    for _ in range(20000):
        src, dst = random.getrandbits(32), random.getrandbits(32)
        pld_len = random.randrange(0, 9000)        # dp_pkt: dma_len + 32/36; rx_ls: UDP payload
        tot_len = pld_len + 28
        hdr = [0x4500, tot_len, 0x0000, 0x4000, 0x4011, 0,
               src >> 16, src & 0xFFFF, dst >> 16, dst & 0xFFFF]
        ref = ipv4_checksum(hdr)
        # RTL: ~fold(src + dst + pld_len + 0xC52D), two end-around folds
        s = (src >> 16) + (src & 0xFFFF) + (dst >> 16) + (dst & 0xFFFF) + pld_len + 0xC52D
        s = (s & 0xFFFF) + (s >> 16)
        s = (s & 0xFFFF) + (s >> 16)
        rtl = (~s) & 0xFFFF
        hdr[5] = rtl
        bad += not ipv4_valid(hdr)
    report("dp_pkt_top / rx_ls_parser IPv4 checksum formula", bad == 0,
           f"{bad} invalid headers out of 20000 random (src, dst, length)")


# ---------------------------------------------------------------------------
# 3. roce_ack incremental IPv4 checksum (roce/roce_ack.sv L524-L538)
# ---------------------------------------------------------------------------
def roce_ack_rtl(chk, old_len, new_len=48):
    st1 = (chk + old_len - new_len) & 0x1FFFF   # 17-bit two's complement
    st2 = (st1 & 0xFFFF) + (st1 >> 16)
    return st2 & 0xFFFF


def check_roce_ack_chksum():
    bad, bad_borrow, borrow_cases, total = 0, 0, 0, 0
    example = None
    for _ in range(200000):
        ttl_proto = (random.randrange(1, 256) << 8) | 17
        ident = random.getrandbits(16)
        flags = random.choice([0x4000, 0x0000])
        dscp = random.choice([0x00, 0x02, 0x60])
        src, dst = random.getrandbits(32), random.getrandbits(32)
        old_len = random.choice([random.randrange(44, 60), random.randrange(60, 9000)])
        req = [0x4500 | dscp, old_len, ident, flags, ttl_proto, 0,
               src >> 16, src & 0xFFFF, dst >> 16, dst & 0xFFFF]
        req[5] = ipv4_checksum(req)
        ack = [0x4500 | dscp, 48, ident, flags, ttl_proto, 0,
               dst >> 16, dst & 0xFFFF, src >> 16, src & 0xFFFF]
        ack[5] = roce_ack_rtl(req[5], old_len)
        total += 1
        borrow = req[5] + old_len < 48
        borrow_cases += borrow
        if not ipv4_valid(ack):
            bad += 1
            bad_borrow += borrow
            if example is None:
                example = (req[5], old_len, ack[5], ipv4_checksum(ack[:5] + [0] + ack[6:]))
    report("roce_ack checksum: invalid results occur only in the borrow case",
           bad == bad_borrow, f"{bad} invalid of {total}; {bad_borrow} of them have chk + old_len < 48 "
                              f"({borrow_cases} borrow cases sampled)")
    # Exhaustive over the borrow region
    errs, region = 0, 0
    for chk in range(0, 48):
        for old_len in range(44, 48):
            if chk + old_len < 48:
                region += 1
                got = roce_ack_rtl(chk, old_len)
                want = (chk + old_len - 48 - 1) & 0xFFFF   # one's-complement end-around borrow
                diff = (got - want) & 0xFFFF
                errs += (diff != 0)
                assert diff in (0, 2)
    report("roce_ack checksum: borrow case is off by exactly 2", errs == region,
           f"exhaustive over chk + old_len < 48 with old_len 44..47: {errs}/{region} wrong, all by +2"
           + (f"; example chk=0x{example[0]:04X} old_len={example[1]} → RTL 0x{example[2]:04X}, "
              f"correct 0x{example[3]:04X}" if example else ""))


def roce_ack_fixed(chk, old_len, new_len=48):
    """Proposed fix (RFC 1624 eq. 3 form): chk + old_len + ~new_len with end-around carry."""
    s = chk + old_len + (0xFFFF ^ new_len)
    s = (s & 0xFFFF) + (s >> 16)
    s = (s & 0xFFFF) + (s >> 16)
    return s & 0xFFFF


def check_roce_ack_fix():
    bad = 0
    total = 0
    for old_len in list(range(44, 60)) + [random.randrange(60, 9000) for _ in range(200)]:
        for _ in range(300):
            src, dst = random.getrandbits(32), random.getrandbits(32)
            req = [0x4500, old_len, random.getrandbits(16), 0x4000, 0x4011, 0,
                   src >> 16, src & 0xFFFF, dst >> 16, dst & 0xFFFF]
            req[5] = ipv4_checksum(req)
            ack = req[:]
            ack[1] = 48
            ack[6:] = req[8:] + req[6:8]
            ack[5] = roce_ack_fixed(req[5], old_len)
            total += 1
            bad += not ipv4_valid(ack)
    # force the borrow region explicitly
    for chk in range(4):
        for old_len in (44, 45, 46, 47):
            if chk + old_len >= 48:
                continue
            got = roce_ack_fixed(chk, old_len)
            want = (chk + old_len - 48 - 1) & 0xFFFF
            bad += got != want
            total += 1
    report("Proposed roce_ack fix (18-bit one's-complement add) is always valid", bad == 0,
           f"{bad} invalid of {total} (random headers + exhaustive borrow region)")


# ---------------------------------------------------------------------------
# 4. Packetizer RAW10 / RAW12 schedules (packetizer_program.cpp, packetizer_top.sv)
# ---------------------------------------------------------------------------
def decode_pack_ctrl(v):
    return dict(ld_arr=v & 0xFFFF, pad=(v >> 16) & 1, duplicate=(v >> 17) & 1,
                max_addr=(v >> 20) & 0xF, latency=(v >> 24) & 0xF, enable=(v >> 28) & 1)


def check_raw_schedules():
    raw10 = decode_pack_ctrl(0x11F1FFF7)
    rows = raw10["max_addr"] + 1
    loads = sum((raw10["ld_arr"] >> r) & 1 for r in range(rows))
    report("RAW10 schedule 0x11F1FFF7: 15 of 16 rows read input → 120 B in, 128 B out",
           (rows, loads, loads * 8, rows * 8) == (16, 15, 120, 128),
           f"{raw10}; rows={rows}, loads={loads}, in={loads*8} B, out={rows*8} B (64-bit SIF)")
    # host get_output_size(): 1920 px RAW10 line
    line_in = 1920 * 10 // 8
    line_out = math.ceil(line_in / 120) * 128
    report("RAW10 1920 px line → 2560 B", line_out == 2560, f"{line_in} B in → {line_out} B out")
    raw12 = decode_pack_ctrl(0x11210007)
    rows = raw12["max_addr"] + 1
    loads = sum((raw12["ld_arr"] >> r) & 1 for r in range(rows))
    report("RAW12 schedule 0x11210007: every row reads input", loads == rows,
           f"{raw12}; rows={rows}, loads={loads}")


# ---------------------------------------------------------------------------
# 5. Packetizer RAM layout (packetizer.sv L69-L134) vs testbench pack_vp_ram_index()
# ---------------------------------------------------------------------------
ODD_EVEN_SIZE = [1, 1, 5, 19, 63, 191, 543, 1471, 3839, 9727, 24063, 58367, 139263]
ODD_EVEN_DEPTH = [1, 1, 3, 6, 10, 15, 21, 28, 36, 45, 55, 66, 78]


def clog2(n):
    return max(0, math.ceil(math.log2(n))) if n > 1 else 0


def odd_even_switches(n):
    """Count compare-exchange elements of Batcher's odd-even merge sort for n = 2^k inputs."""
    def merge(lo, n_, r):
        step = r * 2
        if step < n_:
            return merge(lo, n_, step) + merge(lo + r, n_, step) + \
                sum(1 for i in range(lo + r, lo + n_ - r, step))
        return 1

    def sort(lo, n_):
        if n_ > 1:
            m = n_ // 2
            return sort(lo, m) + sort(lo + m, m) + merge(lo, n_, 1)
        return 0
    return sort(0, n)


def check_packetizer_layout(root):
    pkg = (Path(root) / "fpga/nv_hsb_ip/packetizer/packetizer.sv").read_text()
    ok_tab = all(odd_even_switches(2 ** k) == ODD_EVEN_SIZE[k] for k in range(1, 11))
    report("ODD_EVEN_SIZE table = Batcher odd-even merge sort comparator counts", ok_tab,
           "n = 2..1024: " + ", ".join(str(odd_even_switches(2 ** k)) for k in range(1, 11)))
    rows = []
    for name, din, res, vp, nc, vpc in [("CPNX100 SIF0/1", 64, 2, 64, 3, 2),
                                        ("NV MIPI ref", 64, 2, 64, 3, 1),
                                        ("Terasic S10 (default VP_SIZE 128)", 512, 16, 128, 1, 4)]:
        i = clog2(din) - clog2(res)
        sort_w = ODD_EVEN_SIZE[i] * nc
        clear_w = (din // res) * clog2(nc + 1)
        vp_w = (2 if din == vp else clog2(din // vp) + 1) * vpc
        n = [(w - 1) // 32 + 1 for w in (clear_w, sort_w, vp_w)]
        rows.append(f"{name}: CLEAR/SORT/VP = {n[0]}/{n[1]}/{n[2]} RAMs, total {sum(n)}, "
                    f"{sum(n)*16} writes, pipe {(ODD_EVEN_DEPTH[i]-1)//3}")
    report("Packetizer RAM layout per board (formulas from packetizer.sv)", None, "; ".join(rows))


# ---------------------------------------------------------------------------
# 6. Header sizes / beats (dp_pkt_hdr.sv) and ICRC last-beat lengths (roce_icrc.sv)
# ---------------------------------------------------------------------------
def check_headers():
    sizes = {"RoCE 000": 560, "CoE ?01": 368, "RoCE md 010": 560 + 32 + 1024,
             "CoE md ?11": 368 + 1024, "RoCE+Imm 100": 592}
    rows = [f"{k}: {b//8} B, 64-bit {math.ceil(b/64)} beats, 512-bit {math.ceil(b/512)} beats"
            for k, b in sizes.items()]
    report("dp_pkt_hdr header sizes", sizes["RoCE 000"] == 70 * 8 and sizes["CoE ?01"] == 46 * 8,
           "; ".join(rows))
    eth, ip, udp, bth, reth, imm, aeth = 14, 20, 8, 12, 16, 4, 4
    lens = {"WRITE (n pages)": eth + ip + udp + bth + reth - 6,
            "WRITE+Imm": eth + ip + udp + bth + reth + imm - 6,
            "WRITE+Imm 32 B frame": eth + ip + udp + bth + reth + imm + 32 - 6,
            "ACK": eth + ip + udp + bth + aeth - 6}
    rows = [f"{k}: {v} B → last beat {v % 8 or 8} (64-bit) / {v % 64 or 64} (512-bit)"
            for k, v in lens.items()]
    report("ICRC coverage lengths after dropping 6 B (payload multiples of 128 B)", None, "; ".join(rows))


# ---------------------------------------------------------------------------
# 7. lfsr_hc 8-bit equations = reflected CRC-32 byte step (roce/lfsr_hc.sv)
# ---------------------------------------------------------------------------
def check_lfsr(root):
    src = (Path(root) / "fpga/nv_hsb_ip/roce/lfsr_hc.sv").read_text()
    block = src[src.index("if (DATA_WIDTH==8)"):]
    block = block[:block.index("end")]
    eqs = {}
    for m in re.finditer(r"assign lfsr_c\[(\d+)\] = ([^;]+);", block):
        terms = [t.strip() for t in m.group(2).split("^")]
        eqs[int(m.group(1))] = ([int(t[7:-1]) for t in terms if t.startswith("lfsr_q")],
                                [int(t[4:-1]) for t in terms if t.startswith("din")])

    def step_eq(state, din):
        out = 0
        for bit, (qs, ds) in eqs.items():
            v = 0
            for q in qs:
                v ^= (state >> q) & 1
            for d in ds:
                v ^= (din >> d) & 1
            out |= v << bit
        return out

    def rev(x, w):
        return int(f"{x:0{w}b}"[::-1], 2)

    def wrapper(state, data):            # lfsr_hc.sv: lfsr_q/din reversed, lfsr_c reversed back
        return rev(step_eq(rev(state, 32), rev(data, 8)), 32)

    def crc32_reflected_byte(state, b):  # standard Ethernet CRC-32 byte step (poly 0xEDB88320)
        state ^= b
        for _ in range(8):
            state = (state >> 1) ^ 0xEDB88320 if state & 1 else state >> 1
        return state

    mism = 0
    for _ in range(5000):
        s, b = random.getrandbits(32), random.getrandbits(8)
        mism += wrapper(s, b) != crc32_reflected_byte(s, b)
    report("lfsr_hc DATA_WIDTH=8 with module bit reversal = reflected CRC-32 (Ethernet) byte step",
           mism == 0 and len(eqs) == 32, f"{len(eqs)} equations parsed; {mism} mismatches in 5000 random steps")


# ---------------------------------------------------------------------------
# 8. Misc numbers used in the docs
# ---------------------------------------------------------------------------
def check_misc():
    u = 2 ** -24
    t_clk = 1e9 / 100.446545e6
    ppb = u / t_clk * 1e9
    report("DPLL fa unit at 100.446545 MHz ≈ 6 ppb", 5.5 < ppb < 6.5, f"{ppb:.2f} ppb; range ±2^23 units = ±{2**23*ppb/1e7:.2f} %")
    pi = (19335 * 256) // 100446  # streaming_cdc PHASE_INCREMENT with 99 % target
    report("streaming_cdc PTP→APB phase increment", None,
           f"PHASE_INCREMENT = {pi}, write rate = {pi/256*100.446545:.2f} MHz < 19.53 MHz")
    scl = 19.53125e6 / (2 * 25)
    report("I2C clk_cnt 0x19 at 19.53 MHz", None, f"f_SCL = {scl/1e3:.0f} kHz")
    for mtu in (1500, 4096):
        p = (mtu - 74) // 128 * 128
        report(f"RoCE payload/efficiency at MTU {mtu}", None,
               f"payload {p} B ({p//128} pages), wire {p+98} B, efficiency {p/(p+98)*100:.1f} %")


def check_flow_example():
    """docs/flow.md §6: 1920x1080 RAW10, MTU 1500."""
    line = math.ceil(1920 * 10 // 8 / 120) * 128
    frame = line * 1080
    pay = (1500 - 74) // 128 * 128
    n = math.ceil(frame / pay)
    last = frame - (n - 1) * pay
    ok = (line, frame, pay, n, last) == (2560, 2764800, 1408, 1964, 896)
    report("flow.md worked example (1920x1080 RAW10, MTU 1500)", ok,
           f"line {line} B, frame {frame} B, payload {pay} B, {n} packets, last {last} B ({last//128} pages), "
           f"IPv4 total length {pay + 60}")


def main(root):
    check_eeprom_crc()
    check_c52d()
    check_roce_ack_chksum()
    check_roce_ack_fix()
    check_raw_schedules()
    check_packetizer_layout(root)
    check_headers()
    check_lfsr(root)
    check_misc()
    check_flow_example()
    print("\nFAILED: " + (", ".join(FAILED) if FAILED else "none"))
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../holoscan-sensor-bridge")
