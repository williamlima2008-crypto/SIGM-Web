"""Configuracao online (pre-cadastro online): status, link, QR code e chave.

Usa os mesmos servicos do desktop. Ativar e testar a integracao falam com o
SIGM Online e so o Administrador pode fazer isso.
"""

from pathlib import Path

from flask import abort, jsonify, render_template, request, send_file, session

from banco.database import buscar_configuracao_online_igreja, salvar_configuracao_online_igreja
from config import configuracoes
from servicos.cliente_sigm_online import (
    SIGMOnlineConexaoErro,
    SIGMOnlineErro,
    SIGMOnlineTimeoutErro,
)
from servicos.identidade_online_igreja import (
    API_BASE_URL_PADRAO,
    IdentidadeOnlineIgrejaErro,
    ativar_integracao_online_igreja,
    mascarar_chave_sincronizacao,
    montar_url_formulario,
    testar_ou_recuperar_integracao_online_igreja,
)
from utils.auditoria import registrar_acao
from utils.caminhos import caminho_dados
from utils.qrcode_igreja import QRCodeIgrejaErro, gerar_qrcode_igreja


def pasta_qrcodes():
    return caminho_dados("qrcodes", criar_pai=False)


def _url_publica(config):
    dados = dict(config or {})
    dados["api_base_url"] = API_BASE_URL_PADRAO
    dados["formulario_url"] = ""
    return montar_url_formulario(dados)


def caminho_qrcode(config):
    texto = str((config or {}).get("qr_code_path") or "").strip()
    if not texto or "\x00" in texto:
        return None
    caminho = Path(texto)
    try:
        caminho.resolve().relative_to(pasta_qrcodes().resolve())
    except (ValueError, OSError):
        return None
    return caminho if caminho.is_file() and caminho.suffix.lower() == ".png" else None


def montar_status():
    config = buscar_configuracao_online_igreja()
    identificador = config.get("identificador_publico") or ""
    chave = config.get("chave_sincronizacao") or ""
    configurado = bool(identificador and chave)
    ativado = configurado and int(config.get("ativo") or 0) == 1
    qr = caminho_qrcode(config)
    return {
        "configurado": configurado,
        "ativado": ativado,
        "estado": "Conectado" if ativado else "Ativação pendente" if configurado else "Não conectado",
        "identificador": identificador,
        "chave_mascarada": mascarar_chave_sincronizacao(chave) if chave else "",
        "tem_chave": bool(chave),
        "servidor": API_BASE_URL_PADRAO,
        "link": _url_publica(config) if configurado else "",
        "ultima_sincronizacao": config.get("ultima_sincronizacao") or "",
        "qrcode": {"existe": qr is not None, "versao": int(qr.stat().st_mtime) if qr else 0},
    }


def registrar_rotas_configuracao_online(app, exige_login, exige_admin, dados_igreja, menu_usuario):
    @app.get("/online")
    @exige_login
    def pagina_online():
        return render_template(
            "online.html", igreja=dados_igreja(), sistema=configuracoes.NOME_SISTEMA,
            usuario=session.get("usuario"), menu=menu_usuario("online"),
        )

    @app.get("/api/online")
    @exige_login
    def api_online():
        eh_admin = (session.get("usuario") or {}).get("perfil") == "Administrador"
        return jsonify(**montar_status(), admin=eh_admin)

    @app.post("/api/online/ativar")
    @exige_login
    @exige_admin
    def api_online_ativar():
        try:
            resultado = ativar_integracao_online_igreja()
            registrar_acao("IDENTIDADE_ONLINE_IGREJA_INICIALIZADA", "Identidade online da igreja ativada.",
                           modulo="Pre-cadastros", registro_id=1,
                           detalhes=f"Status: {resultado.get('status') or 'ativada'} (versão web)")
            return jsonify(ok=True, mensagem="Integração online ativada com sucesso.", **montar_status())
        except IdentidadeOnlineIgrejaErro as erro:
            return jsonify(ok=False, mensagem=str(erro)), 400
        except (SIGMOnlineConexaoErro, SIGMOnlineTimeoutErro):
            return jsonify(ok=False, mensagem="A identidade foi criada, mas não foi possível concluir a "
                           "ativação online. Tente novamente quando houver conexão."), 502
        except SIGMOnlineErro as erro:
            return jsonify(ok=False, mensagem=erro.mensagem_diagnostico()), 502
        except Exception:
            return jsonify(ok=False, mensagem="Não foi possível ativar a integração online. Tente novamente."), 500

    @app.post("/api/online/testar")
    @exige_login
    @exige_admin
    def api_online_testar():
        config = buscar_configuracao_online_igreja()
        if not (config.get("identificador_publico") and config.get("chave_sincronizacao")):
            return jsonify(ok=False, mensagem="Inicialize primeiro a identidade online."), 400
        try:
            resultado = testar_ou_recuperar_integracao_online_igreja()
            mensagem = ("Integração online reativada com sucesso." if resultado.get("recuperada")
                        else "Conexão com o SIGM Online realizada com sucesso.")
            return jsonify(ok=True, mensagem=mensagem, **montar_status())
        except IdentidadeOnlineIgrejaErro as erro:
            return jsonify(ok=False, mensagem=str(erro)), 400
        except SIGMOnlineErro as erro:
            return jsonify(ok=False, mensagem=erro.mensagem_diagnostico()), 502
        except Exception:
            return jsonify(ok=False, mensagem="Não foi possível testar a conexão com o SIGM Online."), 500

    @app.post("/api/online/qrcode")
    @exige_login
    def api_online_qrcode():
        status = montar_status()
        if not status["ativado"]:
            return jsonify(ok=False, mensagem="Ative a integração online antes de gerar o QR Code."), 400
        destino = caminho_dados("qrcodes", "qrcode_pre_cadastro_igreja.png")
        try:
            gerado = gerar_qrcode_igreja(status["link"], destino)
            salvar_configuracao_online_igreja({"qr_code_path": gerado})
        except QRCodeIgrejaErro as erro:
            return jsonify(ok=False, mensagem=str(erro)), 400
        except Exception as erro:
            return jsonify(ok=False, mensagem=f"Não foi possível gerar o QR Code: {erro}"), 500
        registrar_acao("QRCODE_PRE_CADASTRO_GERADO", "QR Code de pre-cadastro gerado.",
                       modulo="Pre-cadastros", registro_id=1,
                       detalhes="Conteudo: URL publica do formulario com identificador publico.")
        return jsonify(ok=True, mensagem="QR Code gerado.", **montar_status())

    @app.get("/api/online/qrcode.png")
    @exige_login
    def api_online_qrcode_imagem():
        caminho = caminho_qrcode(buscar_configuracao_online_igreja())
        if not caminho:
            abort(404)
        baixar = request.args.get("baixar") == "1"
        return send_file(caminho, mimetype="image/png", as_attachment=baixar,
                         download_name="qrcode_pre_cadastro.png")

    @app.post("/api/online/chave")
    @exige_login
    @exige_admin
    def api_online_chave():
        chave = buscar_configuracao_online_igreja().get("chave_sincronizacao") or ""
        if not chave:
            return jsonify(ok=False, mensagem="A chave de sincronização ainda não foi gerada."), 404
        registrar_acao("CHAVE_SINCRONIZACAO_EXIBIDA", "Chave de sincronizacao exibida pela versao web.",
                       modulo="Pre-cadastros", registro_id=1)
        return jsonify(ok=True, chave=chave)
