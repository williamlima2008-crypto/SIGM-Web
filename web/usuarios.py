"""Gerenciamento de usuarios na versao web (somente Administrador)."""

import sqlite3

from flask import jsonify, render_template, request, session

from banco.database import (
    alterar_status_usuario,
    atualizar_usuario,
    buscar_usuario_por_id,
    cadastrar_usuario,
    excluir_usuario,
    listar_usuarios,
    redefinir_senha_usuario,
)
from config import configuracoes
from servicos.recuperacao_senha import (
    data_chave_recuperacao,
    existe_chave_recuperacao,
    gerar_chave_recuperacao,
)
from utils.auditoria import registrar_acao

PERFIS = [("Administrador", "Administrador"), ("Usuario", "Usuário")]
SENHA_MINIMA = 8


def _perfil_valido(perfil):
    return perfil in dict(PERFIS)


def _limpar(dados):
    return {
        "nome": str(dados.get("nome") or "").strip(),
        "usuario": str(dados.get("usuario") or "").strip(),
        "perfil": str(dados.get("perfil") or "").strip(),
    }


def _erro_dados(dados):
    if not dados["nome"]:
        return "Informe o nome."
    if not dados["usuario"]:
        return "Informe o login do usuário."
    if " " in dados["usuario"]:
        return "O login não pode ter espaços."
    if not _perfil_valido(dados["perfil"]):
        return "Perfil inválido."
    return None


def _publico(u):
    return {"id": u["id"], "nome": u["nome"], "usuario": u["usuario"], "perfil": u["perfil"],
            "ativo": bool(u["ativo"]), "status": u["status"]}


