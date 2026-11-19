"""Count KLayout DRC violations per rule in a .lyrdb report."""
import sys, collections
import xml.etree.ElementTree as ET
try:
    t = ET.parse(sys.argv[1]).getroot()
except Exception as e:
    print("KLAYOUT_DRC_COUNT ? (no report:", e, ")")
    sys.exit(0)
c = collections.Counter(i.findtext("category").strip("'") for i in t.iter("item"))
print("KLAYOUT_DRC_COUNT", sum(c.values()))
for k, v in c.most_common():
    print(f"  {v:5d}  {k}")
