import json
import unicodedata
from urllib.parse import urljoin, urlsplit

import requests


TIMEOUT_PADRAO = (5, 20)
MENSAGEM_AUTENTICACAO = (
    "Nao foi possivel autenticar esta instalacao no SIGM Online. "
    "Confira a configuracao da integracao."
)
MENSAGEM_CONEXAO = (
    "Nao foi possivel conectar ao SIGM Online. Verifique a internet e tente novamente."
)
MENSAGEM_TIMEOUT = (
    "A comunicacao com o SIGM Online demorou mais que o esperado. Tente novamente."
)
MENSAGEM_RESPOSTA_INVALIDA = (
    "O SIGM Online retornou uma resposta inesperada. Tente novamente mais tarde."
)
ENDPOINTS_DIAGNOSTICO = {"/api/v1/igreja", "/api/v1/igrejas/ativar"}
CHAVES_SENSIVEIS = ("chave", "secret", "senha", "password", "token", "key")


class SIGMOnlineErro(Exception):
    mensagem_usuario = MENSAGEM_RESPOSTA_INVALIDA

    def __init__(
        self,
        mensagem_tecnica=None,
        mensagem_usuario=None,
        status_code=None,
        resposta_json=None,
        endpoint=None,
    ):
        self.mensagem_tecnica = str(mensagem_tecnica or self.mensagem_usuario)
        if mensagem_usuario:
            self.mensagem_usuario = mensagem_usuario
        self.status_code = status_code
        self.resposta_json = sanitizar_json(resposta_json)
        self.endpoint = endpoint
        self.mensagem_servidor = extrair_mensagem_servidor(self.resposta_json)
        super().__init__(self.mensagem_usuario)

    def mensagem_diagnostico(self):
        partes = []
        if self.status_code is not None:
            partes.append(f"HTTP {self.status_code}")
        if self.mensagem_servidor:
            partes.append(f"Mensagem do servidor: {self.mensagem_servidor}")
        return "\n".join(partes) or self.mensagem_usuario


class SIGMOnlineConfiguracaoErro(SIGMOnlineErro):
    mensagem_usuario = (
        "Configure e ative a integracao com o SIGM Online antes de sincronizar."
    )


class SIGMOnlineAutenticacaoErro(SIGMOnlineErro):
    mensagem_usuario = MENSAGEM_AUTENTICACAO


class SIGMOnlineChaveLocalDivergenteErro(SIGMOnlineAutenticacaoErro):
    mensagem_usuario = (
        "A identidade online existe no servidor, mas a chave local nao corresponde. "
        "Confira a configuracao da integracao."
    )

    def mensagem_diagnostico(self):
        partes = [self.mensagem_usuario]
        if self.status_code is not None:
            partes.append(f"HTTP {self.status_code}")
        if self.mensagem_servidor:
            partes.append(f"Mensagem do servidor: {self.mensagem_servidor}")
        return "\n".join(partes)


class SIGMOnlineIgrejaNaoEncontradaErro(SIGMOnlineAutenticacaoErro):
    mensagem_usuario = (
        "A igreja nao foi encontrada no SIGM Online. "
        "A integracao sera reativada automaticamente."
    )


class SIGMOnlineConexaoErro(SIGMOnlineErro):
    mensagem_usuario = MENSAGEM_CONEXAO


class SIGMOnlineTimeoutErro(SIGMOnlineErro):
    mensagem_usuario = MENSAGEM_TIMEOUT


class SIGMOnlineRespostaErro(SIGMOnlineErro):
    mensagem_usuario = MENSAGEM_RESPOSTA_INVALIDA


STATUS_ATIVACAO_ACEITOS = {"ativada", "ja_ativada"}
UFS_BRASIL = {
    "AC": "ACRE",
    "AL": "ALAGOAS",
    "AP": "AMAPA",
    "AM": "AMAZONAS",
    "BA": "BAHIA",
    "CE": "CEARA",
    "DF": "DISTRITO FEDERAL",
    "ES": "ESPIRITO SANTO",
    "GO": "GOIAS",
    "MA": "MARANHAO",
    "MT": "MATO GROSSO",
    "MS": "MATO GROSSO DO SUL",
    "MG": "MINAS GERAIS",
    "PA": "PARA",
    "PB": "PARAIBA",
    "PR": "PARANA",
    "PE": "PERNAMBUCO",
    "PI": "PIAUI",
    "RJ": "RIO DE JANEIRO",
    "RN": "RIO GRANDE DO NORTE",
    "RS": "RIO GRANDE DO SUL",
    "RO": "RONDONIA",
    "RR": "RORAIMA",
    "SC": "SANTA CATARINA",
    "SP": "SAO PAULO",
    "SE": "SERGIPE",
    "TO": "TOCANTINS",
}
UFS_POR_NOME = {nome: uf for uf, nome in UFS_BRASIL.items()}
MAPA_DADOS_LOCAIS_IGREJA = {
    "nome": "nome_igreja",
    "ministerio": "ministerio",
    "cidade": "cidade",
    "estado": "estado",
}


