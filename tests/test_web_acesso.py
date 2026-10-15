import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from banco import database as db
from banco.database import buscar_configuracoes_igreja, listar_usuarios

H = {"X-SIGM": "1"}
PRIMEIRO = {"nome_igreja": "Igreja Nova", "ministerio": "Ministério", "cidade": "Santos", "estado": "sp",
            "nome_admin": "William", "usuario": "will", "senha": "segredo1", "confirmar": "segredo1"}


class Base(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        base = Path(self.pasta.name)
        self.patches = [mock.patch.dict(os.environ, {"SIGM_DADOS_DIR": str(base)}),
                        mock.patch.object(db, "BANCO", base / "sigm.db")]
        for p in self.patches:
            p.start()
        db.criar_tabelas()
        from web.servidor import criar_app
        self.app = criar_app()
        self.app.config["TESTING"] = True
        self.c = self.app.test_client()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.pasta.cleanup()


class TestePrimeiroAcesso(Base):
    def test_login_mostra_formulario_de_primeiro_acesso(self):
        self.assertIn("form-primeiro", self.c.get("/login").data.decode())

    def test_configura_igreja_admin_e_chave(self):
        r = self.c.post("/api/primeiro-acesso", headers=H, json=PRIMEIRO).get_json()
        self.assertTrue(r["ok"], r)
        self.assertRegex(r["chave"], r"^[A-Z0-9]{4}(-[A-Z0-9]{4}){3}$")
        self.assertEqual(buscar_configuracoes_igreja()["nome_igreja"], "Igreja Nova")
        self.assertEqual(buscar_configuracoes_igreja()["estado"], "SP")
        usuarios = listar_usuarios()
        self.assertEqual([(u["usuario"], u["perfil"]) for u in usuarios], [("will", "Administrador")])
        self.assertIsNotNone(db.validar_login("will", "segredo1"))
        self.assertIn("form-login", self.c.get("/login").data.decode())

    def test_so_funciona_uma_vez(self):
        self.c.post("/api/primeiro-acesso", headers=H, json=PRIMEIRO)
        r = self.c.post("/api/primeiro-acesso", headers=H, json={**PRIMEIRO, "usuario": "outro"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(len(listar_usuarios()), 1)

    def test_validacoes(self):
        casos = [({"nome_igreja": ""}, "obrigatórios"), ({"senha": "123", "confirmar": "123"}, "pelo menos"),
                 ({"confirmar": "diferente"}, "não conferem"), ({"usuario": "a b"}, "espaços")]
        for mudanca, trecho in casos:
            r = self.c.post("/api/primeiro-acesso", headers=H, json={**PRIMEIRO, **mudanca})
            self.assertEqual(r.status_code, 400, mudanca)
            self.assertIn(trecho, r.get_json()["mensagem"])
        self.assertEqual(listar_usuarios(), [])

    def test_exige_cabecalho(self):
        self.assertEqual(self.c.post("/api/primeiro-acesso", json=PRIMEIRO).status_code, 403)


class TesteRecuperarSenha(Base):
    def setUp(self):
        super().setUp()
        self.chave = self.c.post("/api/primeiro-acesso", headers=H, json=PRIMEIRO).get_json()["chave"]

    def recuperar(self, **extra):
        dados = {"usuario": "will", "chave": self.chave, "senha": "novasenha", "confirmar": "novasenha"}
        dados.update(extra)
        return self.c.post("/api/recuperar-senha", headers=H, json=dados)

    def test_redefine_com_chave_correta(self):
        r = self.recuperar()
        self.assertTrue(r.get_json()["ok"], r.get_json())
        self.assertIsNone(db.validar_login("will", "segredo1"))
        self.assertIsNotNone(db.validar_login("will", "novasenha"))
        self.assertIn("SENHA_REDEFINIDA_POR_CHAVE", [l["acao"] for l in db.listar_logs_auditoria()])

    def test_chave_ou_usuario_errados_dao_a_mesma_mensagem(self):
        a = self.recuperar(chave="AAAA-BBBB-CCCC-DDDD").get_json()["mensagem"]
        b = self.recuperar(usuario="ninguem").get_json()["mensagem"]
        self.assertEqual(a, b)
        self.assertIsNotNone(db.validar_login("will", "segredo1"))

    def test_validacoes_basicas(self):
        self.assertEqual(self.recuperar(confirmar="x").status_code, 400)
        self.assertEqual(self.recuperar(senha="123", confirmar="123").status_code, 400)
        self.assertEqual(self.recuperar(usuario="").status_code, 400)

    def test_bloqueia_apos_5_falhas(self):
        for _ in range(5):
            self.assertEqual(self.recuperar(chave="AAAA-BBBB-CCCC-DDDD").status_code, 400)
        self.assertEqual(self.recuperar().status_code, 429)
        self.assertIsNotNone(db.validar_login("will", "segredo1"))


class TesteSenhaComEspacosESobre(Base):
    def test_login_ignora_espacos_nas_pontas_como_o_desktop(self):
        db.cadastrar_usuario("A", "a", "senha123", "Administrador")
        r = self.c.post("/api/login", headers=H, json={"usuario": "a", "senha": "  senha123 "})
        self.assertEqual(r.status_code, 200)

    def test_sobre(self):
        db.cadastrar_usuario("A", "a", "senha123", "Administrador")
        with self.c.session_transaction() as s:
            s["usuario"] = {"id_usuario": 1, "nome": "A", "login": "a", "perfil": "Administrador", "status": "Ativo"}
        r = self.c.get("/sobre")
        self.assertEqual(r.status_code, 200)
        self.assertIn("William Lima", r.data.decode())
        self.assertIn('href="/sobre"', r.data.decode())
        self.assertEqual(self.app.test_client().get("/sobre").status_code, 302)


if __name__ == "__main__":
    unittest.main()
