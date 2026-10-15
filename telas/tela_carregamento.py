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
from banco.database import buscar_configuracoes_igreja, existe_administrador
from telas.tela_login import TelaLogin
from telas.tela_primeiro_acesso import TelaPrimeiroAcesso
from utils.janelas import configurar_modal


class TelaCarregamento(ctk.CTkToplevel):

    def __init__(self, master):
        super().__init__(master)

        self.master = master

        self.title("Carregando - SIGM")
        self.geometry("650x420")
        self.resizable(False, False)
        self.configure(fg_color=cores.FUNDO)

        configurar_modal(self, master)
        self.grab_set()

        self.progresso = 0

        self.criar_interface()
        self.after(400, self.iniciar_carregamento)

    def criar_interface(self):
        dados_igreja = buscar_configuracoes_igreja()
        nome_igreja = dados_igreja.get("nome_igreja") or "Igreja nao configurada"

        titulo = ctk.CTkLabel(
            self,
            text=configuracoes.NOME_SISTEMA,
            font=("Segoe UI", 42, "bold"),
            text_color=cores.AZUL_PRINCIPAL
        )
        titulo.pack(pady=(45, 5))

        subtitulo = ctk.CTkLabel(
            self,
            text=configuracoes.DESCRICAO_SISTEMA,
            font=("Segoe UI", 18),
            text_color=cores.PRETO
        )
        subtitulo.pack()

        igreja = ctk.CTkLabel(
            self,
            text=nome_igreja,
            font=("Segoe UI", 14),
            text_color=cores.CINZA
        )
        igreja.pack(pady=(5, 25))

        self.texto_status = ctk.CTkLabel(
            self,
            text="Inicializando banco...",
            font=fontes.TEXTO,
            text_color=cores.CINZA
        )
        self.texto_status.pack(pady=(10, 10))

        self.barra = ctk.CTkProgressBar(
            self,
            width=420,
            height=18,
            corner_radius=10
        )
        self.barra.pack(pady=10)
        self.barra.set(0)

        self.porcentagem = ctk.CTkLabel(
            self,
            text="0%",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL
        )
        self.porcentagem.pack(pady=5)

        versao = ctk.CTkLabel(
            self,
            text=f"Versão {configuracoes.VERSAO}",
            font=fontes.RODAPE,
            text_color=cores.CINZA
        )
        versao.pack(side="bottom", pady=15)

    def iniciar_carregamento(self):
        self.atualizar_progresso()

    def atualizar_progresso(self):
        self.progresso += 10

        self.barra.set(self.progresso / 100)
        self.porcentagem.configure(text=f"{self.progresso}%")

        if self.progresso == 40:
            self.texto_status.configure(text="Carregando membros...")

        if self.progresso == 70:
            self.texto_status.configure(text="Preparando interface...")

        if self.progresso >= 100:
            self.texto_status.configure(text="Pronto!")
            self.after(500, self.abrir_proxima_tela)
            return

        self.after(180, self.atualizar_progresso)

    def abrir_proxima_tela(self):
        self.destroy()

        if existe_administrador():
            TelaLogin(self.master)
        else:
            TelaPrimeiroAcesso(self.master)
