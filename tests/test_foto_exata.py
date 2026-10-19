import tempfile
import unittest
from pathlib import Path
from unittest import mock

from documentos import integrador_documentos as integ


class FotoPorArquivoTests(unittest.TestCase):
    def test_id_nao_casa_com_prefixo_de_outro_membro(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            (pasta / "foto_12.jpg").write_bytes(b"x")
            (pasta / "foto_2.jpg").write_bytes(b"y")
            with mock.patch.object(integ, "PASTA_FOTOS_MEMBROS", pasta):
                self.assertEqual(integ.buscar_foto_membro_por_arquivo(1), "")
                self.assertEqual(
                    Path(integ.buscar_foto_membro_por_arquivo(12)).name,
                    "foto_12.jpg",
                )
                self.assertEqual(
                    Path(integ.buscar_foto_membro_por_arquivo(2)).name,
                    "foto_2.jpg",
                )


if __name__ == "__main__":
    unittest.main()
