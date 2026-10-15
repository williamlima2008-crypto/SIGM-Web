import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from banco import database as db
from documentos import integrador_documentos as integrador
from web import membros as web_membros
from web.servidor import criar_app

CABECALHO = {"X-SIGM": "1"}


def imagem_bytes(formato="PNG", tamanho=(300, 400), cor=(200, 30, 30), modo="RGB"):
    saida = io.BytesIO()
    Image.new(modo, tamanho, cor).save(saida, formato)
    return saida.getvalue()


class TesteWebMembros(unittest.TestCase):
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
        self.cliente = self.app.test_client()
        with self.cliente.session_transaction() as sessao:
            sessao["usuario"] = {
                "id_usuario": 1, "nome": "Teste", "login": "teste",
                "perfil": "Administrador", "status": "Ativo",
            }

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.pasta.cleanup()

    def cadastrar(self, **extra):
        dados = {"nome": "Maria da Silva", "cpf": "12345678909", "celular": "(11) 99999-0000",
                 "cidade": "Santos", "status": "Membro", "data_nascimento": "10/05/1990"}
        dados.update(extra)
        r = self.cliente.post("/api/membros", json=dados, headers=CABECALHO)
        self.assertEqual(r.status_code, 200, r.get_json())
        return r.get_json()["id"]

    # ------------------------------------------------------------ acesso
    def test_exige_login(self):
        anonimo = self.app.test_client()
        self.assertEqual(anonimo.get("/api/membros").status_code, 401)
        self.assertEqual(anonimo.get("/membros").status_code, 302)

    def test_escrita_exige_cabecalho(self):
        r = self.cliente.post("/api/membros", json={"nome": "X"})
        self.assertEqual(r.status_code, 403)

    def test_paginas_abrem(self):
        for caminho in ("/membros", "/pre-cadastros"):
            r = self.cliente.get(caminho)
            self.assertEqual(r.status_code, 200)
            self.assertIn(b'href="/membros"', r.data)
        self.assertEqual(self.cliente.get("/").status_code, 302)

    # ------------------------------------------------------------- CRUD
    def test_cadastrar_e_abrir_ficha(self):
        id_membro = self.cadastrar(rg="426526458", cep="11000100", cargo="diacono",
                                   data_funcao="01/02/2020")
        r = self.cliente.get(f"/api/membros/{id_membro}")
        campos = r.get_json()["campos"]
        self.assertEqual(campos["nome"], "Maria da Silva")
        self.assertEqual(campos["cpf"], "123.456.789-09")
        self.assertEqual(campos["rg"], "42.652.645-8")
        self.assertEqual(campos["cep"], "11000-100")
        self.assertEqual(campos["cargo"], "Diácono")
        self.assertEqual(campos["data_funcao"], "01/02/2020")
        self.assertFalse(r.get_json()["tem_foto"])

    def test_validacoes_iguais_ao_desktop(self):
        casos = [
            ({"nome": ""}, "Nome"),
            ({"nome": "A", "cep": "123"}, "CEP"),
            ({"nome": "A", "data_funcao": "31/31/2020"}, "função"),
            ({"nome": "A", "data_nascimento_conjuge": "abc"}, "cônjuge"),
            ({"nome": "A", "data_batismo_espirito_santo": "99/99/9999"}, "Espírito"),
        ]
        for dados, trecho in casos:
            r = self.cliente.post("/api/membros", json=dados, headers=CABECALHO)
            self.assertEqual(r.status_code, 400, dados)
            self.assertIn(trecho, r.get_json()["mensagem"])

    def test_editar_mantem_campos_nao_enviados(self):
        id_membro = self.cadastrar(email="m@x.com")
        r = self.cliente.put(f"/api/membros/{id_membro}", json={"cidade": "Campinas"},
                             headers=CABECALHO)
        self.assertEqual(r.status_code, 200, r.get_json())
        campos = self.cliente.get(f"/api/membros/{id_membro}").get_json()["campos"]
        self.assertEqual(campos["cidade"], "Campinas")
        self.assertEqual(campos["email"], "m@x.com")
        self.assertEqual(campos["nome"], "Maria da Silva")

    def test_editar_inexistente_da_404(self):
        r = self.cliente.put("/api/membros/999", json={"nome": "X"}, headers=CABECALHO)
        self.assertEqual(r.status_code, 404)

    def test_excluir(self):
        id_membro = self.cadastrar()
        r = self.cliente.post(f"/api/membros/{id_membro}/excluir", json={}, headers=CABECALHO)
        self.assertTrue(r.get_json()["ok"])
        self.assertEqual(self.cliente.get(f"/api/membros/{id_membro}").status_code, 404)

    # ------------------------------------------------------------ lista
    def test_lista_busca_e_filtro(self):
        a = self.cadastrar(nome="José Ângelo", cidade="Santos")
        self.cadastrar(nome="Ana Paula", cpf="98765432100", status="Visitante", cidade="Recife",
                       celular="(81) 98888-7777")
        todos = self.cliente.get("/api/membros").get_json()
        self.assertEqual([i["nome"] for i in todos["itens"]], ["Ana Paula", "José Ângelo"])
        self.assertEqual(todos["contagem"]["todos"], 2)
        self.assertEqual(todos["contagem"]["Visitante"], 1)

        r = self.cliente.get("/api/membros?q=jose angelo").get_json()
        self.assertEqual([i["id"] for i in r["itens"]], [a])
        r = self.cliente.get("/api/membros?q=987.654").get_json()
        self.assertEqual([i["nome"] for i in r["itens"]], ["Ana Paula"])
        r = self.cliente.get("/api/membros?q=88887777").get_json()
        self.assertEqual([i["nome"] for i in r["itens"]], ["Ana Paula"])
        r = self.cliente.get("/api/membros?status=Visitante").get_json()
        self.assertEqual([i["nome"] for i in r["itens"]], ["Ana Paula"])
        self.assertEqual(self.cliente.get("/api/membros?q=zzz").get_json()["itens"], [])
        self.assertNotIn("_busca", todos["itens"][0])

    # ------------------------------------------------------------- foto
    def enviar_foto(self, id_membro, conteudo, nome="foto.png"):
        return self.cliente.post(
            f"/api/membros/{id_membro}/foto", headers=CABECALHO,
            data={"foto": (io.BytesIO(conteudo), nome)},
            content_type="multipart/form-data",
        )

    def test_foto_enviar_exibir_trocar_remover(self):
        id_membro = self.cadastrar()
        self.assertEqual(self.cliente.get(f"/api/membros/{id_membro}/foto").status_code, 404)

        r = self.enviar_foto(id_membro, imagem_bytes("PNG"))
        self.assertTrue(r.get_json()["ok"], r.get_json())
        ficha = self.cliente.get(f"/api/membros/{id_membro}").get_json()
        self.assertTrue(ficha["tem_foto"])
        resposta = self.cliente.get(f"/api/membros/{id_membro}/foto")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(Image.open(io.BytesIO(resposta.data)).format, "JPEG")
        resposta.close()

        # o desktop acha a mesma foto pelo caminho gravado no banco
        caminho = integrador.buscar_caminho_foto_membro(id_membro)
        self.assertTrue(Path(caminho).is_file())
        self.assertEqual(Path(caminho).name, f"foto_{id_membro}.jpg")

        # trocar por outro formato nao deixa arquivo velho para tras
        self.enviar_foto(id_membro, imagem_bytes("WEBP", cor=(0, 0, 200)), "nova.webp")
        arquivos = sorted(p.name for p in (Path(self.pasta.name) / "fotos_membros").iterdir())
        self.assertEqual(arquivos, [f"foto_{id_membro}.jpg"])

        r = self.cliente.delete(f"/api/membros/{id_membro}/foto", headers=CABECALHO)
        self.assertTrue(r.get_json()["ok"])
        self.assertFalse(self.cliente.get(f"/api/membros/{id_membro}").get_json()["tem_foto"])
        self.assertEqual(list((Path(self.pasta.name) / "fotos_membros").iterdir()), [])

    def test_foto_grande_e_reduzida_e_png_transparente_vira_fundo_branco(self):
        id_membro = self.cadastrar()
        self.enviar_foto(id_membro, imagem_bytes("PNG", (4000, 3000)))
        caminho = integrador.buscar_caminho_foto_membro(id_membro)
        with Image.open(caminho) as imagem:
            self.assertLessEqual(max(imagem.size), web_membros.LADO_MAXIMO_FOTO)
        self.enviar_foto(id_membro, imagem_bytes("PNG", (50, 50), (0, 0, 0, 0), "RGBA"))
        with Image.open(integrador.buscar_caminho_foto_membro(id_membro)) as imagem:
            self.assertEqual(imagem.getpixel((10, 10)), (255, 255, 255))

    def test_foto_corrige_rotacao_do_celular(self):
        id_membro = self.cadastrar()
        original = Image.new("RGB", (200, 100), (10, 10, 10))
        exif = Image.Exif()
        exif[0x0112] = 6  # girar 90 graus
        saida = io.BytesIO()
        original.save(saida, "JPEG", exif=exif)
        self.enviar_foto(id_membro, saida.getvalue(), "celular.jpg")
        with Image.open(integrador.buscar_caminho_foto_membro(id_membro)) as imagem:
            self.assertEqual(imagem.size, (100, 200))

    def test_foto_invalida_e_recusada(self):
        id_membro = self.cadastrar()
        r = self.enviar_foto(id_membro, b"isto nao e imagem", "virus.png")
        self.assertEqual(r.status_code, 400)
        self.assertIn("imagem", r.get_json()["mensagem"])
        r = self.cliente.post(f"/api/membros/{id_membro}/foto", headers=CABECALHO,
                              data={}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(self.cliente.get(f"/api/membros/{id_membro}").get_json()["tem_foto"])

    def test_foto_de_membro_inexistente(self):
        self.assertEqual(self.enviar_foto(999, imagem_bytes()).status_code, 404)

    def test_excluir_membro_apaga_a_foto(self):
        id_membro = self.cadastrar()
        self.enviar_foto(id_membro, imagem_bytes())
        self.cliente.post(f"/api/membros/{id_membro}/excluir", json={}, headers=CABECALHO)
        self.assertEqual(list((Path(self.pasta.name) / "fotos_membros").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
