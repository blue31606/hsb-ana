"""Load tools/reviewed.txt: hand-reviewed findings shared by the checking tools."""
from pathlib import Path

FILE = Path(__file__).with_name("reviewed.txt")


def load(tool):
    """Return the (key 1, key 2) pairs listed for one tool."""
    pairs = []
    if FILE.exists():
        for line in FILE.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                parts = line.split(" -- ")[0].split()
                if parts[0] == tool and len(parts) >= 3:
                    pairs.append((parts[1], parts[2]))
    return pairs
