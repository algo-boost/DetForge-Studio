# -*- mode: python ; coding: utf-8 -*-
# DefectLoop Studio (DetForge-Studio) — Windows PyInstaller 配置
# 用法: cd frontend && npm run build && pyinstaller detforge_studio.spec

import sys
from pathlib import Path

block_cipher = None
project_dir = Path(SPECPATH)


def _read_app_version() -> str:
    vf = project_dir / 'version.txt'
    if vf.is_file():
        for line in vf.read_text(encoding='utf-8').splitlines():
            s = line.strip()
            if s and not s.startswith('#'):
                return s
    return '0.0.0'


_app_version = _read_app_version()

datas = [
    (str(project_dir / 'frontend' / 'dist'), 'frontend/dist'),
    (str(project_dir / 'docs'), 'docs'),
    (str(project_dir / 'strategies'), 'strategies'),
    (str(project_dir / 'version.txt'), '.'),
]

hiddenimports = [
    'flask',
    'werkzeug',
    'pandas',
    'pymysql',
    'sqlalchemy',
    'PIL',
    'flask_cors',
    'markdown',
    'server',
    'server.factory',
    'server.core',
    'server.routes',
    'server.routes.api',
    'server.routes.forge',
    'server.routes.spa',
    'server.viz_mount',
    'server.unify_mount',
    'studio',
    'studio.paths',
    'studio.flow.flow_compiler',
    'studio.flow.flow_schema',
    'studio.flow.flow_registry',
    'studio.query.python_builtins',
    'studio.query.pipeline_rules',
    'studio.forge.forge_db',
    'studio.forge.forge_predict',
    'studio.forge.predict_runtime',
    'studio.brand',
    'worker',
]

a = Analysis(
    [str(project_dir / 'app.py')],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'cv2', 'scipy', 'sklearn', 'torch'],
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
    name='DefectLoop-Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='DefectLoop-Studio',
)
