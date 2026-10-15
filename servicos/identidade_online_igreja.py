import secrets
import uuid
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit

from banco.database import (
    buscar_configuracao_online_igreja,
    buscar_configuracoes_igreja,
    salvar_configuracao_online_igreja,
)
from servicos.cliente_sigm_online import (
    ClienteSIGMOnline,
    SIGMOnlineAutenticacaoErro,
    SIGMOnlineChaveLocalDivergenteErro,
    SIGMOnlineConfiguracaoErro,
    SIGMOnlineIgrejaNaoEncontradaErro,
    normalizar_estado_para_uf,
)


CAMPOS_CONFIGURACAO_BASICA_IGREJA = (
    "nome_igreja",
    "ministerio",
    "cidade",
    "estado",
)
CAMPOS_PAYLOAD_IGREJA = {
    "nome": ("nome_igreja", "nome"),
    "ministerio": ("ministerio",),
    "cidade": ("cidade", "municipio"),
    "estado": ("estado", "uf"),
}
ROTULOS_CAMPOS_PAYLOAD_IGREJA = {
    "nome": "nome da igreja",
    "ministerio": "ministerio",
    "cidade": "cidade",
    "estado": "estado/UF",
}
API_BASE_URL_PADRAO = "https://sigm-online-l0ad.onrender.com"
STATUS_ATIVACAO_ATIVADA = "ativada"
STATUS_ATIVACAO_PENDENTE = "pendente"
ERRO_AUTENTICACAO_INVALIDA = "autenticacao_invalida"


class IdentidadeOnlineIgrejaErro(Exception):
    pass


def gerar_identificador_publico():
    return f"sigm-{uuid.uuid4()}"


def gerar_chave_sincronizacao():
    return secrets.token_urlsafe(48)


def mascarar_chave_sincronizacao(chave):
    texto = str(chave or "").strip()
    if not texto:
        return "Nao gerada"
    if len(texto) <= 12:
        return "*" * len(texto)
    return f"{texto[:4]}{'*' * 16}{texto[-4:]}"


def configuracao_basica_igreja_existe():
    try:
        dados_ativacao_igreja_do_banco()
        return True
    except IdentidadeOnlineIgrejaErro:
        return False


def primeiro_valor_configuracao(configuracao, nomes):
    for nome in nomes:
        valor = str((configuracao or {}).get(nome) or "").strip()
        if valor:
            return valor
    return ""


def montar_payload_igreja(configuracao):
    payload = {
        campo: primeiro_valor_configuracao(configuracao, nomes)
        for campo, nomes in CAMPOS_PAYLOAD_IGREJA.items()
    }
    payload["estado"] = normalizar_estado_para_uf(payload.get("estado"))

    ausentes = [
        ROTULOS_CAMPOS_PAYLOAD_IGREJA[campo]
        for campo, valor in payload.items()
        if not str(valor or "").strip()
    ]
    if payload.get("estado") and len(payload["estado"]) != 2:
        ausentes.append(ROTULOS_CAMPOS_PAYLOAD_IGREJA["estado"])
    if ausentes:
        raise IdentidadeOnlineIgrejaErro(
            "Preencha os dados da igreja antes de ativar a integracao online: "
            + ", ".join(ausentes)
            + "."
        )

    return payload


def dados_ativacao_igreja_do_banco():
    return montar_payload_igreja(buscar_configuracoes_igreja())


def dados_basicos_igreja():
    return dados_ativacao_igreja_do_banco()


def preencher_dados_integracao(configuracao, status_ativacao=None, ativo=None):
    dados = dict(configuracao or {})
    dados["api_base_url"] = API_BASE_URL_PADRAO
    dados["formulario_url"] = montar_url_formulario({
        **dados,
        "api_base_url": API_BASE_URL_PADRAO,
        "formulario_url": "",
    })
    if status_ativacao is not None:
        dados["status_ativacao"] = status_ativacao
    if ativo is not None:
        dados["ativo"] = int(ativo)
    return dados


def inicializar_identidade_online_igreja():
    if not configuracao_basica_igreja_existe():
        raise IdentidadeOnlineIgrejaErro(
            "Preencha primeiro as configuracoes basicas da igreja."
        )

    configuracao = buscar_configuracao_online_igreja()
    dados = dict(configuracao)
    criado = False

    if not str(dados.get("identificador_publico") or "").strip():
        dados["identificador_publico"] = gerar_identificador_publico()
        criado = True

    if not str(dados.get("chave_sincronizacao") or "").strip():
        dados["chave_sincronizacao"] = gerar_chave_sincronizacao()
        criado = True

    dados = preencher_dados_integracao(
        dados,
        status_ativacao=dados.get("status_ativacao") or STATUS_ATIVACAO_PENDENTE,
        ativo=dados.get("ativo") or 0,
    )

    if not criado:
        return salvar_configuracao_online_igreja(dados)

    return salvar_configuracao_online_igreja(dados)


