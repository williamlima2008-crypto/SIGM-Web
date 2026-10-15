# -*- mode: python ; coding: utf-8 -*-
# Empacota o SIGM Web (servidor local + janela do navegador) como SIGM.exe.

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
BASE_DIR = Path(SPECPATH).resolve()


def collect_tree(origem, destino):
    origem = BASE_DIR / origem
    arquivos = []
    if not origem.exists():
        return arquivos
    for caminho in origem.rglob("*"):
        if caminho.is_file() and "__pycache__" not in caminho.parts:
            if caminho.suffix.lower() == ".png" and caminho.stat().st_size == 0:
                continue
            pasta_destino = Path(destino) / caminho.relative_to(origem).parent
            arquivos.append((str(caminho), str(pasta_destino)))
    return arquivos


datas = []
datas += collect_tree("assets", "assets")
datas += collect_tree("documentos/modelos", "documentos/modelos")
datas += collect_tree("documentos/modelos_editaveis", "documentos/modelos_editaveis")
datas += collect_tree("web/templates", "web/templates")
datas += collect_tree("web/static", "web/static")

hiddenimports = []
for pacote in ("pypdf", "qrcode", "reportlab", "flask", "jinja2", "werkzeug", "PIL"):
    hiddenimports += collect_submodules(pacote)
hiddenimports += ["fitz", "requests", "sqlite3"]

a = Analysis(
    ["iniciar_web.py"],
    pathex=[str(BASE_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "customtkinter", "_tkinter",
        # bibliotecas do ambiente do desenvolvedor que o SIGM nao usa
        "pandas", "numpy", "pyarrow", "sqlalchemy", "psycopg", "psycopg2", "psycopg_binary",
        "scipy", "matplotlib", "IPython", "notebook", "pytest", "setuptools",
    ],
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
