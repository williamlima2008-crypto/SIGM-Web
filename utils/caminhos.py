from pathlib import Path
import os
import sys


NOME_PASTA_DADOS = "SIGM"
PASTAS_GRAVAVEIS = (
    "backup",
    "documentos_gerados",
    "arquivos_membros",
    "fotos_membros",
    "qrcodes",
    "relatorios",
    "logs",
)
PASTAS_RECURSOS = (
    "assets",
    "documentos/modelos",
    "documentos/modelos_editaveis",
)


def aplicacao_empacotada():
    return bool(getattr(sys, "frozen", False))


def base_projeto():
    return Path(__file__).resolve().parent.parent


def base_recursos():
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return base_projeto()


def base_dados():
    destino = os.environ.get("SIGM_DADOS_DIR")
    if destino:
        return Path(destino).expanduser().resolve()

    if not aplicacao_empacotada():
        return base_projeto()

    base_usuario = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base_usuario:
        return Path(base_usuario) / NOME_PASTA_DADOS

    return Path.home() / NOME_PASTA_DADOS


def caminho_recurso(*partes):
    return base_recursos().joinpath(*partes)


def caminho_dados(*partes, criar_pai=True):
    caminho = base_dados().joinpath(*partes)
    if criar_pai:
        caminho.parent.mkdir(parents=True, exist_ok=True)
    return caminho


def garantir_pastas_runtime():
    for pasta in PASTAS_GRAVAVEIS:
        caminho_dados(pasta, criar_pai=False).mkdir(parents=True, exist_ok=True)

    if not aplicacao_empacotada():
        for pasta in PASTAS_RECURSOS:
            caminho_recurso(pasta).mkdir(parents=True, exist_ok=True)
