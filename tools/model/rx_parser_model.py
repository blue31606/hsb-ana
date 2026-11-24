#!/usr/bin/env python3
"""Cycle model of the rx_parser input path (store-and-forward buffer + metadata FIFOs + readout).

This is NOT a simulator run of the RTL. It re-implements, register by register, the logic
that decides when beats and packet metadata enter and leave rx_parser, so that questions
like "does readout keep up with line rate" and "what happens after the input FIFO drops
a tlast beat" can be answered by running the logic instead of by inspection.

Modelled exactly (upstream commit 41cecaa):
  misc/sc_fifo.sv              wr_en = wr & ~full, rd_en = rd & ~empty, registered
                               empty/full computed from the *current* count (L108-L159),
                               dout/dval one cycle after rd_en, depth rounded to 2^n (L43)
  lib_axis/axis_buffer.sv      single clock, WAIT2SEND = 1, NO_BACKPRESSURE = 1, OUTPUT_SKID = 0:
                               gbx_axis_tready = 1, in_pkt_cnt counts every written tlast
                               (L266), out_pkt_cnt / clear_to_send (L270-L313), cdc hold
                               (L243-L249), fifo_rden / prefetch (L323-L325), axis_reg SKID=0
  lib_axis/axis_reg.sv         load = !r_valid || tready
  rx_parser/rx_parser.sv       INP_FIFO_DEPTH / META_FIFO_DEPTH (L126-L132), hdr / ipv4 / fcs
                               FIFOs (L380-L420, L566-L585), hdr_ready / buf_axis_tready /
                               hdr_rden (L712-L726), w_buf_axis_tready (L737)

  axis_to_vec / proc_pipeline   with i_done tied to 1 (rx_parser.sv L228) o_valid is a
                               one-cycle pulse the cycle after the beat with cnt == D_CYCLES-1
                               (A2V_WAIT, or early_pkt_r when tlast comes first); proc_pipeline[0]
                               registers it, so hdr_buffer is written 2 cycles after that beat and
                               ipv4_buffer 4 cycles later (proc_pipeline[4]) (v7.1: exact, was
                               an approximation in v7)

Approximated:
  MAC                          beats of one frame are contiguous; next frame starts when the
                               previous one has used its wire time (frame + FCS + 20 byte
                               preamble/IFG) at the given line rate.
  ENABLE_ROCE_ACK = 0          ack_empty = 0, as on every shipped board.

Usage:
  python3 tools/model/rx_parser_model.py            # run all scenarios
  python3 tools/model/rx_parser_model.py --wave docs/timing/rx_parser_readout.wave.json
Exit code 1 if a scenario's expectation is violated.
"""
import math
import sys
from collections import deque

HDR_BYTES = 58  # rx_parser.sv L106 with VLAN enabled


class ScFifo:
    """misc/sc_fifo.sv, RST_SYNC = TRUE, state just after reset has been released."""

    def __init__(self, depth, almost_full=None):
        self.depth = 2 ** math.ceil(math.log2(depth))
        self.almost_full = almost_full if almost_full is not None else depth - 4
        self.mem = deque()
        self.empty = True
        self.full = False
        self.afull = False
        self.dout = None
        self.dval = False
        self.overflows = 0
        self.max_count = 0

    def step(self, wr, din, rd):
        """One clock edge. Flags are evaluated on the pre-edge count, as in the RTL."""
        cnt = len(self.mem)
        wr_en = wr and not self.full
        rd_en = rd and not self.empty
        if wr and self.full:
            self.overflows += 1
        empty_n = rd if cnt == 1 else (cnt == 0)
        full_n = wr if cnt == self.depth - 1 else (cnt == self.depth)
        self.dval = rd_en
        if rd_en:
            self.dout = self.mem.popleft()
        if wr_en:
            self.mem.append(din)
        self.afull = cnt > self.almost_full - 1
        self.empty, self.full = empty_n, full_n
        self.max_count = max(self.max_count, len(self.mem))
        return wr_en


