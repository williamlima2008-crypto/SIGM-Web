from pathlib import Path
import os
import sys


base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
tcl_base = base / "tcl"

os.environ.setdefault("TCL_LIBRARY", str(tcl_base / "tcl8.6"))
os.environ.setdefault("TK_LIBRARY", str(tcl_base / "tk8.6"))

base_text = str(base)
if base_text not in sys.path:
    sys.path.insert(0, base_text)