def registrar_rotas_usuarios(app, exige_login, exige_admin, dados_igreja, menu_usuario):
    def _eu():
        return (session.get("usuario") or {}).get("id_usuario")

    @app.get("/usuarios")
    @exige_login
    @exige_admin
    def pagina_usuarios():
        return render_template(
            "usuarios.html", igreja=dados_igreja(), sistema=configuracoes.NOME_SISTEMA,
            usuario=session.get("usuario"), menu=menu_usuario("usuarios"),
            perfis=PERFIS, senha_minima=SENHA_MINIMA,
        )

    @app.get("/api/usuarios")
    @exige_login
    @exige_admin
    def api_usuarios():
        return jsonify(
            itens=[_publico(u) for u in listar_usuarios()], eu=_eu(),
            chave={"existe": existe_chave_recuperacao(), "criada_em": data_chave_recuperacao()},
        )

    @app.post("/api/usuarios")
    @exige_login
    @exige_admin
    def api_usuario_criar():
        bruto = request.get_json(silent=True) or {}
        dados = _limpar(bruto)
        senha = str(bruto.get("senha") or "").strip()
        erro = _erro_dados(dados)
        if not erro and len(senha) < SENHA_MINIMA:
            erro = f"A senha deve ter pelo menos {SENHA_MINIMA} caracteres."
        if erro:
            return jsonify(ok=False, mensagem=erro), 400
        try:
            id_usuario = cadastrar_usuario(dados["nome"], dados["usuario"], senha, dados["perfil"])
        except sqlite3.IntegrityError:
            return jsonify(ok=False, mensagem="Já existe um usuário com esse login."), 400
        registrar_acao("USUARIO_CRIADO", f"Usuario {dados['usuario']} criado.",
                       modulo="Usuarios", registro_id=id_usuario)
        return jsonify(ok=True, id=id_usuario, mensagem="Usuário cadastrado.")

    @app.put("/api/usuarios/<int:id_usuario>")
    @exige_login
    @exige_admin
    def api_usuario_editar(id_usuario):
        atual = buscar_usuario_por_id(id_usuario)
        if not atual:
            return jsonify(ok=False, mensagem="Usuário não encontrado."), 404
        bruto = request.get_json(silent=True) or {}
        dados = _limpar(bruto)
        ativo = 1 if bruto.get("ativo", bool(atual["ativo"])) else 0
        erro = _erro_dados(dados)
        if not erro and id_usuario == _eu() and (ativo != 1 or dados["perfil"] != "Administrador"):
            erro = "Você não pode bloquear nem rebaixar o seu próprio usuário."
        if erro:
            return jsonify(ok=False, mensagem=erro), 400
        try:
            atualizar_usuario(id_usuario, dados["nome"], dados["usuario"], dados["perfil"], ativo)
        except ValueError as e:
            return jsonify(ok=False, mensagem=str(e)), 400
        except sqlite3.IntegrityError:
            return jsonify(ok=False, mensagem="Já existe um usuário com esse login."), 400
        registrar_acao("USUARIO_EDITADO", f"Usuario {dados['usuario']} editado.",
                       modulo="Usuarios", registro_id=id_usuario)
        if int(atual["ativo"]) != ativo:
            registrar_acao("USUARIO_DESBLOQUEADO" if ativo else "USUARIO_BLOQUEADO",
                           f"Usuario {dados['usuario']} foi {'desbloqueado' if ativo else 'bloqueado'}.",
                           modulo="Usuarios", registro_id=id_usuario)
        return jsonify(ok=True, mensagem="Usuário atualizado.")

    @app.post("/api/usuarios/<int:id_usuario>/senha")
    @exige_login
    @exige_admin
    def api_usuario_senha(id_usuario):
        usuario = buscar_usuario_por_id(id_usuario)
        if not usuario:
            return jsonify(ok=False, mensagem="Usuário não encontrado."), 404
        senha = str((request.get_json(silent=True) or {}).get("senha") or "").strip()
        if len(senha) < SENHA_MINIMA:
            return jsonify(ok=False, mensagem=f"A senha deve ter pelo menos {SENHA_MINIMA} caracteres."), 400
        redefinir_senha_usuario(id_usuario, senha)
        registrar_acao("SENHA_REDEFINIDA", f"Senha do usuario {usuario['usuario']} foi redefinida.",
                       modulo="Usuarios", registro_id=id_usuario)
        return jsonify(ok=True, mensagem="Senha redefinida.")

    @app.post("/api/usuarios/<int:id_usuario>/status")
    @exige_login
    @exige_admin
    def api_usuario_status(id_usuario):
        usuario = buscar_usuario_por_id(id_usuario)
        if not usuario:
            return jsonify(ok=False, mensagem="Usuário não encontrado."), 404
        ativo = 1 if (request.get_json(silent=True) or {}).get("ativo") else 0
        if not ativo and id_usuario == _eu():
            return jsonify(ok=False, mensagem="Você não pode bloquear o seu próprio usuário."), 400
        try:
            alterar_status_usuario(id_usuario, ativo)
        except ValueError as e:
            return jsonify(ok=False, mensagem=str(e)), 400
        registrar_acao("USUARIO_DESBLOQUEADO" if ativo else "USUARIO_BLOQUEADO",
                       f"Usuario {usuario['usuario']} foi {'desbloqueado' if ativo else 'bloqueado'}.",
                       modulo="Usuarios", registro_id=id_usuario)
        return jsonify(ok=True, mensagem="Usuário desbloqueado." if ativo else "Usuário bloqueado.")

    @app.post("/api/usuarios/<int:id_usuario>/excluir")
    @exige_login
    @exige_admin
    def api_usuario_excluir(id_usuario):
        usuario = buscar_usuario_por_id(id_usuario)
        if not usuario:
            return jsonify(ok=False, mensagem="Usuário não encontrado."), 404
        if id_usuario == _eu():
            return jsonify(ok=False, mensagem="Você não pode excluir o seu próprio usuário."), 400
        try:
            excluir_usuario(id_usuario)
        except ValueError as e:
            return jsonify(ok=False, mensagem=str(e)), 400
        registrar_acao("USUARIO_EXCLUIDO", f"Usuario {usuario['usuario']} excluido.",
                       modulo="Usuarios", registro_id=id_usuario)
        return jsonify(ok=True, mensagem="Usuário excluído.")

    @app.post("/api/usuarios/chave-recuperacao")
    @exige_login
    @exige_admin
    def api_chave_recuperacao():
        chave = gerar_chave_recuperacao()
        registrar_acao("CHAVE_RECUPERACAO_GERADA", "Nova chave de recuperacao de senha gerada.",
                       modulo="Usuarios")
        return jsonify(ok=True, chave=chave,
                       mensagem="Chave gerada. Ela aparece só desta vez: guarde em local seguro.")
