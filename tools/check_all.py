#!/usr/bin/env python3
"""Run every check in tools/ against the pinned upstream checkout.

Usage:  python3 tools/check_all.py <path-to-holoscan-sensor-bridge> [--models] [--regen] [-v]
  --models  also run the cycle models in tools/model/ (uart_rx_model.py takes about 2 minutes)
  --regen   rewrite the generated files (all-registers.md, the board table, the timing SVGs
            and rx_parser_readout.wave.json) instead of only checking that they are current
  -v        print the full output of every tool

Prints one line per tool (its last summary line), then compares the numbers written in
VERIFICATION.md and other docs (FACTS below) with the tool output, and exits with 1 if any
tool fails, a generated file is out of date, or a number in the docs no longer matches.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T = "tools/"

# Numbers written in the docs, checked against the tool output that produced them.
# (doc, pattern in the doc, tool, pattern in the tool output); groups are compared in order.
FACTS = [
    ("VERIFICATION.md", r"目前 (\d+) 項（高 (\d+)、中 (\d+)、低 (\d+)），另有註解與死碼 (\d+) 項",
     "check_issue_refs.py", r"issues: (\d+) \(高 (\d+), 中 (\d+), 低 (\d+)\); notes and dead code: (\d+)"),
    ("VERIFICATION.md", r"方法分布為 R (\d+)、R \+ M (\d+)、R \+ X (\d+)、R \+ N (\d+)、R \+ I (\d+)、R \+ X \+ N (\d+)",
     "check_issue_refs.py", r"methods: R (\d+), R \+ M (\d+), R \+ X (\d+), R \+ N (\d+), R \+ I (\d+), R \+ X \+ N (\d+)"),
    ("VERIFICATION.md", r"(\d+) 個問題編號都在模組文件",
     "check_issue_refs.py", r"issue IDs defined: (\d+)"),
    ("VERIFICATION.md", r"host 用到的 (\d+) 個位址常數中 (\d+) 個",
     "check_host_regs.py", r"\[RESULT\] (\d+) host address constants, (\d+) found"),
    ("VERIFICATION.md", r"host 寫入的 (\d+) 個常數值中，(\d+) 個",
     "check_host_regs.py --bits", r"constant host writes: (\d+); judged against a regmap register \(non-zero\): (\d+)"),
    ("VERIFICATION.md", r"位元測試的 (\d+) 處中，(\d+) 處",
     "check_host_regs.py --reads", r"with a bit test: (\d+); judged against RTL stat_reg assignments: (\d+)"),
    ("VERIFICATION.md", r"暫存器索引的 (\d+) 個項目中，host 存取了 (\d+) 個",
     "check_unused.py", r"registers in the index: (\d+); touched by the host: (\d+)"),
    ("docs/registers/memory-map.md", r"的 (\d+) 個項目中，host 存取了 (\d+) 個",
     "check_unused.py", r"registers in the index: (\d+); touched by the host: (\d+)"),
    ("VERIFICATION.md", r"文件中 (\d+) 個原始碼連結.*?；(\d+) 個可依識別字判斷的連結中，\d+ 個自動吻合、(\d+) 個人工確認",
     "check_links.py", r"links: (\d+); judged by identifier: (\d+) \((\d+) reviewed"),
    ("VERIFICATION.md", r"(\d+) 個實例中，握手 / 狀態類埠空接 (\d+) 處、輸入綁常數 (\d+) 處",
     "scan_ports.py", r"instances: (\d+); handshake/status ports open: (\d+), inputs tied to a constant: (\d+)"),
    ("VERIFICATION.md", r"檔案內跨時脈 (\d+) 處：(\d+) 處依名稱判定為同步器或準靜態設定，(\d+) 處人工確認",
     "scan_cdc.py", r"crossings: (\d+); accepted by name: (\d+); reviewed by hand: (\d+)"),
    ("docs/modules/lib.md", r"有 (\d+) 個檔案內部有跨時脈，共 (\d+) 處；(\d+) 處",
     "scan_cdc.py", r"files with crossings inside: (\d+); crossings: (\d+); accepted by name: (\d+)"),
    ("VERIFICATION.md", r"經由埠）的跨時脈 (\d+) 處",
     "scan_cdc_ports.py", r"port crossings without a synchronizer module: (\d+)"),
    ("docs/modules/lib.md", r"結果 (\d+) 處：",
     "scan_cdc_ports.py", r"port crossings without a synchronizer module: (\d+)"),
    ("VERIFICATION.md", r"`nv_hsb_ip` 的 (\d+) 個檔案、(\d+) 個模組 / package",
     "check_coverage.py", r"files: (\d+); covered: \d+; modules \+ packages: (\d+)"),
    ("VERIFICATION.md", r"文件表格的 (\d+) 個「行數」欄、(\d+) 個 reset 值與原始碼一致；(\d+) 個表格",
     "check_coverage.py", r"line-count cells checked: (\d+)[\s\S]*reset cells checked against RST_VAL: (\d+)[\s\S]*tables checked: (\d+)"),
    ("VERIFICATION.md", r"的 (\d+) 列設定（(\d+) 格）",
     "gen_board_table.py", r"rows generated: (\d+);.*cells compared: (\d+)"),
]


def check_facts(outputs):
    bad, n = [], 0
    for doc, dpat, tool, tpat in FACTS:
        text = (ROOT / doc).read_text()
        d = re.search(dpat, text, re.S)
        t = re.search(tpat, outputs.get(tool, ""))
        if not t:
            continue                      # tool not run in this mode
        n += 1
        if not d:
            bad.append(f"{doc}: pattern not found: {dpat[:50]}")
        elif d.groups() != t.groups():
            bad.append(f"{doc}: {d.group(0)[:60]} -> tool says {', '.join(t.groups())}")
    return n, bad


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
        [T + "check_host_regs.py", up, "--reads"],
        [T + "scan_ports.py", up],
        [T + "scan_cdc.py", up],
        [T + "scan_cdc_ports.py", up],
        [T + "check_coverage.py", up],
        [T + "check_issue_refs.py"],
        [T + "check_unused.py", up],
        [T + "gen_board_table.py", up] + (["--write"] if regen else []),
    ]
    if "--models" in sys.argv:
        checks += [[T + "model/" + m] for m in ("rx_parser_model.py", "dp_pkt_model.py", "uart_rx_model.py",
                                                "roce_ack_model.py", "reg_cdc_model.py")]
    failed = []
    outputs = {}
    for cmd in checks:
        rc, out = run(cmd, verbose)
        last = [l for l in out.splitlines() if l.strip()]
        heads = ("modules", "files", "links", "issue IDs", "host register reads", "registers in the index", "rows", "constant", "FAILED", "[RESULT]")
        summary = next((l for h in heads for l in last if l.startswith(h)), last[-1] if last else "")
        name = " ".join(c.replace(T, "") for c in cmd if c != up)
        outputs[name.replace(" --write", "")] = out
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

    n_facts, bad_facts = check_facts(outputs)
    print(f"{'ok  ' if not bad_facts else 'FAIL'} {'numbers in the docs':34s} {n_facts} checked against tool output; "
          f"{len(bad_facts)} out of date")
    for b in bad_facts:
        print("       " + b)
    if bad_facts:
        failed.append("numbers in the docs")
    print("\nFAILED: " + ("; ".join(failed) if failed else "none"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
