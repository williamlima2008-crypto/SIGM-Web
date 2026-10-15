import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from banco import database as db
from documentos.campos_documentos import FICHA_CADASTRAL
from documentos.integrador_documentos import montar_dados_documento
from telas.cadastro_membro import CadastroMembro
from telas.documentos.base_editor_documento import BaseEditorDocumento
from telas.documentos.editor_ficha_cadastral import EditorFichaCadastral


class TestFichaCadastralBatismos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.banco_original = db.BANCO
        db.BANCO = Path(self.tmp.name) / "sigm_test.db"
        db.criar_tabelas()

    def tearDown(self):
        db.BANCO = self.banco_original
        self.tmp.cleanup()

    def dados_membro(self, **extras):
        dados = {
            "nome": "Membro Teste",
            "rg": "",
            "orgao_emissor": "",
            "cpf": "",
            "data_nascimento": "",
            "cidade_nascimento": "",
            "estado_nascimento": "",
            "estado_civil": "",
            "nome_conjuge": "",
            "data_nascimento_conjuge": "",
            "profissao": "",
            "nome_pai": "",
            "nome_mae": "",
            "grau_instrucao": "",
            "telefone": "",
            "celular": "",
            "email": "",
            "endereco": "",
            "numero": "",
            "bairro": "",
            "cidade": "",
            "estado": "",
            "cep": "",
            "batismo_aguas": "",
            "data_batismo_espirito_santo": "",
            "ministerio": "",
            "cargo": "",
            "data_funcao": "",
            "curso_teologico": "",
            "status": "Membro",
            "observacoes": "",
        }
        dados.update(extras)
        return dados

    def cadastrar(self, **extras):
        return db.cadastrar_membro(self.dados_membro(**extras))

    def adicionar_colunas_opcionais_membro(self, *colunas):
        conexao = db.conectar()
        try:
            cursor = conexao.cursor()
            cursor.execute("PRAGMA table_info(membros)")
            existentes = {str(coluna[1]).lower() for coluna in cursor.fetchall()}
            for coluna in colunas:
                if coluna.lower() not in existentes:
                    cursor.execute(f"ALTER TABLE membros ADD COLUMN {coluna} TEXT")
            conexao.commit()
        finally:
            conexao.close()

    def atualizar_colunas_membro(self, id_membro, **valores):
        conexao = db.conectar()
        try:
            cursor = conexao.cursor()
            atribuicoes = ", ".join(f"{coluna} = ?" for coluna in valores)
            cursor.execute(
                f"UPDATE membros SET {atribuicoes} WHERE id = ?",
                (*valores.values(), id_membro),
            )
            conexao.commit()
        finally:
            conexao.close()

    def test_migracao_adiciona_somente_data_batismo_espirito_santo_no_membro(self):
        colunas = db.obter_colunas_tabela("membros")

        self.assertIn("data_batismo_espirito_santo", colunas)
        self.assertIn("cep", colunas)
        self.assertNotIn("convencao", colunas)
        self.assertNotIn("igreja_local_convencao_evangelista", colunas)
        self.assertNotIn("igreja_local_convencao_pastor", colunas)
        self.assertNotIn("igreja_local_batismo_aguas", colunas)
        self.assertNotIn("igreja_local_batismo_espirito_santo", colunas)

    def test_batismos_continuam_usando_origem_atual(self):
        db.salvar_configuracoes_igreja({
            "nome_igreja": "Igreja Sede",
            "convencao": "CONVENCAO TESTE",
            "congregacao_local_nome": "Congregacao Central",
        })
        id_membro = self.cadastrar()

        dados = montar_dados_documento(id_membro)

        self.assertEqual(dados["igreja_local_batismo_aguas"], "Congregacao Central")
        self.assertEqual(
            dados["igreja_local_batismo_espirito_santo"],
            "Congregacao Central",
        )

    def test_campos_ministeriais_usam_congregacao_por_cargo_atual(self):
        self.adicionar_colunas_opcionais_membro(
            "igreja_local_batismo_aguas",
            "igreja_local_batismo_espirito_santo",
            "data_consagracao_cooperador",
            "data_consagracao_diacono",
            "data_consagracao_presbitero",
            "data_consagracao_evangelista",
            "data_consagracao_pastor",
        )
        db.salvar_configuracoes_igreja({
            "nome_igreja": "Assembleia de Deus Belem",
            "convencao": "CGADB",
            "congregacao_local_nome": "Bonsucesso",
            "setor": "Setorial Norte",
        })

        cenarios = (
            (
                "Cooperador",
                "cooperador",
                "data_consagracao_cooperador",
                "igreja_local_cooperador",
                "Bonsucesso",
            ),
            (
                "Diacono",
                "diacono",
                "data_consagracao_diacono",
                "igreja_local_diacono",
                "Bonsucesso",
            ),
            (
                "Presbitero",
                "presbitero",
                "data_consagracao_presbitero",
                "igreja_local_presbitero",
                "Bonsucesso",
            ),
            (
                "Evangelista",
                "evangelista",
                "data_consagracao_evangelista",
                "igreja_local_convencao_evangelista",
                "Bonsucesso - CGADB",
            ),
            (
                "Pastor",
                "pastor",
                "data_consagracao_pastor",
                "igreja_local_convencao_pastor",
                "Bonsucesso - CGADB",
            ),
        )

        for indice, (cargo, base, campo_data, campo_local, local) in enumerate(cenarios, 1):
            with self.subTest(cargo=cargo):
                id_membro = self.cadastrar(
                    cargo=cargo,
                    data_funcao="31/12/1999",
                    batismo_aguas="01/01/2000",
                    data_batismo_espirito_santo="02/02/2001",
                )
                self.atualizar_colunas_membro(
                    id_membro,
                    igreja_local_batismo_aguas=f"Igreja Batismo Aguas {indice}",
                    igreja_local_batismo_espirito_santo=f"Igreja Batismo Espirito {indice}",
                    **{campo_data: f"0{indice}/03/2020"},
                )

                dados = montar_dados_documento(id_membro)

                self.assertEqual(
                    dados["igreja_local_batismo_aguas"],
                    f"Igreja Batismo Aguas {indice}",
                )
                self.assertEqual(
                    dados["igreja_local_batismo_espirito_santo"],
                    f"Igreja Batismo Espirito {indice}",
                )
                self.assertEqual(dados[f"{base}_dia"], f"0{indice}")
                self.assertEqual(dados[f"{base}_mes"], "03")
                self.assertEqual(dados[f"{base}_ano"], "2020")
                self.assertEqual(dados[campo_local], local)
                self.assertNotIn("Assembleia de Deus Belem", dados[campo_local])
                self.assertNotIn("Setorial", dados[campo_local])

                for outro_campo in (
                    "igreja_local_cooperador",
                    "igreja_local_diacono",
                    "igreja_local_presbitero",
                    "igreja_local_convencao_evangelista",
                    "igreja_local_convencao_pastor",
                ):
                    if outro_campo != campo_local:
                        self.assertEqual(dados[outro_campo], "")

    def test_coluna_especifica_vazia_nao_usa_data_funcao_antiga(self):
        self.adicionar_colunas_opcionais_membro("data_consagracao_cooperador")
        db.salvar_configuracoes_igreja({"congregacao_local_nome": "Bonsucesso"})
        id_membro = self.cadastrar(cargo="Cooperador", data_funcao="31/12/1999")

        dados = montar_dados_documento(id_membro)

        self.assertEqual(dados["cooperador_dia"], "")
        self.assertEqual(dados["cooperador_mes"], "")
        self.assertEqual(dados["cooperador_ano"], "")

    def test_sem_coluna_especifica_mantem_compatibilidade_com_data_funcao(self):
        db.salvar_configuracoes_igreja({"congregacao_local_nome": "Bonsucesso"})
        id_membro = self.cadastrar(cargo="Cooperador", data_funcao="31/12/1999")

        dados = montar_dados_documento(id_membro)

        self.assertEqual(dados["cooperador_dia"], "31")
        self.assertEqual(dados["cooperador_mes"], "12")
        self.assertEqual(dados["cooperador_ano"], "1999")
        self.assertEqual(dados["igreja_local_cooperador"], "Bonsucesso")

    def test_data_batismo_espirito_santo_vem_do_cadastro_do_membro(self):
        id_membro = self.cadastrar(data_batismo_espirito_santo="2021-03-04")

        dados = montar_dados_documento(id_membro)

        self.assertEqual(dados["batismo_espirito_santo"], "2021-03-04")
        self.assertEqual(dados["batismo_espirito_santo_dia"], "04")
        self.assertEqual(dados["batismo_espirito_santo_mes"], "03")
        self.assertEqual(dados["batismo_espirito_santo_ano"], "2021")

    def test_cep_persiste_no_cadastro_e_chega_a_ficha_cadastral(self):
        id_membro = self.cadastrar(cep="07000-000")

        membro = db.buscar_membro_por_id(id_membro)
        dados = montar_dados_documento(id_membro)

        self.assertEqual(membro[30], "07000-000")
        self.assertEqual(dados["cep"], "07000-000")

    def test_cep_persiste_ao_atualizar_membro(self):
        id_membro = self.cadastrar(cep="07000-000")
        dados = self.dados_membro(cep="07123-456")

        db.atualizar_membro(id_membro, dados)
        membro = db.buscar_membro_por_id(id_membro)

        self.assertEqual(membro[30], "07123-456")

    def test_editor_ficha_cadastral_persiste_cep_no_membro(self):
        id_membro = self.cadastrar(cep="07000-000")
        editor = object.__new__(BaseEditorDocumento)
        editor.id_membro = id_membro

        campos_salvos, campos_sem_persistencia = BaseEditorDocumento.salvar_dados_membro(
            editor,
            {"cep": "07123-456"},
        )

        membro = db.buscar_membro_por_id(id_membro)
        self.assertIn("cep", campos_salvos)
        self.assertEqual(campos_sem_persistencia, [])
        self.assertEqual(membro[30], "07123-456")
        self.assertEqual(montar_dados_documento(id_membro)["cep"], "07123-456")

    def test_editor_ficha_cadastral_envia_cep_para_persistencia(self):
        editor = object.__new__(EditorFichaCadastral)
        editor.caminho_foto_selecionada = ""
        editor.campos = {"cep": None}

        dados = EditorFichaCadastral.campos_editaveis_para_cadastro(
            editor,
            {"cep": "07123-456"},
        )

        self.assertEqual(dados["cep"], "07123-456")

    def test_mascara_cep_do_cadastro_principal(self):
        self.assertEqual(CadastroMembro.formatar_cep("07000000"), "07000-000")
        self.assertEqual(CadastroMembro.formatar_cep("07000-000"), "07000-000")
        self.assertEqual(CadastroMembro.formatar_cep(""), "")

    def test_preenche_apenas_campos_mapeados_que_modelo_pede(self):
        campos_pdf = {campo["nome"] for campo in FICHA_CADASTRAL}
        id_membro = self.cadastrar(data_batismo_espirito_santo="05/06/2022")

        dados = montar_dados_documento(id_membro)

        for campo in (
            "igreja_local_batismo_aguas",
            "batismo_espirito_santo_dia",
            "batismo_espirito_santo_mes",
            "batismo_espirito_santo_ano",
            "igreja_local_batismo_espirito_santo",
            "igreja_local_convencao_evangelista",
            "igreja_local_convencao_pastor",
        ):
            self.assertIn(campo, campos_pdf)
            self.assertIn(campo, dados)

    def test_preserva_valor_especifico_se_coluna_antiga_existir(self):
        conexao = db.conectar()
        try:
            cursor = conexao.cursor()
            cursor.execute("ALTER TABLE membros ADD COLUMN igreja_local_batismo_aguas TEXT")
            cursor.execute(
                "ALTER TABLE membros ADD COLUMN igreja_local_batismo_espirito_santo TEXT"
            )
            conexao.commit()
        finally:
            conexao.close()

        db.salvar_configuracoes_igreja({"nome_igreja": "Igreja Sede"})
        id_membro = self.cadastrar()
        conexao = db.conectar()
        try:
            cursor = conexao.cursor()
            cursor.execute(
                """
                UPDATE membros
                SET igreja_local_batismo_aguas = ?,
                    igreja_local_batismo_espirito_santo = ?
                WHERE id = ?
                """,
                ("Outra Igreja", "Outro Local", id_membro),
            )
            conexao.commit()
        finally:
            conexao.close()

        dados = montar_dados_documento(id_membro)

        self.assertEqual(dados["igreja_local_batismo_aguas"], "Outra Igreja")
        self.assertEqual(dados["igreja_local_batismo_espirito_santo"], "Outro Local")

    def test_campos_vazios_nao_geram_none_ou_null(self):
        id_membro = self.cadastrar()

        dados = montar_dados_documento(id_membro)

        for campo in (
            "igreja_local_batismo_aguas",
            "batismo_espirito_santo",
            "batismo_espirito_santo_dia",
            "batismo_espirito_santo_mes",
            "batismo_espirito_santo_ano",
            "igreja_local_batismo_espirito_santo",
            "igreja_local_convencao_evangelista",
            "igreja_local_convencao_pastor",
            "igreja_local_cooperador",
            "igreja_local_diacono",
            "igreja_local_presbitero",
        ):
            self.assertEqual(dados[campo], "")
            self.assertNotIn("None", dados[campo])
            self.assertNotIn("null", dados[campo].lower())

    def test_campos_ministeriais_da_ficha_continuam_inalterados(self):
        campos = {campo["nome"]: campo for campo in FICHA_CADASTRAL}
        esperado = {
            "cooperador_dia": (90, 135, 10, 15),
            "cooperador_mes": (110, 135, 24, 15),
            "cooperador_ano": (146, 135, 54, 15),
            "igreja_local_cooperador": (266, 135, 300, 15),
            "diacono_dia": (73, 156, 24, 15),
            "diacono_mes": (108, 156, 24, 15),
            "diacono_ano": (143, 156, 57, 15),
            "igreja_local_diacono": (266, 156, 300, 15),
            "presbitero_dia": (84, 177, 13, 15),
            "presbitero_mes": (107, 177, 22, 15),
            "presbitero_ano": (139, 177, 61, 15),
            "igreja_local_presbitero": (266, 177, 300, 15),
            "evangelista_dia": (88, 197, 15, 15),
            "evangelista_mes": (114, 197, 18, 15),
            "evangelista_ano": (143, 197, 57, 15),
            "igreja_local_convencao_evangelista": (323, 197, 243, 15),
            "pastor_dia": (65, 218, 32, 15),
            "pastor_mes": (108, 218, 24, 15),
            "pastor_ano": (143, 218, 57, 15),
            "igreja_local_convencao_pastor": (323, 218, 243, 15),
        }

        for nome, coordenadas in esperado.items():
            with self.subTest(campo=nome):
                campo = campos[nome]
                self.assertEqual(
                    (campo["x"], campo["y"], campo["largura"], campo["altura"]),
                    coordenadas,
                )


