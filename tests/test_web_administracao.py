import io
import os
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from banco import database as db

H = {"X-SIGM": "1"}


class Base(unittest.TestCase):
    perfil = "Administrador"

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base = Path(self.pasta.name)
        self.patches = [mock.patch.dict(os.environ, {"SIGM_DADOS_DIR": str(self.base)}),
                        mock.patch.object(db, "BANCO", self.base / "sigm.db")]
        for p in self.patches:
            p.start()
        db.criar_tabelas()
        self.id_admin = db.cadastrar_usuario("Admin", "admin", "senha123", "Administrador")
        self.id_comum = db.cadastrar_usuario("Comum", "comum", "senha123", "Usuario")
        from web.servidor import criar_app
        self.app = criar_app()
        self.app.config["TESTING"] = True
        self.c = self.app.test_client()
        self.entrar(self.c, self.perfil)

    def entrar(self, cliente, perfil):
        ident = self.id_admin if perfil == "Administrador" else self.id_comum
        with cliente.session_transaction() as s:
            s["usuario"] = {"id_usuario": ident, "nome": "X", "login": "x", "perfil": perfil, "status": "Ativo"}

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.pasta.cleanup()


class TesteAcesso(Base):
    def test_usuario_comum_nao_acessa_admin(self):
        comum = self.app.test_client()
        self.entrar(comum, "Usuario")
        for caminho in ("/api/usuarios", "/api/auditoria", "/api/auditoria/exportar", "/api/backup/SIGM_backup_1.zip/arquivo"):
            self.assertEqual(comum.get(caminho).status_code, 403, caminho)
        for caminho in ("/usuarios", "/auditoria"):
            self.assertEqual(comum.get(caminho).status_code, 302)
        self.assertEqual(comum.post("/api/usuarios/1/excluir", json={}, headers=H).status_code, 403)
        self.assertEqual(comum.post("/api/backup/SIGM_backup_1.zip/restaurar", json={}, headers=H).status_code, 403)
        menu = comum.get("/inicio").data.decode()
        self.assertNotIn('href="/usuarios"', menu)
        self.assertIn('href="/backup"', menu)
        self.assertEqual(comum.get("/api/backup").get_json()["admin"], False)

    def test_admin_ve_menu_e_paginas(self):
        menu = self.c.get("/inicio").data.decode()
        self.assertIn('href="/usuarios"', menu)
        self.assertIn('href="/auditoria"', menu)
        for caminho in ("/usuarios", "/auditoria", "/backup"):
            self.assertEqual(self.c.get(caminho).status_code, 200)

    def test_anonimo(self):
        anon = self.app.test_client()
        self.assertEqual(anon.get("/api/usuarios").status_code, 401)
        self.assertEqual(anon.get("/usuarios").status_code, 302)


