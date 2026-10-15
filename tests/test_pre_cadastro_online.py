import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

from banco import database as db
from servicos import identidade_online_igreja as identidade
from servicos import sincronizacao_pre_cadastro_online as sync
from servicos.cliente_sigm_online import (
    ClienteSIGMOnline,
    SIGMOnlineAutenticacaoErro,
    SIGMOnlineChaveLocalDivergenteErro,
    SIGMOnlineConexaoErro,
    SIGMOnlineIgrejaNaoEncontradaErro,
    SIGMOnlineRespostaErro,
    SIGMOnlineTimeoutErro,
    normalizar_api_base_url,
    normalizar_estado_para_uf,
)
from servicos.identidade_online_igreja import (
    API_BASE_URL_PADRAO,
    STATUS_ATIVACAO_ATIVADA,
    STATUS_ATIVACAO_PENDENTE,
    IdentidadeOnlineIgrejaErro,
    ativar_integracao_online_igreja,
    montar_payload_igreja,
    montar_url_formulario,
    testar_ou_recuperar_integracao_online_igreja,
)


DUMMY_KEY = "x" * 32
OUTRA_DUMMY_KEY = "y" * 32


class RespostaFake:
    def __init__(self, status_code=200, dados=None, erro_json=None):
        self.status_code = status_code
        self._dados = dados
        self._erro_json = erro_json

    def json(self):
        if self._erro_json:
            raise self._erro_json
        return self._dados


class SessaoFake:
    def __init__(self, respostas=None, erro=None):
        self.respostas = list(respostas or [])
        self.erro = erro
        self.chamadas = []

    def get(self, url, headers=None, timeout=None, **kwargs):
        self.chamadas.append(("get", url, headers, timeout, kwargs))
        if self.erro:
            raise self.erro
        return self.respostas.pop(0)

    def post(self, url, headers=None, timeout=None, **kwargs):
        self.chamadas.append(("post", url, headers, timeout, kwargs))
        if self.erro:
            raise self.erro
        return self.respostas.pop(0)


class ClienteFake:
    def __init__(
        self,
        api_base_url,
        identificador_publico,
        chave_sincronizacao,
        pendentes=None,
        confirmar_erro=None,
    ):
        self.api_base_url = api_base_url
        self.identificador_publico = identificador_publico
        self.chave_sincronizacao = chave_sincronizacao
        self.pendentes = list(pendentes or [])
        self.confirmar_erro = confirmar_erro
        self.remote_ids_recebidos = []

    def validar_igreja(self):
        return {"sucesso": True}

    def listar_pre_cadastros_pendentes(self):
        return {
            "pre_cadastros": self.pendentes,
            "quantidade": len(self.pendentes),
            "proximo_cursor": None,
        }

    def confirmar_importacao(self, remote_ids):
        if self.confirmar_erro:
            raise self.confirmar_erro
        self.remote_ids_recebidos = list(remote_ids)
        return {
            "sucesso": True,
            "recebidos": len(remote_ids),
            "marcados_importados": len(remote_ids),
            "ja_importados": 0,
            "nao_encontrados": 0,
        }


def item_online(remote_id="rem-1", dados=None):
    return {
        "remote_id": remote_id,
        "dados": dados if dados is not None else {"nome": "Ana", "email": ""},
        "criado_em": "2026-07-19T10:00:00",
    }


