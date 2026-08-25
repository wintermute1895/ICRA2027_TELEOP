"""Hardware adapters and an offline adapter used by the recorder."""
from __future__ import annotations
import sys
from typing import Protocol

class HandAdapter(Protocol):
    name: str; joint_count: int; minimum: float; maximum: float
    def read(self) -> list[float]: ...
    def write(self, values: list[float]) -> None: ...
    def close(self) -> None: ...

class SimulatedHand:
    def __init__(self, hand: str):
        self.name = hand.upper(); self.joint_count = 10 if self.name == "L10" else 6
        self.minimum, self.maximum = (0.0, 255.0) if self.name == "L10" else (0.0, 100.0)
        self.values = [50.0] * self.joint_count
    def read(self): return list(self.values)
    def write(self, values): self.values = list(values)
    def close(self): pass

class L10Hand:
    name, joint_count, minimum, maximum = "L10", 10, 0.0, 255.0
    def __init__(self, side="left", can="can0"):
        root = __import__("pathlib").Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "LinkerHand"))
        from linker_hand_api import LinkerHandApi
        self.hand = LinkerHandApi(hand_type=side, hand_joint="L10", can=can)
    def read(self): return [float(v) for v in self.hand.get_state()]
    def write(self, values): self.hand.finger_move([int(round(v)) for v in values])
    def close(self):
        if hasattr(self.hand, "close_can"): self.hand.close_can()

class O6Hand:
    name, joint_count, minimum, maximum = "O6", 6, 0.0, 100.0
    def __init__(self, side="left", can="can0"):
        root = __import__("pathlib").Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "thrid_party" / "linkerbot-python-sdk-main" / "src"))
        from linkerbot.hand.o6 import O6
        self.hand = O6(side=side, interface_name=can)
    def read(self): return [float(v) for v in self.hand.angle.get_blocking(timeout_ms=500).angles.to_list()]
    def write(self, values): self.hand.angle.set_angles(list(values))
    def close(self): self.hand.close()

def create_adapter(hand: str, side="left", can="can0", simulate=False):
    if simulate: return SimulatedHand(hand)
    return L10Hand(side, can) if hand.upper() == "L10" else O6Hand(side, can)
