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
from tkinter import messagebox

from config import cores, fontes
from banco.database import cadastrar_igreja, cadastrar_usuario
from servicos.recuperacao_senha import gerar_chave_recuperacao
from telas.recuperar_senha import mostrar_chave_recuperacao
from telas.tela_login import TelaLogin
from utils.auditoria import registrar_acao
from utils.janelas import configurar_modal


class TelaPrimeiroAcesso(ctk.CTkToplevel):

    def __init__(self, master):
        super().__init__(master)

        self.master = master

        self.title("Primeira Configuração - SIGM")
        self.geometry("900x760")
        self.minsize(760, 560)
        self.resizable(True, True)
        self.configure(fg_color=cores.FUNDO)

        configurar_modal(self, master)
        self.grab_set()

        self.criar_interface()

    def criar_interface(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        cabecalho = ctk.CTkFrame(self, fg_color="transparent")
        cabecalho.grid(row=0, column=0, sticky="ew", pady=(25, 15))

        titulo = ctk.CTkLabel(
            cabecalho,
            text="Bem-vindo ao SIGM",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL
        )
        titulo.pack(pady=(0, 5))

        subtitulo = ctk.CTkLabel(
            cabecalho,
            text="Primeira configuração do sistema",
            font=("Segoe UI", 18),
            text_color=cores.CINZA
        )
        subtitulo.pack()

        self.frame = ctk.CTkScrollableFrame(
            self,
            corner_radius=10
        )
        self.frame.grid(row=1, column=0, sticky="nsew", padx=35, pady=(0, 10))

        label_igreja = ctk.CTkLabel(
            self.frame,
            text="Dados da Igreja",
            font=("Segoe UI", 20, "bold"),
            text_color=cores.AZUL_PRINCIPAL
        )
        label_igreja.pack(pady=(20, 10))

        self.nome_igreja = ctk.CTkEntry(
            self.frame,
            width=500,
            height=32,
            placeholder_text="Nome da igreja"
        )
        self.nome_igreja.pack(pady=5)

        self.ministerio = ctk.CTkEntry(
            self.frame,
            width=500,
            height=32,
            placeholder_text="Ministério"
        )
        self.ministerio.pack(pady=5)

        self.cidade = ctk.CTkEntry(
            self.frame,
            width=500,
            height=32,
            placeholder_text="Cidade"
        )
        self.cidade.pack(pady=5)

        self.estado = ctk.CTkEntry(
            self.frame,
            width=500,
            height=32,
            placeholder_text="Estado / UF"
        )
        self.estado.pack(pady=5)

        label_admin = ctk.CTkLabel(
            self.frame,
            text="Administrador do Sistema",
            font=("Segoe UI", 20, "bold"),
            text_color=cores.AZUL_PRINCIPAL
        )
        label_admin.pack(pady=(20, 10))

        self.nome_admin = ctk.CTkEntry(
            self.frame,
            width=500,
            height=32,
            placeholder_text="Nome completo"
        )
        self.nome_admin.pack(pady=5)

        self.usuario_admin = ctk.CTkEntry(
            self.frame,
            width=500,
            height=32,
            placeholder_text="Usuário"
        )
        self.usuario_admin.pack(pady=5)

        self.senha_admin = ctk.CTkEntry(
            self.frame,
            width=500,
            height=32,
            placeholder_text="Senha",
            show="•"
        )
        self.senha_admin.pack(pady=5)

        self.confirmar_senha = ctk.CTkEntry(
            self.frame,
            width=500,
            height=32,
            placeholder_text="Confirmar senha",
            show="•"
        )
        self.confirmar_senha.pack(pady=5)

        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.grid(row=2, column=0, sticky="ew")

        self.mensagem = ctk.CTkLabel(
            rodape,
            text="",
            font=("Segoe UI", 13),
            text_color=cores.VERMELHO
        )
        self.mensagem.pack(pady=(0, 5))

        self.botao_finalizar = ctk.CTkButton(
            rodape,
            text="FINALIZAR CONFIGURAÇÃO",
            width=300,
            height=45,
            corner_radius=8,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            font=fontes.BOTAO,
            command=self.finalizar_configuracao
        )
        self.botao_finalizar.pack(pady=(0, 20))

        self.nome_igreja.focus_set()

        self.nome_igreja.bind("<Return>", lambda event: self.ministerio.focus_set())
        self.ministerio.bind("<Return>", lambda event: self.cidade.focus_set())
        self.cidade.bind("<Return>", lambda event: self.estado.focus_set())
        self.estado.bind("<Return>", lambda event: self.nome_admin.focus_set())
        self.nome_admin.bind("<Return>", lambda event: self.usuario_admin.focus_set())
        self.usuario_admin.bind("<Return>", lambda event: self.senha_admin.focus_set())
        self.senha_admin.bind("<Return>", lambda event: self.confirmar_senha.focus_set())
        self.confirmar_senha.bind("<Return>", lambda event: self.finalizar_configuracao())

    def finalizar_configuracao(self):
        nome_igreja = self.nome_igreja.get().strip()
        ministerio = self.ministerio.get().strip()
        cidade = self.cidade.get().strip()
        estado = self.estado.get().strip()

        nome_admin = self.nome_admin.get().strip()
        usuario_admin = self.usuario_admin.get().strip()
        senha_admin = self.senha_admin.get().strip()
        confirmar_senha = self.confirmar_senha.get().strip()

        if nome_igreja == "" or nome_admin == "" or usuario_admin == "" or senha_admin == "":
            self.mensagem.configure(
                text="Preencha os campos obrigatórios.",
                text_color=cores.VERMELHO
            )
            return

        if senha_admin != confirmar_senha:
            self.mensagem.configure(
                text="As senhas não conferem.",
                text_color=cores.VERMELHO
            )
            return

        try:
            cadastrar_igreja(nome_igreja, ministerio, cidade, estado)

            id_usuario = cadastrar_usuario(
                nome_admin,
                usuario_admin,
                senha_admin,
                "Administrador"
            )
            registrar_acao(
                "USUARIO_CRIADO",
                f"Usuario {usuario_admin} criado.",
                modulo="Usuarios",
                registro_id=id_usuario,
                usuario_nome=nome_admin,
                usuario_login=usuario_admin,
            )

            # Chave para recuperar a senha caso seja esquecida (mostrada uma vez).
            # Se falhar por qualquer motivo, a configuração segue normalmente - o
            # Administrador pode gerar a chave depois, na tela de Usuários.
            try:
                mostrar_chave_recuperacao(self, gerar_chave_recuperacao())
            except Exception:
                pass

            self.mensagem.configure(
                text="Configuração concluída com sucesso!",
                text_color=cores.VERDE
            )

            self.botao_finalizar.configure(
                text="Carregando login...",
                state="disabled"
            )

            self.after(1200, self.abrir_login)

        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Não foi possível finalizar a configuração.\n\nErro: {erro}"
            )

    def abrir_login(self):
        self.destroy()
        TelaLogin(self.master)
