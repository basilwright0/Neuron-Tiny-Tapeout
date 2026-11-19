"""Debug: route bias_b1 with one short schedule and print the conflict locations (no write)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["ROUTE_QUICK"] = sys.argv[1] if len(sys.argv) > 1 else "15"
import topgen as T
def fake(c, box, base=0.8, first=(), last=("vdd", "vss")):
    return c.route(box, layers=("m2", "m3"), order_first=first, order_last=last, base=base, cache=None)
T.route_and_write = fake
T.b1c(True)
