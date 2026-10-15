import io
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from banco import database as db
from web import relatorios as rel
from web.servidor import criar_app

H = {"X-SIGM": "1"}


class TesteWebRelatorios(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        base = Path(self.pasta.name)
        self.patches = [
            mock.patch.dict(os.environ, {"SIGM_DADOS_DIR": str(base)}),
            mock.patch.object(db, "BANCO", base / "sigm.db"),
        ]
        for p in self.patches:
            p.start()
        db.criar_tabelas()
        self.app = criar_app()
        self.app.config["TESTING"] = True
        self.c = self.app.test_client()
        with self.c.session_transaction() as s:
            s["usuario"] = {"id_usuario": 1, "nome": "T", "login": "t", "perfil": "Administrador", "status": "Ativo"}
        hoje = date.today()
        self.membro("Ana Paula", "Membro", f"{hoje.day:02d}/{hoje.month:02d}/1990", "(11) 91111-1111")
        self.membro("Bruno Costa", "Visitante", f"05/{hoje.month:02d}/1985", "")
        outro = 1 if hoje.month != 1 else 2
        self.membro("Carla Dias", "Congregado", f"10/{outro:02d}/2000", "(11) 93333-3333")
        self.membro("Sem Data", "Membro", "", "")

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.pasta.cleanup()

    def membro(self, nome, status, nasc, celular):
        dados = {k: "" for k in ("rg orgao_emissor cpf estado_civil profissao telefone email endereco numero bairro cidade estado "
                                  "batismo_aguas ministerio cargo observacoes").split()}
        dados.update(nome=nome, status=status, data_nascimento=nasc, celular=celular)
        db.cadastrar_membro(dados)

    def test_exige_login(self):
        anon = self.app.test_client()
        for caminho in ("/api/aniversariantes", "/api/relatorios/todos", "/aniversariantes", "/relatorios"):
            self.assertIn(anon.get(caminho).status_code, (302, 401), caminho)

    def test_paginas_abrem_e_menu_completo(self):
        for caminho in ("/aniversariantes", "/relatorios", "/membros", "/pre-cadastros"):
            r = self.c.get(caminho)
            self.assertEqual(r.status_code, 200, caminho)
            for destino in (b'href="/aniversariantes"', b'href="/relatorios"'):
                self.assertIn(destino, r.data)

    def test_aniversariantes_do_mes_atual(self):
        d = self.c.get("/api/aniversariantes").get_json()
        nomes = [i["nome"] for i in d["itens"]]
        self.assertEqual(nomes, sorted(nomes, key=lambda n: ({"Ana Paula": date.today().day, "Bruno Costa": 5}[n], n)))
        self.assertEqual(set(nomes), {"Ana Paula", "Bruno Costa"})
        self.assertEqual(d["total_hoje"], 1)
        self.assertEqual(d["total_mes"], 2)
        ana = next(i for i in d["itens"] if i["nome"] == "Ana Paula")
        self.assertTrue(ana["hoje"])
        self.assertEqual(ana["idade"], date.today().year - 1990)

    def test_aniversariantes_busca_e_mes_invalido(self):
        d = self.c.get("/api/aniversariantes?q=ana").get_json()
        self.assertEqual([i["nome"] for i in d["itens"]], ["Ana Paula"])
        d = self.c.get("/api/aniversariantes?q=91111").get_json()
        self.assertEqual([i["nome"] for i in d["itens"]], ["Ana Paula"])
        d = self.c.get("/api/aniversariantes?mes=99").get_json()
        self.assertEqual(d["mes"], date.today().month)
        d = self.c.get("/api/aniversariantes?mes=abc").get_json()
        self.assertEqual(d["mes"], date.today().month)

    def test_relatorios_tipos(self):
        casos = {"todos": 4, "membros-ativos": 2, "congregados": 1, "visitantes": 1,
                 "aniversariantes-mes": 2, "documentos-emitidos": 0, "arquivos-anexados": 0}
        for slug, total in casos.items():
            d = self.c.get(f"/api/relatorios/{slug}").get_json()
            self.assertEqual(d["total"], total, slug)
            self.assertTrue(d["colunas"])
        self.assertEqual(self.c.get("/api/relatorios/inexistente").status_code, 404)
        todos = self.c.get("/api/relatorios/todos").get_json()
        self.assertEqual([l[1] for l in todos["linhas"]], ["Ana Paula", "Bruno Costa", "Carla Dias", "Sem Data"])

    def test_exportar_pdf_csv_xlsx(self):
        r = self.c.get("/api/relatorios/todos/exportar?formato=pdf")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.startswith(b"%PDF"))
        self.assertIn("attachment", r.headers["Content-Disposition"])
        r = self.c.get("/api/relatorios/todos/exportar?formato=csv")
        texto = r.data.decode("utf-8-sig")
        self.assertIn("ID;Nome;Status", texto)
        self.assertIn("Ana Paula", texto)
        r = self.c.get("/api/relatorios/todos/exportar?formato=xlsx")
        self.assertEqual(r.status_code, 200)
        if r.headers["X-SIGM-Formato"] == "xlsx":
            self.assertTrue(r.data.startswith(b"PK"))
        else:
            self.assertIn("Ana Paula", r.data.decode("utf-8-sig"))
        self.assertEqual(self.c.get("/api/relatorios/todos/exportar?formato=zip").status_code, 404)
        self.assertEqual(self.c.get("/api/relatorios/xx/exportar").status_code, 404)

    def test_pdf_vazio_e_caracteres_especiais(self):
        arquivo = rel.gerar_pdf("Teste <&>", "Igreja & Cia", ["A", "B"], [])
        self.assertTrue(arquivo.read().startswith(b"%PDF"))
        arquivo = rel.gerar_pdf("T", "", ["A", "B"], [["<b>x</b> & y", None]] * 120)
        self.assertTrue(arquivo.read().startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
