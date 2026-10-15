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
from banco.database import buscar_configuracoes_igreja, validar_login
from telas.dashboard import Dashboard
from telas.recuperar_senha import RecuperarSenha
from utils.auditoria import registrar_acao
from utils.janelas import configurar_modal
from utils.sessao import iniciar_sessao


class TelaLogin(ctk.CTkToplevel):

    # Depois de quantas senhas erradas o botão "Recuperar senha" aparece.
    LIMITE_TENTATIVAS_RECUPERACAO = 3

    def __init__(self, master):
        super().__init__(master)

        self.master = master
        self.tentativas_falhas = 0
        self.botao_recuperar = None
        self.recuperar_visivel = False

        self.title("Login - SIGM")
        self.geometry("700x550")
        self.resizable(False, False)
        self.configure(fg_color=cores.FUNDO)

        configurar_modal(self, master)
        self.grab_set()

        self.criar_interface()

    def criar_interface(self):
        dados_igreja = buscar_configuracoes_igreja()
        nome_igreja = dados_igreja.get("nome_igreja") or configuracoes.DESCRICAO_SISTEMA
        detalhes_igreja = " | ".join(
            parte
            for parte in (
                dados_igreja.get("ministerio"),
                f"Setor {dados_igreja.get('setor')}" if dados_igreja.get("setor") else "",
                " - ".join(
                    parte
                    for parte in (dados_igreja.get("cidade"), dados_igreja.get("estado"))
                    if parte
                ),
            )
            if parte
        )

        titulo = ctk.CTkLabel(
            self,
            text=configuracoes.NOME_SISTEMA,
            font=("Segoe UI", 34, "bold"),
            text_color=cores.AZUL_PRINCIPAL
        )
        titulo.pack(pady=(35, 5))

        subtitulo = ctk.CTkLabel(
            self,
            text=nome_igreja,
            font=("Segoe UI", 18),
            text_color=cores.PRETO
        )
        subtitulo.pack()

        if detalhes_igreja:
            ctk.CTkLabel(
                self,
                text=detalhes_igreja,
                font=("Segoe UI", 12),
                text_color=cores.CINZA,
            ).pack(pady=(4, 0))

        boas_vindas = ctk.CTkLabel(
            self,
            text="Bem-vindo ao SIGM",
            font=("Segoe UI", 22, "bold"),
            text_color=cores.PRETO
        )
        boas_vindas.pack(pady=(30, 20))

        self.campo_usuario = ctk.CTkEntry(
            self,
            width=350,
            height=42,
            placeholder_text="Usuário",
            font=fontes.TEXTO
        )
        self.campo_usuario.pack(pady=8)

        self.campo_senha = ctk.CTkEntry(
            self,
            width=350,
            height=42,
            placeholder_text="Senha",
            show="•",
            font=fontes.TEXTO
        )
        self.campo_senha.pack(pady=8)

        self.mostrar_senha = ctk.CTkCheckBox(
            self,
            text="Mostrar senha",
            command=self.alternar_senha,
            text_color=cores.CINZA
        )
        self.mostrar_senha.pack(pady=(5, 15))

        self.mensagem = ctk.CTkLabel(
            self,
            text="",
            font=("Segoe UI", 13),
            text_color=cores.VERMELHO
        )
        self.mensagem.pack(pady=5)

        self.botao_entrar = ctk.CTkButton(
            self,
            text="ENTRAR",
            width=350,
            height=45,
            corner_radius=8,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            font=fontes.BOTAO,
            command=self.entrar
        )
        self.botao_entrar.pack(pady=15)

        # Só é exibido (mostrar_botao_recuperar) depois de várias senhas erradas.
        self.botao_recuperar = ctk.CTkButton(
            self,
            text="Esqueci minha senha - Recuperar senha",
            width=350,
            height=34,
            corner_radius=8,
            fg_color="transparent",
            text_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.CINZA_CLARO,
            font=("Segoe UI", 13, "bold"),
            command=self.abrir_recuperacao
        )

        versao = ctk.CTkLabel(
            self,
            text=f"Versão {configuracoes.VERSAO}",
            font=fontes.RODAPE,
            text_color=cores.CINZA
        )
        versao.pack(side="bottom", pady=15)

        self.campo_usuario.bind("<Return>", lambda event: self.campo_senha.focus_set())
        self.campo_senha.bind("<Return>", lambda event: self.entrar())
        self.botao_entrar.bind("<Return>", lambda event: self.entrar())
        self.bind("<Return>", lambda event: self.entrar())

        self.after(200, lambda: self.campo_usuario.focus_set())

    def alternar_senha(self):
        if self.mostrar_senha.get() == 1:
            self.campo_senha.configure(show="")
        else:
            self.campo_senha.configure(show="•")

    def entrar(self):
        usuario = self.campo_usuario.get().strip()
        senha = self.campo_senha.get().strip()

        if usuario == "" or senha == "":
            self.mensagem.configure(
                text="Preencha usuário e senha.",
                text_color=cores.VERMELHO
            )
            return

        usuario_logado = validar_login(usuario, senha)

        if isinstance(usuario_logado, dict) and usuario_logado.get("bloqueado"):
            registrar_acao(
                "USUARIO_BLOQUEADO_TENTATIVA_LOGIN",
                f"Usuario bloqueado tentou entrar: {usuario}.",
                modulo="Autenticacao",
                usuario_login=usuario,
                usuario_nome=usuario_logado.get("nome"),
            )
            self.mensagem.configure(
                text="Usuario bloqueado. Procure o Administrador.",
                text_color=cores.VERMELHO
            )
            return

        if usuario_logado is None:
            registrar_acao(
                "LOGIN_RECUSADO",
                f"Tentativa de login recusada para o usuario {usuario}.",
                modulo="Autenticacao",
                usuario_login=usuario,
            )

            self.tentativas_falhas += 1
            texto_erro = "Usuário ou senha inválidos."
            if self.tentativas_falhas >= self.LIMITE_TENTATIVAS_RECUPERACAO:
                self.mostrar_botao_recuperar()
                texto_erro = "Usuário ou senha inválidos. Esqueceu a senha? Use \"Recuperar senha\"."

            self.mensagem.configure(
                text=texto_erro,
                text_color=cores.VERMELHO
            )
            return

        self.mensagem.configure(
            text="Login realizado com sucesso!",
            text_color=cores.VERDE
        )

        self.botao_entrar.configure(
            text="Entrando...",
            state="disabled"
        )

        sessao = iniciar_sessao(usuario_logado)
        registrar_acao(
            "LOGIN_SUCESSO",
            f"Login realizado com sucesso por {sessao.get('login') or usuario}.",
            modulo="Autenticacao",
        )
        self.after(800, lambda: self.abrir_dashboard(sessao))

    def abrir_dashboard(self, usuario_logado):
        self.destroy()
        Dashboard(self.master, usuario_logado)

    def mostrar_botao_recuperar(self):
        if self.recuperar_visivel or self.botao_recuperar is None:
            return

        self.recuperar_visivel = True
        # Logo abaixo do ENTRAR; a janela cresce um pouco para caber.
        self.botao_recuperar.pack(after=self.botao_entrar, pady=(0, 6))
        self.geometry("700x610")

    def abrir_recuperacao(self):
        janela = RecuperarSenha(
            self,
            usuario_inicial=self.campo_usuario.get().strip(),
            ao_concluir=self.aplicar_recuperacao,
        )
        self.wait_window(janela)

        # Volta a tela de login a ser a janela ativa.
        try:
            if self.winfo_exists():
                self.grab_set()
                self.campo_senha.focus_set()
        except Exception:
            pass

    def aplicar_recuperacao(self, usuario):
        self.tentativas_falhas = 0
        self.campo_usuario.delete(0, "end")
        self.campo_usuario.insert(0, usuario)
        self.campo_senha.delete(0, "end")
        self.mensagem.configure(
            text="Senha redefinida. Entre com a nova senha.",
            text_color=cores.VERDE
        )
