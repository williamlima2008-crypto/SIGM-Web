# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


block_cipher = None
BASE_DIR = Path(SPECPATH).resolve()


def collect_tree(origem, destino):
    origem = BASE_DIR / origem
    arquivos = []
    if not origem.exists():
        return arquivos

    for caminho in origem.rglob("*"):
        if caminho.is_file():
            if caminho.suffix.lower() == ".png" and caminho.stat().st_size == 0:
                continue
            pasta_destino = Path(destino) / caminho.relative_to(origem).parent
            arquivos.append((str(caminho), str(pasta_destino)))

    return arquivos


datas = []
datas += collect_data_files("customtkinter")
datas += collect_tree("assets", "assets")
datas += collect_tree("documentos/modelos", "documentos/modelos")
datas += collect_tree("documentos/modelos_editaveis", "documentos/modelos_editaveis")
datas += collect_tree(Path(sys.base_prefix) / "Lib" / "tkinter", "tkinter")
datas += collect_tree(Path(sys.base_prefix) / "tcl", "tcl")

binaries = [
    (str(Path(sys.base_prefix) / "DLLs" / "_tkinter.pyd"), "."),
    (str(Path(sys.base_prefix) / "DLLs" / "tcl86t.dll"), "."),
    (str(Path(sys.base_prefix) / "DLLs" / "tk86t.dll"), "."),
]

hiddenimports = collect_submodules("pypdf")
hiddenimports += collect_submodules("qrcode")


a = Analysis(
    ["app.py"],
    pathex=[str(BASE_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(BASE_DIR / "hooks" / "pyi_rth_sigm_tkinter.py")],
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
    name="SIGM",
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
    icon=str(BASE_DIR / "assets" / "icones" / "sigm.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SIGM",
)