class TestClienteSIGMOnline(unittest.TestCase):
    def test_url_publica_padrao_do_formulario_online(self):
        url = montar_url_formulario({"identificador_publico": "sigm-abc"})
        self.assertEqual(url, f"{API_BASE_URL_PADRAO}/cadastro/sigm-abc")

    def test_url_publica_padrao_codifica_identificador(self):
        url = montar_url_formulario({
            "api_base_url": "https://online.test/",
            "identificador_publico": "sigm com espaco",
        })
        self.assertEqual(url, "https://online.test/cadastro/sigm%20com%20espaco")

    def test_url_customizada_antiga_continua_com_parametro_igreja(self):
        url = montar_url_formulario({
            "formulario_url": "https://forms.test/cadastro",
            "identificador_publico": "sigm-abc",
        })
        self.assertEqual(url, "https://forms.test/cadastro?igreja=sigm-abc")

    def test_montagem_correta_da_url(self):
        self.assertEqual(
            normalizar_api_base_url("http://127.0.0.1:5000///"),
            "http://127.0.0.1:5000",
        )
        cliente = ClienteSIGMOnline("http://127.0.0.1:5000/", "igreja", DUMMY_KEY)
        self.assertEqual(
            cliente.montar_url("/api/v1/igreja"),
            "http://127.0.0.1:5000/api/v1/igreja",
        )

    def test_cabecalhos_corretos(self):
        cliente = ClienteSIGMOnline("http://local.test", "igreja", DUMMY_KEY)
        self.assertEqual(cliente.cabecalhos()["X-SIGM-Igreja"], "igreja")
        self.assertEqual(cliente.cabecalhos()["X-SIGM-Key"], DUMMY_KEY)
        self.assertEqual(cliente.cabecalhos()["Accept"], "application/json")
        self.assertEqual(
            cliente.cabecalhos(conteudo_json=True)["Content-Type"],
            "application/json",
        )

    def test_normaliza_estado_para_uf(self):
        casos = {
            "sp": "SP",
            "São Paulo": "SP",
            "Sao Paulo": "SP",
            "Estado de São Paulo": "SP",
            "Rio de Janeiro - RJ": "RJ",
            "Minas Gerais": "MG",
            "Pará": "PA",
        }
        for valor, esperado in casos.items():
            with self.subTest(valor=valor):
                self.assertEqual(normalizar_estado_para_uf(valor), esperado)

    def test_chave_nao_aparece_em_excecoes(self):
        sessao = SessaoFake(respostas=[RespostaFake(401, {"sucesso": False})])
        cliente = ClienteSIGMOnline("http://local.test", "igreja", OUTRA_DUMMY_KEY, sessao=sessao)
        with self.assertRaises(SIGMOnlineAutenticacaoErro) as contexto:
            cliente.validar_igreja()
        self.assertNotIn(OUTRA_DUMMY_KEY, str(contexto.exception))

    def test_diagnostico_autenticacao_registra_http_e_json_sem_chave(self):
        sessao = SessaoFake(respostas=[
            RespostaFake(401, {
                "sucesso": False,
                "mensagem": "credencial recusada",
                "chave_secreta": OUTRA_DUMMY_KEY,
            })
        ])
        cliente = ClienteSIGMOnline("http://local.test", "igreja", OUTRA_DUMMY_KEY, sessao=sessao)
        with mock.patch("utils.auditoria.registrar_acao") as registrar:
            with self.assertRaises(SIGMOnlineAutenticacaoErro) as contexto:
                cliente.validar_igreja()

        mensagem = contexto.exception.mensagem_diagnostico()
        self.assertIn("HTTP 401", mensagem)
        self.assertIn("credencial recusada", mensagem)
        self.assertNotIn(OUTRA_DUMMY_KEY, mensagem)
        detalhes = registrar.call_args.kwargs["detalhes"]
        self.assertIn("endpoint=/api/v1/igreja", detalhes)
        self.assertIn("http_status=401", detalhes)
        self.assertIn("credencial recusada", detalhes)
        self.assertIn('"chave_secreta": "***"', detalhes)
        self.assertNotIn(OUTRA_DUMMY_KEY, detalhes)

    def test_validacao_de_igreja_com_sucesso(self):
        sessao = SessaoFake(respostas=[
            RespostaFake(200, {
                "sucesso": True,
                "igreja": {"identificador_publico": "igreja", "ativa": True},
            })
        ])
        cliente = ClienteSIGMOnline("http://local.test", "igreja", DUMMY_KEY, sessao=sessao)
        self.assertTrue(cliente.validar_igreja()["sucesso"])

    def test_diagnostico_autenticacao_registra_sucesso(self):
        sessao = SessaoFake(respostas=[
            RespostaFake(200, {
                "sucesso": True,
                "mensagem": "ok",
                "igreja": {"identificador_publico": "igreja", "ativa": True},
            })
        ])
        cliente = ClienteSIGMOnline("http://local.test", "igreja", DUMMY_KEY, sessao=sessao)
        with mock.patch("utils.auditoria.registrar_acao") as registrar:
            cliente.validar_igreja()

        detalhes = registrar.call_args.kwargs["detalhes"]
        self.assertIn("endpoint=/api/v1/igreja", detalhes)
        self.assertIn("http_status=200", detalhes)
        self.assertIn('"mensagem": "ok"', detalhes)
        self.assertNotIn(DUMMY_KEY, detalhes)

    def test_autenticacao_invalida(self):
        sessao = SessaoFake(respostas=[
            RespostaFake(403, {"sucesso": False})
        ])
        cliente = ClienteSIGMOnline("http://local.test", "igreja", DUMMY_KEY, sessao=sessao)
        with self.assertRaises(SIGMOnlineAutenticacaoErro):
            cliente.validar_igreja()

    def test_timeout(self):
        sessao = SessaoFake(erro=requests.exceptions.Timeout())
        cliente = ClienteSIGMOnline("http://local.test", "igreja", DUMMY_KEY, sessao=sessao)
        with self.assertRaises(SIGMOnlineTimeoutErro):
            cliente.listar_pre_cadastros_pendentes()

    def test_conexao_recusada(self):
        sessao = SessaoFake(erro=requests.exceptions.ConnectionError())
        cliente = ClienteSIGMOnline("http://local.test", "igreja", DUMMY_KEY, sessao=sessao)
        with self.assertRaises(SIGMOnlineConexaoErro):
            cliente.listar_pre_cadastros_pendentes()

    def test_resposta_sem_json(self):
        sessao = SessaoFake(respostas=[RespostaFake(200, erro_json=ValueError("no json"))])
        cliente = ClienteSIGMOnline("http://local.test", "igreja", DUMMY_KEY, sessao=sessao)
        with self.assertRaises(SIGMOnlineRespostaErro):
            cliente.listar_pre_cadastros_pendentes()

    def test_json_invalido(self):
        sessao = SessaoFake(respostas=[RespostaFake(200, ["lista"])])
        cliente = ClienteSIGMOnline("http://local.test", "igreja", DUMMY_KEY, sessao=sessao)
        with self.assertRaises(SIGMOnlineRespostaErro):
            cliente.listar_pre_cadastros_pendentes()

    def test_http_500(self):
        sessao = SessaoFake(respostas=[RespostaFake(500, {"sucesso": False})])
        cliente = ClienteSIGMOnline("http://local.test", "igreja", DUMMY_KEY, sessao=sessao)
        with self.assertRaises(SIGMOnlineRespostaErro):
            cliente.listar_pre_cadastros_pendentes()

    def test_lista_vazia(self):
        sessao = SessaoFake(respostas=[RespostaFake(200, {"sucesso": True, "pre_cadastros": []})])
        cliente = ClienteSIGMOnline("http://local.test", "igreja", DUMMY_KEY, sessao=sessao)
        self.assertEqual(cliente.listar_pre_cadastros_pendentes()["pre_cadastros"], [])

    def test_download_de_um_registro(self):
        sessao = SessaoFake(respostas=[
            RespostaFake(200, {"sucesso": True, "pre_cadastros": [item_online()]})
        ])
        cliente = ClienteSIGMOnline("http://local.test", "igreja", DUMMY_KEY, sessao=sessao)
        self.assertEqual(len(cliente.listar_pre_cadastros_pendentes()["pre_cadastros"]), 1)

    def test_download_de_varios_registros(self):
        sessao = SessaoFake(respostas=[
            RespostaFake(200, {"sucesso": True, "pre_cadastros": [item_online("1"), item_online("2")]})
        ])
        cliente = ClienteSIGMOnline("http://local.test", "igreja", DUMMY_KEY, sessao=sessao)
        self.assertEqual(len(cliente.listar_pre_cadastros_pendentes()["pre_cadastros"]), 2)

    def test_confirmacao_enviada_com_remote_ids_corretos(self):
        sessao = SessaoFake(respostas=[
            RespostaFake(200, {
                "sucesso": True,
                "recebidos": 2,
                "marcados_importados": 2,
                "ja_importados": 0,
                "nao_encontrados": 0,
            })
        ])
        cliente = ClienteSIGMOnline("http://local.test", "igreja", DUMMY_KEY, sessao=sessao)
        cliente.confirmar_importacao(["a", "", "b"])
        metodo, _url, headers, _timeout, kwargs = sessao.chamadas[0]
        self.assertEqual(metodo, "post")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(kwargs["json"], {"remote_ids": ["a", "b"]})

    def test_ativacao_envia_payload_correto(self):
        sessao = SessaoFake(respostas=[RespostaFake(200, {"status": "ativada"})])
        cliente = ClienteSIGMOnline("https://online.test", "sigm-1", DUMMY_KEY, sessao=sessao)
        resposta = cliente.ativar_igreja({
            "nome": "Igreja",
            "ministerio": "Ministerio",
            "cidade": "Cidade",
            "estado": "SP",
        })
        metodo, url, headers, _timeout, kwargs = sessao.chamadas[0]
        self.assertEqual(resposta["status"], "ativada")
        self.assertEqual(metodo, "post")
        self.assertEqual(url, "https://online.test/api/v1/igrejas/ativar")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(kwargs["json"], {
            "nome": "Igreja",
            "ministerio": "Ministerio",
            "cidade": "Cidade",
            "estado": "SP",
            "identificador_publico": "sigm-1",
            "chave_secreta": DUMMY_KEY,
        })

    def test_ativacao_normaliza_estado_no_payload(self):
        sessao = SessaoFake(respostas=[RespostaFake(200, {"status": "ativada"})])
        cliente = ClienteSIGMOnline("https://online.test", "sigm-1", DUMMY_KEY, sessao=sessao)
        cliente.ativar_igreja({
            "nome": "Igreja",
            "ministerio": "Ministerio",
            "cidade": "Sao Paulo",
            "estado": "São Paulo",
        })
        payload = sessao.chamadas[0][4]["json"]
        self.assertEqual(payload["estado"], "SP")

    def test_ativacao_registra_payload_sanitizado_com_estado_normalizado(self):
        sessao = SessaoFake(respostas=[RespostaFake(200, {"status": "ativada"})])
        cliente = ClienteSIGMOnline("https://online.test", "sigm-1", OUTRA_DUMMY_KEY, sessao=sessao)
        with mock.patch("utils.auditoria.registrar_acao") as registrar:
            cliente.ativar_igreja({
                "nome": "Igreja",
                "ministerio": "Ministerio",
                "cidade": "Sao Paulo",
                "estado": "São Paulo",
            })

        chamadas_payload = [
            chamada
            for chamada in registrar.call_args_list
            if chamada.args
            and chamada.args[0] == "SIGM_ONLINE_PAYLOAD_ATIVACAO_DIAGNOSTICO"
        ]
        self.assertEqual(len(chamadas_payload), 1)
        detalhes = chamadas_payload[0].kwargs["detalhes"]
        self.assertIn("endpoint=/api/v1/igrejas/ativar", detalhes)
        self.assertIn('"estado": "SP"', detalhes)
        self.assertIn('"chave_secreta": "***"', detalhes)
        self.assertNotIn(OUTRA_DUMMY_KEY, detalhes)

    def test_diagnostico_ativacao_registra_http_e_json_sem_chave(self):
        sessao = SessaoFake(respostas=[
            RespostaFake(200, {
                "status": "ativada",
                "mensagem": "ativacao concluida",
                "chave_secreta": OUTRA_DUMMY_KEY,
            })
        ])
        cliente = ClienteSIGMOnline("https://online.test", "sigm-1", OUTRA_DUMMY_KEY, sessao=sessao)
        with mock.patch("utils.auditoria.registrar_acao") as registrar:
            cliente.ativar_igreja({"nome": "Igreja"})

        detalhes = registrar.call_args.kwargs["detalhes"]
        self.assertIn("endpoint=/api/v1/igrejas/ativar", detalhes)
        self.assertIn("http_status=200", detalhes)
        self.assertIn("ativacao concluida", detalhes)
        self.assertIn('"chave_secreta": "***"', detalhes)
        self.assertNotIn(OUTRA_DUMMY_KEY, detalhes)

    def test_ativacao_aceita_ja_ativada(self):
        sessao = SessaoFake(respostas=[RespostaFake(200, {"status": "ja_ativada"})])
        cliente = ClienteSIGMOnline("https://online.test", "sigm-1", DUMMY_KEY, sessao=sessao)
        self.assertEqual(cliente.ativar_igreja({"nome": "I"})["status"], "ja_ativada")

    def test_ativacao_servidor_indisponivel(self):
        sessao = SessaoFake(erro=requests.exceptions.ConnectionError())
        cliente = ClienteSIGMOnline("https://online.test", "sigm-1", DUMMY_KEY, sessao=sessao)
        with self.assertRaises(SIGMOnlineConexaoErro):
            cliente.ativar_igreja({"nome": "I"})

    def test_ativacao_timeout(self):
        sessao = SessaoFake(erro=requests.exceptions.Timeout())
        cliente = ClienteSIGMOnline("https://online.test", "sigm-1", DUMMY_KEY, sessao=sessao)
        with self.assertRaises(SIGMOnlineTimeoutErro):
            cliente.ativar_igreja({"nome": "I"})

    def test_ativacao_erro_401(self):
        sessao = SessaoFake(respostas=[RespostaFake(401, {"status": "erro"})])
        cliente = ClienteSIGMOnline("https://online.test", "sigm-1", DUMMY_KEY, sessao=sessao)
        with self.assertRaises(SIGMOnlineAutenticacaoErro):
            cliente.ativar_igreja({"nome": "I"})

    def test_validacao_igreja_nao_encontrada_por_404(self):
        sessao = SessaoFake(respostas=[RespostaFake(404, {"mensagem": "Igreja nao encontrada"})])
        cliente = ClienteSIGMOnline("https://online.test", "sigm-1", DUMMY_KEY, sessao=sessao)
        with self.assertRaises(SIGMOnlineIgrejaNaoEncontradaErro):
            cliente.validar_igreja()

    def test_validacao_igreja_nao_encontrada_por_payload(self):
        sessao = SessaoFake(respostas=[
            RespostaFake(200, {"sucesso": False, "mensagem": "Igreja não encontrada"})
        ])
        cliente = ClienteSIGMOnline("https://online.test", "sigm-1", DUMMY_KEY, sessao=sessao)
        with self.assertRaises(SIGMOnlineIgrejaNaoEncontradaErro):
            cliente.validar_igreja()


