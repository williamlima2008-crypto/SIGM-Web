"""
==========================================================
SIGM - Sistema de Gestão de Membros

Arquivo: app.py
Descrição: Inicializa o sistema.

Desenvolvido por:
William Lima

"Servindo à Igreja com organização e excelência."
==========================================================
"""

from banco.database import criar_tabelas
from telas.tela_inicial import TelaInicial
from utils.caminhos import garantir_pastas_runtime


if __name__ == "__main__":
    garantir_pastas_runtime()
    criar_tabelas()

    app = TelaInicial()
    app.mainloop()
    
