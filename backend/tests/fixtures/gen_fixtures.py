"""One-off generator for road_cases.json — NOT part of the test suite.
Run manually when the road algorithms change:
    python backend/tests/fixtures/gen_fixtures.py
"""

import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ))

from app.services.derived_roads import compute_all_roads  # noqa: E402

random.seed(42)

CASES = [
    "B",
    "T",
    "BP",
    "BB",
    "BBBBBB",
    "BBBBBBB",
    "BBBBBBBB",
    "BBBBBBBBBBBB",
    "BPBPBPBP",
    "BBPPBBPP",
    "BPPBPPBPP",
    "TBPBPT",
    "BTBBPPT",
    "BBBBBBPPPPPP",
    "BBBBBBBBBBBBPPPPPPPPPPPP",
    "BPBBPPBBBPPPBBBBPPPP",
    "BBPBBPBBPBBPBBPBBPBBP",
    "TTTBPBPBP",
    "BBBPPPBBBPPPBBBPPP",
]

# Add some randomized long sequences for broader coverage.
for _ in range(10):
    n = random.randint(15, 60)
    seq = "".join(random.choices(["B", "P", "T"], weights=[0.46, 0.45, 0.09], k=n))
    CASES.append(seq)


def serialize_cells(cells):
    return [vars(c) if hasattr(c, "__dict__") else c.__dict__ for c in cells]


def main():
    out = []
    for seq in CASES:
        results = list(seq)
        roads = compute_all_roads(results)
        out.append(
            {
                "input": seq,
                "bigRoad": [c.__dict__ for c in roads.bigRoad],
                "bigEye": [c.__dict__ for c in roads.bigEye],
                "small": [c.__dict__ for c in roads.small],
                "cockroach": [c.__dict__ for c in roads.cockroach],
            }
        )

    path = os.path.join(os.path.dirname(__file__), "road_cases.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {len(out)} cases to {path}")


if __name__ == "__main__":
    main()