def ativar_integracao_online_igreja(cliente_factory=ClienteSIGMOnline):
    igreja = dados_basicos_igreja()
    configuracao = inicializar_identidade_online_igreja()
    configuracao = salvar_configuracao_online_igreja(
        preencher_dados_integracao(
            configuracao,
            status_ativacao=STATUS_ATIVACAO_PENDENTE,
            ativo=0,
        )
    )

    cliente = cliente_factory(
        configuracao.get("api_base_url"),
        configuracao.get("identificador_publico"),
        configuracao.get("chave_sincronizacao"),
    )
    resposta = cliente.ativar_igreja(igreja)
    configuracao = salvar_configuracao_online_igreja(
        preencher_dados_integracao(
            configuracao,
            status_ativacao=STATUS_ATIVACAO_ATIVADA,
            ativo=1,
        )
    )
    return {
        "configuracao": configuracao,
        "status": str(resposta.get("status") or STATUS_ATIVACAO_ATIVADA),
        "resposta": resposta,
    }


def cliente_para_configuracao(configuracao, cliente_factory=ClienteSIGMOnline):
    identificador = str((configuracao or {}).get("identificador_publico") or "").strip()
    chave = str((configuracao or {}).get("chave_sincronizacao") or "")
    if not identificador or not chave:
        raise SIGMOnlineConfiguracaoErro("identidade online ausente")

    return cliente_factory(
        (configuracao or {}).get("api_base_url") or API_BASE_URL_PADRAO,
        identificador,
        chave,
    )


def erro_autenticacao_invalida_401(erro):
    resposta = getattr(erro, "resposta_json", None)
    return (
        isinstance(erro, SIGMOnlineAutenticacaoErro)
        and int(getattr(erro, "status_code", 0) or 0) == 401
        and isinstance(resposta, dict)
        and str(resposta.get("erro") or "").strip().lower() == ERRO_AUTENTICACAO_INVALIDA
    )


def recuperar_integracao_com_ativacao_unica(configuracao, cliente, igreja):
    try:
        resposta = cliente.ativar_igreja(igreja)
    except SIGMOnlineAutenticacaoErro as erro:
        if int(getattr(erro, "status_code", 0) or 0) == 401:
            raise SIGMOnlineChaveLocalDivergenteErro(
                "chave local divergente",
                status_code=erro.status_code,
                resposta_json=erro.resposta_json,
                endpoint=erro.endpoint,
            ) from erro
        raise

    configuracao = salvar_configuracao_online_igreja(
        preencher_dados_integracao(
            configuracao,
            status_ativacao=STATUS_ATIVACAO_ATIVADA,
            ativo=1,
        )
    )
    validacao = cliente.validar_igreja()
    return {
        "configuracao": configuracao,
        "status": str(resposta.get("status") or STATUS_ATIVACAO_ATIVADA),
        "recuperada": True,
        "validacao": validacao,
    }


def testar_ou_recuperar_integracao_online_igreja(cliente_factory=ClienteSIGMOnline):
    configuracao = buscar_configuracao_online_igreja()
    igreja = dados_ativacao_igreja_do_banco()
    cliente = cliente_para_configuracao(configuracao, cliente_factory)

    try:
        validacao = cliente.validar_igreja()
        return {
            "configuracao": configuracao,
            "status": STATUS_ATIVACAO_ATIVADA,
            "recuperada": False,
            "validacao": validacao,
        }
    except SIGMOnlineIgrejaNaoEncontradaErro:
        return recuperar_integracao_com_ativacao_unica(configuracao, cliente, igreja)
    except SIGMOnlineAutenticacaoErro as erro:
        if not erro_autenticacao_invalida_401(erro):
            raise
        return recuperar_integracao_com_ativacao_unica(configuracao, cliente, igreja)


def montar_url_formulario(configuracao):
    configuracao = configuracao or {}
    formulario_url = str(configuracao.get("formulario_url") or "").strip()
    identificador = str(configuracao.get("identificador_publico") or "").strip()
    api_base_url = str(configuracao.get("api_base_url") or API_BASE_URL_PADRAO).strip().rstrip("/")

    if not identificador:
        return ""

    url_padrao = urljoin(f"{api_base_url}/", f"cadastro/{quote(identificador, safe='')}")
    if not formulario_url:
        return url_padrao

    if formulario_url.rstrip("/") == url_padrao.rstrip("/"):
        return url_padrao

    partes = urlsplit(formulario_url)
    parametros = parse_qsl(partes.query, keep_blank_values=True)
    parametros = [
        (chave, valor)
        for chave, valor in parametros
        if chave.lower() not in {"igreja", "identificador_publico_igreja"}
    ]
    parametros.append(("igreja", identificador))

    return urlunsplit((
        partes.scheme,
        partes.netloc,
        partes.path,
        urlencode(parametros),
        partes.fragment,
    ))
