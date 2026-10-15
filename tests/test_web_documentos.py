import importlib
import os
import sys
import tempfile
import types
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from banco import database as db


def _instalar_stubs_de_interface():
    """Em computadores sem tkinter/customtkinter/fitz (ex.: servidor de testes)
    cria modulos de mentira so para os editores desktop poderem ser importados."""
    for nome in ("tkinter", "customtkinter", "fitz"):
        try:
            importlib.import_module(nome)
            continue
        except ImportError:
            pass
        modulo = types.ModuleType(nome)
        cache = {}

        def __getattr__(atributo, _cache=cache):
            if atributo.startswith("__"):
                raise AttributeError(atributo)
            return _cache.setdefault(atributo, type(atributo, (), {"__init__": lambda *a, **k: None}))

        modulo.__getattr__ = __getattr__
        sys.modules[nome] = modulo


_instalar_stubs_de_interface()

from documentos import gerar_documentos as gd  # noqa: E402
from documentos import integrador_documentos as integrador  # noqa: E402
from web import documentos_web  # noqa: E402
from web import membros as web_membros  # noqa: E402
from web.servidor import criar_app  # noqa: E402

H = {"X-SIGM": "1"}
PDF_FALSO = b"%PDF-1.4\n%falso\n"


class TesteWebDocumentos(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        base = Path(self.pasta.name)
        (base / "fotos_membros").mkdir()
        self.patches = [
            mock.patch.dict(os.environ, {"SIGM_DADOS_DIR": str(base)}),
            mock.patch.object(db, "BANCO", base / "sigm.db"),
            mock.patch.object(web_membros, "PASTA_FOTOS_MEMBROS", base / "fotos_membros"),
            mock.patch.object(integrador, "PASTA_FOTOS_MEMBROS", base / "fotos_membros"),
        ]
        for p in self.patches:
            p.start()
        db.criar_tabelas()
        self.app = criar_app()
        self.app.config["TESTING"] = True
        self.c = self.app.test_client()
        with self.c.session_transaction() as s:
            s["usuario"] = {"id_usuario": 1, "nome": "Secretário", "login": "sec",
                            "perfil": "Administrador", "status": "Ativo"}
        r = self.c.post("/api/membros", headers=H, json={
            "nome": "Maria da Silva", "cpf": "12345678909", "cargo": "Diácono",
            "cidade": "Santos", "estado": "SP", "observacoes": "Obs do cadastro"})
        self.id = r.get_json()["id"]

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.pasta.cleanup()

    def gerador_falso(self, capturas):
        def falso(modelo_pdf, caminho_saida, dados, mapeamento):
            capturas.append({"modelo": modelo_pdf, "dados": dict(dados), "mapeamento": mapeamento})
            Path(caminho_saida).write_bytes(PDF_FALSO)
            return str(caminho_saida)
        return falso

    # ------------------------------------------------------------- acesso
    def test_exige_login(self):
        anon = self.app.test_client()
        for caminho in (f"/api/membros/{self.id}/documentos", "/api/documentos-emitidos/1/arquivo"):
            self.assertEqual(anon.get(caminho).status_code, 401)
        r = anon.post(f"/api/membros/{self.id}/documentos/carta-recomendacao", headers=H, json={})
        self.assertEqual(r.status_code, 401)

    def test_catalogo_e_historico_vazio(self):
        d = self.c.get(f"/api/membros/{self.id}/documentos").get_json()
        self.assertEqual([i["slug"] for i in d["catalogo"]],
                         ["ficha-cadastral", "membramento", "reconciliacao", "carta-recomendacao"])
        self.assertEqual(d["historico"], [])
        self.assertEqual(self.c.get("/api/membros/999/documentos").status_code, 404)

    # ------------------------------------------------------ formulario
    def test_formulario_membramento_tem_campos_do_desktop(self):
        d = self.c.get(f"/api/membros/{self.id}/documentos/membramento/formulario").get_json()
        nomes = [c["nome"] for c in d["campos"]]
        self.assertEqual(nomes, ["igreja_origem", "cidade_origem", "estado_origem",
                                 "trouxe_carta", "trouxe_familia", "observacoes"])
        self.assertEqual(next(c for c in d["campos"] if c["nome"] == "observacoes")["valor"], "Obs do cadastro")
        self.assertTrue(d["data"]["usar_atual"])
        rotulos = [a["rotulo"] for a in d["automaticos"]]
        self.assertIn("Nome do membro", rotulos)
        self.assertEqual(next(a for a in d["automaticos"] if a["rotulo"] == "Nome do membro")["valor"], "Maria da Silva")

    def test_formulario_reconciliacao_e_carta(self):
        d = self.c.get(f"/api/membros/{self.id}/documentos/reconciliacao/formulario").get_json()
        self.assertEqual([c["nome"] for c in d["campos"]], ["observacoes"])
        d = self.c.get(f"/api/membros/{self.id}/documentos/carta-recomendacao/formulario").get_json()
        self.assertEqual([c["nome"] for c in d["campos"]],
                         ["nome_membro", "cargo", "sexo", "setor_campo", "congregacao", "apresentar_em"])
        self.assertEqual(d["campos"][0]["valor"], "Maria da Silva")
        self.assertEqual(self.c.get(f"/api/membros/{self.id}/documentos/xx/formulario").status_code, 404)

    # --------------------------------------------------------- geracao
    def test_gerar_membramento_monta_os_dados_como_o_editor(self):
        capturas = []
        with mock.patch("documentos.renderizador_pdf.gerar_pdf_final", self.gerador_falso(capturas)):
            r = self.c.post(f"/api/membros/{self.id}/documentos/membramento", headers=H, json={
                "igreja_origem": "AD Centro", "cidade_origem": "Santos", "estado_origem": "SP",
                "trouxe_carta": "sim", "trouxe_familia": "nao", "observacoes": "Veio com carta",
                "usar_data_atual": False, "data_documento": "05/03/2026"})
        j = r.get_json()
        self.assertTrue(j["ok"], j)
        d = capturas[0]["dados"]
        self.assertEqual(d["nome_membro"], "Maria da Silva")
        self.assertEqual(d["igreja_origem"], "AD Centro")
        self.assertEqual(d["trouxe_carta"], "Sim")
        self.assertTrue(d["trouxe_carta_sim"])
        self.assertFalse(d["trouxe_carta_nao"])
        self.assertEqual(d["trouxe_familia"], "Nao")
        self.assertTrue(d["trouxe_familia_nao"])
        self.assertEqual(d["observacoes"], "Veio com carta")
        self.assertEqual((d["local_dia"], d["local_mes"], d["local_ano"]), ("05", "marco", "2026"))
        self.assertEqual(d["data_documento"], "05/03/2026")
        self.assertTrue(d["data_documento_extenso"].endswith("05 de marco de 2026"))
        self.assertTrue(capturas[0]["mapeamento"]["campos"])
        self.assertTrue(str(capturas[0]["modelo"]).endswith("pedido_membramento.pdf"))

        # registrou no historico e o arquivo abre
        hist = self.c.get(f"/api/membros/{self.id}/documentos").get_json()["historico"]
        self.assertEqual(len(hist), 1)
        self.assertTrue(hist[0]["disponivel"])
        self.assertEqual(hist[0]["usuario"], "Secretário")
        arq = self.c.get(j["url"])
        self.assertEqual(arq.status_code, 200)
        self.assertEqual(arq.mimetype, "application/pdf")
        self.assertEqual(arq.data, PDF_FALSO)
        arq.close()

    def test_gerar_reconciliacao_usa_data_atual(self):
        capturas = []
        with mock.patch("documentos.renderizador_pdf.gerar_pdf_final", self.gerador_falso(capturas)):
            r = self.c.post(f"/api/membros/{self.id}/documentos/reconciliacao", headers=H,
                            json={"observacoes": "Retornou", "usar_data_atual": True})
        self.assertTrue(r.get_json()["ok"])
        d = capturas[0]["dados"]
        self.assertEqual(d["local_ano"], str(date.today().year))
        self.assertEqual(d["observacoes"], "Retornou")
        self.assertTrue(str(capturas[0]["modelo"]).endswith("pedido_reconciliacao.pdf"))
        self.assertNotIn("trouxe_carta", d)

    def test_data_invalida_e_recusada(self):
        for valor in ("31/31/2026", "abc", ""):
            r = self.c.post(f"/api/membros/{self.id}/documentos/reconciliacao", headers=H,
                            json={"usar_data_atual": False, "data_documento": valor})
            self.assertEqual(r.status_code, 400, valor)
            self.assertIn("Data", r.get_json()["mensagem"])
        self.assertEqual(self.c.get(f"/api/membros/{self.id}/documentos").get_json()["historico"], [])

    def test_gerar_ficha_usa_o_mesmo_caminho_do_botao_final(self):
        chamadas = []
        base = Path(self.pasta.name)

        def preencher(tipo, id_membro):
            chamadas.append(("preencher", tipo, id_membro))
            arquivo = base / "ficha_editavel.pdf"
            arquivo.write_bytes(PDF_FALSO)
            return str(arquivo)

        def final(caminho):
            chamadas.append(("final", caminho))
            novo = base / "ficha_FINAL.pdf"
            novo.write_bytes(PDF_FALSO)
            return str(novo)

        def foto(caminho, id_membro):
            chamadas.append(("foto", caminho, id_membro))
            return True

        with mock.patch.object(gd, "preencher_copia_pdf_editavel_com_membro", preencher), \
                mock.patch.object(gd, "gerar_pdf_final", final), \
                mock.patch.object(gd, "inserir_foto_ficha_cadastral", foto):
            r = self.c.post(f"/api/membros/{self.id}/documentos/ficha-cadastral", headers=H, json={})
        self.assertTrue(r.get_json()["ok"], r.get_json())
        self.assertEqual([c[0] for c in chamadas], ["preencher", "final", "foto"])
        self.assertEqual(chamadas[0][1:], ("Ficha Cadastral", self.id))
        hist = self.c.get(f"/api/membros/{self.id}/documentos").get_json()["historico"]
        self.assertEqual(hist[0]["titulo"], "Ficha Cadastral")

    def test_ficha_segue_sem_foto_se_a_foto_falhar(self):
        base = Path(self.pasta.name)

        def preencher(tipo, id_membro):
            (base / "e.pdf").write_bytes(PDF_FALSO)
            return str(base / "e.pdf")

        def final(caminho):
            (base / "f.pdf").write_bytes(PDF_FALSO)
            return str(base / "f.pdf")

        with mock.patch.object(gd, "preencher_copia_pdf_editavel_com_membro", preencher), \
                mock.patch.object(gd, "gerar_pdf_final", final), \
                mock.patch.object(gd, "inserir_foto_ficha_cadastral", side_effect=RuntimeError("foto ruim")):
            r = self.c.post(f"/api/membros/{self.id}/documentos/ficha-cadastral", headers=H, json={})
        self.assertTrue(r.get_json()["ok"])

    def test_gerar_carta_com_campos_editados(self):
        capturas = []

        def falso(tipo, dados, igreja=None, apresentar_em=""):
            capturas.append((tipo, dict(dados), apresentar_em))
            arquivo = Path(self.pasta.name) / "carta.pdf"
            arquivo.write_bytes(PDF_FALSO)
            return arquivo

        with mock.patch.object(gd, "gerar_pdf_documento", falso):
            r = self.c.post(f"/api/membros/{self.id}/documentos/carta-recomendacao", headers=H, json={
                "nome_membro": "", "cargo": "Evangelista", "sexo": "Feminino",
                "setor_campo": "12", "congregacao": "", "apresentar_em": "AD Belém"})
        self.assertTrue(r.get_json()["ok"], r.get_json())
        tipo, dados, apresentar = capturas[0]
        self.assertEqual(tipo, "Carta de Recomendação")
        self.assertEqual(dados["nome_membro"], "Maria da Silva")  # vazio nao apaga
        self.assertEqual(dados["cargo"], "Evangelista")
        self.assertEqual(dados["sexo"], "Feminino")
        self.assertEqual(dados["setor_campo"], "12")
        self.assertEqual(apresentar, "AD Belém")

    def test_falha_do_gerador_vira_mensagem_e_nao_registra(self):
        with mock.patch("documentos.renderizador_pdf.gerar_pdf_final", side_effect=FileNotFoundError("modelo sumiu")):
            r = self.c.post(f"/api/membros/{self.id}/documentos/membramento", headers=H, json={})
        self.assertEqual(r.status_code, 500)
        self.assertIn("modelo sumiu", r.get_json()["mensagem"])
        self.assertEqual(self.c.get(f"/api/membros/{self.id}/documentos").get_json()["historico"], [])

    def test_titulos_aparecem_com_acento_sem_mudar_o_banco(self):
        capturas = []
        with mock.patch("documentos.renderizador_pdf.gerar_pdf_final", self.gerador_falso(capturas)):
            self.c.post(f"/api/membros/{self.id}/documentos/reconciliacao", headers=H, json={})
            self.c.post(f"/api/membros/{self.id}/documentos/membramento", headers=H, json={})
        titulos = [h["titulo"] for h in self.c.get(f"/api/membros/{self.id}/documentos").get_json()["historico"]]
        self.assertIn("Pedido para Reconciliação", titulos)
        self.assertIn("Pedido para Apresentação / Membramento", titulos)
        self.assertEqual(documentos_web.acentuar("Numero da Congregacao"), "Número da Congregação")
        rel = self.c.get("/api/relatorios/documentos-emitidos").get_json()
        self.assertIn("Pedido para Reconciliação", [l[0] for l in rel["linhas"]])
        f = self.c.get(f"/api/membros/{self.id}/documentos/membramento/formulario").get_json()
        rotulos = [a["rotulo"] for a in f["automaticos"]]
        self.assertIn("Congregação", rotulos)
        self.assertIn("Número da Congregação", rotulos)

    def test_documento_e_membro_inexistentes(self):
        self.assertEqual(self.c.post(f"/api/membros/{self.id}/documentos/xx", headers=H, json={}).status_code, 404)
        self.assertEqual(self.c.post("/api/membros/999/documentos/membramento", headers=H, json={}).status_code, 404)
        self.assertEqual(self.c.get("/api/documentos-emitidos/999/arquivo").status_code, 404)

    def test_arquivo_sumido_nao_e_servido(self):
        capturas = []
        with mock.patch("documentos.renderizador_pdf.gerar_pdf_final", self.gerador_falso(capturas)):
            j = self.c.post(f"/api/membros/{self.id}/documentos/reconciliacao", headers=H, json={}).get_json()
        Path(capturas[0]["dados"] and next(Path(self.pasta.name, "documentos_gerados").glob("*.pdf"))).unlink()
        self.assertEqual(self.c.get(j["url"]).status_code, 404)
        hist = self.c.get(f"/api/membros/{self.id}/documentos").get_json()["historico"]
        self.assertFalse(hist[0]["disponivel"])


if __name__ == "__main__":
    unittest.main()
