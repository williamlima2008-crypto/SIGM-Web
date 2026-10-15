import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from banco import database as db
from web import painel
from web.servidor import criar_app

H = {"X-SIGM": "1"}


class TestePainel(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        base = Path(self.pasta.name)
        self.patches = [mock.patch.dict(os.environ, {"SIGM_DADOS_DIR": str(base)}),
                        mock.patch.object(db, "BANCO", base / "sigm.db")]
        for p in self.patches:
            p.start()
        db.criar_tabelas()
        self.app = criar_app()
        self.app.config["TESTING"] = True
        self.c = self.app.test_client()
        with self.c.session_transaction() as s:
            s["usuario"] = {"id_usuario": 1, "nome": "Teste", "login": "t",
                            "perfil": "Administrador", "status": "Ativo"}

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.pasta.cleanup()

    def test_login_exigido_e_raiz_vai_para_inicio(self):
        anon = self.app.test_client()
        self.assertEqual(anon.get("/api/painel").status_code, 401)
        self.assertEqual(anon.get("/inicio").status_code, 302)
        r = self.c.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/inicio"))

    def test_pagina_tem_saudacao_e_menu(self):
        r = self.c.get("/inicio")
        self.assertEqual(r.status_code, 200)
        texto = r.data.decode()
        self.assertIn("Teste!", texto)
        self.assertIn('href="/inicio"', texto)

    def test_indicadores_refletem_o_banco(self):
        for nome, status in (("Ana", "Membro"), ("Bia", "Visitante"), ("Caio", "Membro")):
            self.c.post("/api/membros", json={"nome": nome, "status": status,
                                              "data_nascimento": "10/05/1990"}, headers=H)
        d = self.c.get("/api/painel").get_json()
        self.assertEqual(d["indicadores"]["total"], 3)
        self.assertEqual(d["indicadores"]["membros"], 2)
        self.assertEqual(d["indicadores"]["visitantes"], 1)
        self.assertEqual(d["ultimos_membros"][0]["nome"], "Caio")
        self.assertEqual(len(d["aniversariantes"]), 3)
        self.assertFalse(d["backup"]["existe"])

    def test_ultimo_backup_e_saudacao(self):
        pasta = Path(self.pasta.name) / "backup"
        pasta.mkdir(exist_ok=True)
        (pasta / "SIGM_backup_1.zip").write_bytes(b"x" * 2048)
        d = self.c.get("/api/painel").get_json()["backup"]
        self.assertTrue(d["existe"])
        self.assertEqual(d["arquivo"], "SIGM_backup_1.zip")
        self.assertEqual(d["tamanho"], "2.0 KB")
        self.assertEqual(painel.saudacao(datetime(2026, 1, 1, 9)), "Bom dia")
        self.assertEqual(painel.saudacao(datetime(2026, 1, 1, 15)), "Boa tarde")
        self.assertEqual(painel.saudacao(datetime(2026, 1, 1, 21)), "Boa noite")


if __name__ == "__main__":
    unittest.main()
