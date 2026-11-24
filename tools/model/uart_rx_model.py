#!/usr/bin/env python3
"""Cycle model of the uart.sv receiver (issues PE-3, PE-4).

Re-implements, register by register, the receive path of fpga/nv_hsb_ip/uart/uart.sv at
commit 41cecaa with the configuration the directed test U2 uses:
OVERSAMPLE = 8, 8 data bits, no parity, 1 stop bit, glitch filter off, RTS asserted.

Modelled (line numbers in uart.sv):
  rx_sync / rx_falling_edge        L463-L475  two flops, edge = rx_sync == 2'b10
  rx_start_lock / baud counter     L282-L308  counter reloaded with 2 on lock, tick when
                                              counter >= baud_div (period baud_div + 1)
  sample point / bit decision      L344-L349, L351-L409 (filter off: centre sample at cnt 4,
                                              decided at cnt 7)
  RX FSM                           L478-L631  IDLE / START / DATA / STOP, back-to-back re-lock
                                              only when a falling edge coincides with the tick
  rx_data_valid                    L640-L655

The transmitter is ideal: N back-to-back 8N1 frames, no idle, bit time scaled by
1 / (1 + ppm * 1e-6) relative to the receiver's nominal bit time (8 * (baud_div + 1) clocks),
exactly as tests/unit/tb_uart_rx_rate.sv drives it. The line level seen at clock k is the
level just before k (the SV test changes uart_rx between clock edges).

Usage:  python3 tools/model/uart_rx_model.py
Exit code 1 if an expectation is violated.
"""
import random
import sys

OVERSAMPLE = 8
IDLE, START, DATA, STOP = range(4)


class UartRx:
    def __init__(self, baud_div):
        self.baud_div = baud_div
        self.rx_sync = 0b11
        self.counter = 0
        self.tick = False
        self.state = IDLE
        self.cnt = 0
        self.bit_cnt = 0
        self.shift = 0
        self.discard = False
        self.sampled = 1
        self.frame_err = False
        self.stop_cycles = 0
        self.out = []            # (byte, frame_error)
        self.sample_cycles = []  # clock of each centre sample (for PE-4)

    def step(self, rx_in, k):
        s1 = (self.rx_sync >> 1) & 1                         # rx_sync[1]
        fe = self.rx_sync == 0b10
        start_lock = (self.state == IDLE and fe) or \
                     (self.state == STOP and self.cnt >= self.stop_cycles - 1 and self.tick and fe)
        # bit decision (filter off)
        bit_valid = self.cnt >= OVERSAMPLE - 1
        bit_value = self.sampled if bit_valid else 1
        sample_point = self.cnt == (OVERSAMPLE >> 1) or self.cnt == OVERSAMPLE + (OVERSAMPLE >> 1)

        # ---- next-state values ----
        n = dict(state=self.state, cnt=self.cnt, bit_cnt=self.bit_cnt, shift=self.shift,
                 discard=self.discard, sampled=self.sampled, frame_err=self.frame_err,
                 stop_cycles=self.stop_cycles)
        if self.state == IDLE:
            if fe:
                n.update(state=START, cnt=0, discard=False)
        elif self.tick:
            if sample_point:
                n["sampled"] = s1
                self.sample_cycles.append(k)
            if self.state == START:
                if self.cnt >= OVERSAMPLE - 1:
                    if not (bit_valid and not bit_value):
                        n["discard"] = True
                    n.update(cnt=0, state=DATA, bit_cnt=0)
                else:
                    n["cnt"] = self.cnt + 1
            elif self.state == DATA:
                if self.cnt >= OVERSAMPLE - 1:
                    n["cnt"] = 0
                    n["shift"] = (bit_value << 7) | (self.shift >> 1)
                    if self.bit_cnt >= 7:
                        n.update(state=STOP, frame_err=False, stop_cycles=OVERSAMPLE)
                    else:
                        n["bit_cnt"] = self.bit_cnt + 1
                else:
                    n["cnt"] = self.cnt + 1
            elif self.state == STOP:
                if self.cnt == OVERSAMPLE - 1 and not bit_value:
                    n["frame_err"] = True
                if self.cnt >= self.stop_cycles - 1:
                    if fe:
                        n.update(state=START, cnt=0, discard=False)
                    else:
                        n.update(state=IDLE, cnt=0)
                else:
                    n["cnt"] = self.cnt + 1
        # output register
        if self.state == STOP and self.cnt >= self.stop_cycles - 1 and self.tick:
            if not self.discard:
                err = self.frame_err or (self.cnt == OVERSAMPLE - 1 and not bit_value)
                self.out.append((self.shift, err))
        # baud generator
        if start_lock:
            counter, tick = 2, False
        elif self.state != IDLE:
            if self.counter >= self.baud_div:
                counter, tick = 0, True
            else:
                counter, tick = self.counter + 1, False
        else:
            counter, tick = 0, False
        # commit
        self.rx_sync = ((self.rx_sync << 1) | rx_in) & 0b11
        self.counter, self.tick = counter, tick
        for key, v in n.items():
            setattr(self, key, v)


