_sessao_atual = None


def iniciar_sessao(usuario):
    global _sessao_atual

    if not usuario:
        _sessao_atual = None
        return None

    _sessao_atual = {
        "id_usuario": usuario.get("id_usuario") or usuario.get("id"),
        "nome": usuario.get("nome", ""),
        "login": usuario.get("login") or usuario.get("usuario", ""),
        "perfil": usuario.get("perfil", ""),
        "status": usuario.get("status", ""),
    }
    return dict(_sessao_atual)


def obter_sessao():
    if _sessao_atual is None:
        return None
    return dict(_sessao_atual)


def limpar_sessao():
    global _sessao_atual
    _sessao_atual = None


def usuario_eh_administrador():
    sessao = obter_sessao()
    return bool(sessao and sessao.get("perfil") == "Administrador")
