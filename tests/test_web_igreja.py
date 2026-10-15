import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from banco import database as db
from banco.database import buscar_configuracoes_igreja
from web import igreja as web_igreja
from web.servidor import criar_app

CABECALHO = {"X-SIGM": "1"}


def png(tamanho=(300, 200), cor=(10, 90, 200, 255)):
    saida = io.BytesIO()
    Image.new("RGBA", tamanho, cor).save(saida, "PNG")
    return saida.getvalue()


class TesteWebIgreja(unittest.TestCase):
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
        self.cliente = self.app.test_client()
        with self.cliente.session_transaction() as sessao:
            sessao["usuario"] = {"id_usuario": 1, "nome": "Teste", "login": "teste",
                                 "perfil": "Administrador", "status": "Ativo"}

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.pasta.cleanup()

    def salvar(self, **extra):
        dados = {"nome_igreja": "Igreja Teste", "ministerio": "Ministério X",
                 "cidade": "Santos", "estado": "sp"}
        dados.update(extra)
        return self.cliente.put("/api/igreja", json=dados, headers=CABECALHO)

    def enviar(self, tipo, conteudo, nome="a.png"):
        return self.cliente.post(f"/api/igreja/imagem/{tipo}", headers=CABECALHO,
                                 data={"arquivo": (io.BytesIO(conteudo), nome)},
                                 content_type="multipart/form-data")

    def test_exige_login_e_cabecalho(self):
        anonimo = self.app.test_client()
        self.assertEqual(anonimo.get("/api/igreja").status_code, 401)
        self.assertEqual(anonimo.get("/igreja").status_code, 302)
        self.assertEqual(self.cliente.put("/api/igreja", json={}).status_code, 403)

    def test_pagina_abre_com_abas_e_sem_secretarios(self):
        r = self.cliente.get("/igreja")
        self.assertEqual(r.status_code, 200)
        texto = r.data.decode()
        for aba in ("Identificação", "Liderança", "Contatos", "Congregação Local",
                    "Endereço", "Identidade visual", "Sistema"):
            self.assertIn(aba, texto)
        self.assertNotIn('name="primeiro_secretario"', texto)
        self.assertIn('href="/igreja"', texto)

    def test_salvar_normaliza_e_grava_no_banco_do_desktop(self):
        r = self.salvar(cep="11000100", congregacao_local_nome="Filial Centro",
                        congregacao_local_dirigente="Pr. João", congregacao_local_cep="11010-000")
        self.assertTrue(r.get_json()["ok"], r.get_json())
        dados = buscar_configuracoes_igreja()
        self.assertEqual(dados["estado"], "SP")
        self.assertEqual(dados["cep"], "11000-100")
        self.assertEqual(dados["congregacao_local_nome"], "Filial Centro")
        lido = self.cliente.get("/api/igreja").get_json()["campos"]
        self.assertEqual(lido["congregacao_local_dirigente"], "Pr. João")

    def test_obrigatorios_e_cep_invalido(self):
        r = self.cliente.put("/api/igreja", json={"nome_igreja": "X"}, headers=CABECALHO)
        self.assertEqual(r.status_code, 400)
        self.assertIn("obrigatórios", r.get_json()["mensagem"])
        self.assertEqual(self.salvar(cep="123").status_code, 400)

    def test_salvar_parcial_preserva_o_resto_e_secretarios_antigos(self):
        base = buscar_configuracoes_igreja()
        db.salvar_configuracoes_igreja({**base, "nome_igreja": "A", "ministerio": "M",
                                        "cidade": "C", "estado": "SP"})
        # Secretarios antigos (coluna legada) devem sobreviver a qualquer salvamento da web.
        con = db.conectar()
        try:
            colunas = [c[1] for c in con.execute("PRAGMA table_info(configuracoes_igreja)")]
            if "primeiro_secretario" in colunas:
                con.execute("UPDATE configuracoes_igreja SET primeiro_secretario = 'Antigo' WHERE id = 1")
                con.commit()
        finally:
            con.close()
        r = self.cliente.put("/api/igreja", json={"telefone": "(13) 3333-0000"}, headers=CABECALHO)
        self.assertTrue(r.get_json()["ok"])
        dados = buscar_configuracoes_igreja()
        self.assertEqual(dados["nome_igreja"], "A")
        self.assertEqual(dados["telefone"], "(13) 3333-0000")
        if "primeiro_secretario" in colunas:
            con = db.conectar()
            try:
                antigo = con.execute("SELECT primeiro_secretario FROM configuracoes_igreja WHERE id = 1").fetchone()[0]
            finally:
                con.close()
            self.assertEqual(antigo, "Antigo")

    def test_auditoria_registra_grupos(self):
        with mock.patch.object(web_igreja, "registrar_acao") as registro:
            self.salvar(telefone="1", congregacao_local_nome="L")
        acoes = [c.args[0] for c in registro.call_args_list]
        self.assertIn("CONFIGURACOES_IGREJA_ALTERADAS", acoes)
        self.assertIn("CONTATOS_IGREJA_ALTERADOS", acoes)
        self.assertIn("DADOS_CONGREGACAO_LOCAL_ALTERADOS", acoes)
        with mock.patch.object(web_igreja, "registrar_acao") as registro:
            self.salvar(telefone="1", congregacao_local_nome="L")
        registro.assert_not_called()

    def test_logo_enviar_servir_e_remover(self):
        r = self.enviar("logotipo", png())
        self.assertTrue(r.get_json()["ok"], r.get_json())
        caminho = Path(buscar_configuracoes_igreja()["logotipo"])
        self.assertTrue(caminho.is_file())
        self.assertEqual(caminho.parent.name, "imagens_igreja")
        # logo publica (login) e privada
        publico = self.app.test_client().get("/igreja/logo")
        self.assertEqual(publico.status_code, 200)
        self.assertEqual(Image.open(io.BytesIO(publico.data)).format, "PNG")
        publico.close()
        self.assertIn("/igreja/logo?v=", self.cliente.get("/membros").data.decode())
        self.assertIn("/igreja/logo?v=", self.app.test_client().get("/login").data.decode())

        r = self.cliente.delete("/api/igreja/imagem/logotipo", headers=CABECALHO)
        self.assertTrue(r.get_json()["ok"])
        self.assertEqual(buscar_configuracoes_igreja()["logotipo"], "")
        self.assertFalse(caminho.exists())

    def test_carimbo_e_assinatura_exigem_login(self):
        self.enviar("carimbo", png())
        self.enviar("assinatura_pastor", png((400, 100)))
        resposta = self.cliente.get("/igreja/imagem/carimbo")
        self.assertEqual(resposta.status_code, 200)
        resposta.close()
        anonimo = self.app.test_client()
        self.assertIn(anonimo.get("/igreja/imagem/carimbo").status_code, (302, 401))
        self.assertIn(anonimo.get("/igreja/imagem/assinatura_pastor").status_code, (302, 401))
        info = self.cliente.get("/api/igreja").get_json()["imagens"]
        self.assertTrue(info["carimbo"]["tem"])

    def test_imagem_invalida_ou_tipo_desconhecido(self):
        r = self.enviar("logotipo", b"nao e imagem")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.enviar("outro", png()).status_code, 404)
        self.assertEqual(self.cliente.post("/api/igreja/imagem/logotipo", headers=CABECALHO,
                                           data={}, content_type="multipart/form-data").status_code, 400)

    def test_remover_nao_apaga_arquivo_fora_da_pasta_da_igreja(self):
        externo = Path(self.pasta.name) / "meu_logo.png"
        externo.write_bytes(png())
        base = buscar_configuracoes_igreja()
        db.salvar_configuracoes_igreja({**base, "logotipo": str(externo)})
        self.cliente.delete("/api/igreja/imagem/logotipo", headers=CABECALHO)
        self.assertTrue(externo.exists())
        self.assertEqual(buscar_configuracoes_igreja()["logotipo"], "")


if __name__ == "__main__":
    unittest.main()