class TesteUsuarios(Base):
    def test_criar_validar_e_duplicado(self):
        r = self.c.post("/api/usuarios", headers=H, json={"nome": "Novo", "usuario": "novo", "senha": "abcdef", "perfil": "Usuario"})
        self.assertTrue(r.get_json()["ok"], r.get_json())
        self.assertIsNotNone(db.validar_login("novo", "abcdef"))
        casos = [({"nome": "", "usuario": "a", "senha": "abcdef", "perfil": "Usuario"}, "nome"),
                 ({"nome": "A", "usuario": "a b", "senha": "abcdef", "perfil": "Usuario"}, "espaços"),
                 ({"nome": "A", "usuario": "a", "senha": "123", "perfil": "Usuario"}, "senha"),
                 ({"nome": "A", "usuario": "a", "senha": "abcdef", "perfil": "Root"}, "Perfil"),
                 ({"nome": "A", "usuario": "novo", "senha": "abcdef", "perfil": "Usuario"}, "Já existe")]
        for dados, trecho in casos:
            r = self.c.post("/api/usuarios", headers=H, json=dados)
            self.assertEqual(r.status_code, 400, dados)
            self.assertIn(trecho, r.get_json()["mensagem"])

    def test_lista_nao_expoe_hash(self):
        itens = self.c.get("/api/usuarios").get_json()["itens"]
        self.assertEqual(len(itens), 2)
        self.assertNotIn("senha", itens[0])

    def test_editar_senha_status_excluir(self):
        r = self.c.put(f"/api/usuarios/{self.id_comum}", headers=H,
                       json={"nome": "Comum 2", "usuario": "comum", "perfil": "Usuario", "ativo": True})
        self.assertTrue(r.get_json()["ok"])
        self.assertEqual(db.buscar_usuario_por_id(self.id_comum)["nome"], "Comum 2")
        self.assertEqual(self.c.post(f"/api/usuarios/{self.id_comum}/senha", headers=H, json={"senha": "123"}).status_code, 400)
        self.c.post(f"/api/usuarios/{self.id_comum}/senha", headers=H, json={"senha": "nova1234"})
        self.assertIsNotNone(db.validar_login("comum", "nova1234"))
        self.c.post(f"/api/usuarios/{self.id_comum}/status", headers=H, json={"ativo": False})
        self.assertTrue(db.validar_login("comum", "nova1234")["bloqueado"])
        self.c.post(f"/api/usuarios/{self.id_comum}/status", headers=H, json={"ativo": True})
        self.assertTrue(self.c.post(f"/api/usuarios/{self.id_comum}/excluir", headers=H, json={}).get_json()["ok"])
        self.assertIsNone(db.buscar_usuario_por_id(self.id_comum))

    def test_protecoes_do_proprio_admin_e_do_ultimo_admin(self):
        for rota, corpo in ((f"/api/usuarios/{self.id_admin}/excluir", {}),
                            (f"/api/usuarios/{self.id_admin}/status", {"ativo": False})):
            self.assertEqual(self.c.post(rota, headers=H, json=corpo).status_code, 400)
        r = self.c.put(f"/api/usuarios/{self.id_admin}", headers=H,
                       json={"nome": "Admin", "usuario": "admin", "perfil": "Usuario", "ativo": True})
        self.assertEqual(r.status_code, 400)
        # outro admin tentando mexer no ultimo admin ativo (regra do banco)
        outro = self.app.test_client()
        self.entrar(outro, "Administrador")
        with outro.session_transaction() as s:
            s["usuario"] = {"id_usuario": 999, "nome": "Y", "login": "y", "perfil": "Administrador", "status": "Ativo"}
        r = outro.post(f"/api/usuarios/{self.id_admin}/excluir", headers=H, json={})
        self.assertEqual(r.status_code, 400)
        self.assertIn("ultimo Administrador", r.get_json()["mensagem"])
        self.assertIsNotNone(db.buscar_usuario_por_id(self.id_admin))

    def test_chave_de_recuperacao(self):
        self.assertFalse(self.c.get("/api/usuarios").get_json()["chave"]["existe"])
        r = self.c.post("/api/usuarios/chave-recuperacao", headers=H, json={}).get_json()
        self.assertRegex(r["chave"], r"^[A-Z0-9]{4}(-[A-Z0-9]{4}){3}$")
        self.assertTrue(self.c.get("/api/usuarios").get_json()["chave"]["existe"])
        self.assertNotIn(r["chave"], self.c.get("/api/usuarios").data.decode())

    def test_acoes_vao_para_a_auditoria(self):
        self.c.post("/api/usuarios", headers=H, json={"nome": "N", "usuario": "n", "senha": "abcdef", "perfil": "Usuario"})
        acoes = [l["acao"] for l in db.listar_logs_auditoria()]
        self.assertIn("USUARIO_CRIADO", acoes)


class TesteAuditoria(Base):
    def test_listar_filtrar_detalhe_e_pdf(self):
        from utils.auditoria import registrar_acao
        registrar_acao("TESTE_A", "Primeira acao", modulo="Modulo1", usuario_nome="Ana", usuario_login="ana")
        registrar_acao("TESTE_B", "Segunda acao", modulo="Modulo2", usuario_nome="Beto", usuario_login="beto")
        d = self.c.get("/api/auditoria").get_json()
        self.assertGreaterEqual(len(d["itens"]), 2)
        r = self.c.get("/api/auditoria?usuario=beto").get_json()
        self.assertEqual([i["acao"] for i in r["itens"]], ["TESTE_B"])
        r = self.c.get("/api/auditoria?q=primeira").get_json()
        self.assertEqual([i["acao"] for i in r["itens"]], ["TESTE_A"])
        det = self.c.get(f"/api/auditoria/{r['itens'][0]['id']}").get_json()
        self.assertEqual(det["modulo"], "Modulo1")
        self.assertEqual(self.c.get("/api/auditoria/99999").status_code, 404)
        pdf = self.c.get("/api/auditoria/exportar?modulo=Modulo1")
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.data.startswith(b"%PDF"))
        pdf.close()
        self.assertEqual(self.c.get("/api/auditoria/exportar?q=nadaaqui").status_code, 404)


