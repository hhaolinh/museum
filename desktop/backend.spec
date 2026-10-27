from pathlib import Path
ROOT = Path(SPECPATH).parent
analysis = Analysis(
    [str(ROOT / 'desktop/server.py')], pathex=[str(ROOT)],
    binaries=[], datas=[(str(ROOT / name), name) for name in ('templates', 'static', 'data')],
    hiddenimports=['PIL._webp'], excludes=['pytest', 'tkinter', 'matplotlib', 'numpy', 'babel', 'geonamescache'],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name='CabinetServer',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=True, target_arch='arm64', codesign_identity=None)
collection = COLLECT(exe, analysis.binaries, analysis.datas, strip=False, upx=False, name='CabinetServer')
app = BUNDLE(collection, name='CabinetServer.app', bundle_identifier='io.github.hhaolinh.cabinet.server',
             info_plist={'LSBackgroundOnly': True, 'LSMinimumSystemVersion': '12.0'})
