"""
==========================================================
SIGM - Sistema de Gestão de Membros

Arquivo: tela_inicial.py
Descrição: Tela inicial do sistema.

Desenvolvido por:
William Lima

"Servindo à Igreja com organização e excelência."
==========================================================
"""

import customtkinter as ctk

from config import cores, fontes, configuracoes
from banco.database import buscar_configuracoes_igreja
from telas.tela_carregamento import TelaCarregamento
from utils.janelas import configurar_janela_principal


class TelaInicial(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title(f"{configuracoes.NOME_SISTEMA} - {configuracoes.DESCRICAO_SISTEMA}")
        configurar_janela_principal(self, 1000, 650, 850, 550)
        self.configure(fg_color=cores.FUNDO)

        self.criar_interface()

    def criar_interface(self):
        dados_igreja = buscar_configuracoes_igreja()
        nome_igreja = dados_igreja.get("nome_igreja", "")
        versiculo_texto = (
            dados_igreja.get("versiculo_institucional")
            or '"E tudo quanto fizerdes, fazei-o de todo o coração,\ncomo para o Senhor e não para os homens."\n\nColossenses 3:23'
        )

        titulo = ctk.CTkLabel(
            self,
            text=configuracoes.NOME_SISTEMA,
            font=("Segoe UI", 42, "bold"),
            text_color=cores.AZUL_PRINCIPAL
        )
        titulo.pack(pady=(70, 10))

        subtitulo = ctk.CTkLabel(
            self,
            text=configuracoes.DESCRICAO_SISTEMA,
            font=fontes.SUBTITULO,
            text_color=cores.PRETO
        )
        subtitulo.pack()

        if nome_igreja:
            ctk.CTkLabel(
                self,
                text=nome_igreja,
                font=("Segoe UI", 15, "bold"),
                text_color=cores.AZUL_PRINCIPAL,
            ).pack(pady=(8, 0))

        frase = ctk.CTkLabel(
            self,
            text="Servindo à Igreja com organização e excelência.",
            font=("Segoe UI", 17, "italic"),
            text_color=cores.CINZA
        )
        frase.pack(pady=(20, 50))

        self.botao_iniciar = ctk.CTkButton(
            self,
            text="INICIAR",
            width=240,
            height=50,
            corner_radius=8,
            font=fontes.BOTAO,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            command=self.iniciar_sistema
        )
        self.botao_iniciar.pack()

        versiculo = ctk.CTkLabel(
            self,
            text=versiculo_texto,
            font=("Segoe UI", 12),
            text_color=cores.CINZA
        )
        versiculo.pack(side="bottom", pady=(0, 20))

        assinatura = ctk.CTkLabel(
            self,
            text=f"Versão {configuracoes.VERSAO}",
            font=fontes.RODAPE,
            text_color=cores.CINZA
        )
        assinatura.pack(side="bottom", pady=(0, 5))

    def iniciar_sistema(self):
        self.botao_iniciar.configure(
            text="Carregando...",
            state="disabled"
        )

        self.after(1200, self.abrir_proxima_tela)

    def abrir_proxima_tela(self):
        self.withdraw()
        TelaCarregamento(self)
