from banco.database import registrar_log_auditoria
from utils.sessao import obter_sessao


def registrar_acao(
    acao,
    descricao,
    modulo=None,
    registro_id=None,
    detalhes=None,
    usuario_id=None,
    usuario_nome=None,
    usuario_login=None,
):
    try:
        sessao = obter_sessao() or {}
        id_usuario = usuario_id
        nome = usuario_nome
        login = usuario_login

        if id_usuario is None:
            id_usuario = sessao.get("id_usuario") or sessao.get("id")
        if nome is None:
            nome = sessao.get("nome")
        if login is None:
            login = sessao.get("login") or sessao.get("usuario")

        return registrar_log_auditoria(
            acao=acao,
            descricao=descricao,
            usuario_id=id_usuario,
            usuario_nome=nome,
            usuario_login=login,
            modulo=modulo,
            registro_id=registro_id,
            detalhes=detalhes,
        )
    except Exception as erro:
        try:
            print(f"[AUDITORIA] Falha no servico de auditoria: {erro}")
        except Exception:
            pass
        return None