class RxParser:
    def __init__(self, width, mtu):
        self.width = width
        kw = width // 8
        pkt_depth = (mtu + kw - 1) // kw
        inp = pkt_depth * 3 if width >= 256 else pkt_depth * 2
        meta = 8 if width < 32 else 31
        self.data = ScFifo(inp)
        self.hdr = ScFifo(meta)
        self.ipv4 = ScFifo(meta)
        self.fcs = ScFifo(meta)
        self.d_cycles = (HDR_BYTES * 8 - 1) // width + 1
        # axis_buffer state
        self.in_pkt_cnt = 0
        self.out_pkt_cnt = 0
        self.clear_to_send = False
        self.hold = False
        self.r_valid = False
        self.r_beat = None
        # readout state
        self.bt = False          # buf_axis_tready
        self.hr = False          # hdr_ready
        # bookkeeping
        self.meta_events = {}    # cycle -> list of (fifo, pkt_id)
        self.cur_meta = None
        self.mismatch = 0
        self.first_mismatch = None
        self.out_pkts = []       # (pkt_id_of_metadata, pkt_id_of_data_eop, cycle of eop)
        self.trace = None        # set to [] to record per-cycle signals
        self.bubbles = []        # cycles where buf_axis_tready = 1 but no beat is valid (mid-packet gap)
        self.cycle = 0

    def schedule_meta(self, start, nbeats, pid):
        k = min(self.d_cycles - 1, nbeats - 1)
        self.meta_events.setdefault(start + k + 2, []).append(("hdr", pid))
        self.meta_events.setdefault(start + k + 6, []).append(("ipv4", pid))
        self.meta_events.setdefault(start + nbeats - 1, []).append(("fcs", pid))

    def step(self, in_beat, stall):
        """in_beat: None or (pkt_id, last, is_btx). stall: downstream bridge not ready."""
        t = self.cycle
        # ---- combinational, from registered state ----
        cur_btx = self.r_beat[2] if self.r_valid else False
        tx_ready = self.bt and (not stall or not cur_btx)          # w_buf_axis_tready
        cdc_valid = self.data.dval or self.hold
        cdc_beat = self.data.dout
        cdc_ready = (not self.r_valid) or tx_ready                  # axis_reg SKID=0 load
        done = cdc_valid and cdc_beat[1] and cdc_ready
        prefetch = ((not self.hold) and (not cdc_valid)) or cdc_ready
        rden = (not self.data.empty) and self.clear_to_send and prefetch and not done
        out_nxt = self.out_pkt_cnt + done
        pkt_avail = self.in_pkt_cnt != out_nxt
        accept = self.r_valid and tx_ready
        eop = accept and self.r_beat[1]
        hdr_rden = self.hr and not self.bt
        meta_empty = self.hdr.empty or self.ipv4.empty or self.fcs.empty
        # data / metadata pairing check on accepted beats
        if accept:
            if self.r_beat[0] != self.cur_meta:
                self.mismatch += 1
                if self.first_mismatch is None:
                    self.first_mismatch = (t, self.cur_meta, self.r_beat[0])
            if eop:
                self.out_pkts.append((self.cur_meta, self.r_beat[0], t))
        elif self.bt and not self.r_valid:
            self.bubbles.append(t)
        if self.trace is not None:
            ev_now = [f for f, _ in self.meta_events.get(t, [])]
            self.trace.append(dict(
                in_valid=in_beat is not None, in_last=bool(in_beat and in_beat[1]),
                hdr_wr="hdr" in ev_now, fcs_wr="fcs" in ev_now, ipv4_wr="ipv4" in ev_now,
                hdr_ready=self.hr, hdr_rden=hdr_rden, buf_tready=self.bt,
                buf_tvalid=accept, buf_tlast=eop,
                out_id=self.r_beat[0] if accept else None))
        # ---- clock edge ----
        wr = in_beat is not None
        self.data.step(wr, in_beat, rden)
        if wr and in_beat[1]:
            self.in_pkt_cnt += 1                                    # axis_buffer L266: not gated by full
        ev = dict((f, p) for f, p in self.meta_events.pop(t, []))
        hdr_head = self.hdr.mem[0] if (hdr_rden and not self.hdr.empty) else None
        self.hdr.step("hdr" in ev, ev.get("hdr"), hdr_rden)
        self.ipv4.step("ipv4" in ev, ev.get("ipv4"), hdr_rden)
        self.fcs.step("fcs" in ev, ev.get("fcs"), hdr_rden)
        if hdr_rden:
            self.cur_meta = hdr_head
        if self.r_valid is False or tx_ready:
            self.r_valid, self.r_beat = cdc_valid, cdc_beat
        self.hold = cdc_valid and not cdc_ready
        self.out_pkt_cnt = out_nxt
        self.clear_to_send = pkt_avail
        self.bt = (not eop) if self.bt else self.hr
        self.hr = (not meta_empty) and not hdr_rden
        self.cycle += 1


