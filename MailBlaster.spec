# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for MailBlaster — windowed (no console) one-folder build.

from PyInstaller.utils.hooks import collect_submodules

datas = [("static", "static")]
hiddenimports = ["app_paths", "store", "mailer", "templates_data", "inbox_sync", "tunnel"]
hiddenimports += collect_submodules("dns")   # dnspython (MX/SPF/DMARC checks)

a = Analysis(
    ["server.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "IPython", "notebook", "pytest", "numpy", "PIL"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="MailBlaster",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False, icon="mailblaster.ico")
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, upx_exclude=[],
               name="MailBlaster")
