#!/usr/bin/env python3
"""Packet-level model of the roce_ack response decision (issues TX-1, TX-2, TX-3).

Re-implements the per-packet decision of fpga/nv_hsb_ip/roce/roce_ack.sv at commit 41cecaa
for RC packets that pass every other check (no error injection, sensor TX ready):

  status RAM       L158-L172  one entry per QP, reset to all 0: {has_inited[49], has_nacked[48],
                              msn[47:24], psn[23:0]}; sts_ram_data is read when the packet's
                              header arrives (sts_ram_rden = i_hdr_valid) and held until the next one
  decision chain   L267-L357  !has_inited -> initialise (psn_next = psn + 1, ACK)
                              psn == psn_exp -> ACK, psn_next = psn_exp + 1
                              psn >  psn_exp -> NAK (only if !has_nacked), drop
                              else           -> duplicate: drop, no response
  write-back       L363       {1, is_nacked, msn_next, psn_next}
  response         L486-L511  BTH PSN field = psn_exp (the value read at the header),
                              AETH = syndrome + msn_next

The comparison is a plain 24-bit unsigned compare (L313, L324), as in the RTL. Cycle timing
is not modelled: each packet is processed completely before the next header arrives.

Usage:  python3 tools/model/roce_ack_model.py
Exit code 1 if an expectation is violated.
"""
import sys

M24 = 0xFFFFFF


class RoceAck:
    def __init__(self):
        self.ram = {}                         # qp -> (inited, nacked, msn, psn)

    def packet(self, qp, psn, last=True, ack_req=True):
        inited, nacked, msn, psn_exp = self.ram.get(qp, (0, 0, 0, 0))
        if not inited:
            ack, trig, msn_n, psn_n, kind = True, ack_req, int(last), (psn + 1) & M24, "init"
        elif psn == psn_exp:
            ack, trig, msn_n, psn_n, kind = True, ack_req, (msn + last) & M24, (psn_exp + 1) & M24, "in-order"
        elif psn > psn_exp:
            ack, trig, msn_n, psn_n, kind = False, not nacked, msn, psn_exp, "ahead"
        else:
            ack, trig, msn_n, psn_n, kind = False, False, msn, psn_exp, "duplicate"
        is_nacked = 0 if ack else int((trig and not ack) or nacked)
        self.ram[qp] = (1, is_nacked, msn_n, psn_n)
        resp = None
        if trig:
            resp = ("ACK" if ack else "NAK-PSN-seq", psn_exp, msn_n)
        return kind, resp


FAILS = []


def check(name, ok, detail):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}\n        {detail}")
    if not ok:
        FAILS.append(name)


def fmt(log):
    return "; ".join(f"psn {p:#08x}: {k} -> " + (f"{r[0]} psn={r[1]:#08x} msn={r[2]}" if r else "no response")
                     for p, k, r in log)


def run(seq, qp=2):
    ra = RoceAck()
    log = []
    for p in seq:
        k, r = ra.packet(qp, p)
        log.append((p, k, r))
    return log


def main():
    # TX-2: first packet of a QP with a non-zero starting PSN.
    log = run([0x100, 0x101])
    check("TX-2: first ACK carries PSN 0 (status RAM reset value), not the packet's PSN",
          log[0][2] == ("ACK", 0, 1) and log[1][2][1] == 0x101, fmt(log))

    # TX-1: duplicate of an already-acknowledged packet (its ACK was lost).
    log = run([0, 1, 2, 3, 3])
    check("TX-1: a duplicate request gets no response",
          log[4][1] == "duplicate" and log[4][2] is None, fmt(log))

    # TX-1 + TX-2: starting PSN 0x100, the requester does not accept the ACK for PSN 0
    # and retransmits 0x100.
    log = run([0x100, 0x100, 0x100])
    check("TX-1 + TX-2: retransmissions of the first packet are never answered",
          log[0][2][1] == 0 and log[1][2] is None and log[2][2] is None, fmt(log))

    # TX-3: loss across the 24-bit wrap. psn_exp = 0xFFFFFE; 0xFFFFFE and 0xFFFFFF are lost,
    # 0x000000 arrives: it is *ahead*, but the unsigned compare calls it a duplicate.
    log = run([0xFFFFFC, 0xFFFFFD, 0x000000, 0x000001])
    check("TX-3: a packet ahead across the wrap is dropped as a duplicate, no NAK",
          log[2][1] == "duplicate" and log[2][2] is None and log[3][2] is None, fmt(log))

    # TX-3 (other direction): psn_exp = 0x000001; a late duplicate of 0xFFFFFF arrives and is
    # treated as ahead, so the responder sends a sequence-error NAK instead of staying silent.
    log = run([0xFFFFFE, 0xFFFFFF, 0x000000, 0xFFFFFF])
    check("TX-3: a duplicate across the wrap triggers a sequence-error NAK",
          log[3][1] == "ahead" and log[3][2] and log[3][2][0] == "NAK-PSN-seq", fmt(log))

    # Control: in-order traffic, a lost packet, NAK once, then recovery.
    log = run([0, 1, 3, 4, 2, 3])
    check("control: gap -> one NAK, retransmission -> ACKs resume",
          [r[0] if r else None for _, _, r in log] == ["ACK", "ACK", "NAK-PSN-seq", None, "ACK", "ACK"],
          fmt(log))

    print("\nFAILED: " + (", ".join(FAILS) if FAILS else "none"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
