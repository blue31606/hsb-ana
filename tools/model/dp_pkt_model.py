#!/usr/bin/env python3
"""Cycle model of the dp_pkt_top header FSM and packet hand-off (performance §3).

Re-implements, register by register, the part of fpga/nv_hsb_ip/dp_pkt at commit 41cecaa
that decides when the next data packet can start on a host port:

  dp_pkt_top.sv
    sif_req / hif_mask / hif_reserved / hif_sif_mask fairness   L646-L700
    rrarb VP arbitration (round robin, grants only while IDLE)   L713-L736
    ROCE FSM IDLE / LOAD_STS / GRANT / CALC / STORE / HDR_WAIT   L776-L917
      (BUFFER_4K_REG = 1 as instantiated by HOLOLINK_top: DUMP_CLK_CYCLES = 7)
    commit handshake: at_commit_point, pkt_len_en_stall,
      commit_arm_comb, commit_pending_r, pkt_commit, fsm_cnt_hold L586-L645, L931-L963
    hif_busy / hif_preempt / hif_data_en                         L646-L680
    header + payload stitch, dp_axis_tready                      L1432-L1497
  dp_pkt.sv
    pkt_active / pkt_cnt / near_pkt_end / hif_not_busy_soon      L90-L170
  dp_pkt_hdr.sv
    vec FSM (IDLE / SEND / LAST, rising-edge trigger), axis_reg  L130-L252

Assumptions (stated, not modelled):
  - downstream of dp_pkt_top (roce_icrc, eth_pkt, MAC) is always ready; their fixed
    latency and the extra ICRC beat are not part of the gap measured here
  - cfg_ram_rd_valid = 1 (no APB access to the configuration RAM during streaming)
  - every VP always has data (i_axis_tvalid = 1), frames are long (no EOF / metadata),
    md_disable = 0; the first packet of each VP reads all 18 words (is_first_run)
  - RoCE header (70 bytes): 9 beats at 64 bit, 2 beats at 512 bit

The gap reported is the number of idle cycles on dout (dp_pkt_top's per-host output)
between the tlast of one packet and the first beat of the next.

Usage:  python3 tools/model/dp_pkt_model.py
Exit code 1 if an expectation is violated.
"""
import sys

IDLE, LOAD_STS, GRANT, CALC, STORE, HDR_WAIT = range(6)
DUMP = 7                      # DUMP_CLK_CYCLES with BUFFER_4K_REG = 1
CYCLES_AHEAD, MIN_OVERLAP = 10, 8


class HdrGen:
    """dp_pkt_hdr: vec FSM + axis_reg (SKID = 1), downstream always ready."""

    def __init__(self, beats):
        self.H = beats
        self.r_trigger = False
        self.state = "IDLE"
        self.cnt = 0
        self.data_is_zero = True
        self.r_busy = False
        self.is_valid = False
        self.is_last_r = False
        self.o_valid = False
        self.o_last = False

    @property
    def busy(self):
        return self.r_busy or self.o_valid

    def step(self, trigger):
        tready = True
        is_last = (self.H == 1) if self.state == "IDLE" else (self.cnt == self.H - 2)
        # axis_reg: output takes the registered input when it can load
        o_valid_n, o_last_n = self.is_valid, self.is_last_r and self.is_valid
        cnt_n = 0 if self.data_is_zero else self.cnt + tready
        st, busy, dz, val, il = self.state, self.r_busy, self.data_is_zero, self.is_valid, self.is_last_r
        if self.state == "IDLE":
            if trigger and not self.r_trigger:
                st, busy, dz, val, il = ("LAST" if is_last else "SEND"), True, False, True, is_last
        elif self.state == "SEND":
            if tready:
                st, il = ("LAST" if is_last else "SEND"), is_last
        elif self.state == "LAST":
            st, busy, dz, val, il = "IDLE", False, True, False, False
        self.r_trigger = trigger
        self.state, self.r_busy, self.data_is_zero, self.is_valid, self.is_last_r = st, busy, dz, val, il
        self.cnt = cnt_n
        self.o_valid, self.o_last = o_valid_n, o_last_n


class DpPkt:
    """dp_pkt: one per host."""

    def __init__(self):
        self.active = False
        self.cnt = 1
        self.len = 0
        self.near = False
        self.soon = False

    def step(self, len_en, plen, tready):
        accepted = self.active and tready
        last = accepted and self.cnt == self.len
        near_n = (self.active and self.len >= MIN_OVERLAP and (self.len - self.cnt) < CYCLES_AHEAD)
        soon_n = self.active and self.near
        if self.active:
            if tready:
                if self.cnt == self.len:
                    self.active, self.cnt = False, 1
                else:
                    self.cnt += 1
        else:
            self.cnt = 1
            if len_en:
                self.active, self.len = True, plen
        self.near, self.soon = near_n, soon_n
        return accepted, last


