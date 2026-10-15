import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from banco import database as db
from banco.database import listar_arquivos_membro

H = {"X-SIGM": "1"}
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"


def png():
    saida = io.BytesIO()
    Image.new("RGB", (20, 20), (1, 2, 3)).save(saida, "PNG")
    return saida.getvalue()


class TesteArquivosMembro(unittest.TestCase):
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
        self.c = self.app.test_client()
        with self.c.session_transaction() as s:
            s["usuario"] = {"id_usuario": 1, "nome": "Teste", "login": "t",
                            "perfil": "Administrador", "status": "Ativo"}
        self.membro = self.c.post("/api/membros", json={"nome": "Ana Lima"}, headers=H).get_json()["id"]

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.pasta.cleanup()

    def anexar(self, conteudo=PDF, nome="rg.pdf", tipo="RG", titulo="RG da Ana", membro=None, **extra):
        dados = {"arquivo": (io.BytesIO(conteudo), nome), "tipo": tipo, "titulo": titulo}
        dados.update(extra)
        return self.c.post(f"/api/membros/{membro or self.membro}/arquivos", headers=H, data=dados,
                           content_type="multipart/form-data")

    def test_login_exigido(self):
        anon = self.app.test_client()
        self.assertEqual(anon.get(f"/api/membros/{self.membro}/arquivos").status_code, 401)
        self.assertEqual(anon.get("/api/arquivos-membro/1/arquivo").status_code, 401)
        self.assertEqual(self.c.post(f"/api/membros/{self.membro}/arquivos").status_code, 403)

    def test_anexar_listar_e_baixar_na_pasta_do_desktop(self):
        r = self.anexar(observacao="frente e verso")
        self.assertTrue(r.get_json()["ok"], r.get_json())
        registro = listar_arquivos_membro(self.membro)[0]
        caminho = Path(registro["caminho_arquivo"])
        self.assertTrue(caminho.is_file())
        self.assertIn(f"membro_{self.membro:06d}", str(caminho))
        self.assertEqual(caminho.parent.name, "documentos")
        self.assertEqual(registro["usuario_responsavel"], "Teste")
        itens = self.c.get(f"/api/membros/{self.membro}/arquivos").get_json()["itens"]
        self.assertEqual(itens[0]["titulo"], "RG da Ana")
        self.assertTrue(itens[0]["disponivel"])
        self.assertNotIn("caminho_arquivo", itens[0])
        resposta = self.c.get(f"/api/arquivos-membro/{itens[0]['id']}/arquivo")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.mimetype, "application/pdf")
        resposta.close()

    def test_imagem_vai_para_pasta_imagens_e_tipo_com_acento(self):
        r = self.anexar(png(), "foto.PNG", "Certidao de Batismo", "Batismo")
        self.assertTrue(r.get_json()["ok"])
        registro = listar_arquivos_membro(self.membro)[0]
        self.assertEqual(Path(registro["caminho_arquivo"]).parent.name, "imagens")
        item = self.c.get(f"/api/membros/{self.membro}/arquivos").get_json()["itens"][0]
        self.assertEqual(item["tipo_rotulo"], "Certidão de Batismo")
        self.assertTrue(item["eh_imagem"])

    def test_validacoes(self):
        self.assertEqual(self.anexar(b"MZ...", "virus.exe").status_code, 400)
        self.assertEqual(self.anexar(b"nao e pdf", "falso.pdf").status_code, 400)
        self.assertEqual(self.anexar(b"", "vazio.pdf").status_code, 400)
        self.assertEqual(self.anexar(tipo="Qualquer").status_code, 400)
        self.assertEqual(self.anexar(titulo="  ").status_code, 400)
        self.assertEqual(self.anexar(membro=999).status_code, 404)
        self.assertEqual(listar_arquivos_membro(self.membro), [])

    def test_renomear(self):
        self.anexar()
        id_ = listar_arquivos_membro(self.membro)[0]["id"]
        r = self.c.put(f"/api/arquivos-membro/{id_}", json={"titulo": "Novo"}, headers=H)
        self.assertTrue(r.get_json()["ok"])
        self.assertEqual(listar_arquivos_membro(self.membro)[0]["titulo"], "Novo")
        self.assertEqual(self.c.put(f"/api/arquivos-membro/{id_}", json={"titulo": " "}, headers=H).status_code, 400)

    def test_excluir_com_e_sem_arquivo_fisico(self):
        self.anexar(titulo="A")
        self.anexar(titulo="B")
        a, b = listar_arquivos_membro(self.membro)
        r = self.c.post(f"/api/arquivos-membro/{a['id']}/excluir", json={"fisico": True}, headers=H)
        self.assertTrue(r.get_json()["arquivo_apagado"])
        self.assertFalse(Path(a["caminho_arquivo"]).exists())
        r = self.c.post(f"/api/arquivos-membro/{b['id']}/excluir", json={}, headers=H)
        self.assertFalse(r.get_json()["arquivo_apagado"])
        self.assertTrue(Path(b["caminho_arquivo"]).exists())
        self.assertEqual(listar_arquivos_membro(self.membro), [])

    def test_nao_serve_nem_apaga_arquivo_fora_da_pasta(self):
        externo = self.base / "segredo.pdf"
        externo.write_bytes(PDF)
        id_ = db.registrar_arquivo_membro(self.membro, "RG", "Externo", "segredo.pdf", str(externo))
        self.assertEqual(self.c.get(f"/api/arquivos-membro/{id_}/arquivo").status_code, 404)
        item = self.c.get(f"/api/membros/{self.membro}/arquivos").get_json()["itens"][0]
        self.assertFalse(item["disponivel"])
        self.c.post(f"/api/arquivos-membro/{id_}/excluir", json={"fisico": True}, headers=H)
        self.assertTrue(externo.exists())


if __name__ == "__main__":
    unittest.main()
