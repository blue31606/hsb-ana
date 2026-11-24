#!/usr/bin/env python3
"""Check every source permalink in the docs against the pinned upstream commit.

For each link of the form
  https://github.com/nvidia-holoscan/holoscan-sensor-bridge/blob/<sha>/<path>#L<a>[-L<b>]
the script checks:
  1. the commit is the one the analysis is pinned to;
  2. the file exists and the line range lies inside it (a <= b <= last line);
  3. the identifiers written in backticks in the text that leads up to the link (same line,
     from the previous link or the start of the line, without the link's own display text,
     file names and AXIS handshake words) appear in the cited lines (+-2 lines; identifiers
     of 5+ characters may match as substrings). A link passes when at least one of those
     identifiers is found; links whose leading text has no identifier are counted as
     "no identifier" and not judged. The rule is a heuristic: a mismatch means "read this
     citation again", not "this citation is wrong".

Usage:
  python3 tools/check_links.py <path-to-holoscan-sensor-bridge> [--verbose]
Exit code 1 on a broken link (rule 1 or 2) or a link whose identifiers are all missing.
"""
import re
import sys
from pathlib import Path

SHA = "41cecaa81ab906a55e7ec22e5e6989f7e602a4c8"
ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"\]\((https://github\.com/nvidia-holoscan/holoscan-sensor-bridge/blob/"
                  r"([0-9a-f]+)/([^)#\s]+)(?:#L(\d+)(?:-L(\d+))?)?)\)")
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
STOP = {"if", "else", "begin", "end", "assign", "logic", "input", "output", "reg", "wire",
        "and", "or", "not", "the", "to", "in", "of", "for", "case", "default", "int",
        "true", "false", "bit", "TRUE", "FALSE", "IDLE",
        # AXIS handshake words and short generic words used in prose
        "tvalid", "tready", "tlast", "tuser", "tkeep", "tdata", "status", "host", "sec",
        "src", "dst", "pld", "ctrl", "clog2"}
SLACK = 2          # lines of tolerance around the cited range


def idents(text, exclude):
    out = []
    for tok in re.findall(r"`([^`]+)`", text):
        for m in IDENT.findall(tok):
            if (len(m) >= 3 and m not in STOP and m not in exclude
                    and not re.fullmatch(r"L\d+", m)
                    and not re.fullmatch(r"[0-9a-fA-Fx_]+h?", m)):
                out.append(m)
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    up = Path(sys.argv[1])
    verbose = "--verbose" in sys.argv
    cache = {}
    n_links = n_judged = n_unjudged = 0
    broken, mismatched = [], []
    for md in sorted(ROOT.rglob("*.md")):
        rel = md.relative_to(ROOT)
        for ln, line in enumerate(md.read_text().split("\n"), 1):
            prev_end = 0
            for m in LINK.finditer(line):
                n_links += 1
                url, sha, path, a, b = m.groups()
                ctx = line[prev_end:m.start()]
                # drop the link's own display text ("[...]")
                ob = ctx.rfind("[")
                if ob >= 0:
                    ctx = ctx[:ob]
                prev_end = m.end()
                where = f"{rel}:{ln}"
                if sha != SHA:
                    broken.append((where, url, f"commit {sha[:7]} is not {SHA[:7]}"))
                    continue
                f = up / path
                if not f.is_file():
                    broken.append((where, url, "file not found"))
                    continue
                if path not in cache:
                    cache[path] = f.read_text(errors="replace").split("\n")
                src = cache[path]
                if a is None:
                    continue
                a = int(a)
                b = int(b) if b else a
                if not (1 <= a <= b <= len(src)):
                    broken.append((where, url, f"range L{a}-L{b} outside 1-{len(src)}"))
                    continue
                stems = {Path(path).stem}
                stems |= {Path(x).stem for x in re.findall(r"[\w/]+\.(?:sv|v|svh|cpp|hpp|py)", ctx)}
                ids = idents(ctx, stems)
                if not ids:
                    n_unjudged += 1
                    continue
                n_judged += 1
                body = "\n".join(src[max(0, a - 1 - SLACK):b + SLACK])
                found = [i for i in ids
                         if (re.search(re.escape(i), body) if len(i) >= 5
                             else re.search(r"\b" + re.escape(i) + r"\b", body))]
                if not found:
                    mismatched.append((where, f"{path}#L{a}" + (f"-L{b}" if b != a else ""),
                                       ", ".join(sorted(set(ids)))))
                elif verbose:
                    print(f"ok   {where} {path}#L{a}: {found[0]}")
    reviewed = set()
    rv = ROOT / "tools" / "check_links_reviewed.txt"
    if rv.exists():
        for l in rv.read_text().split("\n"):
            if l.strip() and not l.startswith("#"):
                doc, cite = l.split()[:2]
                reviewed.add((doc, cite))
    still = []
    n_rev = 0
    for w, u, ids in mismatched:
        doc = w.split(":")[0]
        cite = Path(u.split("#")[0]).name + "#" + u.split("#")[1]
        if (doc, cite) in reviewed:
            n_rev += 1
        else:
            still.append((w, u, ids))
    mismatched = still
    print(f"links: {n_links}; judged by identifier: {n_judged} ({n_rev} reviewed by hand, "
          f"tools/check_links_reviewed.txt); no identifier in the leading text: {n_unjudged}")
    for w, u, why in broken:
        print(f"[BROKEN] {w}: {why}\n         {u}")
    for w, u, ids in mismatched:
        print(f"[MISMATCH] {w}: none of [{ids}] in {u}")
    print("\nFAILED: " + (f"{len(broken)} broken, {len(mismatched)} mismatched"
                          if broken or mismatched else "none"))
    return 1 if broken or mismatched else 0


if __name__ == "__main__":
    sys.exit(main())
