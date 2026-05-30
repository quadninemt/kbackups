# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

project_root = os.path.abspath(os.getcwd())
src_hiddenimports = collect_submodules('src')

# tkinterdnd2 is optional — only include if installed in the current environment
try:
    import tkinterdnd2
    optional_imports = ['tkinterdnd2']
except ImportError:
    optional_imports = []

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=['smbclient', 'tkinter', 'sqlite3', 'configparser'] + optional_imports + src_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BackupUtility',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\app_icon.ico'] if os.path.exists('assets\\app_icon.ico') else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='k_backups_dist',
)
