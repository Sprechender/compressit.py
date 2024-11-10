import os
import sys
import shutil
import subprocess
from pathlib import Path
import sv_ttk

def compile_app():
    """Compile the application into a Windows executable"""
    print("Starting compilation process...")

    # Ensure PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Get sv_ttk package location and theme files
    sv_ttk_path = os.path.dirname(sv_ttk.__file__)
    
    # Create spec file content
    spec_content = f'''
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['media_compressor_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        (r'{sv_ttk_path}', 'sv_ttk'),
        ('assets', 'assets'),
    ],
    hiddenimports=[
        'PIL._tkinter_finder',
        'tkinterdnd2',
        'ffmpeg',
        'matplotlib',
        'sv_ttk',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# Ensure sv_ttk theme files are included
a.datas += Tree(r'{sv_ttk_path}', prefix='sv_ttk')

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='compressit',
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
    icon='assets/icon.ico'
)
'''

    # Create assets directory if it doesn't exist
    assets_dir = Path('assets')
    assets_dir.mkdir(exist_ok=True)

    # Write spec file
    with open('compressit.spec', 'w') as f:
        f.write(spec_content)

    # Run PyInstaller with spec file
    print("Running PyInstaller...")
    try:
        subprocess.check_call(['pyinstaller', 'compressit.spec', '--noconfirm'])
        print("\nCompilation successful!")
        print("Executable can be found in the 'dist' directory")
        
        # Clean up build files
        print("\nCleaning up build files...")
        if os.path.exists('build'):
            shutil.rmtree('build')
        if os.path.exists('compressit.spec'):
            os.remove('compressit.spec')
            
    except subprocess.CalledProcessError as e:
        print(f"\nError during compilation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    compile_app()