def traffic(width, f_mhz, rate_gbps, sizes, btx=False, offset=20):
    """Yield (start_cycle, nbeats, pkt_id, is_btx); frames back to back at line rate."""
    bpc = rate_gbps * 1e9 / 8 / (f_mhz * 1e6)       # wire bytes per HIF clock
    kw = width // 8
    t = float(offset)
    for pid, size in enumerate(sizes):
        size = max(size, 60)
        n = -(-size // kw)
        start = math.ceil(t)
        yield start, n, pid, btx
        t = max(start + n, t + (size + 4 + 20) / bpc)


def run(width, mtu, f_mhz, rate_gbps, sizes, btx=False, stall=lambda t: False, tail=20000):
    rp = RxParser(width, mtu)
    pkts = list(traffic(width, f_mhz, rate_gbps, sizes, btx))
    beats = {}
    for start, n, pid, b in pkts:
        rp.schedule_meta(start, n, pid)
        for i in range(n):
            beats[start + i] = (pid, i == n - 1, b)
    end = max(beats) + tail
    for t in range(end):
        rp.step(beats.get(t), stall(t))
    in_period = (pkts[-1][0] - pkts[0][0]) / (len(pkts) - 1) if len(pkts) > 1 else 0
    outs = rp.out_pkts
    out_period = ((outs[-1][2] - outs[len(outs) // 2][2]) / (len(outs) - 1 - len(outs) // 2)
                  if len(outs) > 2 else 0)
    return rp, in_period, out_period


def readout_cycles_per_packet(width, nbeats):
    """Steady-state readout period when the buffer is backlogged (measured from the model)."""
    size = nbeats * width // 8
    depth = RxParser(width, 4096).data.depth
    count = min(25, depth // nbeats - 1)
    # Fill the buffer while the (bridge) output is stalled, then release it and time the drain.
    rp, _, _ = run(width, 4096, 1e6, 1e6, [size] * count, btx=True,
                   stall=lambda t: t < 3000)
    assert rp.data.overflows == 0 and rp.hdr.overflows == 0 and len(rp.out_pkts) == count
    ts = [c for _, _, c in rp.out_pkts]
    return (ts[-1] - ts[1]) / (len(ts) - 2)


class BridgeHifRxBuffer:
    """bridge_pkt_proc.sv L184-L206: axis_buffer with default BUF_DEPTH = 256,
    ALMOST_FULL_DEPTH = 224, NO_BACKPRESSURE = 0, WAIT2SEND = 1, and o_axis_rx_tready
    left unconnected (L199). Upstream never sees the buffer's back-pressure, so a beat
    offered while gbx_axis_tready = 0 is simply not written (fifo_wren = valid && tready)."""

    def __init__(self):
        self.f = ScFifo(256, almost_full=256 * 7 // 8)
        self.gbx_tready = False      # reset value 0, then !afull
        self.in_pkt_cnt = 0
        self.out_pkt_cnt = 0
        self.cts = False
        self.hold = False
        self.r_valid = False
        self.r_beat = None
        self.dropped = 0
        self.out = []                # (pkt ids seen in the frame, cycle)
        self.cur = []

    def step(self, beat):
        cdc_valid = self.f.dval or self.hold
        cdc_beat = self.f.dout
        cdc_ready = True             # axis_reg SKID=1 with downstream always ready (best case)
        done = cdc_valid and cdc_beat[1] and cdc_ready
        prefetch = ((not self.hold) and (not cdc_valid)) or cdc_ready
        rden = (not self.f.empty) and self.cts and prefetch and not done
        out_nxt = self.out_pkt_cnt + done
        avail = self.in_pkt_cnt != out_nxt
        wren = beat is not None and self.gbx_tready
        if beat is not None and not self.gbx_tready:
            self.dropped += 1
        if cdc_valid:
            self.cur.append(cdc_beat[0])
            if cdc_beat[1]:
                self.out.append(sorted(set(self.cur)))
                self.cur = []
        self.f.step(wren, beat, rden)
        if wren and beat[1]:
            self.in_pkt_cnt += 1
        self.gbx_tready = not self.f.afull
        self.hold = cdc_valid and not cdc_ready
        self.out_pkt_cnt = out_nxt
        self.cts = avail


def run_bridge(sizes, gap=12):
    b = BridgeHifRxBuffer()
    t = 5
    beats = {}
    for pid, size in enumerate(sizes):
        n = -(-size // 8)
        for i in range(n):
            beats[t + i] = (pid, i == n - 1)
        t += n + gap
    for c in range(t + 2000):
        b.step(beats.get(c))
    return b


def wave_json(path):
    """Write docs/timing/rx_parser_readout.wave.json from a model trace: two back-to-back
    10-beat packets at HOST_WIDTH = 64, readout not stalled."""
    import json
    rp = RxParser(64, 4096)
    rp.trace = []
    beats = {}
    start = 1
    for pid in range(2):
        for i in range(10):
            beats[start + i] = (pid, i == 9, False)
            rp.schedule_meta(start, 10, pid)  if i == 0 else None
        start += 10
    for t in range(44):
        rp.step(beats.get(t), False)
    tr = rp.trace

    def w(key):
        out, prev = "", None
        for c in tr:
            v = "1" if c[key] else "0"
            out += "." if v == prev else v
            prev = v
        return out

    def data_wave():
        out, labels, prev = "", [], "x"
        for c in tr:
            pid = c["out_id"]
            cur = "x" if pid is None else pid
            if cur == prev:
                out += "."
            elif pid is None:
                out += "x"
            else:
                out += "="
                labels.append(f"P{pid}")
            prev = cur
        return out, labels

    dw, labels = data_wave()
    spec = {
        "title": "rx_parser：兩個背靠背 10-beat 封包（HOST_WIDTH=64），由 tools/model/rx_parser_model.py 逐拍模型產生",
        "signal": [
            {"name": "clk", "wave": "p" * len(tr)},
            {"name": "i_axis_rx_tvalid", "wave": w("in_valid")},
            {"name": "i_axis_rx_tlast", "wave": w("in_last")},
            {"name": "hdr_buffer.wr (pp[0])", "wave": w("hdr_wr")},
            {"name": "fcs_buffer.wr", "wave": w("fcs_wr")},
            {"name": "ipv4_buffer.wr (pp[4])", "wave": w("ipv4_wr")},
            {"name": "hdr_ready", "wave": w("hdr_ready")},
            {"name": "hdr_rden", "wave": w("hdr_rden")},
            {"name": "buf_axis_tready", "wave": w("buf_tready")},
            {"name": "buf_axis_tvalid", "wave": w("buf_tvalid")},
            {"name": "buf_axis_tlast", "wave": w("buf_tlast")},
            {"name": "packet", "wave": dw, "data": labels},
        ],
    }
    with open(path, "w") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)
        f.write("\n")


FAILS = []


def check(name, ok, detail, quiet=False):
    tag = "PASS" if ok else "FAIL"
    if not ok:
        FAILS.append(name)
    print(f"[{tag}] {name}\n        {detail}")


def main():
    quiet = "--quiet" in sys.argv
    if "--wave" in sys.argv:
        wave_json(sys.argv[sys.argv.index("--wave") + 1])
        return 0

    # 1. Readout cost per packet when backlogged: n beats + gap.
    gaps = {}
    for w, ns in ((64, (8, 9, 24, 188)), (512, (1, 2, 8, 24))):   # 64-bit: >= 60-byte frames
        for n in ns:
            gaps[(w, n)] = readout_cycles_per_packet(w, n) - n
    g = sorted(set(round(v, 3) for v in gaps.values()))
    check("rx_parser backlogged readout = n + 1 cycles per packet",
          g == [1.0], f"gap cycles per (width, beats): {gaps}")

    # 2. Line-rate minimum-size frames per board.
    boards = [("CPNX100 / NV MIPI / MPF200", 64, 4096, 156.25, 10, True),
              ("MPF200 (MTU 1500)", 64, 1500, 156.25, 10, True),
              ("Terasic S10", 512, 4096, 201.42, 100, False),
              ("PYNQ RFSoC", 512, 4096, 322.27, 100, True)]
    for name, w, mtu, f, r, expect_ok in boards:
        rp, ip, op = run(w, mtu, f, r, [60] * 5000)
        ovf = rp.data.overflows + rp.hdr.overflows + rp.ipv4.overflows + rp.fcs.overflows
        ok = (ovf == 0 and rp.mismatch == 0) == expect_ok
        check(f"60-byte frames at {r}G line rate, {name}",
              ok,
              f"input period {ip:.2f} cyc, readout period {op:.2f} cyc; overflow data/hdr/ipv4/fcs = "
              f"{rp.data.overflows}/{rp.hdr.overflows}/{rp.ipv4.overflows}/{rp.fcs.overflows}; "
              f"max count data {rp.data.max_count}/{rp.data.depth}, hdr {rp.hdr.max_count}/{rp.hdr.depth}; "
              f"mismatched beats {rp.mismatch}")

    # 3. Sustained 100G on the 512-bit boards: readout needs n + 1 cycles per frame,
    #    the MAC delivers one frame every max(n, (frame + 24) / bytes-per-cycle) cycles.
    #    For each size: periods, and how many back-to-back frames fit before the first overflow.
    for name, f in (("Terasic S10", 201.42), ("PYNQ RFSoC", 322.27)):
        rows = []
        for size in (60, 64, 128, 256, 512, 1024, 1500, 2048, 4000):
            nfr = 5000
            rp, ip, op = run(512, 4096, f, 100, [size] * nfr, tail=2000)
            first = None
            if rp.data.overflows or rp.hdr.overflows or rp.fcs.overflows or rp.ipv4.overflows:
                # rerun with fewer frames to find the burst length that still fits
                lo, hi = 1, nfr
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    r2, _, _ = run(512, 4096, f, 100, [size] * mid, tail=2000)
                    if r2.data.overflows + r2.hdr.overflows + r2.fcs.overflows + r2.ipv4.overflows:
                        hi = mid - 1
                    else:
                        lo = mid
                first = lo
            need = -(-max(size, 60) // 64) + 1
            rows.append(f"{size} B: MAC delivers one every {ip:.2f} cyc, readout needs {need}, "
                        + (f"overflows after {first} frames" if first else f"no overflow in {nfr}"))
        print(f"[RESULT] back-to-back frames at 100G, {name}\n        " + "\n        ".join(rows))

    # 4. DP-1: a stall that overflows the input FIFO in the middle of a packet.
    #    Bridge-mode broadcast traffic (is_btx), 1500-byte frames at 10G, readout stalled 2000 cycles,
    #    then 60 more frames long after the stall has ended.
    rp, _, _ = run(64, 4096, 156.25, 10, [1500] * 120, btx=True,
                   stall=lambda t: 200 <= t < 2200)
    late = [(m, d) for m, d, c in rp.out_pkts if c > 12000]
    late_bad = sum(1 for m, d in late if m != d)
    late_bubbles = sum(1 for c in rp.bubbles if c > 12000)
    check("DP-1 dropped beats break data/metadata pairing permanently",
          rp.data.overflows > 0 and late and late_bad == len(late)
          and rp.in_pkt_cnt - rp.out_pkt_cnt >= 1,
          f"input FIFO overflow beats {rp.data.overflows}; first mismatch (cycle, meta id, data id) "
          f"{rp.first_mismatch}; in_pkt_cnt - out_pkt_cnt after drain = {rp.in_pkt_cnt - rp.out_pkt_cnt}; "
          f"frames read out after cycle 12000 (stall ended at 2200): {len(late)}, with wrong metadata: "
          f"{late_bad}, mid-packet output bubbles: {late_bubbles}")

    # 5. Same stall, but the FIFO never fills (shorter stall): no damage.
    rp, _, _ = run(64, 4096, 156.25, 10, [1500] * 60, btx=True,
                   stall=lambda t: 200 <= t < 600)
    check("DP-1 control: stall shorter than the FIFO headroom causes no damage",
          rp.data.overflows == 0 and rp.mismatch == 0 and rp.in_pkt_cnt == rp.out_pkt_cnt
          and not rp.bubbles,
          f"overflow {rp.data.overflows}, mismatched beats {rp.mismatch}, packets out {len(rp.out_pkts)}, "
          f"mid-packet bubbles {len(rp.bubbles)}")

    # 6. BR-1: bridge host RX buffer, 64-bit. One 2000-byte frame (250 beats > 224), then 1500-byte frames.
    b = run_bridge([200, 1500, 2000] + [1500] * 20)
    check("BR-1 frame longer than ALMOST_FULL kills the bridge host-RX path",
          b.out == [[0], [1]] and b.dropped > 0,
          f"frames out (ids): {b.out}; beats offered but not written: {b.dropped}; "
          f"FIFO count stuck at {len(b.f.mem)}")
    b = run_bridge([1500] * 23)
    check("BR-1 control: 1500-byte frames pass",
          len(b.out) == 23 and b.dropped == 0, f"frames out {len(b.out)}, dropped beats {b.dropped}")

    print("\nFAILED: " + (", ".join(FAILS) if FAILS else "none"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
