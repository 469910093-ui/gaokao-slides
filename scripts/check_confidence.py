#!/usr/bin/env python3
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "data" / "provinces"
low = []
all_tracks = 0
for f in root.glob("*.json"):
    d = json.loads(f.read_text(encoding="utf-8"))
    for y, yo in d.get("years", {}).items():
        for t, td in yo.get("tracks", {}).items():
            all_tracks += 1
            cs = td.get("confidenceScore", 0)
            if cs < 0.8:
                low.append((f.stem, y, t, cs, td.get("confidence"), td.get("source")))

print(f"total tracks: {all_tracks}, confidence < 80%: {len(low)}")
print("low sample:", low[:10])

js = json.loads((root / "江苏.json").read_text(encoding="utf-8"))
phy = js["years"]["2025"]["tracks"]["物理类"]
segs = phy["segments"]
print("江苏2025物理:", phy["confidenceScore"], phy["confidence"], phy["source"])
for s in [463, 500, 550, 600, 650, 700]:
    near = min(segs, key=lambda x: abs(x["s"] - s))
    print(f"  score~{s}: p={near['p']}% at={near['s']}")

hist = js["years"]["2025"]["tracks"]["历史类"]
segs2 = hist["segments"]
print("江苏2025历史:", hist["confidenceScore"], hist["confidence"], hist["source"])
for s in [463, 500, 550, 600]:
    near = min(segs2, key=lambda x: abs(x["s"] - s))
    print(f"  score~{s}: p={near['p']}% at={near['s']}")
