"""
==========================================================
SIGM - Sistema de Gestão de Membros

Arquivo: recuperar_senha.py
Descrição: Telas da recuperação de senha:
- RecuperarSenha: diálogo aberto na tela de login, depois de 3
  tentativas erradas, para redefinir a senha com a chave de recuperação;
- mostrar_chave_recuperacao(): exibe a chave de recuperação (uma única
  vez), com botão para copiar.

Desenvolvido por:
William Lima

"Servindo à Igreja com organização e excelência."
==========================================================
"""
from tkinter import messagebox

import customtkinter as ctk

from config import cores, fontes
from servicos.recuperacao_senha import (
    existe_chave_recuperacao,
    gerar_chave_recuperacao,
    redefinir_senha_com_chave,
)
from utils.auditoria import registrar_acao
from utils.janelas import configurar_modal


def _tentar_grab(janela, tentativas=10):
    """Torna a janela modal; se o Windows ainda não a exibiu, tenta de novo."""
    try:
        if not janela.winfo_exists():
            return
        janela.grab_set()
    except Exception:
        if tentativas > 0:
            try:
                janela.after(100, lambda: _tentar_grab(janela, tentativas - 1))
            except Exception:
                pass


class ChaveRecuperacao(ctk.CTkToplevel):
    """Mostra a chave de recuperação uma única vez."""

    def __init__(self, master, chave, titulo="Chave de recuperação", aviso=""):
        super().__init__(master)

        self.chave = chave

        self.title("Chave de recuperação - SIGM")
        self.geometry("580x520")
        self.resizable(False, False)
        self.configure(fg_color=cores.FUNDO)

        configurar_modal(self, master)
        _tentar_grab(self)

        ctk.CTkLabel(
            self,
            text=titulo,
            font=("Segoe UI", 24, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(24, 6))

        if aviso:
            ctk.CTkLabel(
                self,
                text=aviso,
                font=("Segoe UI", 13, "bold"),
                text_color=cores.PRETO,
                wraplength=500,
                justify="center",
            ).pack(padx=30, pady=(0, 6))

        ctk.CTkLabel(
            self,
            text=(
                "Anote ou imprima a chave abaixo e guarde em local seguro "
                "(por exemplo, com o pastor ou na secretaria). "
                "Ela será mostrada somente agora."
            ),
            font=("Segoe UI", 13),
            text_color=cores.CINZA,
            wraplength=500,
            justify="center",
        ).pack(padx=30, pady=(0, 12))

        quadro = ctk.CTkFrame(self, fg_color=cores.BRANCO, corner_radius=10)
        quadro.pack(padx=40, pady=6, fill="x")

        ctk.CTkLabel(
            quadro,
            text=chave,
            font=("Consolas", 30, "bold"),
            text_color=cores.PRETO,
        ).pack(pady=20)

        ctk.CTkLabel(
            self,
            text="Quem tiver esta chave pode redefinir senhas do SIGM. Não a compartilhe.",
            font=("Segoe UI", 12, "bold"),
            text_color=cores.VERMELHO,
            wraplength=500,
            justify="center",
        ).pack(padx=30, pady=(10, 10))

        self.botao_copiar = ctk.CTkButton(
            self,
            text="COPIAR CHAVE",
            width=240,
            height=38,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            command=self.copiar,
        )
        self.botao_copiar.pack(pady=(4, 8))

        ctk.CTkButton(
            self,
            text="JÁ ANOTEI A CHAVE",
            width=240,
            height=42,
            fg_color=cores.VERDE,
            hover_color="#1F7A45",
            font=fontes.BOTAO,
            command=self.destroy,
        ).pack(pady=(4, 18))

        self.protocol("WM_DELETE_WINDOW", self.tentar_fechar)

    def copiar(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.chave)
            self.botao_copiar.configure(text="CHAVE COPIADA!")
        except Exception:
            pass

    def tentar_fechar(self):
        if messagebox.askyesno(
            "SIGM",
            "Você já anotou a chave de recuperação?\n\n"
            "Ela não será mostrada novamente.",
            parent=self,
        ):
            self.destroy()


def mostrar_chave_recuperacao(master, chave, titulo="Chave de recuperação", aviso=""):
    """Abre a janela da chave e só retorna quando ela for fechada."""
    janela = ChaveRecuperacao(master, chave, titulo=titulo, aviso=aviso)
    master.wait_window(janela)


class RecuperarSenha(ctk.CTkToplevel):
    """Diálogo para redefinir a senha usando a chave de recuperação."""

    LIMITE_TENTATIVAS = 5

    def __init__(self, master, usuario_inicial="", ao_concluir=None):
        super().__init__(master)

        self.ao_concluir = ao_concluir
        self.tentativas = 0
        self.possui_chave = existe_chave_recuperacao()

        self.title("Recuperar senha - SIGM")
        self.geometry("500x610")
        self.resizable(False, False)
        self.configure(fg_color=cores.FUNDO)

        configurar_modal(self, master)
        _tentar_grab(self)

        self.criar_interface(usuario_inicial)

    def criar_interface(self, usuario_inicial):
        ctk.CTkLabel(
            self,
            text="Recuperar senha",
            font=("Segoe UI", 26, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(24, 6))

        ctk.CTkLabel(
            self,
            text=(
                "Informe seu usuário, a chave de recuperação do Administrador "
                "e escolha uma nova senha."
            ),
            font=("Segoe UI", 13),
            text_color=cores.CINZA,
            wraplength=420,
            justify="center",
        ).pack(padx=30, pady=(0, 12))

        if not self.possui_chave:
            ctk.CTkLabel(
                self,
                text=(
                    "Ainda não existe chave de recuperação neste computador.\n"
                    "Peça a um Administrador para redefinir sua senha em "
                    "Usuários → SENHA."
                ),
                font=("Segoe UI", 13, "bold"),
                text_color=cores.VERMELHO,
                wraplength=420,
                justify="center",
            ).pack(padx=30, pady=(0, 10))

        self.campo_usuario = self.criar_campo("Usuário")
        self.campo_chave = self.criar_campo("Chave de recuperação (XXXX-XXXX-XXXX-XXXX)")
        self.campo_nova = self.criar_campo("Nova senha", senha=True)
        self.campo_confirmar = self.criar_campo("Confirmar nova senha", senha=True)

        if usuario_inicial:
            self.campo_usuario.insert(0, usuario_inicial)

        self.mensagem = ctk.CTkLabel(
            self,
            text="",
            font=("Segoe UI", 13),
            text_color=cores.VERMELHO,
            wraplength=420,
            justify="center",
        )
        self.mensagem.pack(pady=(8, 4))

        self.botao_redefinir = ctk.CTkButton(
            self,
            text="REDEFINIR SENHA",
            width=380,
            height=44,
            corner_radius=8,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            font=fontes.BOTAO,
            command=self.redefinir,
            state="normal" if self.possui_chave else "disabled",
        )
        self.botao_redefinir.pack(pady=(8, 6))

        ctk.CTkButton(
            self,
            text="CANCELAR",
            width=380,
            height=38,
            corner_radius=8,
            fg_color=cores.CINZA,
            hover_color="#444444",
            command=self.destroy,
        ).pack(pady=(0, 16))

        self.campo_usuario.bind("<Return>", lambda event: self.campo_chave.focus_set())
        self.campo_chave.bind("<Return>", lambda event: self.campo_nova.focus_set())
        self.campo_nova.bind("<Return>", lambda event: self.campo_confirmar.focus_set())
        self.campo_confirmar.bind("<Return>", lambda event: self.redefinir())

        proximo = self.campo_chave if usuario_inicial else self.campo_usuario
        self.after(250, lambda: self.focar(proximo))

    def criar_campo(self, texto_guia, senha=False):
        opcoes = {"show": "•"} if senha else {}
        campo = ctk.CTkEntry(
            self,
            width=380,
            height=40,
            placeholder_text=texto_guia,
            font=fontes.TEXTO,
            **opcoes,
        )
        campo.pack(pady=6)
        return campo

    def focar(self, campo):
        try:
            if self.winfo_exists():
                campo.focus_set()
        except Exception:
            pass

    def exibir_mensagem(self, texto, cor):
        self.mensagem.configure(text=texto, text_color=cor)

    def redefinir(self):
        if not self.possui_chave:
            return

        if self.tentativas >= self.LIMITE_TENTATIVAS:
            self.exibir_mensagem(
                "Muitas tentativas. Feche e abra o SIGM para tentar de novo.",
                cores.VERMELHO,
            )
            return

        usuario = self.campo_usuario.get().strip()
        chave = self.campo_chave.get().strip()
        nova_senha = self.campo_nova.get().strip()
        confirmar = self.campo_confirmar.get().strip()

        if not usuario or not chave or not nova_senha or not confirmar:
            self.exibir_mensagem("Preencha todos os campos.", cores.VERMELHO)
            return

        if nova_senha != confirmar:
            self.exibir_mensagem("As senhas não conferem.", cores.VERMELHO)
            return

        sucesso, mensagem, dados = redefinir_senha_com_chave(usuario, chave, nova_senha)

        if not sucesso:
            self.tentativas += 1
            registrar_acao(
                "RECUPERACAO_SENHA_FALHA",
                f"Tentativa de recuperacao de senha recusada para o usuario {usuario}.",
                modulo="Autenticacao",
                usuario_login=usuario,
            )

            if self.tentativas >= self.LIMITE_TENTATIVAS:
                self.botao_redefinir.configure(state="disabled")
                self.exibir_mensagem(
                    "Muitas tentativas. Feche e abra o SIGM para tentar de novo.",
                    cores.VERMELHO,
                )
            else:
                self.exibir_mensagem(mensagem, cores.VERMELHO)
            return

        registrar_acao(
            "SENHA_REDEFINIDA_POR_CHAVE",
            f"Senha do usuario {dados['usuario']} redefinida pela chave de recuperacao.",
            modulo="Autenticacao",
            registro_id=dados["id"],
            usuario_login=dados["usuario"],
            usuario_nome=dados["nome"],
        )
        self.concluir(dados)

    def concluir(self, dados):
        messagebox.showinfo(
            "SIGM",
            "Senha redefinida com sucesso!\n\nEntre com a nova senha.",
            parent=self,
        )

        # A chave é de uso único: gera a próxima e mostra para ser guardada.
        nova_chave = None
        try:
            nova_chave = gerar_chave_recuperacao()
            registrar_acao(
                "CHAVE_RECUPERACAO_RENOVADA",
                "Chave de recuperacao renovada apos o uso.",
                modulo="Autenticacao",
                usuario_login=dados["usuario"],
            )
        except Exception:
            nova_chave = None

        if nova_chave:
            try:
                mostrar_chave_recuperacao(
                    self,
                    nova_chave,
                    titulo="Nova chave de recuperação",
                    aviso="A chave que você usou deixou de valer. Guarde esta nova chave.",
                )
            except Exception:
                messagebox.showinfo(
                    "SIGM",
                    f"Sua NOVA chave de recuperação é:\n\n{nova_chave}\n\n"
                    "Anote-a agora; ela não será mostrada novamente.",
                    parent=self,
                )

        retorno = self.ao_concluir
        self.destroy()
        if retorno:
            retorno(dados["usuario"])
