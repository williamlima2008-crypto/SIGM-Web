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

from config import cores, fontes
from banco.database import listar_membros
from componentes.cabecalho_igreja import CabecalhoIgreja
from telas.cadastro_membro import CadastroMembro
from telas.ficha_membro import FichaMembro
from utils.janelas import configurar_janela_principal


class ConsultaMembros(ctk.CTkToplevel):

    def __init__(self, master):
        super().__init__(master)

        self.janela_cadastro = None
        self.janela_ficha = None

        self.title("Consulta de Membros - SIGM")
        configurar_janela_principal(self, 1120, 700, 980, 620, master)
        self.configure(fg_color=cores.FUNDO)

        self.criar_interface()

    def criar_interface(self):
        titulo = ctk.CTkLabel(
            self,
            text="Consulta de Membros",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL
        )
        titulo.pack(pady=(25, 10))

        self.cabecalho_igreja = CabecalhoIgreja(self)
        self.cabecalho_igreja.pack(fill="x", padx=30, pady=(0, 12))

        self.campo_pesquisa = ctk.CTkEntry(
            self,
            width=520,
            height=40,
            placeholder_text="🔎 Pesquisar por nome...",
            font=fontes.TEXTO
        )
        self.campo_pesquisa.pack(pady=8)
        self.campo_pesquisa.bind("<KeyRelease>", self.pesquisar_em_tempo_real)

        botao_novo = ctk.CTkButton(
            self,
            text="+ NOVO MEMBRO",
            width=200,
            height=40,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            font=fontes.BOTAO,
            command=self.abrir_cadastro
        )
        botao_novo.pack(pady=10)

        self.frame_lista = ctk.CTkScrollableFrame(
            self,
            width=950,
            height=430,
            corner_radius=10
        )
        self.frame_lista.pack(padx=30, pady=10, fill="both", expand=True)

        self.carregar_membros()

    def pesquisar_em_tempo_real(self, event=None):
        termo = self.campo_pesquisa.get().strip().lower()
        self.carregar_membros(termo)

    def carregar_membros(self, termo=""):
        for widget in self.frame_lista.winfo_children():
            widget.destroy()

        membros = listar_membros()

        if termo:
            membros = [
                membro for membro in membros
                if termo in str(membro[1]).lower()
            ]

        if not membros:
            ctk.CTkLabel(
                self.frame_lista,
                text="Nenhum membro encontrado.",
                font=fontes.TEXTO,
                text_color=cores.CINZA
            ).pack(pady=30)
            return

        cabecalho = ctk.CTkFrame(
            self.frame_lista,
            fg_color=cores.AZUL_PRINCIPAL
        )
        cabecalho.pack(fill="x", padx=10, pady=(10, 5))

        colunas = [
            ("ID", 60),
            ("Nome", 350),
            ("Celular", 180),
            ("Cidade", 180),
            ("Status", 150)
        ]

        for indice, (titulo, largura) in enumerate(colunas):
            ctk.CTkLabel(
                cabecalho,
                text=titulo,
                width=largura,
                text_color=cores.BRANCO,
                font=("Segoe UI", 13, "bold")
            ).grid(row=0, column=indice, padx=5, pady=8)

        for membro in membros:
            id_membro, nome, celular, cidade, status = membro

            linha = ctk.CTkFrame(
                self.frame_lista,
                fg_color=cores.BRANCO,
                corner_radius=8
            )
            linha.pack(fill="x", padx=10, pady=4)

            valores = [
                (str(id_membro), 60),
                (nome or "-", 350),
                (celular or "-", 180),
                (cidade or "-", 180),
                (status or "-", 150)
            ]

            for indice, (valor, largura) in enumerate(valores):
                label = ctk.CTkLabel(
                    linha,
                    text=valor,
                    width=largura,
                    anchor="w",
                    font=("Segoe UI", 13),
                    text_color=cores.PRETO
                )
                label.grid(row=0, column=indice, padx=5, pady=8)

                label.bind(
                    "<Double-Button-1>",
                    lambda event, id=id_membro: self.abrir_ficha(id)
                )

            linha.bind(
                "<Double-Button-1>",
                lambda event, id=id_membro: self.abrir_ficha(id)
            )

    def abrir_cadastro(self):
        if self.janela_cadastro is not None and self.janela_cadastro.winfo_exists():
            self.janela_cadastro.lift()
            self.janela_cadastro.focus_force()
            return

        self.janela_cadastro = CadastroMembro(
            self,
            ao_salvar=self.atualizar_lista
        )

    def abrir_ficha(self, id_membro):
        if self.janela_ficha is not None and self.janela_ficha.winfo_exists():
            self.janela_ficha.destroy()

        self.janela_ficha = FichaMembro(
            self,
            id_membro,
            ao_alterar=self.atualizar_lista
        )

    def atualizar_lista(self):
        termo = self.campo_pesquisa.get().strip().lower()
        self.carregar_membros(termo)
