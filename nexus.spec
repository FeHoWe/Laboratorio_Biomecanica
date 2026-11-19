# PyInstaller spec — NEXUS BIOMECHANICS
# Uso: pyinstaller nexus.spec --noconfirm
from PyInstaller.utils.hooks import collect_submodules

hidden = collect_submodules("application") + collect_submodules("interface") + \
         collect_submodules("core") + collect_submodules("biomechanics") + \
         collect_submodules("simulation") + collect_submodules("research") + \
         collect_submodules("infrastructure") + collect_submodules("visualization") + \
         ["matplotlib.backends.backend_qtagg", "matplotlib.backends.backend_agg", "matplotlib.backends.backend_pdf"]

a = Analysis(["main.py"], pathex=["."], datas=[("config/settings.json", "config")],
             hiddenimports=hidden, excludes=["tkinter", "pkg_resources", "setuptools", "PySide6.QtWebEngineCore", "PySide6.QtQuick"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="NEXUS_BIOMECHANICS", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="NEXUS_BIOMECHANICS")
