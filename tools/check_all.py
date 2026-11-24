#!/usr/bin/env python3
"""Run every check in tools/ against the pinned upstream checkout.

Usage:  python3 tools/check_all.py <path-to-holoscan-sensor-bridge> [--models] [--regen] [-v]
  --models  also run the cycle models in tools/model/ (uart_rx_model.py takes about 2 minutes)
  --regen   rewrite the generated files (all-registers.md, the board table, the timing SVGs
            and rx_parser_readout.wave.json) instead of only checking that they are current
  -v        print the full output of every tool

Prints one line per tool (its last summary line) and exits with 1 if any tool fails or a
generated file is out of date.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T = "tools/"


def run(cmd, verbose):
    p = subprocess.run([sys.executable] + cmd, cwd=ROOT, capture_output=True, text=True)
    out = (p.stdout + p.stderr).strip()
    if verbose:
        print(out + "\n")
    return p.returncode, out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__)
        return 2
    up = args[0]
    verbose = "-v" in sys.argv
    regen = "--regen" in sys.argv
    checks = [
        [T + "verify/verify_calcs.py", up],
        [T + "check_tests.py", up],
        [T + "check_links.py", up],
        [T + "check_host_regs.py", up],
        [T + "check_host_regs.py", up, "--bits"],
        [T + "scan_ports.py", up],
        [T + "scan_cdc.py", up],
        [T + "check_coverage.py", up],
        [T + "gen_board_table.py", up] + (["--write"] if regen else []),
    ]
    if "--models" in sys.argv:
        checks += [[T + "model/" + m] for m in ("rx_parser_model.py", "dp_pkt_model.py", "uart_rx_model.py",
                                                "roce_ack_model.py", "reg_cdc_model.py")]
    failed = []
    for cmd in checks:
        rc, out = run(cmd, verbose)
        last = [l for l in out.splitlines() if l.strip()]
        heads = ("modules", "files", "links", "rows", "constant", "FAILED", "[RESULT]")
        summary = next((l for h in heads for l in last if l.startswith(h)), last[-1] if last else "")
        name = " ".join(c.replace(T, "") for c in cmd if c != up)
        print(f"{'ok  ' if rc == 0 else 'FAIL'} {name:34s} {summary[:110]}")
        if rc:
            failed.append(name)

    # generated files
    allregs = ROOT / "docs/registers/all-registers.md"
    rc, out = run([T + "gen_allregs.py", up], False)
    if regen:
        allregs.write_text(out + "\n" if not out.endswith("\n") else out)
    elif rc or out.strip() != allregs.read_text().strip():
        failed.append("all-registers.md out of date (run with --regen)")
    print(f"{'ok  ' if 'all-registers.md out of date (run with --regen)' not in failed else 'FAIL'} "
          f"{'gen_allregs.py':34s} docs/registers/all-registers.md {'rewritten' if regen else 'current'}")
    if regen:
        run([T + "model/rx_parser_model.py", "--wave", "docs/timing/rx_parser_readout.wave.json"], verbose)
        waves = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "docs/timing").glob("*.wave.json"))
        run([T + "wave.py"] + waves, verbose)
        print(f"ok   {'wave.py':34s} {len(waves)} timing diagrams rewritten")

    print("\nFAILED: " + ("; ".join(failed) if failed else "none"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
