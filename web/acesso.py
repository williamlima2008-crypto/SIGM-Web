"""Primeiro acesso, recuperacao de senha por chave e tela Sobre (versao web)."""

from flask import jsonify, render_template, request, session

from banco.database import (
    buscar_configuracoes_igreja,
    cadastrar_igreja,
    cadastrar_usuario,
    listar_usuarios,
)
from config import configuracoes
from config.versao import DESENVOLVEDOR, NOME_COMPLETO, VERSAO
from servicos.recuperacao_senha import gerar_chave_recuperacao, redefinir_senha_com_chave
from utils.auditoria import registrar_acao
from web import limite_tentativas

SENHA_MINIMA = 8
LIMITE_TENTATIVAS = 5
JANELA_SEGUNDOS = 300


def registrar_rotas_acesso(app, exige_login, dados_igreja, menu_usuario):
    def _bloqueado(ip):
        return limite_tentativas.bloqueado("recuperar", ip, LIMITE_TENTATIVAS, JANELA_SEGUNDOS)

    def _falhou(ip):
        limite_tentativas.falhou("recuperar", ip, JANELA_SEGUNDOS)

    @app.post("/api/primeiro-acesso")
    def api_primeiro_acesso():
        if listar_usuarios():
            return jsonify(ok=False, mensagem="O sistema já foi configurado. Entre com seu usuário."), 403
        d = request.get_json(silent=True) or {}
        campo = lambda n: str(d.get(n) or "").strip()  # noqa: E731
        nome_igreja, ministerio, cidade, estado = (campo(n) for n in ("nome_igreja", "ministerio", "cidade", "estado"))
        nome_admin, usuario, senha, confirmar = (campo(n) for n in ("nome_admin", "usuario", "senha", "confirmar"))
        if not (nome_igreja and nome_admin and usuario and senha):
            return jsonify(ok=False, mensagem="Preencha os campos obrigatórios."), 400
        if " " in usuario:
            return jsonify(ok=False, mensagem="O login não pode ter espaços."), 400
        if len(senha) < SENHA_MINIMA:
            return jsonify(ok=False, mensagem=f"A senha deve ter pelo menos {SENHA_MINIMA} caracteres."), 400
        if senha != confirmar:
            return jsonify(ok=False, mensagem="As senhas não conferem."), 400
        cadastrar_igreja(nome_igreja, ministerio, cidade.strip(), estado.strip().upper())
        id_usuario = cadastrar_usuario(nome_admin, usuario, senha, "Administrador")
        registrar_acao("USUARIO_CRIADO", f"Usuario {usuario} criado.", modulo="Usuarios",
                       registro_id=id_usuario, usuario_nome=nome_admin, usuario_login=usuario)
        try:
            chave = gerar_chave_recuperacao()
        except Exception:
            chave = ""
        return jsonify(ok=True, chave=chave, mensagem="Configuração concluída.")

    @app.post("/api/recuperar-senha")
    def api_recuperar_senha():
        ip = request.remote_addr
        if _bloqueado(ip):
            return jsonify(ok=False, mensagem="Muitas tentativas. Aguarde 5 minutos."), 429
        d = request.get_json(silent=True) or {}
        usuario = str(d.get("usuario") or "").strip()
        chave = str(d.get("chave") or "").strip()
        nova = str(d.get("senha") or "").strip()
        confirmar = str(d.get("confirmar") or "").strip()
        if not (usuario and chave and nova and confirmar):
            return jsonify(ok=False, mensagem="Preencha todos os campos."), 400
        if nova != confirmar:
            return jsonify(ok=False, mensagem="As senhas não conferem."), 400
        if len(nova) < SENHA_MINIMA:
            return jsonify(ok=False, mensagem=f"A senha deve ter pelo menos {SENHA_MINIMA} caracteres."), 400
        sucesso, mensagem, dados = redefinir_senha_com_chave(usuario, chave, nova)
        if not sucesso:
            _falhou(ip)
            registrar_acao("RECUPERACAO_SENHA_FALHA",
                           f"Tentativa de recuperacao de senha recusada para o usuario {usuario}.",
                           modulo="Autenticacao", usuario_login=usuario)
            return jsonify(ok=False, mensagem=mensagem), 400
        limite_tentativas.limpar("recuperar", ip)
        registrar_acao("SENHA_REDEFINIDA_POR_CHAVE",
                       f"Senha do usuario {dados['usuario']} redefinida pela chave de recuperacao.",
                       modulo="Autenticacao", registro_id=dados["id"],
                       usuario_login=dados["usuario"], usuario_nome=dados["nome"])
        return jsonify(ok=True, mensagem="Senha redefinida. Entre com a nova senha.")

    @app.get("/sobre")
    @exige_login
    def pagina_sobre():
        igreja = buscar_configuracoes_igreja()
        local = " - ".join(p for p in (igreja.get("cidade"), igreja.get("estado")) if p)
        return render_template(
            "sobre.html", igreja=dados_igreja(), sistema=configuracoes.NOME_SISTEMA,
            usuario=session.get("usuario"), menu=menu_usuario("sobre"),
            nome_completo=NOME_COMPLETO, versao=VERSAO, desenvolvedor=DESENVOLVEDOR,
            nome_igreja=igreja.get("nome_igreja") or "", local=local,
        )
