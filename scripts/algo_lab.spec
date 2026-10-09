# PyInstaller recipe for the Windows download. Run it with scripts\build_exe.bat, not directly.
# A "one-folder" build: dist/AlgoTradingLab/AlgoTradingLab.exe plus a folder of support files. It starts
# faster than a single giant .exe and is flagged by antivirus programs less often.
from PyInstaller.utils.hooks import collect_submodules

root = SPECPATH.rsplit("\\", 1)[0].rsplit("/", 1)[0]  # the repo root (this file is in scripts/)

# uvicorn and SQLAlchemy pick pieces by name at run time, so PyInstaller can't see them by reading imports.
hidden = (
    collect_submodules("uvicorn")
    + collect_submodules("websockets")
    + collect_submodules("backend")
    + ["sqlalchemy.dialects.sqlite", "h11"]
)

a = Analysis(
    [root + "/desktop/launcher.py"],
    pathex=[root],
    datas=[(root + "/frontend", "frontend")],
    hiddenimports=hidden,
    excludes=["pytest", "tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="AlgoTradingLab", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="AlgoTradingLab")