class TestBotoesEditorFichaCadastral(unittest.TestCase):
    def editor_fake(self):
        editor = object.__new__(BaseEditorDocumento)
        editor.id_membro = 10
        editor.documento = SimpleNamespace(
            codigo="ficha_cadastral",
            titulo="Ficha Cadastral",
            modelo_pdf=Path("modelo.pdf"),
            mapeamento={"codigo": "ficha_cadastral", "campos": []},
        )
        editor.dados_iniciais = {"nome_membro": "Membro Teste"}
        editor.caminho_ultimo_pdf = None
        editor.validar_antes_de_gerar = mock.Mock(return_value=True)
        editor.coletar_dados = mock.Mock(return_value={"nome_membro": "Editado"})
        editor.campos_editaveis_para_cadastro = mock.Mock(return_value={"nome": "Editado"})
        editor.salvar_dados_membro = mock.Mock(return_value=(["nome"], []))
        editor.gerar_pdf_final = mock.Mock(return_value=Path("saida.pdf"))
        editor.registrar_emissao_documento = mock.Mock(return_value=20)
        editor.abrir_pdf = mock.Mock()
        return editor

    def test_botao_salvar_alteracoes_salva_valores_atuais(self):
        editor = self.editor_fake()

        with mock.patch("telas.documentos.base_editor_documento.messagebox.showinfo") as info:
            BaseEditorDocumento.salvar_alteracoes(editor)

        editor.salvar_dados_membro.assert_called_once_with({"nome": "Editado"})
        self.assertEqual(editor.dados_iniciais["nome_membro"], "Editado")
        info.assert_called_once()

    def test_botao_salvar_como_pdf_gera_pdf_com_dados_editados(self):
        editor = self.editor_fake()

        with mock.patch("telas.documentos.base_editor_documento.messagebox.showinfo") as info, \
                mock.patch("telas.documentos.base_editor_documento.registrar_acao"):
            BaseEditorDocumento.salvar_como_pdf(editor)

        editor.gerar_pdf_final.assert_called_once()
        editor.registrar_emissao_documento.assert_called_once_with(Path("saida.pdf"), "PDF salvo")
        editor.abrir_pdf.assert_called_once_with(Path("saida.pdf"))
        self.assertEqual(editor.caminho_ultimo_pdf, Path("saida.pdf"))
        info.assert_called_once()

    def test_botao_imprimir_usa_fluxo_de_impressao(self):
        editor = self.editor_fake()

        with mock.patch("telas.documentos.base_editor_documento.os.startfile") as startfile, \
                mock.patch("telas.documentos.base_editor_documento.registrar_acao"), \
                mock.patch("telas.documentos.base_editor_documento.messagebox.showinfo") as info:
            BaseEditorDocumento.imprimir(editor)

        editor.gerar_pdf_final.assert_called_once()
        startfile.assert_called_once_with(Path("saida.pdf"), "print")
        editor.registrar_emissao_documento.assert_called_once_with(
            Path("saida.pdf"),
            "Enviado para impressao",
        )
        info.assert_called_once()

    def test_botoes_nao_fecham_janela_em_falha(self):
        editor = self.editor_fake()
        editor.destroy = mock.Mock()
        editor.gerar_pdf_final.side_effect = RuntimeError("falha")

        with mock.patch("telas.documentos.base_editor_documento.messagebox.showerror"):
            BaseEditorDocumento.salvar_como_pdf(editor)

        editor.destroy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
