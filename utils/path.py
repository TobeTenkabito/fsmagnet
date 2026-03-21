# utils/path.py
import sys, os


def resource_path(relative: str) -> str:
    if hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        base = os.path.abspath('.')
    return os.path.join(base, relative)