class TestAtivacaoIntegracaoOnlineIgreja(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.banco_original = db.BANCO
        db.BANCO = Path(self.tmp.name) / "sigm_test.db"
        db.criar_tabelas()
        db.salvar_configuracoes_igreja({
            "nome_igreja": "Igreja Teste",
            "ministerio": "Ministerio Teste",
            "cidade": "Cidade Teste",
            "estado": "SP",
        })

    def tearDown(self):
        db.BANCO = self.banco_original
        self.tmp.cleanup()

    def factory_ativacao(self, status="ativada", erro=None, recipiente=None):
        class ClienteAtivacaoFake:
            def __init__(self, api_base_url, identificador_publico, chave_sincronizacao):
                self.api_base_url = api_base_url
                self.identificador_publico = identificador_publico
                self.chave_sincronizacao = chave_sincronizacao
                if recipiente is not None:
                    recipiente.append(self)

            def ativar_igreja(self, igreja):
                self.igreja = dict(igreja)
                if erro:
                    raise erro
                return {"status": status}

        return ClienteAtivacaoFake

    def test_ativacao_com_sucesso_salva_configuracao(self):
        clientes = []
        resultado = ativar_integracao_online_igreja(self.factory_ativacao(recipiente=clientes))
        configuracao = resultado["configuracao"]
        self.assertEqual(resultado["status"], "ativada")
        self.assertEqual(configuracao["ativo"], 1)
        self.assertEqual(configuracao["status_ativacao"], STATUS_ATIVACAO_ATIVADA)
        self.assertEqual(configuracao["api_base_url"], API_BASE_URL_PADRAO)
        self.assertEqual(
            configuracao["formulario_url"],
            f"{API_BASE_URL_PADRAO}/cadastro/{configuracao['identificador_publico']}",
        )
        self.assertEqual(clientes[0].igreja["nome"], "Igreja Teste")

    def test_ativacao_normaliza_estado_sem_alterar_cadastro_local(self):
        db.salvar_configuracoes_igreja({
            "nome_igreja": "Igreja Teste",
            "ministerio": "Ministerio Teste",
            "cidade": "Cidade Teste",
            "estado": "São Paulo",
        })
        sessao = SessaoFake(respostas=[RespostaFake(200, {"status": "ativada"})])

        def factory(api_base_url, identificador_publico, chave_sincronizacao):
            return ClienteSIGMOnline(
                api_base_url,
                identificador_publico,
                chave_sincronizacao,
                sessao=sessao,
            )

        ativar_integracao_online_igreja(factory)

        payload = sessao.chamadas[0][4]["json"]
        self.assertEqual(payload["estado"], "SP")
        self.assertEqual(db.buscar_configuracoes_igreja()["estado"], "São Paulo")

    def test_ativacao_completa_payload_vazio_com_cadastro_local(self):
        db.salvar_configuracoes_igreja({
            "nome_igreja": "Igreja Local",
            "ministerio": "Ministerio Local",
            "cidade": "Cidade Local",
            "estado": "São Paulo",
        })
        sessao = SessaoFake(respostas=[RespostaFake(200, {"status": "ativada"})])
        cliente = ClienteSIGMOnline("https://online.test", "sigm-1", DUMMY_KEY, sessao=sessao)

        cliente.ativar_igreja({})

        payload = sessao.chamadas[0][4]["json"]
        self.assertEqual(payload["nome"], "Igreja Local")
        self.assertEqual(payload["ministerio"], "Ministerio Local")
        self.assertEqual(payload["cidade"], "Cidade Local")
        self.assertEqual(payload["estado"], "SP")
        self.assertEqual(db.buscar_configuracoes_igreja()["estado"], "São Paulo")

    def test_mapeia_nomes_de_colunas_alternativos_para_payload(self):
        payload = montar_payload_igreja({
            "nome": "Igreja Alias",
            "ministerio": "Ministerio Alias",
            "municipio": "Cidade Alias",
            "uf": "RJ",
        })
        self.assertEqual(payload, {
            "nome": "Igreja Alias",
            "ministerio": "Ministerio Alias",
            "cidade": "Cidade Alias",
            "estado": "RJ",
        })

    def test_recuperacao_carrega_dados_reais_do_banco_para_ativacao(self):
        db.salvar_configuracoes_igreja({
            "nome_igreja": "Igreja Banco",
            "ministerio": "Ministerio Banco",
            "cidade": "Cidade Banco",
            "estado": "São Paulo",
        })
        self.salvar_integracao_ativa_local()
        clientes = []

        testar_ou_recuperar_integracao_online_igreja(
            self.factory_recuperacao(
                recipiente=clientes,
                primeiro_erro=self.erro_autenticacao_invalida(),
            )
        )

        self.assertEqual(clientes[0].igreja, {
            "nome": "Igreja Banco",
            "ministerio": "Ministerio Banco",
            "cidade": "Cidade Banco",
            "estado": "SP",
        })

    def test_recuperacao_envia_payload_nao_vazio_quando_igreja_cadastrada(self):
        self.salvar_integracao_ativa_local()
        clientes = []

        testar_ou_recuperar_integracao_online_igreja(
            self.factory_recuperacao(
                recipiente=clientes,
                primeiro_erro=self.erro_autenticacao_invalida(),
            )
        )

        for campo in ("nome", "ministerio", "cidade", "estado"):
            self.assertTrue(clientes[0].igreja[campo])

    def test_recuperacao_sem_dados_obrigatorios_nao_chama_http(self):
        db.salvar_configuracoes_igreja({
            "nome_igreja": "",
            "ministerio": "",
            "cidade": "",
            "estado": "",
        })
        self.salvar_integracao_ativa_local()
        factory = mock.Mock()

        with self.assertRaises(IdentidadeOnlineIgrejaErro) as contexto:
            testar_ou_recuperar_integracao_online_igreja(factory)

        mensagem = str(contexto.exception)
        self.assertIn("nome da igreja", mensagem)
        self.assertIn("ministerio", mensagem)
        self.assertIn("cidade", mensagem)
        self.assertIn("estado/UF", mensagem)
        factory.assert_not_called()

    def test_ativacao_aceita_resposta_ja_ativada(self):
        resultado = ativar_integracao_online_igreja(self.factory_ativacao("ja_ativada"))
        self.assertEqual(resultado["status"], "ja_ativada")
        self.assertEqual(resultado["configuracao"]["ativo"], 1)

    def test_servidor_indisponivel_preserva_identidade_pendente(self):
        with self.assertRaises(SIGMOnlineConexaoErro):
            ativar_integracao_online_igreja(
                self.factory_ativacao(erro=SIGMOnlineConexaoErro("offline"))
            )
        configuracao = db.buscar_configuracao_online_igreja()
        self.assertTrue(configuracao["identificador_publico"].startswith("sigm-"))
        self.assertTrue(configuracao["chave_sincronizacao"])
        self.assertEqual(configuracao["ativo"], 0)
        self.assertEqual(configuracao["status_ativacao"], STATUS_ATIVACAO_PENDENTE)

    def test_timeout_preserva_identidade_pendente(self):
        with self.assertRaises(SIGMOnlineTimeoutErro):
            ativar_integracao_online_igreja(
                self.factory_ativacao(erro=SIGMOnlineTimeoutErro("timeout"))
            )
        configuracao = db.buscar_configuracao_online_igreja()
        self.assertTrue(configuracao["identificador_publico"])
        self.assertEqual(configuracao["status_ativacao"], STATUS_ATIVACAO_PENDENTE)

    def test_erro_401_nao_expoe_chave(self):
        db.salvar_configuracao_online_igreja({"chave_sincronizacao": OUTRA_DUMMY_KEY})
        with self.assertRaises(SIGMOnlineAutenticacaoErro) as contexto:
            ativar_integracao_online_igreja(
                self.factory_ativacao(erro=SIGMOnlineAutenticacaoErro("401"))
            )
        texto = str(contexto.exception) + str(db.listar_logs_auditoria())
        self.assertNotIn(OUTRA_DUMMY_KEY, texto)

    def test_campos_da_igreja_ausentes_nao_gera_identidade(self):
        db.salvar_configuracoes_igreja({"nome_igreja": "", "ministerio": "", "cidade": "", "estado": ""})
        with self.assertRaises(IdentidadeOnlineIgrejaErro):
            ativar_integracao_online_igreja(self.factory_ativacao())
        configuracao = db.buscar_configuracao_online_igreja()
        self.assertEqual(configuracao["identificador_publico"], "")
        self.assertEqual(configuracao["chave_sincronizacao"], "")

    def test_repeticao_nao_gera_nova_identidade(self):
        with self.assertRaises(SIGMOnlineConexaoErro):
            ativar_integracao_online_igreja(
                self.factory_ativacao(erro=SIGMOnlineConexaoErro("offline"))
            )
        pendente = db.buscar_configuracao_online_igreja()

        with mock.patch.object(identidade, "gerar_identificador_publico") as gerar_id, \
                mock.patch.object(identidade, "gerar_chave_sincronizacao") as gerar_chave:
            resultado = ativar_integracao_online_igreja(self.factory_ativacao("ja_ativada"))

        gerar_id.assert_not_called()
        gerar_chave.assert_not_called()
        ativada = resultado["configuracao"]
        self.assertEqual(ativada["identificador_publico"], pendente["identificador_publico"])
        self.assertEqual(ativada["chave_sincronizacao"], pendente["chave_sincronizacao"])

    def salvar_integracao_ativa_local(self):
        return db.salvar_configuracao_online_igreja({
            "api_base_url": API_BASE_URL_PADRAO,
            "formulario_url": f"{API_BASE_URL_PADRAO}/cadastro/sigm-local",
            "identificador_publico": "sigm-local",
            "chave_sincronizacao": OUTRA_DUMMY_KEY,
            "ativo": 1,
            "status_ativacao": STATUS_ATIVACAO_ATIVADA,
        })

    def erro_autenticacao_invalida(self, endpoint="/api/v1/igreja"):
        return SIGMOnlineAutenticacaoErro(
            "autenticacao recusada",
            status_code=401,
            resposta_json={"erro": "autenticacao_invalida", "sucesso": False},
            endpoint=endpoint,
        )

    def factory_recuperacao(
        self,
        status="ativada",
        erro_ativacao=None,
        recipiente=None,
        primeiro_erro=None,
        erro_segunda_validacao=None,
    ):
        class ClienteRecuperacaoFake:
            def __init__(self, api_base_url, identificador_publico, chave_sincronizacao):
                self.api_base_url = api_base_url
                self.identificador_publico = identificador_publico
                self.chave_sincronizacao = chave_sincronizacao
                self.validacoes = 0
                self.ativacoes = 0
                if recipiente is not None:
                    recipiente.append(self)

            def validar_igreja(self):
                self.validacoes += 1
                if self.validacoes == 1:
                    if primeiro_erro is not None:
                        raise primeiro_erro
                    raise SIGMOnlineIgrejaNaoEncontradaErro("igreja nao encontrada")
                if erro_segunda_validacao is not None:
                    raise erro_segunda_validacao
                return {
                    "sucesso": True,
                    "igreja": {
                        "identificador_publico": self.identificador_publico,
                        "ativa": True,
                    },
                }

            def ativar_igreja(self, igreja):
                self.ativacoes += 1
                self.igreja = dict(igreja)
                if erro_ativacao:
                    raise erro_ativacao
                return {"status": status}

        return ClienteRecuperacaoFake

    def test_igreja_ativa_localmente_ausente_no_servidor_e_recuperada(self):
        self.salvar_integracao_ativa_local()
        clientes = []
        resultado = testar_ou_recuperar_integracao_online_igreja(
            self.factory_recuperacao(recipiente=clientes)
        )
        self.assertTrue(resultado["recuperada"])
        self.assertEqual(clientes[0].ativacoes, 1)
        self.assertEqual(clientes[0].validacoes, 2)
        self.assertEqual(resultado["configuracao"]["ativo"], 1)

    def test_reativacao_usa_mesma_identidade(self):
        configuracao = self.salvar_integracao_ativa_local()
        clientes = []
        with mock.patch.object(identidade, "gerar_identificador_publico") as gerar_id, \
                mock.patch.object(identidade, "gerar_chave_sincronizacao") as gerar_chave:
            testar_ou_recuperar_integracao_online_igreja(
                self.factory_recuperacao(recipiente=clientes)
            )
        gerar_id.assert_not_called()
        gerar_chave.assert_not_called()
        self.assertEqual(clientes[0].identificador_publico, configuracao["identificador_publico"])
        self.assertEqual(clientes[0].chave_sincronizacao, configuracao["chave_sincronizacao"])

    def test_recuperacao_aceita_resposta_ativada(self):
        self.salvar_integracao_ativa_local()
        resultado = testar_ou_recuperar_integracao_online_igreja(
            self.factory_recuperacao("ativada")
        )
        self.assertEqual(resultado["status"], "ativada")

    def test_recuperacao_aceita_resposta_ja_ativada(self):
        self.salvar_integracao_ativa_local()
        resultado = testar_ou_recuperar_integracao_online_igreja(
            self.factory_recuperacao("ja_ativada")
        )
        self.assertEqual(resultado["status"], "ja_ativada")

    def test_falha_de_rede_na_recuperacao_preserva_identidade(self):
        configuracao = self.salvar_integracao_ativa_local()
        with self.assertRaises(SIGMOnlineConexaoErro):
            testar_ou_recuperar_integracao_online_igreja(
                self.factory_recuperacao(erro_ativacao=SIGMOnlineConexaoErro("offline"))
            )
        atual = db.buscar_configuracao_online_igreja()
        self.assertEqual(atual["identificador_publico"], configuracao["identificador_publico"])
        self.assertEqual(atual["chave_sincronizacao"], configuracao["chave_sincronizacao"])

    def test_get_401_autenticacao_invalida_seguido_de_ativacao_com_sucesso(self):
        self.salvar_integracao_ativa_local()
        clientes = []
        resultado = testar_ou_recuperar_integracao_online_igreja(
            self.factory_recuperacao(
                recipiente=clientes,
                primeiro_erro=self.erro_autenticacao_invalida(),
            )
        )
        self.assertTrue(resultado["recuperada"])
        self.assertEqual(resultado["status"], "ativada")
        self.assertEqual(clientes[0].ativacoes, 1)
        self.assertEqual(clientes[0].validacoes, 2)
        self.assertEqual(clientes[0].igreja["nome"], "Igreja Teste")

    def test_get_401_usa_endpoint_oficial_de_ativacao_e_testa_novamente(self):
        configuracao = self.salvar_integracao_ativa_local()
        sessao = SessaoFake(respostas=[
            RespostaFake(401, {
                "erro": "autenticacao_invalida",
                "sucesso": False,
            }),
            RespostaFake(200, {"status": "ativada"}),
            RespostaFake(200, {
                "sucesso": True,
                "igreja": {
                    "identificador_publico": configuracao["identificador_publico"],
                    "ativa": True,
                },
            }),
        ])

        def factory(api_base_url, identificador_publico, chave_sincronizacao):
            return ClienteSIGMOnline(
                api_base_url,
                identificador_publico,
                chave_sincronizacao,
                sessao=sessao,
            )

        resultado = testar_ou_recuperar_integracao_online_igreja(factory)

        self.assertTrue(resultado["recuperada"])
        self.assertEqual(
            [chamada[0] for chamada in sessao.chamadas],
            ["get", "post", "get"],
        )
        self.assertEqual(
            [chamada[1] for chamada in sessao.chamadas],
            [
                f"{API_BASE_URL_PADRAO}/api/v1/igreja",
                f"{API_BASE_URL_PADRAO}/api/v1/igrejas/ativar",
                f"{API_BASE_URL_PADRAO}/api/v1/igreja",
            ],
        )
        payload = sessao.chamadas[1][4]["json"]
        self.assertEqual(payload["identificador_publico"], configuracao["identificador_publico"])
        self.assertEqual(payload["chave_secreta"], configuracao["chave_sincronizacao"])
        self.assertEqual(payload["nome"], "Igreja Teste")
        self.assertEqual(payload["estado"], "SP")

    def test_get_401_autenticacao_invalida_seguido_de_ja_ativada(self):
        self.salvar_integracao_ativa_local()
        clientes = []
        resultado = testar_ou_recuperar_integracao_online_igreja(
            self.factory_recuperacao(
                status="ja_ativada",
                recipiente=clientes,
                primeiro_erro=self.erro_autenticacao_invalida(),
            )
        )
        self.assertEqual(resultado["status"], "ja_ativada")
        self.assertEqual(clientes[0].ativacoes, 1)
        self.assertEqual(clientes[0].validacoes, 2)

    def test_get_401_e_post_ativacao_401_informa_chave_local_divergente(self):
        configuracao = self.salvar_integracao_ativa_local()
        erro_post = SIGMOnlineAutenticacaoErro(
            "autenticacao recusada",
            status_code=401,
            resposta_json={
                "erro": "autenticacao_invalida",
                "chave_secreta": configuracao["chave_sincronizacao"],
            },
            endpoint="/api/v1/igrejas/ativar",
        )
        with self.assertRaises(SIGMOnlineChaveLocalDivergenteErro) as contexto:
            testar_ou_recuperar_integracao_online_igreja(
                self.factory_recuperacao(
                    erro_ativacao=erro_post,
                    primeiro_erro=self.erro_autenticacao_invalida(),
                )
            )

        mensagem = contexto.exception.mensagem_diagnostico()
        self.assertIn("identidade online existe no servidor", mensagem)
        self.assertIn("chave local nao corresponde", mensagem)
        self.assertNotIn(configuracao["chave_sincronizacao"], mensagem)
        atual = db.buscar_configuracao_online_igreja()
        self.assertEqual(atual["identificador_publico"], configuracao["identificador_publico"])
        self.assertEqual(atual["chave_sincronizacao"], configuracao["chave_sincronizacao"])

    def test_novo_get_bem_sucedido_apos_ativacao(self):
        configuracao = self.salvar_integracao_ativa_local()
        resultado = testar_ou_recuperar_integracao_online_igreja(
            self.factory_recuperacao(
                primeiro_erro=self.erro_autenticacao_invalida(),
            )
        )
        self.assertEqual(
            resultado["validacao"]["igreja"]["identificador_publico"],
            configuracao["identificador_publico"],
        )
        self.assertTrue(resultado["validacao"]["igreja"]["ativa"])

    def test_recuperacao_por_401_nao_repete_ativacao_indefinidamente(self):
        self.salvar_integracao_ativa_local()
        clientes = []
        with self.assertRaises(SIGMOnlineAutenticacaoErro):
            testar_ou_recuperar_integracao_online_igreja(
                self.factory_recuperacao(
                    recipiente=clientes,
                    primeiro_erro=self.erro_autenticacao_invalida(),
                    erro_segunda_validacao=self.erro_autenticacao_invalida(),
                )
            )
        self.assertEqual(clientes[0].ativacoes, 1)
        self.assertEqual(clientes[0].validacoes, 2)

    def test_recuperacao_por_401_reutiliza_mesma_identidade_e_chave(self):
        configuracao = self.salvar_integracao_ativa_local()
        clientes = []
        with mock.patch.object(identidade, "gerar_identificador_publico") as gerar_id, \
                mock.patch.object(identidade, "gerar_chave_sincronizacao") as gerar_chave:
            testar_ou_recuperar_integracao_online_igreja(
                self.factory_recuperacao(
                    recipiente=clientes,
                    primeiro_erro=self.erro_autenticacao_invalida(),
                )
            )
        gerar_id.assert_not_called()
        gerar_chave.assert_not_called()
        self.assertEqual(clientes[0].identificador_publico, configuracao["identificador_publico"])
        self.assertEqual(clientes[0].chave_sincronizacao, configuracao["chave_sincronizacao"])

    def test_falha_de_rede_na_recuperacao_por_401_preserva_identidade(self):
        configuracao = self.salvar_integracao_ativa_local()
        with self.assertRaises(SIGMOnlineConexaoErro):
            testar_ou_recuperar_integracao_online_igreja(
                self.factory_recuperacao(
                    erro_ativacao=SIGMOnlineConexaoErro("offline"),
                    primeiro_erro=self.erro_autenticacao_invalida(),
                )
            )
        atual = db.buscar_configuracao_online_igreja()
        self.assertEqual(atual["identificador_publico"], configuracao["identificador_publico"])
        self.assertEqual(atual["chave_sincronizacao"], configuracao["chave_sincronizacao"])

    def test_recuperacao_nao_expoe_chave(self):
        self.salvar_integracao_ativa_local()
        with self.assertRaises(SIGMOnlineConexaoErro) as contexto:
            testar_ou_recuperar_integracao_online_igreja(
                self.factory_recuperacao(erro_ativacao=SIGMOnlineConexaoErro("offline"))
            )
        texto = str(contexto.exception) + str(db.listar_logs_auditoria())
        self.assertNotIn(OUTRA_DUMMY_KEY, texto)


class TestSincronizacaoPreCadastroOnline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.banco_original = db.BANCO
        db.BANCO = Path(self.tmp.name) / "sigm_test.db"
        db.criar_tabelas()
        db.salvar_configuracao_online_igreja({
            "api_base_url": "http://127.0.0.1:5000",
            "identificador_publico": "igreja",
            "chave_sincronizacao": DUMMY_KEY,
            "ativo": 1,
        })
        self.auditoria = mock.patch.object(sync, "registrar_acao", return_value=None)
        self.auditoria.start()

    def tearDown(self):
        self.auditoria.stop()
        db.BANCO = self.banco_original
        self.tmp.cleanup()

    def cliente_factory(self, pendentes, confirmar_erro=None, recipiente=None):
        def factory(**kwargs):
            cliente = ClienteFake(**kwargs, pendentes=pendentes, confirmar_erro=confirmar_erro)
            if recipiente is not None:
                recipiente.append(cliente)
            return cliente
        return factory

    def test_registro_com_campos_vazios(self):
        relatorio = sync.sincronizar_pre_cadastros_online(
            self.cliente_factory([item_online("vazio", {"nome": "", "email": ""})])
        )
        self.assertTrue(relatorio["sucesso"])
        self.assertEqual(db.buscar_pre_cadastro_por_remote_id("vazio")["nome"], "")

    def test_registro_incompleto_e_aceito(self):
        relatorio = sync.sincronizar_pre_cadastros_online(
            self.cliente_factory([item_online("incompleto", {"email": "a@b.com"})])
        )
        self.assertEqual(relatorio["inseridos"], 1)
        self.assertEqual(db.buscar_pre_cadastro_por_remote_id("incompleto")["email"], "a@b.com")

    def test_remote_id_novo_e_inserido(self):
        relatorio = sync.sincronizar_pre_cadastros_online(
            self.cliente_factory([item_online("novo")])
        )
        self.assertEqual(relatorio["inseridos"], 1)
        self.assertIsNotNone(db.buscar_pre_cadastro_por_remote_id("novo"))

    def test_remote_id_existente_nao_duplica(self):
        db.salvar_pre_cadastro({"remote_id": "igual", "nome": "Local", "origem": "online"})
        relatorio = sync.sincronizar_pre_cadastros_online(
            self.cliente_factory([item_online("igual", {"nome": "Remoto"})])
        )
        self.assertEqual(relatorio["existentes"], 1)
        self.assertEqual(len(db.listar_pre_cadastros()), 1)

    def test_alteracao_local_nao_e_sobrescrita(self):
        db.salvar_pre_cadastro({"remote_id": "editado", "nome": "Nome Local", "origem": "online"})
        sync.sincronizar_pre_cadastros_online(
            self.cliente_factory([item_online("editado", {"nome": "Nome Remoto"})])
        )
        self.assertEqual(db.buscar_pre_cadastro_por_remote_id("editado")["nome"], "Nome Local")

    def test_registro_malformado_nao_interrompe_os_demais(self):
        relatorio = sync.sincronizar_pre_cadastros_online(
            self.cliente_factory([{"remote_id": "ruim"}, item_online("bom")])
        )
        self.assertEqual(relatorio["erros"], 1)
        self.assertEqual(relatorio["inseridos"], 1)
        self.assertIsNotNone(db.buscar_pre_cadastro_por_remote_id("bom"))

    def test_somente_registros_salvos_sao_confirmados(self):
        clientes = []
        sync.sincronizar_pre_cadastros_online(
            self.cliente_factory([{"remote_id": "ruim"}, item_online("ok")], recipiente=clientes)
        )
        self.assertEqual(clientes[0].remote_ids_recebidos, ["ok"])

    def test_falha_na_confirmacao_mantem_dados_locais(self):
        relatorio = sync.sincronizar_pre_cadastros_online(
            self.cliente_factory(
                [item_online("pendente-confirmacao")],
                confirmar_erro=SIGMOnlineRespostaErro("confirmacao falhou"),
            )
        )
        self.assertTrue(relatorio["confirmacao_falhou"])
        self.assertIsNotNone(db.buscar_pre_cadastro_por_remote_id("pendente-confirmacao"))

    def test_historico_de_sincronizacao_e_registrado(self):
        sync.sincronizar_pre_cadastros_online(
            self.cliente_factory([item_online("hist")])
        )
        historico = db.listar_sincronizacoes_pre_cadastro()
        self.assertEqual(len(historico), 1)
        self.assertEqual(historico[0]["quantidade_nova"], 1)

    def test_nenhum_registro_vai_diretamente_para_membros(self):
        sync.sincronizar_pre_cadastros_online(
            self.cliente_factory([item_online("membro")])
        )
        self.assertEqual(db.total_membros(), 0)

    def test_fluxo_existente_de_aprovacao_continua_funcionando(self):
        relatorio = sync.sincronizar_pre_cadastros_online(
            self.cliente_factory([item_online("aprovar", {"nome": "Ana"})])
        )
        from servicos.aprovacao_pre_cadastro import aprovar_pre_cadastro

        registro = db.buscar_pre_cadastro_por_remote_id("aprovar")
        resultado = aprovar_pre_cadastro(registro["id"], permitir_duplicidade=True)
        self.assertTrue(relatorio["sucesso"])
        self.assertTrue(resultado["sucesso"])
        self.assertEqual(db.total_membros(), 1)

    def test_importacao_json_manual_continua_funcionando(self):
        arquivo = Path(self.tmp.name) / "pre.json"
        arquivo.write_text('[{"remote_id": "json-1", "nome": "Json"}]', encoding="utf-8")
        from servicos.importador_pre_cadastro_json import importar_pre_cadastros_json

        relatorio = importar_pre_cadastros_json(arquivo)
        self.assertEqual(relatorio["inseridos"], 1)
        self.assertEqual(db.buscar_pre_cadastro_por_remote_id("json-1")["origem"], "importacao_json")

    def test_ausencia_de_configuracao_retorna_mensagem_segura(self):
        db.salvar_configuracao_online_igreja({
            "api_base_url": "",
            "identificador_publico": "",
            "chave_sincronizacao": "",
            "ativo": 1,
        })
        relatorio = sync.sincronizar_pre_cadastros_online()
        self.assertFalse(relatorio["sucesso"])
        self.assertNotIn(DUMMY_KEY, relatorio["mensagem_usuario"])

    def test_integracao_desativada_nao_tenta_acessar_internet(self):
        db.salvar_configuracao_online_igreja({"ativo": 0})
        factory = mock.Mock()
        relatorio = sync.sincronizar_pre_cadastros_online(factory)
        self.assertFalse(relatorio["sucesso"])
        factory.assert_not_called()

    def test_thread_nao_atualiza_widgets_diretamente(self):
        import telas.pre_cadastros as tela

        origem = Path(tela.__file__).read_text(encoding="utf-8")
        self.assertIn("threading.Thread", origem)
        self.assertIn("self.after(0", origem)

    def test_nenhuma_informacao_secreta_em_logs(self):
        relatorio = sync.sincronizar_pre_cadastros_online(
            self.cliente_factory([item_online("seguro")])
        )
        texto = str(relatorio) + str(db.listar_sincronizacoes_pre_cadastro())
        self.assertNotIn(DUMMY_KEY, texto)


if __name__ == "__main__":
    unittest.main()
