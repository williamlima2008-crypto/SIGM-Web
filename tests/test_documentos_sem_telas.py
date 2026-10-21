"""Garante que os pedidos de Membramento/Reconciliacao funcionam como no
instalador: sem a pasta telas, sem tkinter e sem customtkinter."""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

SCRIPT = textwrap.dedent('''
    import os, sys
    for nome in ("telas", "telas.documentos", "tkinter", "_tkinter", "customtkinter"):
        sys.modules[nome] = None          # qualquer import desses modulos falha
    sys.path.insert(0, os.getcwd())
    from pathlib import Path
    from banco import database as db
    base = Path(os.environ["SIGM_DADOS_DIR"])
    db.BANCO = base / "sigm.db"
    db.criar_tabelas()
    from web.servidor import criar_app
    app = criar_app(); app.config["TESTING"] = True
    c = app.test_client()
    with c.session_transaction() as s:
        s["usuario"] = {"id_usuario": 1, "nome": "Sec", "login": "sec",
                        "perfil": "Administrador", "status": "Ativo"}
    H = {"X-SIGM": "1"}
    r = c.post("/api/membros", headers=H, json={"nome": "Maria da Silva", "cpf": "12345678909"})
    mid = r.get_json()["id"]
    for slug in ("membramento", "reconciliacao"):
        r = c.get(f"/api/membros/{mid}/documentos/{slug}/formulario")
        d = r.get_json()
        assert r.status_code == 200, (slug, r.status_code, d)
        assert any(a["valor"] == "Maria da Silva" for a in d["automaticos"]), (slug, d)
    print("OK")
''')


class TesteDocumentosSemTelas(unittest.TestCase):
    def test_formularios_abrem_sem_telas_nem_tkinter(self):
        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta) / "fotos_membros").mkdir()
            ambiente = dict(os.environ, SIGM_DADOS_DIR=pasta)
            r = subprocess.run([sys.executable, "-c", SCRIPT], cwd=RAIZ, env=ambiente,
                               capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK", r.stdout)


if __name__ == "__main__":
    unittest.main()