def sanitizar_json(valor):
    if isinstance(valor, dict):
        seguro = {}
        for chave, item in valor.items():
            chave_texto = str(chave)
            chave_normalizada = chave_texto.lower()
            if any(sensivel in chave_normalizada for sensivel in CHAVES_SENSIVEIS):
                seguro[chave_texto] = "***"
            else:
                seguro[chave_texto] = sanitizar_json(item)
        return seguro
    if isinstance(valor, list):
        return [sanitizar_json(item) for item in valor]
    return valor


def extrair_mensagem_servidor(dados):
    if not isinstance(dados, dict):
        return ""

    for chave in ("mensagem", "message", "erro", "error", "detalhe", "detail", "status"):
        valor = dados.get(chave)
        if isinstance(valor, (str, int, float)):
            texto = str(valor).strip()
            if texto:
                return texto

    for chave in ("dados", "data"):
        valor = dados.get(chave)
        if isinstance(valor, dict):
            mensagem = extrair_mensagem_servidor(valor)
            if mensagem:
                return mensagem
    return ""


def resposta_json_para_log(dados):
    try:
        return json.dumps(sanitizar_json(dados), ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return json.dumps({"erro": "resposta JSON nao serializavel"})


def registrar_diagnostico_http(metodo, endpoint, status_code, resposta_json):
    if endpoint not in ENDPOINTS_DIAGNOSTICO:
        return

    try:
        from utils.auditoria import registrar_acao

        registrar_acao(
            "SIGM_ONLINE_HTTP_DIAGNOSTICO",
            "Diagnostico HTTP do SIGM Online.",
            modulo="Pre-cadastros",
            registro_id=None,
            detalhes=(
                f"metodo={str(metodo).upper()}; "
                f"endpoint={endpoint}; "
                f"http_status={status_code}; "
                f"resposta_json={resposta_json_para_log(resposta_json)}"
            ),
        )
    except Exception:
        pass


def registrar_diagnostico_payload_ativacao(payload):
    try:
        from utils.auditoria import registrar_acao

        registrar_acao(
            "SIGM_ONLINE_PAYLOAD_ATIVACAO_DIAGNOSTICO",
            "Payload enviado para ativacao do SIGM Online.",
            modulo="Pre-cadastros",
            registro_id=None,
            detalhes=(
                "metodo=POST; "
                "endpoint=/api/v1/igrejas/ativar; "
                f"payload_json={resposta_json_para_log(payload)}"
            ),
        )
    except Exception:
        pass


def completar_dados_igreja_para_ativacao(igreja):
    dados = dict(igreja or {})
    if all(str(dados.get(campo) or "").strip() for campo in MAPA_DADOS_LOCAIS_IGREJA):
        return dados

    try:
        from banco.database import buscar_configuracoes_igreja

        dados_locais = buscar_configuracoes_igreja()
    except Exception:
        dados_locais = {}

    for campo_payload, campo_local in MAPA_DADOS_LOCAIS_IGREJA.items():
        if not str(dados.get(campo_payload) or "").strip():
            dados[campo_payload] = dados_locais.get(campo_local, "")
    return dados


def resposta_indica_igreja_nao_encontrada(dados):
    if not isinstance(dados, dict):
        return False

    valores = [
        dados.get("status"),
        dados.get("erro"),
        dados.get("codigo"),
        dados.get("mensagem"),
        dados.get("message"),
    ]
    texto = " ".join(str(valor or "").lower() for valor in valores)
    return (
        "igreja" in texto
        and (
            "nao encontrada" in texto
            or "não encontrada" in texto
            or "not found" in texto
        )
    )


def normalizar_texto_estado(valor):
    texto = unicodedata.normalize("NFKD", str(valor or "").strip())
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    partes = []
    palavra = []
    for caractere in texto.upper():
        if caractere.isalnum():
            palavra.append(caractere)
        elif palavra:
            partes.append("".join(palavra))
            palavra = []
    if palavra:
        partes.append("".join(palavra))
    return partes


def normalizar_estado_para_uf(valor):
    partes = normalizar_texto_estado(valor)
    if not partes:
        return ""

    texto = " ".join(partes)
    if texto in UFS_POR_NOME:
        return UFS_POR_NOME[texto]

    for parte in partes:
        if parte in UFS_BRASIL:
            return parte

    for nome, uf in UFS_POR_NOME.items():
        if nome in texto:
            return uf

    texto_compacto = "".join(partes)
    if len(texto_compacto) >= 2:
        return texto_compacto[:2].upper()
    return ""


def normalizar_api_base_url(api_base_url):
    url = str(api_base_url or "").strip().rstrip("/")
    if not url:
        raise SIGMOnlineConfiguracaoErro("api_base_url ausente")

    partes = urlsplit(url)
    if partes.scheme not in {"http", "https"} or not partes.netloc:
        raise SIGMOnlineConfiguracaoErro("api_base_url invalida")

    return url


def valor_booleano(valor, padrao=False):
    if isinstance(valor, bool):
        return valor
    if valor is None:
        return padrao
    if isinstance(valor, (int, float)):
        return bool(valor)

    texto = str(valor).strip().lower()
    if texto in {"1", "true", "sim", "s", "ativo", "ativa", "yes", "y"}:
        return True
    if texto in {"0", "false", "nao", "n", "inativo", "inativa", "no"}:
        return False
    return padrao


def extrair_identificador_igreja(dados):
    candidatos = [
        dados.get("identificador_publico"),
        dados.get("identificador"),
    ]
    for chave in ("igreja", "dados"):
        valor = dados.get(chave)
        if isinstance(valor, dict):
            candidatos.extend([
                valor.get("identificador_publico"),
                valor.get("identificador"),
                valor.get("igreja"),
            ])

    for candidato in candidatos:
        if isinstance(candidato, dict):
            continue
        texto = str(candidato or "").strip()
        if texto:
            return texto
    return ""


def extrair_igreja_ativa(dados):
    for chave in ("ativa", "ativo"):
        if chave in dados:
            return valor_booleano(dados.get(chave))

    for chave in ("igreja", "dados"):
        valor = dados.get(chave)
        if isinstance(valor, dict):
            for campo in ("ativa", "ativo"):
                if campo in valor:
                    return valor_booleano(valor.get(campo))

    return False


class ClienteSIGMOnline:
    def __init__(
        self,
        api_base_url,
        identificador_publico,
        chave_sincronizacao,
        timeout=TIMEOUT_PADRAO,
        sessao=None,
    ):
        self.api_base_url = normalizar_api_base_url(api_base_url)
        self.identificador_publico = str(identificador_publico or "").strip()
        self.chave_sincronizacao = str(chave_sincronizacao or "")
        self.timeout = timeout
        self.sessao = sessao or requests.Session()
        self.ultima_resposta_http = None
        self.ultima_resposta_json = None
        self.ultimo_endpoint = None

        if not self.identificador_publico or not self.chave_sincronizacao:
            raise SIGMOnlineConfiguracaoErro("identificador ou chave ausente")

    def montar_url(self, caminho):
        return urljoin(f"{self.api_base_url}/", str(caminho or "").lstrip("/"))

    def cabecalhos(self, conteudo_json=False):
        cabecalhos = {
            "X-SIGM-Igreja": self.identificador_publico,
            "X-SIGM-Key": self.chave_sincronizacao,
            "Accept": "application/json",
        }
        if conteudo_json:
            cabecalhos["Content-Type"] = "application/json"
        return cabecalhos

    def _request(self, metodo, caminho, **kwargs):
        url = self.montar_url(caminho)
        try:
            resposta = getattr(self.sessao, metodo)(
                url,
                headers=self.cabecalhos(conteudo_json=metodo == "post"),
                timeout=self.timeout,
                **kwargs,
            )
        except requests.exceptions.Timeout as erro:
            raise SIGMOnlineTimeoutErro("timeout na comunicacao") from erro
        except requests.exceptions.ConnectionError as erro:
            raise SIGMOnlineConexaoErro("falha de conexao") from erro
        except requests.exceptions.RequestException as erro:
            raise SIGMOnlineConexaoErro("falha na requisicao") from erro

        try:
            dados = resposta.json()
        except (ValueError, json.JSONDecodeError) as erro:
            status = int(getattr(resposta, "status_code", 0) or 0)
            dados_erro = {"erro": "resposta sem JSON valido"}
            self.ultima_resposta_http = status
            self.ultima_resposta_json = dados_erro
            self.ultimo_endpoint = caminho
            registrar_diagnostico_http(metodo, caminho, status, dados_erro)
            raise SIGMOnlineRespostaErro(
                "resposta sem JSON valido",
                status_code=status,
                resposta_json=dados_erro,
                endpoint=caminho,
            ) from erro

        if not isinstance(dados, dict):
            status = int(getattr(resposta, "status_code", 0) or 0)
            dados_erro = {"erro": "json raiz nao e objeto"}
            self.ultima_resposta_http = status
            self.ultima_resposta_json = dados_erro
            self.ultimo_endpoint = caminho
            registrar_diagnostico_http(metodo, caminho, status, dados_erro)
            raise SIGMOnlineRespostaErro(
                "json raiz nao e objeto",
                status_code=status,
                resposta_json=dados_erro,
                endpoint=caminho,
            )

        status = int(getattr(resposta, "status_code", 0) or 0)
        self.ultima_resposta_http = status
        self.ultima_resposta_json = sanitizar_json(dados)
        self.ultimo_endpoint = caminho
        registrar_diagnostico_http(metodo, caminho, status, dados)

        if status in {401, 403}:
            raise SIGMOnlineAutenticacaoErro(
                "autenticacao recusada",
                status_code=status,
                resposta_json=dados,
                endpoint=caminho,
            )
        if status == 404:
            raise SIGMOnlineIgrejaNaoEncontradaErro(
                "igreja nao encontrada",
                status_code=status,
                resposta_json=dados,
                endpoint=caminho,
            )
        if status >= 400:
            raise SIGMOnlineRespostaErro(
                f"http_status={status}",
                status_code=status,
                resposta_json=dados,
                endpoint=caminho,
            )
        return dados

    def validar_igreja(self):
        dados = self._request("get", "/api/v1/igreja")
        if dados.get("sucesso") is not True:
            if resposta_indica_igreja_nao_encontrada(dados):
                raise SIGMOnlineIgrejaNaoEncontradaErro(
                    "igreja nao encontrada",
                    status_code=self.ultima_resposta_http,
                    resposta_json=dados,
                    endpoint=self.ultimo_endpoint,
                )
            raise SIGMOnlineAutenticacaoErro(
                "sucesso falso ao validar igreja",
                status_code=self.ultima_resposta_http,
                resposta_json=dados,
                endpoint=self.ultimo_endpoint,
            )

        identificador = extrair_identificador_igreja(dados)
        if identificador != self.identificador_publico:
            raise SIGMOnlineAutenticacaoErro(
                "identificador divergente",
                status_code=self.ultima_resposta_http,
                resposta_json=dados,
                endpoint=self.ultimo_endpoint,
            )

        if not extrair_igreja_ativa(dados):
            raise SIGMOnlineAutenticacaoErro(
                "igreja inativa",
                status_code=self.ultima_resposta_http,
                resposta_json=dados,
                endpoint=self.ultimo_endpoint,
            )

        return dados

    def ativar_igreja(self, igreja):
        igreja = completar_dados_igreja_para_ativacao(igreja)
        payload = {
            "nome": str(igreja.get("nome") or "").strip(),
            "ministerio": str(igreja.get("ministerio") or "").strip(),
            "cidade": str(igreja.get("cidade") or "").strip(),
            "estado": normalizar_estado_para_uf(igreja.get("estado")),
            "identificador_publico": self.identificador_publico,
            "chave_secreta": self.chave_sincronizacao,
        }
        registrar_diagnostico_payload_ativacao(payload)
        dados = self._request(
            "post",
            "/api/v1/igrejas/ativar",
            json=payload,
        )
        status = str(dados.get("status") or "").strip().lower()
        if status not in STATUS_ATIVACAO_ACEITOS:
            raise SIGMOnlineRespostaErro(
                "status de ativacao inesperado",
                status_code=self.ultima_resposta_http,
                resposta_json=dados,
                endpoint=self.ultimo_endpoint,
            )
        return dados

    def listar_pre_cadastros_pendentes(self):
        dados = self._request("get", "/api/v1/pre-cadastros/pendentes")
        if dados.get("sucesso") is not True:
            raise SIGMOnlineRespostaErro("sucesso falso ao listar pendentes")

        pre_cadastros = dados.get("pre_cadastros")
        if not isinstance(pre_cadastros, list):
            raise SIGMOnlineRespostaErro("pre_cadastros nao e lista")

        quantidade = dados.get("quantidade", len(pre_cadastros))
        try:
            quantidade = int(quantidade)
        except (TypeError, ValueError):
            quantidade = len(pre_cadastros)

        return {
            "pre_cadastros": pre_cadastros,
            "quantidade": quantidade,
            "proximo_cursor": dados.get("proximo_cursor"),
        }

    def confirmar_importacao(self, remote_ids):
        ids = [
            str(remote_id or "").strip()
            for remote_id in remote_ids
            if str(remote_id or "").strip()
        ]
        dados = self._request(
            "post",
            "/api/v1/pre-cadastros/confirmar-importacao",
            json={"remote_ids": ids},
        )
        if dados.get("sucesso") is not True:
            raise SIGMOnlineRespostaErro("sucesso falso ao confirmar importacao")

        for campo in (
            "recebidos",
            "marcados_importados",
            "ja_importados",
            "nao_encontrados",
        ):
            if campo in dados:
                try:
                    int(dados.get(campo) or 0)
                except (TypeError, ValueError) as erro:
                    raise SIGMOnlineRespostaErro(f"{campo} invalido") from erro

        return dados
