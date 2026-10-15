import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from banco import database as db

H = {"X-SIGM": "1"}


class TesteCentralDocumentos(unittest.TestCase):
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
        with self.c.session_transaction() as s:
            s["usuario"] = {"id_usuario": 1, "nome": "Teste", "login": "t",
                            "perfil": "Administrador", "status": "Ativo"}

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.pasta.cleanup()

    def pdf(self, nome):
        caminho = Path(self.pasta.name) / nome
        caminho.write_bytes(b"%PDF-1.4\n%%EOF\n")
        return str(caminho)

    def membro(self, nome):
        return self.c.post("/api/membros", json={"nome": nome}, headers=H).get_json()["id"]

    def test_login_e_pagina(self):
        anon = self.app.test_client()
        self.assertEqual(anon.get("/api/documentos-emitidos").status_code, 401)
        self.assertEqual(anon.get("/documentos").status_code, 302)
        r = self.c.get("/documentos")
        self.assertEqual(r.status_code, 200)
        self.assertIn('href="/documentos"', r.data.decode())

    def test_lista_busca_e_arquivo(self):
        ana, bia = self.membro("Ana Lima"), self.membro("Bia Souza")
        db.registrar_documento_emitido(ana, "carta", "Carta de Recomendacao", self.pdf("a.pdf"))
        db.registrar_documento_emitido(bia, "ficha", "Ficha Cadastral", "/nao/existe.pdf")
        d = self.c.get("/api/documentos-emitidos").get_json()
        self.assertEqual(d["total"], 2)
        titulos = {i["titulo"]: i for i in d["itens"]}
        self.assertIn("Carta de Recomendação", titulos)
        self.assertTrue(titulos["Carta de Recomendação"]["disponivel"])
        self.assertEqual(titulos["Carta de Recomendação"]["membro"], "Ana Lima")
        self.assertFalse(titulos["Ficha Cadastral"]["disponivel"])
        r = self.c.get("/api/documentos-emitidos?q=souza").get_json()
        self.assertEqual([i["membro"] for i in r["itens"]], ["Bia Souza"])
        r = self.c.get("/api/documentos-emitidos?q=recomendacao").get_json()
        self.assertEqual(len(r["itens"]), 1)
        self.assertEqual(self.c.get("/api/documentos-emitidos?q=zzz").get_json()["itens"], [])
        self.assertNotIn("_busca", d["itens"][0])
        self.assertNotIn("caminho_arquivo", d["itens"][0])

    def test_sem_filtro_limita_a_20(self):
        ana = self.membro("Ana")
        for n in range(25):
            db.registrar_documento_emitido(ana, "x", f"Doc {n}", self.pdf(f"{n}.pdf"))
        d = self.c.get("/api/documentos-emitidos").get_json()
        self.assertEqual(d["total"], 25)
        self.assertEqual(len(d["itens"]), 20)

    def test_excluir_so_registro_mantem_pdf(self):
        ana = self.membro("Ana")
        pdf = Path(self.pasta.name) / "documentos_gerados" / "a.pdf"
        pdf.parent.mkdir(exist_ok=True)
        pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
        db.registrar_documento_emitido(ana, "carta", "Carta", str(pdf))
        doc_id = self.c.get("/api/documentos-emitidos").get_json()["itens"][0]["id"]
        r = self.c.post(f"/api/documentos-emitidos/{doc_id}/excluir", json={}, headers=H)
        self.assertTrue(r.get_json()["ok"])
        self.assertFalse(r.get_json()["arquivo_apagado"])
        self.assertTrue(pdf.exists())
        self.assertEqual(self.c.get("/api/documentos-emitidos").get_json()["total"], 0)
        self.assertEqual(self.c.post(f"/api/documentos-emitidos/{doc_id}/excluir", json={}, headers=H).status_code, 404)

    def test_excluir_com_pdf_apaga_so_dentro_da_pasta_do_sistema(self):
        ana = self.membro("Ana")
        dentro = Path(self.pasta.name) / "documentos_gerados" / "b.pdf"
        dentro.parent.mkdir(exist_ok=True)
        dentro.write_bytes(b"%PDF-1.4\n%%EOF\n")
        fora = Path(self.pdf("fora.pdf"))
        db.registrar_documento_emitido(ana, "x", "Dentro", str(dentro))
        db.registrar_documento_emitido(ana, "x", "Fora", str(fora))
        itens = {i["titulo"]: i["id"] for i in self.c.get("/api/documentos-emitidos").get_json()["itens"]}
        r = self.c.post(f"/api/documentos-emitidos/{itens['Dentro']}/excluir", json={"fisico": True}, headers=H)
        self.assertTrue(r.get_json()["arquivo_apagado"])
        self.assertFalse(dentro.exists())
        r = self.c.post(f"/api/documentos-emitidos/{itens['Fora']}/excluir", json={"fisico": True}, headers=H)
        self.assertFalse(r.get_json()["arquivo_apagado"])
        self.assertTrue(fora.exists())
        acoes = [l["acao"] for l in db.listar_logs_auditoria(limite=10)]
        self.assertIn("HISTORICO_DOCUMENTO_EXCLUIDO", acoes)

    def test_excluir_exige_login_e_cabecalho(self):
        self.assertEqual(self.app.test_client().post("/api/documentos-emitidos/1/excluir", json={}, headers=H).status_code, 401)
        self.assertEqual(self.c.post("/api/documentos-emitidos/1/excluir", json={}).status_code, 403)

    def test_excluir_pre_cadastros_em_lote(self):
        for nome, st in (("A", "aprovado"), ("B", "aprovado"), ("C", "duplicado"), ("D", "pendente")):
            pid = db.salvar_pre_cadastro({"nome": nome, "cpf": "", "celular": ""})
            pid = pid["id"] if isinstance(pid, dict) else pid
            if st != "pendente":
                db.atualizar_status_pre_cadastro(pid, st)
        self.assertEqual(self.c.post("/api/pre-cadastros/excluir-lote", json={"status": "pendente"}, headers=H).status_code, 400)
        self.assertEqual(self.c.post("/api/pre-cadastros/excluir-lote", json={}, headers=H).status_code, 400)
        r = self.c.post("/api/pre-cadastros/excluir-lote", json={"status": "aprovado"}, headers=H).get_json()
        self.assertEqual(r["total"], 2)
        restantes = {p["nome"] for p in db.listar_pre_cadastros()}
        self.assertEqual(restantes, {"C", "D"})
        self.assertEqual(self.c.post("/api/pre-cadastros/excluir-lote", json={"status": "duplicado"}, headers=H).get_json()["total"], 1)
        self.assertEqual({p["nome"] for p in db.listar_pre_cadastros()}, {"D"})


if __name__ == "__main__":
    unittest.main()
