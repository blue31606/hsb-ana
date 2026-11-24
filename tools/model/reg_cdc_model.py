#!/usr/bin/env python3
"""Two-clock model of misc/reg_cdc.sv as used by s_apb_reg (issue CP-6).

reg_cdc (L31-L88) is a four-phase handshake: a write pulse i_a_val captures the value,
a_val_qq is raised and held until the acknowledge returns from the B domain, and a new
pulse only starts a transfer on the rising edge a_val_q && !a_val_qq. In s_apb_reg
(L72, L94, L173-L185) every control register's reg_cdc shares the same i_a_val =
reg_wdval, which pulses on *any* register write in the block, so two writes to *different*
registers of one block inside the handshake time lose the second value (it is only
transferred by a later write).

Write spacing on the APB side comes from apb_switch (L106-L170): grant in IDLE, REQUESTED
with psel, then penable, slave pready (s_apb_reg: reg_wren one cycle after psel&penable,
reg_ready one cycle later), then DELAY for 11 cycles. Back-to-back writes from one master
are therefore at least 16 APB cycles apart (more if decode stages add latency).

The model runs both clocks on a common time axis (A period = 1, B period = ratio, B phase
swept), issues writes to two registers of one block at a given spacing, and reports whether
the B side ends up with the last written value of each register.

Usage:  python3 tools/model/reg_cdc_model.py
"""
import math
import sys


class RegCdc:
    def __init__(self):
        self.a_val_q = self.a_val_qq = False
        self.a_reg_q = self.a_reg_qq = 0
        self.ack_sync = [False, False]
        self.b_sync = [False, False, False]
        self.b_reg = 0
        self.b_ack = False

    def a_edge(self, a_val, a_reg):
        ack1 = self.ack_sync[1]
        new_q = a_val
        new_qq = (self.a_val_q or self.a_val_qq) and not ack1
        new_ack = [self.b_ack, self.ack_sync[0]]
        if a_val:
            reg_q = a_reg
        else:
            reg_q = self.a_reg_q
        reg_qq = self.a_reg_q if (self.a_val_q and not self.a_val_qq) else self.a_reg_qq
        self.a_val_q, self.a_val_qq, self.ack_sync = new_q, new_qq, new_ack
        self.a_reg_q, self.a_reg_qq = reg_q, reg_qq

    def b_edge(self):
        s = self.b_sync
        if s[1] and not s[2]:
            self.b_reg = self.a_reg_qq
        self.b_ack = s[1]
        self.b_sync = [self.a_val_qq, s[0], s[1]]


def run(ratio, phase, spacing, n_pairs=6):
    """Writes: register X then register Y `spacing` A-cycles later, repeated. Returns True
    if both registers end with their last written values on the B side."""
    regs = {"X": RegCdc(), "Y": RegCdc()}
    ctrl = {"X": 0, "Y": 0}
    writes = {}
    t = 5
    val = 1
    for _ in range(n_pairs):
        for r in ("X", "Y"):
            writes[t] = (r, val)
            val += 1
            t += spacing
    end_a = t + 200
    a_t = [float(k) for k in range(end_a)]
    b_t = [phase + k * ratio for k in range(int(end_a / ratio) + 2)]
    events = sorted([(x, 0, int(x)) for x in a_t] + [(x, 1, None) for x in b_t])
    wdval = False
    pending = None
    for tm, kind, k in events:
        if kind == 0:
            # s_apb_reg: reg_wdval is registered from reg_wren; model the write landing
            # in reg_ctrl and reg_wdval in the same A edge (both are registered from reg_wren)
            this_wdval = pending is not None
            if pending is not None:
                ctrl[pending[0]] = pending[1]
            for name, c in regs.items():
                c.a_edge(this_wdval, ctrl[name])
            pending = writes.get(k)
        else:
            for c in regs.values():
                c.b_edge()
    return all(regs[r].b_reg == ctrl[r] for r in regs)


def min_safe_spacing(ratio):
    for sp in range(1, 60):
        if all(run(ratio, ph * ratio / 8, sp) for ph in range(8)):
            return sp
    return None


def main():
    print("[RESULT] smallest write spacing (APB cycles) that never loses a value, by B/A clock ratio")
    rows = []
    for fa_over_fb in (0.125, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0):
        sp = min_safe_spacing(fa_over_fb)
        rows.append((fa_over_fb, sp))
        print(f"        f_APB / f_module = {fa_over_fb:5.3f}: >= {sp} APB cycles")
    # apb_switch gives >= 16; find the largest ratio that is still safe
    lim = None
    r = 0.25
    while r < 6:
        if min_safe_spacing(r) > 16:
            lim = r
            break
        r += 0.05
    print(f"[RESULT] with apb_switch's >= 16-cycle spacing, values are lost once "
          f"f_APB / f_module >= {lim:.2f} (module clock below {1/lim:.2f} x APB clock)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
