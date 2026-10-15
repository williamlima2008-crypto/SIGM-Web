from tkinter import messagebox

import customtkinter as ctk

from banco.database import (
    alterar_status_usuario,
    atualizar_usuario,
    buscar_usuario_por_id,
    cadastrar_usuario,
    excluir_usuario,
    listar_usuarios,
    redefinir_senha_usuario,
)
from componentes.cabecalho_igreja import CabecalhoIgreja
from config import cores, fontes
from servicos.recuperacao_senha import (
    data_chave_recuperacao,
    existe_chave_recuperacao,
    gerar_chave_recuperacao,
)
from telas.recuperar_senha import mostrar_chave_recuperacao
from utils.auditoria import registrar_acao
from utils.janelas import configurar_janela_principal, configurar_modal
from utils.sessao import usuario_eh_administrador


class Usuarios(ctk.CTkToplevel):
    LARGURA_PERFIL = 115
    LARGURA_STATUS = 95
    LARGURA_ACOES = 270

    def __init__(self, master):
        super().__init__(master)

        if not usuario_eh_administrador():
            messagebox.showwarning(
                "SIGM",
                "Apenas o Administrador pode acessar o gerenciamento de usuarios.",
                parent=master,
            )
            self.destroy()
            return

        self.title("Usuarios - SIGM")
        configurar_janela_principal(self, 1040, 660, 900, 580, master)
        self.configure(fg_color=cores.FUNDO)

        self.criar_interface()
        self.carregar_usuarios()

    def criar_interface(self):
        ctk.CTkLabel(
            self,
            text="Gerenciamento de Usuarios",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(24, 8))

        self.cabecalho_igreja = CabecalhoIgreja(self)
        self.cabecalho_igreja.pack(fill="x", padx=24, pady=(0, 12))

        frame_topo = ctk.CTkFrame(self, fg_color="transparent")
        frame_topo.pack(fill="x", padx=24, pady=(0, 12))

        ctk.CTkButton(
            frame_topo,
            text="NOVO USUARIO",
            width=150,
            height=38,
            fg_color=cores.VERDE,
            hover_color="#1F7A45",
            command=self.novo_usuario,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            frame_topo,
            text="ATUALIZAR",
            width=130,
            height=38,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            command=self.carregar_usuarios,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            frame_topo,
            text="CHAVE DE RECUPERAÇÃO",
            width=210,
            height=38,
            fg_color=cores.AMARELO,
            text_color=cores.PRETO,
            hover_color="#E0A800",
            command=self.abrir_chave_recuperacao,
        ).pack(side="left", padx=6)

        self.frame_lista = ctk.CTkScrollableFrame(self, corner_radius=10)
        self.frame_lista.pack(padx=24, pady=(0, 14), fill="both", expand=True)

        frame_rodape = ctk.CTkFrame(self, fg_color="transparent")
        frame_rodape.pack(fill="x", padx=24, pady=(0, 18))

        ctk.CTkButton(
            frame_rodape,
            text="FECHAR",
            width=130,
            height=38,
            fg_color=cores.CINZA,
            hover_color="#444444",
            command=self.destroy,
        ).pack(side="right", padx=8)

    def abrir_chave_recuperacao(self):
        if existe_chave_recuperacao():
            criada_em = data_chave_recuperacao()
            texto = (
                "Já existe uma chave de recuperação"
                + (f" (criada em {criada_em})" if criada_em else "")
                + ".\n\nGerar uma nova vai INVALIDAR a anterior.\n\nDeseja continuar?"
            )
        else:
            texto = (
                "Será gerada a chave de recuperação de senha.\n\n"
                "Com ela, a senha pode ser redefinida na tela de login caso seja "
                "esquecida. A chave aparece uma única vez - guarde em local seguro."
                "\n\nDeseja continuar?"
            )

        if not messagebox.askyesno("SIGM", texto, parent=self):
            return

        try:
            chave = gerar_chave_recuperacao()
        except Exception as erro:
            messagebox.showerror(
                "SIGM",
                f"Não foi possível gerar a chave de recuperação.\n\nErro: {erro}",
                parent=self,
            )
            return

        registrar_acao(
            "CHAVE_RECUPERACAO_GERADA",
            "Nova chave de recuperacao de senha gerada.",
            modulo="Usuarios",
        )
        mostrar_chave_recuperacao(self, chave)

    def carregar_usuarios(self):
        for widget in self.frame_lista.winfo_children():
            widget.destroy()

        usuarios = listar_usuarios()
        self.criar_cabecalho()

        for usuario in usuarios:
            self.criar_linha_usuario(usuario)

    def criar_cabecalho(self):
        linha = ctk.CTkFrame(
            self.frame_lista,
            fg_color=cores.AZUL_PRINCIPAL,
            corner_radius=8,
        )
        linha.pack(fill="x", padx=10, pady=(10, 5))
        self.configurar_grid_linha(linha)

        colunas = [
            ("Nome", 190),
            ("Login", 130),
            ("Perfil", self.LARGURA_PERFIL),
            ("Status", self.LARGURA_STATUS),
            ("Acoes", self.LARGURA_ACOES),
        ]

        for indice, (texto, largura) in enumerate(colunas):
            ctk.CTkLabel(
                linha,
                text=texto,
                width=largura,
                anchor="w",
                font=("Segoe UI", 12, "bold"),
                text_color=cores.BRANCO,
            ).grid(row=0, column=indice, padx=4, pady=8, sticky="ew")

    def criar_linha_usuario(self, usuario):
        linha = ctk.CTkFrame(self.frame_lista, fg_color=cores.BRANCO, corner_radius=8)
        linha.pack(fill="x", padx=10, pady=4)
        self.configurar_grid_linha(linha)

        valores = [
            self.encurtar_texto(usuario["nome"], 34),
            self.encurtar_texto(usuario["usuario"], 22),
            usuario["perfil"],
            usuario["status"],
        ]

        for indice, valor in enumerate(valores):
            ctk.CTkLabel(
                linha,
                text=valor or "-",
                anchor="w",
                font=("Segoe UI", 12),
                text_color=cores.PRETO if usuario["ativo"] else cores.VERMELHO,
            ).grid(row=0, column=indice, padx=4, pady=8, sticky="ew")

        frame_acoes = ctk.CTkFrame(linha, fg_color="transparent")
        frame_acoes.grid(row=0, column=4, padx=4, pady=6, sticky="ew")
        frame_acoes.configure(width=self.LARGURA_ACOES, height=32)
        frame_acoes.grid_propagate(False)

        texto_status = "BLOQUEAR" if usuario["ativo"] else "DESBLOQUEAR"
        acoes = [
            ("EDITAR", 58, lambda item=usuario: self.editar_usuario(item["id"]), cores.AZUL_PRINCIPAL, cores.AZUL_ESCURO),
            ("SENHA", 54, lambda item=usuario: self.redefinir_senha(item["id"]), cores.AZUL_PRINCIPAL, cores.AZUL_ESCURO),
            (texto_status, 84, lambda item=usuario: self.alternar_status(item), cores.VERDE if not usuario["ativo"] else cores.AMARELO, "#D39E00"),
            ("EXCLUIR", 64, lambda item=usuario: self.remover_usuario(item["id"]), cores.VERMELHO, "#A71D2A"),
        ]

        for texto, largura, comando, cor, hover in acoes:
            ctk.CTkButton(
                frame_acoes,
                text=texto,
                width=largura,
                height=30,
                fg_color=cor,
                hover_color=hover,
                font=("Segoe UI", 10, "bold"),
                text_color=cores.PRETO if cor == cores.AMARELO else cores.BRANCO,
                command=comando,
            ).pack(side="left", padx=1)

    def configurar_grid_linha(self, linha):
        linha.grid_columnconfigure(0, minsize=120, weight=2)
        linha.grid_columnconfigure(1, minsize=90, weight=1)
        linha.grid_columnconfigure(2, minsize=self.LARGURA_PERFIL, weight=0)
        linha.grid_columnconfigure(3, minsize=self.LARGURA_STATUS, weight=0)
        linha.grid_columnconfigure(4, minsize=self.LARGURA_ACOES, weight=0)

    @staticmethod
    def encurtar_texto(valor, limite):
        texto = str(valor or "")
        if len(texto) <= limite:
            return texto
        return f"{texto[:limite - 3]}..."

    def novo_usuario(self):
        dados = self.solicitar_dados_usuario(titulo="Novo Usuario")
        if not dados:
            return

        try:
            id_usuario = cadastrar_usuario(
                dados["nome"],
                dados["usuario"],
                dados["senha"],
                dados["perfil"],
            )
            registrar_acao(
                "USUARIO_CRIADO",
                f"Usuario {dados['usuario']} criado.",
                modulo="Usuarios",
                registro_id=id_usuario,
            )
            self.carregar_usuarios()
            messagebox.showinfo("SIGM", "Usuario cadastrado com sucesso.", parent=self)
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel cadastrar o usuario.\n\nErro: {erro}",
                parent=self,
            )

    def editar_usuario(self, id_usuario):
        usuario = buscar_usuario_por_id(id_usuario)
        if not usuario:
            messagebox.showerror("SIGM", "Usuario nao encontrado.", parent=self)
            return

        dados = self.solicitar_dados_usuario(
            titulo="Editar Usuario",
            usuario=usuario,
            exigir_senha=False,
        )
        if not dados:
            return

        try:
            atualizar_usuario(
                id_usuario,
                dados["nome"],
                dados["usuario"],
                dados["perfil"],
                dados["ativo"],
            )
            registrar_acao(
                "USUARIO_EDITADO",
                f"Usuario {dados['usuario']} editado.",
                modulo="Usuarios",
                registro_id=id_usuario,
            )
            if int(usuario["ativo"]) != int(dados["ativo"]):
                registrar_acao(
                    "USUARIO_DESBLOQUEADO" if dados["ativo"] else "USUARIO_BLOQUEADO",
                    f"Usuario {dados['usuario']} foi {'desbloqueado' if dados['ativo'] else 'bloqueado'}.",
                    modulo="Usuarios",
                    registro_id=id_usuario,
                )
            self.carregar_usuarios()
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel atualizar o usuario.\n\nErro: {erro}",
                parent=self,
            )

    def redefinir_senha(self, id_usuario):
        nova_senha = self.solicitar_senha()
        if not nova_senha:
            return

        try:
            redefinir_senha_usuario(id_usuario, nova_senha)
            usuario = buscar_usuario_por_id(id_usuario) or {}
            registrar_acao(
                "SENHA_REDEFINIDA",
                f"Senha do usuario {usuario.get('usuario') or id_usuario} foi redefinida.",
                modulo="Usuarios",
                registro_id=id_usuario,
            )
            messagebox.showinfo("SIGM", "Senha redefinida com sucesso.", parent=self)
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel redefinir a senha.\n\nErro: {erro}",
                parent=self,
            )

    def alternar_status(self, usuario):
        novo_status = 0 if usuario["ativo"] else 1
        acao = "bloquear" if novo_status == 0 else "desbloquear"

        confirmar = messagebox.askyesno(
            "Confirmar",
            f"Deseja {acao} este usuario?",
            parent=self,
        )
        if not confirmar:
            return

        try:
            alterar_status_usuario(usuario["id"], novo_status)
            registrar_acao(
                "USUARIO_BLOQUEADO" if novo_status == 0 else "USUARIO_DESBLOQUEADO",
                f"Usuario {usuario.get('usuario') or usuario.get('nome') or usuario['id']} foi {'bloqueado' if novo_status == 0 else 'desbloqueado'}.",
                modulo="Usuarios",
                registro_id=usuario["id"],
            )
            self.carregar_usuarios()
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel alterar o status.\n\nErro: {erro}",
                parent=self,
            )

    def remover_usuario(self, id_usuario):
        confirmar = messagebox.askyesno(
            "Confirmar exclusao",
            "Deseja excluir este usuario?",
            parent=self,
        )
        if not confirmar:
            return

        try:
            usuario = buscar_usuario_por_id(id_usuario) or {}
            excluir_usuario(id_usuario)
            registrar_acao(
                "USUARIO_EXCLUIDO",
                f"Usuario {usuario.get('usuario') or id_usuario} excluido.",
                modulo="Usuarios",
                registro_id=id_usuario,
            )
            self.carregar_usuarios()
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel excluir o usuario.\n\nErro: {erro}",
                parent=self,
            )

    def solicitar_dados_usuario(self, titulo, usuario=None, exigir_senha=True):
        janela = ctk.CTkToplevel(self)
        janela.title(f"{titulo} - SIGM")
        janela.geometry("460x430" if exigir_senha else "460x390")
        janela.resizable(False, False)
        janela.configure(fg_color=cores.FUNDO)
        configurar_modal(janela, self)
        janela.grab_set()

        resultado = {"dados": None}

        ctk.CTkLabel(
            janela,
            text=titulo,
            font=fontes.SUBTITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(22, 12))

        frame = ctk.CTkFrame(janela, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=(0, 10))
        frame.grid_columnconfigure(1, weight=1)

        nome = self.criar_entrada_modal(frame, "Nome:", 0, usuario["nome"] if usuario else "")
        login = self.criar_entrada_modal(frame, "Login:", 1, usuario["usuario"] if usuario else "")

        senha = None
        linha_atual = 2
        if exigir_senha:
            senha = self.criar_entrada_modal(frame, "Senha:", linha_atual, "", show="*")
            linha_atual += 1

        ctk.CTkLabel(frame, text="Perfil:", anchor="w").grid(row=linha_atual, column=0, sticky="w", pady=8)
        perfil = ctk.CTkComboBox(frame, values=["Administrador", "Usuario"])
        perfil.set(usuario["perfil"] if usuario else "Usuario")
        perfil.grid(row=linha_atual, column=1, sticky="ew", pady=8)
        linha_atual += 1

        ctk.CTkLabel(frame, text="Status:", anchor="w").grid(row=linha_atual, column=0, sticky="w", pady=8)
        status = ctk.CTkComboBox(frame, values=["Ativo", "Bloqueado"])
        status.set("Ativo" if not usuario or usuario["ativo"] else "Bloqueado")
        status.grid(row=linha_atual, column=1, sticky="ew", pady=8)

        def confirmar():
            dados = {
                "nome": nome.get().strip(),
                "usuario": login.get().strip(),
                "senha": senha.get().strip() if senha else "",
                "perfil": perfil.get().strip(),
                "ativo": 1 if status.get() == "Ativo" else 0,
            }

            if not dados["nome"] or not dados["usuario"]:
                messagebox.showwarning("SIGM", "Informe nome e login.", parent=janela)
                return

            if exigir_senha and not dados["senha"]:
                messagebox.showwarning("SIGM", "Informe a senha.", parent=janela)
                return

            resultado["dados"] = dados
            janela.destroy()

        frame_botoes = ctk.CTkFrame(janela, fg_color="transparent")
        frame_botoes.pack(fill="x", padx=24, pady=(0, 18))

        ctk.CTkButton(
            frame_botoes,
            text="SALVAR",
            width=120,
            fg_color=cores.VERDE,
            hover_color="#1F7A45",
            command=confirmar,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            frame_botoes,
            text="CANCELAR",
            width=120,
            fg_color=cores.CINZA,
            hover_color="#444444",
            command=janela.destroy,
        ).pack(side="right", padx=6)

        self.wait_window(janela)
        return resultado["dados"]

    def criar_entrada_modal(self, frame, rotulo, linha, valor="", show=None):
        ctk.CTkLabel(frame, text=rotulo, anchor="w").grid(row=linha, column=0, sticky="w", pady=8)
        entrada = ctk.CTkEntry(frame, show=show)
        entrada.insert(0, valor or "")
        entrada.grid(row=linha, column=1, sticky="ew", pady=8)
        return entrada

    def solicitar_senha(self):
        janela = ctk.CTkToplevel(self)
        janela.title("Redefinir Senha - SIGM")
        janela.geometry("420x230")
        janela.resizable(False, False)
        janela.configure(fg_color=cores.FUNDO)
        configurar_modal(janela, self)
        janela.grab_set()

        resultado = {"senha": None}

        ctk.CTkLabel(
            janela,
            text="Redefinir Senha",
            font=fontes.SUBTITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(22, 12))

        senha = ctk.CTkEntry(janela, width=320, show="*", placeholder_text="Nova senha")
        senha.pack(pady=8)

        confirmar = ctk.CTkEntry(janela, width=320, show="*", placeholder_text="Confirmar senha")
        confirmar.pack(pady=8)

        def salvar():
            if not senha.get().strip():
                messagebox.showwarning("SIGM", "Informe a nova senha.", parent=janela)
                return

            if senha.get().strip() != confirmar.get().strip():
                messagebox.showwarning("SIGM", "As senhas nao conferem.", parent=janela)
                return

            resultado["senha"] = senha.get().strip()
            janela.destroy()

        frame_botoes = ctk.CTkFrame(janela, fg_color="transparent")
        frame_botoes.pack(fill="x", padx=46, pady=(8, 0))

        ctk.CTkButton(
            frame_botoes,
            text="SALVAR",
            width=110,
            fg_color=cores.VERDE,
            hover_color="#1F7A45",
            command=salvar,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            frame_botoes,
            text="CANCELAR",
            width=110,
            fg_color=cores.CINZA,
            hover_color="#444444",
            command=janela.destroy,
        ).pack(side="right", padx=4)

        self.wait_window(janela)
        return resultado["senha"]
