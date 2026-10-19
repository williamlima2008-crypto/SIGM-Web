"""Limite de tentativas de login/recuperacao que sobrevive ao reinicio do app.

Guarda as falhas em um arquivo JSON na pasta de dados (so o necessario:
escopo + chave, quantidade e horario da ultima falha).
"""

import json
import threading
import time
from pathlib import Path

from utils.caminhos import caminho_dados

_trava = threading.Lock()


def _arquivo():
    return Path(caminho_dados("tentativas_web.json"))


def _ler():
    try:
        dados = json.loads(_arquivo().read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def _gravar(dados):
    try:
        _arquivo().write_text(json.dumps(dados), encoding="utf-8")
    except OSError:
        pass  # sem disco: o limite continua valendo so nesta execucao


def _chave(escopo, chave):
    return f"{escopo}|{chave}"


def bloqueado(escopo, chave, maximo, janela):
    with _trava:
        total, ultimo = _ler().get(_chave(escopo, chave), (0, 0.0))
        return total >= maximo and time.time() - ultimo < janela


def falhou(escopo, chave, janela):
    with _trava:
        dados = _ler()
        agora = time.time()
        for k in [k for k, (_, t) in dados.items() if agora - t >= janela]:
            dados.pop(k, None)
        total, _ = dados.get(_chave(escopo, chave), (0, 0.0))
        dados[_chave(escopo, chave)] = (total + 1, agora)
        _gravar(dados)


def limpar(escopo, chave):
    with _trava:
        dados = _ler()
        if dados.pop(_chave(escopo, chave), None) is not None:
            _gravar(dados)