class DpPktTop:
    def __init__(self, n_host, hdr_beats, payload_beats):
        self.N = n_host                      # one VP per host, vp_mask[h] = 1 << h
        self.P = payload_beats
        self.hdr = HdrGen(hdr_beats)
        self.dp = [DpPkt() for _ in range(n_host)]
        self.state = IDLE
        self.fsm_cnt = 0
        self.cnt_max = 0
        self.target = 0
        self.gnt_r = None                    # granted VP (= host)
        self.pending = False
        self.sif_req = [False] * n_host
        self.hif_busy = [False] * n_host
        self.hif_preempt = [False] * n_host
        self.hif_data_en = [False] * n_host
        self.sif_mask = [False] * n_host     # hif_sif_mask[h][h]
        self.unserved = [False] * n_host
        self.served = [False] * n_host
        self.first_run = [True] * n_host
        self.rr_last = n_host - 1
        self.hdr_trigger = False
        self.len_en = [False] * n_host
        self.dp_r_valid = [False] * n_host
        self.dp_r_last = [False] * n_host
        self.cycle = 0
        self.dout = [[] for _ in range(n_host)]   # per host: list of (cycle, is_first, is_last)
        self.in_pkt = [False] * n_host

    def step(self):
        t = self.cycle
        N = self.N
        h = self.gnt_r
        # ---- combinational ----
        reserved = [self.hif_preempt[i] or (self.hif_busy[i] and not self.dp[i].soon) for i in range(N)]
        hif_mask = [(not reserved[i]) and not self.sif_mask[i] for i in range(N)]
        acp = self.state == CALC and self.fsm_cnt == self.target
        stall = acp and self.hif_busy[h]
        arm = acp and not stall and not self.pending
        commit = self.pending and not self.hif_busy[h]
        hold = stall or arm or (self.pending and not commit)
        # rrarb, grants only while IDLE
        gnt = None
        if self.state == IDLE and any(self.sif_req):
            for k in range(1, N + 1):
                c = (self.rr_last + k) % N
                if self.sif_req[c]:
                    gnt = c
                    break
        # dout per host (header goes to the granted host)
        dout_last = [False] * N
        dp_tready = [False] * N
        hdr_valid, hdr_last = self.hdr.o_valid, self.hdr.o_last
        for i in range(N):
            if i == h and hdr_valid:              # HDR + Data
                v = self.dp_r_valid[i] or self.dp[i].active
                dp_tready[i] = hdr_last
                if v:
                    self.dout[i].append((t, not self.in_pkt[i], False))
                    self.in_pkt[i] = True
            else:                                 # steady state data
                dp_tready[i] = self.hif_data_en[i]
                if self.dp_r_valid[i]:
                    dout_last[i] = self.dp_r_last[i]
                    self.dout[i].append((t, not self.in_pkt[i], dout_last[i]))
                    self.in_pkt[i] = not dout_last[i]
        # ---- registers ----
        nxt = {}
        # dp_pkt and the payload register in front of dout
        for i in range(N):
            acc, last = self.dp[i].step(self.len_en[i], self.P, dp_tready[i])
            if dp_tready[i]:
                self.dp_r_valid[i], self.dp_r_last[i] = acc, last
        hdr_busy_before = self.hdr.busy
        self.hdr.step(self.hdr_trigger)
        # hif_* registers
        for i in range(N):
            self.hif_busy[i], busy_old = ((True if (commit and i == h) else
                                           (not dout_last[i]) if self.hif_busy[i] else False),
                                          self.hif_busy[i])
            if commit and i == h:
                self.hif_preempt[i] = False
            elif gnt is not None and i == gnt and busy_old:
                self.hif_preempt[i] = True
            self.hif_data_en[i] = busy_old if self.hif_data_en[i] else (i == h and hdr_busy_before)
        sif_gnt_r_vec = [self.gnt_r == i for i in range(N)]
        for i in range(N):
            sm, us, sv = self.sif_mask[i], self.unserved[i], self.served[i]
            self.sif_mask[i] = False if sv else (sm or sif_gnt_r_vec[i])
            self.unserved[i] = not sm                     # (vp_mask & tvalid) & ~mask, tvalid = 1
            self.served[i] = not us
        self.sif_req = hif_mask[:]
        # FSM
        trig_n, len_en_n = False, [False] * N
        st, cnt = self.state, self.fsm_cnt
        if self.state == IDLE:
            cnt = 0
            if gnt is not None:
                st, self.gnt_r, self.rr_last = LOAD_STS, gnt, gnt
        elif self.state == LOAD_STS:
            st, cnt = GRANT, cnt + 1
        elif self.state == GRANT:
            st, cnt = CALC, cnt + 1
            fr = self.first_run[h]
            self.cnt_max = 18 if fr else DUMP
            self.target = 18 if fr else DUMP
        elif self.state == CALC:
            cnt = cnt + ((not hold) or (commit and cnt != self.cnt_max))
            if commit:
                trig_n = True
                len_en_n[h] = True
                self.first_run[h] = False
            if self.fsm_cnt == self.cnt_max and (commit or self.target != self.cnt_max):
                st = STORE
        elif self.state == STORE:
            if cnt >= 9:
                st = HDR_WAIT
            cnt += 1
        elif self.state == HDR_WAIT:
            cnt = 0
            st = HDR_WAIT if self.hdr.busy else IDLE
        self.pending = False if commit else (True if arm else self.pending)
        self.state, self.fsm_cnt = st, cnt
        self.hdr_trigger, self.len_en = trig_n, len_en_n
        self.cycle += 1


