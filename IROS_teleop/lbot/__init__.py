"""LBot Python API.

Legacy 1.0.1 symbols are loaded lazily so importing the isolated 1.0.3 binding
does not load both incompatible SDK ABIs into one process.
"""

from importlib import import_module

__version__ = "1.0.0"
__all__ = [
    'LbotArm', 'LbotMoveType', 'LbotPosition', 'LbotOrientation',
    'LbotEuler', 'LbotArmState', 'LbotFullState', 'api'
]


def __getattr__(name):
    if name in __all__:
        return getattr(import_module(".lbot_api", __name__), name)
    raise AttributeError(name)
