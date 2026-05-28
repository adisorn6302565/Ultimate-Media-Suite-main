# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Add FFmpeg and yt-dlp binaries if they exist
print("\n" + "="*80)
print("  Ultimate Media Suite - Packaging Process")
print("="*80)

if os.path.exists('bin'):
    files_to_bundle = []
    
    # Check each file individually
    if os.path.exists('bin/ffmpeg.exe'):
        files_to_bundle.append(('bin/ffmpeg.exe', 'bin'))
        print("[OK] Bundling: ffmpeg.exe (Found)")
    else:
        print("[MISSING] bin/ffmpeg.exe - Conversion feature will be disabled in exe!")
    
    if os.path.exists('bin/ffprobe.exe'):
        files_to_bundle.append(('bin/ffprobe.exe', 'bin'))
        print("[OK] Bundling: ffprobe.exe (Found)")
    else:
        print("[MISSING] bin/ffprobe.exe - Media analysis feature will be disabled in exe!")
    
    if os.path.exists('bin/yt-dlp.exe'):
        files_to_bundle.append(('bin/yt-dlp.exe', 'bin'))
        print("[OK] Bundling: yt-dlp.exe (Found)")
    else:
        print("[MISSING] bin/yt-dlp.exe - Download feature will be disabled in exe!")
    
    if files_to_bundle:
        datas += files_to_bundle
        print(f"\nTotal: {len(files_to_bundle)} engine files bundled.")
    else:
        print("\n[WARN] No engine binaries found in bin/ folder!")
else:
    print("[ERROR] bin/ folder not found!")

# Add logo if exists
if os.path.exists('logo.ico'):
    print("[OK] Added: Custom Application Icon (logo.ico)")
else:
    print("[WARN] No logo.ico found, using default window icon.")

print("="*80 + "\n")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Ultimate Media Suite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['logo.ico'] if os.path.exists('logo.ico') else None,
)
