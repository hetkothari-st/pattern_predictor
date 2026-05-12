from .cup_handle import CupHandle
from .double_top_bottom import DoubleTopBottom
from .flag_pennant import FlagPennant
from .head_shoulders import HeadAndShoulders
from .triangle import Triangle
from .wedge import Wedge

REGISTRY = [
    HeadAndShoulders,
    DoubleTopBottom,
    Triangle,
    Wedge,
    FlagPennant,
    CupHandle,
]