def run(ppm, baud_div=107, n_bytes=64, seed=1):
    rng = random.Random(seed)
    data = [rng.randrange(256) for _ in range(n_bytes)]
    bit = OVERSAMPLE * (baud_div + 1) / (1.0 + ppm * 1e-6)   # clocks per transmitted bit
    t0 = 10.0 + 3 * bit + 0.37                               # off-grid start, as in the SV test
    edges = []                                               # (time, level)
    t = t0
    starts = []
    for b in data:
        starts.append(t)
        levels = [0] + [(b >> i) & 1 for i in range(8)] + [1]
        for lv in levels:
            edges.append((t, lv))
            t += bit
    end = t + 20 * bit
    rx = UartRx(baud_div)
    idx, level = 0, 1
    for k in range(int(end) + 1):
        while idx < len(edges) and edges[idx][0] < k:
            level = edges[idx][1]
            idx += 1
        rx.step(level, k)
    got = [b for b, _ in rx.out]
    good = 0
    for i, b in enumerate(data):
        if i < len(got) and got[i] == b:
            good += 1
    return data, rx, got, good, bit, starts


FAILS = []


def check(name, ok, detail):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}\n        {detail}")
    if not ok:
        FAILS.append(name)


def main():
    rows = []
    results = {}
    for ppm in (-20000, -5000, -1000, 0, 100, 1000, 5000, 20000):
        data, rx, got, good, _, _ = run(ppm)
        results[ppm] = (len(got), good)
        ferr = sum(1 for _, e in rx.out if e)
        rows.append(f"ppm {ppm:+6d}: received {len(got):2d} / {len(data)}, correct in order {good:2d}, "
                    f"frame errors {ferr}")
    print("[RESULT] 64 back-to-back 8N1 frames, baud_div 107 (U2 configuration)\n        "
          + "\n        ".join(rows))
    check("PE-3: sender slower or equal -> every byte received",
          all(results[p] == (64, 64) for p in (-20000, -5000, -1000, 0)),
          str({p: results[p] for p in (-20000, -5000, -1000, 0)}))
    check("PE-3: sender faster -> framing lost",
          all(results[p][1] < 64 for p in (1000, 5000, 20000)),
          str({p: results[p] for p in (100, 1000, 5000, 20000)}))

    # smallest positive error that loses framing
    lo = None
    for ppm in range(1, 2001):
        _, _, got, good, _, _ = run(ppm, n_bytes=64)
        if good < 64:
            lo = ppm
            break
    print(f"[RESULT] smallest sender-faster error that loses a byte (64 frames)\n        {lo} ppm")

    # The threshold is about one receiver clock per 10-bit frame: 1e6 / (10 * 8 * (baud_div + 1)) ppm.
    rows = []
    ok = True
    for bd in (15, 53, 107):
        pred = 1e6 / (10 * OVERSAMPLE * (bd + 1))
        found = None
        for ppm in range(int(pred * 0.5), int(pred * 2), max(1, int(pred / 50))):
            if run(ppm, baud_div=bd, n_bytes=32)[3] < 32:
                found = ppm
                break
        ok &= found is not None and abs(found - pred) / pred < 0.1
        rows.append(f"baud_div {bd}: one clock per frame = {pred:.0f} ppm, framing lost from {found} ppm")
    check("PE-3: threshold is about one receiver clock per frame", ok, "; ".join(rows))

    # PE-4: where in the bit the centre sample is taken (ideal sender)
    data, rx, got, good, bit, starts = run(0, n_bytes=4)
    first = rx.sample_cycles[0] - starts[0]                  # start bit centre sample
    frac = first / bit
    check("PE-4: centre sample is taken about 5/8 into the bit, not 1/2",
          0.60 <= frac <= 0.66,
          f"start-bit sample {first:.1f} clocks after the wire edge = {frac:.3f} of a bit "
          f"({bit:.0f} clocks per bit)")

    print("\nFAILED: " + (", ".join(FAILS) if FAILS else "none"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
