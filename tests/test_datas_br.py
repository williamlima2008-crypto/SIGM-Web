import unittest

from documentos.datas import data_para_br, normalizar_campo_data, valor_sim_nao
from servicos.aprovacao_pre_cadastro import preparar_dados_membro


class DatasBrasileirasTests(unittest.TestCase):
    def test_iso_vira_dd_mm_aaaa(self):
        self.assertEqual(data_para_br("2023-09-16"), "16/09/2023")
        self.assertEqual(data_para_br("2023-09-16T10:00:00"), "16/09/2023")
        self.assertEqual(data_para_br("16/09/2023"), "16/09/2023")
        self.assertEqual(data_para_br(""), "")

    def test_batismo_true_false_vira_sim_nao(self):
        self.assertEqual(normalizar_campo_data("batismo_aguas", "True"), "Sim")
        self.assertEqual(normalizar_campo_data("batismo_aguas", True), "Sim")
        self.assertEqual(normalizar_campo_data("batismo_aguas", False), "Não")
        self.assertEqual(normalizar_campo_data("batismo_aguas", "1"), "Sim")
        self.assertEqual(normalizar_campo_data("batismo_aguas", "2023-09-16"), "16/09/2023")
        self.assertEqual(normalizar_campo_data("batismo_aguas", "16/09/2023"), "16/09/2023")
        self.assertEqual(normalizar_campo_data("data_funcao", "True"), "True")  # so batismo vira Sim/Nao

    def test_valor_sim_nao(self):
        self.assertIsNone(valor_sim_nao("16/09/2023"))
        self.assertEqual(valor_sim_nao("nao"), "Não")

    def test_aprovacao_de_pre_cadastro_guarda_datas_e_batismo_no_padrao_brasileiro(self):
        dados = preparar_dados_membro({
            "nome": "Ana", "batismo_aguas": True, "data_funcao": "2023-09-16",
            "data_nascimento": "1990-01-05", "data_nascimento_conjuge": "",
        })
        self.assertEqual(dados["batismo_aguas"], "Sim")
        self.assertEqual(dados["data_funcao"], "16/09/2023")
        self.assertEqual(dados["data_nascimento"], "05/01/1990")
        self.assertEqual(preparar_dados_membro({"nome": "B", "batismo_aguas": False})["batismo_aguas"], "Não")


if __name__ == "__main__":
    unittest.main()
