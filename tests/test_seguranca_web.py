import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from banco import database as db
from web import limite_tentativas

H = {"X-SIGM": "1"}


class SegurancaWebTestCase(unittest.TestCase):
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

    def test_host_estranho_e_recusado(self):
        r = self.c.get("/login", headers={"Host": "evil.example.com"})
        self.assertEqual(r.status_code, 400)

    def test_host_local_e_ip_passam(self):
        for host in ("localhost:8765", "127.0.0.1:8765", "192.168.0.10:8765", "[::1]:8765"):
            self.assertEqual(self.c.get("/api/ping", headers={"Host": host}).status_code, 200, host)

    def test_senha_minima_oito(self):
        db.cadastrar_usuario("A", "a", "senha1234", "Administrador")
        self.c.post("/api/login", headers=H, json={"usuario": "a", "senha": "senha1234"})
        r = self.c.post("/api/usuarios", headers=H,
                        json={"nome": "N", "usuario": "n", "senha": "1234567", "perfil": "Usuario"})
        self.assertEqual(r.status_code, 400)
        r = self.c.post("/api/usuarios", headers=H,
                        json={"nome": "N", "usuario": "n", "senha": "12345678", "perfil": "Usuario"})
        self.assertEqual(r.status_code, 200)

    def test_bloqueio_de_login_sobrevive_ao_reinicio(self):
        db.cadastrar_usuario("A", "a", "senha1234", "Administrador")
        for _ in range(5):
            self.c.post("/api/login", headers=H, json={"usuario": "a", "senha": "errada"})
        from web.servidor import criar_app
        novo = criar_app()
        novo.config["TESTING"] = True
        r = novo.test_client().post("/api/login", headers=H, json={"usuario": "a", "senha": "senha1234"})
        self.assertEqual(r.status_code, 429)

    def test_limpar_zera_falhas(self):
        limite_tentativas.falhou("x", "k", 60)
        self.assertFalse(limite_tentativas.bloqueado("x", "k", 2, 60))
        limite_tentativas.falhou("x", "k", 60)
        self.assertTrue(limite_tentativas.bloqueado("x", "k", 2, 60))
        limite_tentativas.limpar("x", "k")
        self.assertFalse(limite_tentativas.bloqueado("x", "k", 2, 60))


if __name__ == "__main__":
    unittest.main()