class TesteLimpezaAuditoria(Base):
    def test_limpar_antigos_com_minimo_e_registro(self):
        from banco.database import conectar
        con = conectar()
        con.execute("INSERT INTO logs_auditoria (acao, descricao, data_hora) VALUES ('VELHO','x','2020-01-01 10:00:00')")
        con.commit()
        con.close()
        for corpo in ({}, {"dias": 10}, {"dias": "abc"}):
            self.assertEqual(self.c.post("/api/auditoria/limpar", json=corpo, headers=H).status_code, 400)
        r = self.c.post("/api/auditoria/limpar", json={"dias": 90}, headers=H).get_json()
        self.assertTrue(r["ok"])
        self.assertGreaterEqual(r["removidos"], 1)
        acoes = [l["acao"] for l in db.listar_logs_auditoria(limite=50)]
        self.assertNotIn("VELHO", acoes)
        self.assertIn("LOG_AUDITORIA_LIMPO", acoes)

    def test_usuario_comum_nao_limpa(self):
        comum = self.app.test_client()
        self.entrar(comum, "Usuario")
        self.assertEqual(comum.post("/api/auditoria/limpar", json={"dias": 90}, headers=H).status_code, 403)


class TesteBackup(Base):
    def test_criar_listar_baixar(self):
        (self.base / "fotos_membros").mkdir(exist_ok=True)
        (self.base / "fotos_membros" / "foto_1.jpg").write_bytes(b"jpg")
        r = self.c.post("/api/backup", headers=H, json={}).get_json()
        self.assertTrue(r["ok"], r)
        itens = self.c.get("/api/backup").get_json()["itens"]
        self.assertEqual([i["nome"] for i in itens], [r["nome"]])
        with zipfile.ZipFile(self.base / "backup" / r["nome"]) as z:
            nomes = z.namelist()
        self.assertIn("sigm.db", nomes)
        self.assertTrue(any(n.replace("\\", "/") == "fotos_membros/foto_1.jpg" for n in nomes))
        baixar = self.c.get(f"/api/backup/{r['nome']}/arquivo")
        self.assertEqual(baixar.status_code, 200)
        self.assertEqual(baixar.mimetype, "application/zip")
        baixar.close()
        self.assertEqual(self.c.get("/api/backup/..%2Fsigm.db/arquivo").status_code, 404)
        self.assertEqual(self.c.get("/api/backup/outro.zip/arquivo").status_code, 404)

    def test_restaurar_volta_o_banco_e_guarda_seguranca(self):
        nome = self.c.post("/api/backup", headers=H, json={}).get_json()["nome"]
        db.cadastrar_usuario("Depois", "depois", "abcdef", "Usuario")
        self.assertIsNotNone(db.validar_login("depois", "abcdef"))
        self.assertEqual(self.c.post(f"/api/backup/{nome}/restaurar", headers=H, json={}).status_code, 400)
        r = self.c.post(f"/api/backup/{nome}/restaurar", headers=H, json={"confirmar": True}).get_json()
        self.assertTrue(r["ok"], r)
        self.assertIsNone(db.validar_login("depois", "abcdef"))
        self.assertIn(r["seguranca"], [i["nome"] for i in self.c.get("/api/backup").get_json()["itens"]])

    def test_backup_invalido_e_recusado(self):
        pasta = self.base / "backup"
        pasta.mkdir(exist_ok=True)
        with zipfile.ZipFile(pasta / "SIGM_backup_ruim1.zip", "w") as z:
            z.writestr("outro.txt", "x")
        with zipfile.ZipFile(pasta / "SIGM_backup_ruim2.zip", "w") as z:
            z.writestr("sigm.db", "isso nao e sqlite")
        with zipfile.ZipFile(pasta / "SIGM_backup_ruim3.zip", "w") as z:
            z.writestr("sigm.db", b"SQLite format 3\x00" + b"0" * 100)
            z.writestr("../fugiu.txt", "x")
        (pasta / "SIGM_backup_ruim4.zip").write_bytes(b"nao e zip")
        for nome in ("ruim1", "ruim2", "ruim3", "ruim4"):
            r = self.c.post(f"/api/backup/SIGM_backup_{nome}.zip/restaurar", headers=H, json={"confirmar": True})
            self.assertEqual(r.status_code, 400, nome)
        self.assertFalse((self.base.parent / "fugiu.txt").exists())
        self.assertEqual(self.c.post("/api/backup/inexistente.zip/restaurar", headers=H, json={"confirmar": True}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
