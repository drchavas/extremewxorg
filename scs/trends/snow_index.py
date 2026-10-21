#!/usr/bin/env python3
"""snow_index.py SNOW_JSON_GZ INDEX_JSON -- add/replace the heavy-snow entry in the
county page's index.json, keeping the menu order of the other builders."""
import gzip, json, sys
ORDER = ["hail", "tornado", "wind", "derechoday", "heatindex", "heat", "rain", "snow",
         "fzra", "pkwnd", "derecho"]
d = json.load(gzip.open(sys.argv[1])); m = d["meta"]
idx = json.load(open(sys.argv[2]))
idx["hazards"] = [h for h in idx["hazards"] if h["key"] != "snow"]
idx["hazards"].append({"key": "snow", "label": m["label"], "unit": m["unit"], "note": m["note"],
                       "thresholds": m["thresholds"], "year0": m["year0"], "year1": m["year1"],
                       "kind": "station", "season": m["season"], "file": "snow.json.gz",
                       "nDelPizzo": m["nQC"], "nQC": m["nQC"]})
o = {k: i for i, k in enumerate(ORDER)}
idx["hazards"].sort(key=lambda h: o.get(h["key"], 99))
json.dump(idx, open(sys.argv[2], "w"), indent=1)
print([h["key"] for h in idx["hazards"]])
