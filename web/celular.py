"""Sincronizacao com o SIGM Celular na versao web.

Usa o mesmo servico do desktop (servicos/sincronizacao_celular.py): o computador
da igreja ENVIA os membros, a configuracao e o logotipo ao Celular, e trata as
ALTERACOES sugeridas por la (aplicar ou rejeitar). O envio roda em segundo plano
e a tela acompanha o andamento.
"""

import threading
from datetime import datetime

from flask import jsonify, render_template, request, session

from banco.database import buscar_configuracao_online_igreja
from config import configuracoes
from servicos import sincronizacao_celular as celular
from utils.auditoria import registrar_acao as _registrar_acao_padrao

_trava = threading.Lock()
_estado = {"em_andamento": False, "mensagem": "", "erro": "", "resumo": None, "concluido_em": ""}
_contexto = threading.local()


def _registrar_acao(*args, **kwargs):
    """Auditoria com o usuario certo tambem no envio em segundo plano.

    Na thread do envio nao ha sessao da requisicao; o usuario que clicou em
    Enviar e guardado ao iniciar e entra aqui.
    """
    usuario = getattr(_contexto, "usuario", None)
    if usuario:
        kwargs.setdefault("usuario_id", usuario.get("id_usuario") or usuario.get("id"))
        kwargs.setdefault("usuario_nome", usuario.get("nome"))
        kwargs.setdefault("usuario_login", usuario.get("login"))
    return _registrar_acao_padrao(*args, **kwargs)


celular.registrar_acao = _registrar_acao


def _definir(**campos):
    with _trava:
        _estado.update(campos)


def _copia_estado():
    with _trava:
        return dict(_estado)


def _integracao_ativa():
    config = buscar_configuracao_online_igreja()
    return bool(
        int(config.get("ativo") or 0)
        and config.get("identificador_publico")
        and config.get("chave_sincronizacao")
    )


def montar_status():
    estado = _copia_estado()
    estado["resumo_texto"] = celular.texto_resumo(estado["resumo"]) if estado["resumo"] else ""
    estado["ativado"] = _integracao_ativa()
    return estado


def _trabalhar(usuario):
    _contexto.usuario = usuario
    try:
        resumo = celular.enviar_dados_para_celular(progresso=lambda texto: _definir(mensagem=texto))
        _definir(
            em_andamento=False, erro="", resumo=resumo, mensagem="",
            concluido_em=datetime.now().strftime("%d/%m/%Y %H:%M"),
        )
    except Exception as erro:  # noqa: BLE001 - a mensagem amigavel vem do servico
        _definir(em_andamento=False, erro=celular.mensagem_erro(erro), mensagem="", resumo=None)
    finally:
        _contexto.usuario = None


def _alteracao_por_id(cliente, id_alteracao):
    for alteracao in cliente.listar_alteracoes():
        if str(alteracao.get("id")) == str(id_alteracao):
            return alteracao
    return None


def registrar_rotas_celular(app, exige_login, dados_igreja, menu_usuario):
    @app.get("/celular")
    @exige_login
    def pagina_celular():
        return render_template(
            "celular.html", igreja=dados_igreja(), sistema=configuracoes.NOME_SISTEMA,
            usuario=session.get("usuario"), menu=menu_usuario("celular"),
        )

    @app.get("/api/celular")
    @exige_login
    def api_celular():
        return jsonify(**montar_status())

    @app.post("/api/celular/enviar")
    @exige_login
    def api_celular_enviar():
        if not _integracao_ativa():
            return jsonify(ok=False, mensagem="Ative a integração online da igreja (menu Pré-cadastro online) "
                           "antes de sincronizar com o Celular."), 400
        with _trava:
            if _estado["em_andamento"]:
                return jsonify(ok=False, mensagem="Já existe um envio em andamento."), 409
            _estado.update(em_andamento=True, mensagem="Enviando dados ao Celular...", erro="", resumo=None)
        usuario = dict(session.get("usuario") or {})
        threading.Thread(target=_trabalhar, args=(usuario,), daemon=True).start()
        return jsonify(ok=True, mensagem="Envio iniciado.")

    @app.post("/api/celular/alteracoes/buscar")
    @exige_login
    def api_celular_buscar():
        try:
            alteracoes = celular.buscar_alteracoes()
        except Exception as erro:  # noqa: BLE001
            return jsonify(ok=False, mensagem=celular.mensagem_erro(erro)), 502
        return jsonify(ok=True, alteracoes=alteracoes)

    @app.post("/api/celular/alteracoes/responder")
    @exige_login
    def api_celular_responder():
        dados = request.get_json(silent=True) or {}
        acao = dados.get("acao")
        if acao not in ("aplicar", "rejeitar") or dados.get("id") in (None, ""):
            return jsonify(ok=False, mensagem="Pedido inválido."), 400
        try:
            cliente = celular.criar_cliente()
            alteracao = _alteracao_por_id(cliente, dados["id"])
            if alteracao is None:
                return jsonify(ok=False, mensagem="Esta sugestão já foi tratada ou não existe mais."), 404
            mensagem = celular.responder_alteracao(
                cliente, alteracao, acao == "aplicar", str(dados.get("motivo") or "")[:200],
            )
        except Exception as erro:  # noqa: BLE001
            return jsonify(ok=False, mensagem=celular.mensagem_erro(erro)), 502
        return jsonify(ok=True, mensagem=mensagem)
