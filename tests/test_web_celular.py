import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from banco import database as db

H = {"X-SIGM": "1"}


class ClienteFalso:
    """Faz o papel do SIGM Celular (nada sai pela rede)."""

    def __init__(self, alteracoes=None):
        self.alteracoes = alteracoes or []
        self.membros_enviados = []
        self.configuracoes = []
        self.finalizados = []
        self.resultados = []

    def validar_igreja(self):
        return {}

    def enviar_configuracao(self, configuracao, logotipo_base64=None):
        self.configuracoes.append((configuracao, logotipo_base64))

    def estado(self):
        return {}

    def enviar_membros(self, itens):
        self.membros_enviados.extend(itens)
        return {"sucesso": True, "criados": len(itens), "atualizados": 0, "erros": 0}

    def finalizar(self, ids):
        self.finalizados.append(ids)
        return {"sucesso": True, "removidos": 0}

    def listar_alteracoes(self):
        return list(self.alteracoes)

    def enviar_resultados(self, resultados):
        self.resultados.extend(resultados)
        return {"sucesso": True}


ATIVA = {"ativo": 1, "identificador_publico": "sigm-teste", "chave_sincronizacao": "chave-longa-de-teste"}


class TesteCelular(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base = Path(self.pasta.name)
        self.patches = [mock.patch.dict(os.environ, {"SIGM_DADOS_DIR": str(base)}),
                        mock.patch.object(db, "BANCO", base / "sigm.db")]
        for p in self.patches:
            p.start()
        db.criar_tabelas()
        from web import celular as web_celular
        self.web = web_celular
        web_celular._estado.update(em_andamento=False, mensagem="", erro="", resumo=None, concluido_em="")
        from web.servidor import criar_app
        self.app = criar_app()
        self.app.config["TESTING"] = True
        self.c = self.app.test_client()
        with self.c.session_transaction() as s:
            s["usuario"] = {"id_usuario": 1, "nome": "Maria Secretaria", "login": "maria",
                            "perfil": "Administrador", "status": "Ativo"}
        self.cliente = ClienteFalso()
        self.patches += [
            mock.patch("web.celular.buscar_configuracao_online_igreja", return_value=ATIVA),
            mock.patch("servicos.sincronizacao_celular.buscar_configuracao_online_igreja", return_value=ATIVA),
            mock.patch("servicos.sincronizacao_celular.criar_cliente", side_effect=lambda: self.cliente),
        ]
        for p in self.patches[2:]:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.pasta.cleanup()

    def membro(self, nome, **extra):
        r = self.c.post("/api/membros", json={"nome": nome, **extra}, headers=H)
        return r.get_json()["id"]

    def esperar_fim(self):
        for _ in range(100):
            estado = self.c.get("/api/celular").get_json()
            if not estado["em_andamento"]:
                return estado
            time.sleep(0.1)
        self.fail("o envio nao terminou")

    def test_login_obrigatorio_e_menu(self):
        anon = self.app.test_client()
        self.assertEqual(anon.get("/api/celular").status_code, 401)
        self.assertEqual(anon.get("/celular").status_code, 302)
        r = self.c.get("/celular")
        self.assertEqual(r.status_code, 200)
        self.assertIn('href="/celular"', r.data.decode())
        self.assertIn("Enviar dados ao Celular", r.data.decode())

    def test_sem_integracao_nao_envia(self):
        with mock.patch("web.celular.buscar_configuracao_online_igreja", return_value={"ativo": 0}):
            self.assertFalse(self.c.get("/api/celular").get_json()["ativado"])
            r = self.c.post("/api/celular/enviar", json={}, headers=H)
        self.assertEqual(r.status_code, 400)
        self.assertIn("integração", r.get_json()["mensagem"])

    def test_envio_manda_membros_e_igreja_e_registra_quem_enviou(self):
        id_ana = self.membro("Ana Lima", cidade="Guarulhos")
        self.membro("Bia Souza")
        r = self.c.post("/api/celular/enviar", json={}, headers=H)
        self.assertTrue(r.get_json()["ok"])
        estado = self.esperar_fim()
        self.assertEqual(estado["erro"], "")
        self.assertEqual(estado["resumo"]["enviados"], 2)
        self.assertIn("2 enviado(s)", estado["resumo_texto"])
        nomes = sorted(i["dados"]["nome"] for i in self.cliente.membros_enviados)
        self.assertEqual(nomes, ["Ana Lima", "Bia Souza"])
        ana = next(i for i in self.cliente.membros_enviados if i["id_desktop"] == id_ana)
        self.assertEqual(ana["dados"]["cidade"], "Guarulhos")
        self.assertEqual(len(self.cliente.configuracoes), 1)
        self.assertEqual(sorted(self.cliente.finalizados[0]), sorted(i["id_desktop"] for i in self.cliente.membros_enviados))
        logs = [dict(l) if not isinstance(l, dict) else l for l in db.listar_logs_auditoria(acao="SINCRONIZACAO_CELULAR_CONCLUIDA")]
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["usuario_nome"], "Maria Secretaria")

    def test_erro_do_celular_vira_mensagem_amigavel(self):
        def falha():
            raise ValueError("segredo tecnico")
        self.cliente.validar_igreja = falha
        self.c.post("/api/celular/enviar", json={}, headers=H)
        estado = self.esperar_fim()
        self.assertIn("Nao foi possivel sincronizar", estado["erro"])
        self.assertNotIn("segredo", estado["erro"])
        self.assertIsNone(estado["resumo"])

    def test_nao_inicia_dois_envios_ao_mesmo_tempo(self):
        self.web._estado["em_andamento"] = True
        r = self.c.post("/api/celular/enviar", json={}, headers=H)
        self.assertEqual(r.status_code, 409)

    def alteracao(self, id_membro, **campos):
        return {"id": 7, "id_desktop": id_membro, "nome": "Ana Lima", "criado_por": "lider",
                "campos": campos or {"cidade": {"antes": "", "depois": "Guarulhos"}}}

    def test_buscar_mostra_valor_atual_e_o_proposto(self):
        id_ana = self.membro("Ana Lima", cidade="Osasco")
        self.cliente.alteracoes = [self.alteracao(id_ana)]
        d = self.c.post("/api/celular/alteracoes/buscar", json={}, headers=H).get_json()
        self.assertTrue(d["ok"])
        campo = d["alteracoes"][0]["situacao"]["campos"]["cidade"]
        self.assertEqual((campo["atual"], campo["depois"]), ("Osasco", "Guarulhos"))

    def test_aplicar_grava_no_membro_e_avisa_o_celular(self):
        id_ana = self.membro("Ana Lima", cidade="Osasco")
        self.cliente.alteracoes = [self.alteracao(id_ana)]
        r = self.c.post("/api/celular/alteracoes/responder", json={"id": 7, "acao": "aplicar"}, headers=H)
        self.assertTrue(r.get_json()["ok"], r.get_json())
        self.assertEqual(self.c.get(f"/api/membros/{id_ana}").get_json()["campos"]["cidade"], "Guarulhos")
        self.assertEqual(self.cliente.resultados, [{"id": 7, "status": "aplicada"}])

    def test_rejeitar_nao_altera_o_membro(self):
        id_ana = self.membro("Ana Lima", cidade="Osasco")
        self.cliente.alteracoes = [self.alteracao(id_ana)]
        r = self.c.post("/api/celular/alteracoes/responder", json={"id": 7, "acao": "rejeitar"}, headers=H)
        self.assertTrue(r.get_json()["ok"])
        self.assertEqual(self.c.get(f"/api/membros/{id_ana}").get_json()["campos"]["cidade"], "Osasco")
        self.assertEqual(self.cliente.resultados[0]["status"], "rejeitada")

    def test_responder_valida_pedido_e_sugestao_inexistente(self):
        r = self.c.post("/api/celular/alteracoes/responder", json={"id": 7, "acao": "apagar"}, headers=H)
        self.assertEqual(r.status_code, 400)
        r = self.c.post("/api/celular/alteracoes/responder", json={"id": 99, "acao": "aplicar"}, headers=H)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.cliente.resultados, [])

    def test_envio_traz_primeiro_as_edicoes_do_celular(self):
        id_ana = self.membro("Ana Lima", cidade="Osasco", bairro="Centro")
        self.cliente.alteracoes = [self.alteracao(
            id_ana, cidade={"antes": "Osasco", "depois": "Guarulhos"})]
        self.c.post("/api/celular/enviar", json={}, headers=H)
        estado = self.esperar_fim()
        self.assertEqual(estado["erro"], "")
        self.assertEqual(self.c.get(f"/api/membros/{id_ana}").get_json()["campos"]["cidade"], "Guarulhos")
        self.assertEqual(self.cliente.resultados, [{"id": 7, "status": "aplicada", "motivo": ""}])
        enviado = next(i for i in self.cliente.membros_enviados if i["id_desktop"] == id_ana)
        self.assertEqual(enviado["dados"]["cidade"], "Guarulhos")  # ja sai com o valor novo
        self.assertIn("edicoes feitas no Celular", estado["resumo_texto"])

    def test_campo_alterado_nos_dois_lados_vale_o_do_desktop(self):
        id_ana = self.membro("Ana Lima", cidade="Osasco", bairro="Centro")
        self.cliente.alteracoes = [self.alteracao(
            id_ana,
            cidade={"antes": "Barueri", "depois": "Guarulhos"},   # desktop mudou para Osasco depois
            bairro={"antes": "Centro", "depois": "Vila Nova"},    # so o celular mudou
        )]
        self.c.post("/api/celular/enviar", json={}, headers=H)
        estado = self.esperar_fim()
        campos = self.c.get(f"/api/membros/{id_ana}").get_json()["campos"]
        self.assertEqual((campos["cidade"], campos["bairro"]), ("Osasco", "Vila Nova"))
        self.assertEqual(self.cliente.resultados[0]["status"], "aplicada")
        self.assertIn("cidade", self.cliente.resultados[0]["motivo"])
        self.assertIn("valeu o do desktop", estado["resumo_texto"])

    def test_edicao_de_membro_apagado_no_desktop_e_rejeitada(self):
        self.cliente.alteracoes = [self.alteracao(9999)]
        self.c.post("/api/celular/enviar", json={}, headers=H)
        self.esperar_fim()
        self.assertEqual(self.cliente.resultados[0]["status"], "rejeitada")


if __name__ == "__main__":
    unittest.main()
