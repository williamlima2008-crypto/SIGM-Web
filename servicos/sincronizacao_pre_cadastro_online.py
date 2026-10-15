import json
from datetime import datetime

from banco.database import (
    atualizar_ultima_sincronizacao,
    buscar_configuracao_online_igreja,
    registrar_sincronizacao_pre_cadastro,
    salvar_pre_cadastro,
)
from servicos.cliente_sigm_online import (
    ClienteSIGMOnline,
    SIGMOnlineAutenticacaoErro,
    SIGMOnlineConfiguracaoErro,
    SIGMOnlineConexaoErro,
    SIGMOnlineErro,
    SIGMOnlineRespostaErro,
    SIGMOnlineTimeoutErro,
)
from servicos.importador_pre_cadastro_json import normalizar_item
from utils.auditoria import registrar_acao


ORIGEM_ONLINE = "online"
MENSAGEM_SEM_NOVOS = "Nenhum novo pre-cadastro esta disponivel."
MENSAGEM_CONFIRMACAO_FALHOU = (
    "Os pre-cadastros foram salvos no computador, mas a confirmacao online "
    "nao foi concluida. Uma nova sincronizacao podera tentar novamente."
)


class RegistroOnlineInvalido(ValueError):
    pass


def agora_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def validar_iso8601(valor):
    texto = str(valor or "").strip()
    if not texto:
        return True
    try:
        datetime.fromisoformat(texto.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def payload_json_seguro(item):
    return json.dumps(item, ensure_ascii=False, sort_keys=True)


def normalizar_registro_online(item, identificador_publico):
    if not isinstance(item, dict):
        raise RegistroOnlineInvalido("registro nao e objeto")

    remote_id = str(item.get("remote_id") or "").strip()
    if not remote_id:
        raise RegistroOnlineInvalido("remote_id ausente")

    dados = item.get("dados")
    if not isinstance(dados, dict):
        raise RegistroOnlineInvalido("dados nao e objeto")

    for campo_data in ("criado_em", "atualizado_em", "recebido_em", "enviado_em"):
        if campo_data in item and not validar_iso8601(item.get(campo_data)):
            raise RegistroOnlineInvalido(f"{campo_data} invalido")

    dados_para_normalizar = dict(dados)
    dados_para_normalizar["remote_id"] = remote_id
    dados_para_normalizar["identificador_publico_igreja"] = (
        item.get("identificador_publico_igreja") or identificador_publico
    )

    normalizado = normalizar_item(dados_para_normalizar)
    normalizado["remote_id"] = remote_id
    normalizado["identificador_publico_igreja"] = str(
        normalizado.get("identificador_publico_igreja") or identificador_publico
    ).strip()
    normalizado["payload_json"] = payload_json_seguro(item)
    normalizado["origem"] = ORIGEM_ONLINE
    normalizado["status"] = "pendente"
    normalizado["recebido_em"] = agora_iso()
    return normalizado


def relatorio_base():
    return {
        "sucesso": False,
        "status": "erro",
        "mensagem_usuario": "",
        "total_recebido": 0,
        "inseridos": 0,
        "existentes": 0,
        "erros": 0,
        "erros_itens": [],
        "remote_ids_confirmados": [],
        "confirmacao": None,
        "confirmacao_ok": False,
        "confirmacao_falhou": False,
    }


def mensagem_resultado(relatorio):
    inseridos = int(relatorio.get("inseridos") or 0)
    existentes = int(relatorio.get("existentes") or 0)
    erros = int(relatorio.get("erros") or 0)

    if relatorio.get("confirmacao_falhou"):
        return MENSAGEM_CONFIRMACAO_FALHOU
    if inseridos == 0 and existentes == 0 and erros == 0:
        return MENSAGEM_SEM_NOVOS
    if erros:
        recebidos = inseridos + existentes
        return (
            f"Sincronizacao concluida parcialmente. {recebidos} registros foram "
            f"recebidos e {erros} apresentou erro."
        )
    if inseridos == 0:
        return MENSAGEM_SEM_NOVOS
    if inseridos == 1:
        return "Sincronizacao concluida. 1 novo pre-cadastro foi recebido."
    return f"Sincronizacao concluida. {inseridos} novos pre-cadastros foram recebidos."


def detalhes_relatorio(relatorio):
    confirmacao = relatorio.get("confirmacao") or {}
    return (
        "origem=online; "
        f"recebidos={relatorio.get('total_recebido', 0)}; "
        f"novos={relatorio.get('inseridos', 0)}; "
        f"existentes={relatorio.get('existentes', 0)}; "
        f"erros={relatorio.get('erros', 0)}; "
        f"confirmacao_ok={int(bool(relatorio.get('confirmacao_ok')))}; "
        f"marcados_importados={confirmacao.get('marcados_importados', 0)}; "
        f"ja_importados={confirmacao.get('ja_importados', 0)}"
    )


def registrar_historico(relatorio, erro=None):
    registrar_sincronizacao_pre_cadastro(
        status=relatorio.get("status") or ("erro" if erro else "sucesso"),
        quantidade_recebida=relatorio.get("total_recebido", 0),
        quantidade_nova=relatorio.get("inseridos", 0),
        quantidade_ignorada=relatorio.get("existentes", 0),
        erro=erro,
        detalhes=detalhes_relatorio(relatorio),
    )


def registrar_auditoria(acao, descricao, relatorio=None, detalhes=None):
    relatorio = relatorio or {}
    detalhes = detalhes or (
        f"Novos: {relatorio.get('inseridos', 0)}; "
        f"Existentes: {relatorio.get('existentes', 0)}; "
        f"Erros: {relatorio.get('erros', 0)}"
    )
    registrar_acao(
        acao,
        descricao,
        modulo="Pre-cadastros",
        registro_id=None,
        detalhes=detalhes,
    )


def configuracao_para_cliente():
    configuracao = buscar_configuracao_online_igreja()
    if not int(configuracao.get("ativo") or 0):
        raise SIGMOnlineConfiguracaoErro("integracao desativada")

    return {
        "api_base_url": configuracao.get("api_base_url") or "",
        "identificador_publico": configuracao.get("identificador_publico") or "",
        "chave_sincronizacao": configuracao.get("chave_sincronizacao") or "",
    }


def classificar_erro(erro):
    if isinstance(erro, SIGMOnlineErro):
        return erro.mensagem_usuario, erro.mensagem_tecnica
    return (
        "Nao foi possivel sincronizar os pre-cadastros. Tente novamente.",
        "erro inesperado na sincronizacao",
    )


def sincronizar_pre_cadastros_online(cliente_factory=ClienteSIGMOnline):
    relatorio = relatorio_base()
    registrar_auditoria(
        "SINCRONIZACAO_PRE_CADASTRO_ONLINE_INICIADA",
        "Sincronizacao online de pre-cadastros iniciada.",
        detalhes="Origem: online",
    )

    try:
        configuracao = configuracao_para_cliente()
        cliente = cliente_factory(**configuracao)
        cliente.validar_igreja()
        resposta = cliente.listar_pre_cadastros_pendentes()
        itens = resposta["pre_cadastros"]
        relatorio["total_recebido"] = len(itens)
    except (
        SIGMOnlineConfiguracaoErro,
        SIGMOnlineAutenticacaoErro,
        SIGMOnlineConexaoErro,
        SIGMOnlineTimeoutErro,
        SIGMOnlineRespostaErro,
    ) as erro:
        mensagem_usuario, mensagem_tecnica = classificar_erro(erro)
        relatorio["mensagem_usuario"] = mensagem_usuario
        registrar_historico(relatorio, erro=mensagem_tecnica)
        registrar_auditoria(
            "SINCRONIZACAO_PRE_CADASTRO_ONLINE_FALHOU",
            "Sincronizacao online de pre-cadastros falhou.",
            relatorio,
            detalhes=mensagem_tecnica,
        )
        return relatorio

    remote_ids_seguros = []
    for indice, item in enumerate(itens, start=1):
        try:
            dados = normalizar_registro_online(
                item,
                configuracao["identificador_publico"],
            )
            resultado = salvar_pre_cadastro(dados)
        except RegistroOnlineInvalido as erro:
            relatorio["erros"] += 1
            relatorio["erros_itens"].append(f"Item {indice}: {erro}")
            continue
        except Exception:
            relatorio["erros"] += 1
            relatorio["erros_itens"].append(f"Item {indice}: falha ao salvar")
            continue

        remote_id = dados["remote_id"]
        if resultado.get("inserido"):
            relatorio["inseridos"] += 1
            remote_ids_seguros.append(remote_id)
        elif resultado.get("existente"):
            relatorio["existentes"] += 1
            remote_ids_seguros.append(remote_id)
        else:
            relatorio["erros"] += 1
            relatorio["erros_itens"].append(f"Item {indice}: nao armazenado")

    relatorio["remote_ids_confirmados"] = list(remote_ids_seguros)

    if remote_ids_seguros:
        try:
            relatorio["confirmacao"] = cliente.confirmar_importacao(remote_ids_seguros)
            relatorio["confirmacao_ok"] = True
        except SIGMOnlineErro:
            relatorio["confirmacao_falhou"] = True
        except Exception:
            relatorio["confirmacao_falhou"] = True

    status = "sucesso"
    if relatorio["erros"] or relatorio["confirmacao_falhou"]:
        status = "parcial"
    relatorio["status"] = status
    relatorio["sucesso"] = status in {"sucesso", "parcial"}
    relatorio["mensagem_usuario"] = mensagem_resultado(relatorio)

    atualizar_ultima_sincronizacao(agora_iso())
    registrar_historico(
        relatorio,
        erro="confirmacao online falhou" if relatorio["confirmacao_falhou"] else None,
    )
    registrar_auditoria(
        "SINCRONIZACAO_PRE_CADASTRO_ONLINE_CONCLUIDA",
        "Sincronizacao online de pre-cadastros concluida.",
        relatorio,
    )
    return relatorio