def gaps(top, host, skip=2):
    """Idle cycles between consecutive packets on one host's dout, after `skip` packets."""
    beats = top.dout[host]
    starts = [c for c, first, _ in beats if first]
    lasts = [c for c, _, last in beats if last]
    out = []
    for k in range(skip, min(len(starts), len(lasts) + 1) - 1):
        out.append(starts[k + 1] - lasts[k] - 1)
    return out, starts, lasts


def beats_per_packet(top, host):
    b = top.dout[host]
    starts = [c for c, first, _ in b if first]
    lasts = [c for c, _, last in b if last]
    return lasts[2] - starts[2] + 1


FAILS = []


def check(name, ok, detail):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}\n        {detail}")
    if not ok:
        FAILS.append(name)


def run(n_host, H, P, cycles=4000):
    top = DpPktTop(n_host, H, P)
    for _ in range(cycles):
        top.step()
    return top


def main():
    cases = [  # name, width, f_MHz, H, P (payload beats), wire bytes per packet, payload bytes
        ("64 bit / 156.25 MHz, MTU 1500", 64, 156.25, 9, 1408 // 8, 1506, 1408),
        ("64 bit / 156.25 MHz, MTU 4096", 64, 156.25, 9, 3968 // 8, 4066, 3968),
        ("512 bit / 201.42 MHz (S10), MTU 1500", 512, 201.42, 2, 1408 // 64, 1506, 1408),
        ("512 bit / 201.42 MHz (S10), MTU 4096", 512, 201.42, 2, 3968 // 64, 4066, 3968),
    ]
    rows = []
    for name, w, f, H, P, wire, pay in cases:
        top = run(1, H, P)
        g, _, _ = gaps(top, 0)
        n = beats_per_packet(top, 0)
        gap = g[-1]                                # steady state (phase-locked)
        period = n + gap                           # dout start-to-start; the 64-bit ICRC beat is
                                                   # assumed to fit into the gap (roce_icrc not modelled)
        hsb_gbps = pay * 8 * f * 1e6 / period / 1e9
        line = pay / wire * (10 if w == 64 else 100)
        rows.append((name, n, sorted(set(g)), period, hsb_gbps, line))
    print("[RESULT] one host, one VP, back-to-back data packets (dout of dp_pkt_top)")
    for name, n, g, period, gb, line in rows:
        print(f"        {name}: {n} beats/packet, steady gap {period - n} -> {period} cycles/packet "
              f"= {gb:.2f} Gb/s payload; line limit {line:.2f} Gb/s")
    check("gap between data packets is 4 to 7 cycles (4 + up to 3 cycles of hif_sif_mask phase)",
          all(min(r[2]) >= 4 and max(r[2]) <= 7 for r in rows), str([(r[0], r[2]) for r in rows]))

    # hif_sif_mask with one VP: three registers in an inverting ring -> period 6, 3 cycles masked.
    top = DpPktTop(1, 9, 176)
    seq = []
    for _ in range(400):
        top.step()
        seq.append(int(top.sif_mask[0]))
    tail = "".join(map(str, seq[300:318]))
    check("single-VP hif_sif_mask oscillates with period 6 (3 cycles masked)",
          tail in ("111000" * 3)[0:18] or tail in ("111000" * 4)[1:19] or tail in ("111000" * 4)[2:20]
          or tail in ("111000" * 4)[3:21] or tail in ("111000" * 4)[4:22] or tail in ("111000" * 4)[5:23],
          f"hif_sif_mask[0] over 18 cycles: {tail}")

    # Two hosts, one VP each, both saturated: the single FSM alternates.
    rows2 = []
    for name, w, f, H, P, wire, pay in cases:
        top = run(2, H, P, cycles=6000)
        res = []
        for hh in range(2):
            g, s, l = gaps(top, hh)
            n = beats_per_packet(top, hh)
            per = (s[-1] - s[3]) / (len(s) - 4) if len(s) > 5 else float("nan")
            res.append((n, per))
        n = res[0][0]
        # each host gets one packet per `per` cycles
        gbs = [pay * 8 * f * 1e6 / p / 1e9 for _, p in res]
        single = [r for r in rows if r[0] == name][0][4]
        rows2.append((name, res, gbs, single))
    print("[RESULT] two hosts, one VP each, both saturated")
    for name, res, gbs, single in rows2:
        print(f"        {name}: cycles between packet starts per host "
              f"{res[0][1]:.1f} / {res[1][1]:.1f} -> {gbs[0]:.2f} / {gbs[1]:.2f} Gb/s "
              f"(one host alone {single:.2f})")
    print("\nFAILED: " + (", ".join(FAILS) if FAILS else "none"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
