import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from banco import database as db
from servicos.cliente_sigm_online import SIGMOnlineConexaoErro
from servicos.identidade_online_igreja import IdentidadeOnlineIgrejaErro
from web import configuracao_online as web_online

H = {"X-SIGM": "1"}
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


class TesteOnline(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.base = Path(self.pasta.name)
        self.patches = [mock.patch.dict(os.environ, {"SIGM_DADOS_DIR": str(self.base)}),
                        mock.patch.object(db, "BANCO", self.base / "sigm.db")]
        for p in self.patches:
            p.start()
        db.criar_tabelas()
        from web.servidor import criar_app
        self.app = criar_app()
        self.app.config["TESTING"] = True
        self.c = self.cliente("Administrador")

    def cliente(self, perfil):
        c = self.app.test_client()
        with c.session_transaction() as s:
            s["usuario"] = {"id_usuario": 1, "nome": "X", "login": "x", "perfil": perfil, "status": "Ativo"}
        return c

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.pasta.cleanup()

    def ativar_no_banco(self, ativo=1):
        db.salvar_configuracao_online_igreja({
            "identificador_publico": "igreja-abc123", "chave_sincronizacao": "CHAVE-SECRETA-123456",
            "ativo": ativo, "status_ativacao": "ativada" if ativo else "pendente"})

    def test_acesso(self):
        anon = self.app.test_client()
        self.assertEqual(anon.get("/api/online").status_code, 401)
        self.assertEqual(anon.get("/online").status_code, 302)
        self.assertEqual(self.c.get("/online").status_code, 200)
        self.assertIn('href="/online"', self.c.get("/inicio").data.decode())

    def test_status_nao_configurado_e_ativado(self):
        d = self.c.get("/api/online").get_json()
        self.assertFalse(d["configurado"])
        self.assertEqual(d["estado"], "Não conectado")
        self.assertEqual(d["link"], "")
        self.ativar_no_banco()
        d = self.c.get("/api/online").get_json()
        self.assertTrue(d["ativado"])
        self.assertEqual(d["estado"], "Conectado")
        self.assertTrue(d["link"].endswith("/cadastro/igreja-abc123"))
        self.assertNotIn("CHAVE-SECRETA-123456", self.c.get("/api/online").data.decode())
        self.ativar_no_banco(0)
        self.assertEqual(self.c.get("/api/online").get_json()["estado"], "Ativação pendente")

    def test_usuario_comum_nao_ativa_testa_nem_ve_chave(self):
        comum = self.cliente("Usuario")
        self.assertFalse(comum.get("/api/online").get_json()["admin"])
        for rota in ("ativar", "testar", "chave"):
            self.assertEqual(comum.post(f"/api/online/{rota}", headers=H, json={}).status_code, 403, rota)

    def test_ativar_com_servico_simulado_e_erros(self):
        with mock.patch.object(web_online, "ativar_integracao_online_igreja") as ativar:
            ativar.side_effect = lambda: (self.ativar_no_banco(), {"status": "ativada"})[1]
            r = self.c.post("/api/online/ativar", headers=H, json={}).get_json()
        self.assertTrue(r["ok"])
        self.assertTrue(r["ativado"])
        with mock.patch.object(web_online, "ativar_integracao_online_igreja",
                               side_effect=IdentidadeOnlineIgrejaErro("Cadastre os dados da igreja.")):
            r = self.c.post("/api/online/ativar", headers=H, json={})
        self.assertEqual(r.status_code, 400)
        self.assertIn("dados da igreja", r.get_json()["mensagem"])
        with mock.patch.object(web_online, "ativar_integracao_online_igreja",
                               side_effect=SIGMOnlineConexaoErro("sem rede")):
            r = self.c.post("/api/online/ativar", headers=H, json={})
        self.assertEqual(r.status_code, 502)
        self.assertIn("conexão", r.get_json()["mensagem"])

    def test_testar_conexao(self):
        r = self.c.post("/api/online/testar", headers=H, json={})
        self.assertEqual(r.status_code, 400)
        self.ativar_no_banco()
        with mock.patch.object(web_online, "testar_ou_recuperar_integracao_online_igreja",
                               return_value={"recuperada": False}):
            r = self.c.post("/api/online/testar", headers=H, json={}).get_json()
        self.assertTrue(r["ok"])
        self.assertIn("Conexão", r["mensagem"])

    def test_qrcode_exige_ativacao_gera_e_serve(self):
        r = self.c.post("/api/online/qrcode", headers=H, json={})
        self.assertEqual(r.status_code, 400)
        self.ativar_no_banco()

        def falso(url, destino):
            Path(destino).write_bytes(PNG)
            self.url_usada = url
            return str(destino)

        with mock.patch.object(web_online, "gerar_qrcode_igreja", side_effect=falso):
            r = self.c.post("/api/online/qrcode", headers=H, json={}).get_json()
        self.assertTrue(r["ok"])
        self.assertTrue(r["qrcode"]["existe"])
        self.assertTrue(self.url_usada.endswith("/cadastro/igreja-abc123"))
        img = self.c.get("/api/online/qrcode.png")
        self.assertEqual(img.status_code, 200)
        self.assertEqual(img.mimetype, "image/png")
        img.close()
        self.assertEqual(self.app.test_client().get("/api/online/qrcode.png").status_code, 401)

    def test_qrcode_fora_da_pasta_nao_e_servido(self):
        externo = self.base / "outro.png"
        externo.write_bytes(PNG)
        self.ativar_no_banco()
        db.salvar_configuracao_online_igreja({"qr_code_path": str(externo)})
        self.assertEqual(self.c.get("/api/online/qrcode.png").status_code, 404)

    def test_chave_so_para_admin_e_auditada(self):
        self.assertEqual(self.c.post("/api/online/chave", headers=H, json={}).status_code, 404)
        self.ativar_no_banco()
        r = self.c.post("/api/online/chave", headers=H, json={}).get_json()
        self.assertEqual(r["chave"], "CHAVE-SECRETA-123456")
        acoes = [l["acao"] for l in db.listar_logs_auditoria()]
        self.assertIn("CHAVE_SINCRONIZACAO_EXIBIDA", acoes)


if __name__ == "__main__":
    unittest.main()
