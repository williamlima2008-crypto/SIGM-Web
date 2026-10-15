from pathlib import Path
from tkinter import messagebox
import os

import customtkinter as ctk

from banco.database import listar_documentos_emitidos, total_documentos_emitidos
from componentes.cabecalho_igreja import CabecalhoIgreja
from config import cores, fontes
from documentos.gerar_documentos import TIPOS_DOCUMENTOS_OFICIAIS_EDITAVEIS
from telas.documentos.historico_documentos import HistoricoDocumentos
from utils.formatadores import formatar_data_hora, normalizar_texto_busca
from utils.janelas import configurar_janela_principal


class CentralDocumentos(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)

        self.documentos = []
        self.termo_pesquisa = ctk.StringVar(value="")
        self.janela_historico = None

        self.title("Central de Documentos - SIGM")
        configurar_janela_principal(self, 1080, 700, 920, 600, master)
        self.configure(fg_color=cores.FUNDO)

        self.criar_interface()
        self.carregar_documentos()

    def criar_interface(self):
        ctk.CTkLabel(
            self,
            text="Central de Documentos",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(22, 8))

        CabecalhoIgreja(self).pack(fill="x", padx=24, pady=(0, 12))

        painel = ctk.CTkFrame(self, fg_color=cores.BRANCO, corner_radius=8)
        painel.pack(fill="x", padx=24, pady=(0, 12))
        painel.grid_columnconfigure((0, 1), weight=1)

        oficiais = "\n".join(f"- {nome}" for nome in TIPOS_DOCUMENTOS_OFICIAIS_EDITAVEIS)
        self.criar_bloco(painel, "Documentos oficiais disponiveis", oficiais).grid(
            row=0, column=0, padx=12, pady=12, sticky="nsew"
        )
        self.bloco_total = self.criar_bloco(painel, "Total de documentos emitidos", "0")
        self.bloco_total.grid(row=0, column=1, padx=12, pady=12, sticky="nsew")

        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", padx=24, pady=(0, 10))
        barra.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            barra,
            text="Pesquisar:",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")

        self.entrada_pesquisa = ctk.CTkEntry(
            barra,
            textvariable=self.termo_pesquisa,
            height=34,
        )
        self.entrada_pesquisa.grid(row=0, column=1, sticky="ew")
        self.termo_pesquisa.trace_add("write", lambda *_args: self.renderizar_documentos())

        self.frame_lista = ctk.CTkScrollableFrame(self, corner_radius=8)
        self.frame_lista.pack(fill="both", expand=True, padx=24, pady=(0, 12))

        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.pack(fill="x", padx=24, pady=(0, 18))

        self.botao(rodape, "HISTORICO GERAL", self.abrir_historico).pack(side="left", padx=5)
        self.botao(rodape, "LOCALIZAR DOCUMENTOS", self.focar_pesquisa).pack(side="left", padx=5)
        self.botao(rodape, "ATUALIZAR", self.carregar_documentos).pack(side="left", padx=5)
        self.botao(rodape, "FECHAR", self.destroy, cor=cores.CINZA, hover="#444444").pack(side="right", padx=5)

    def criar_bloco(self, master, titulo, texto):
        bloco = ctk.CTkFrame(master, fg_color=cores.FUNDO, corner_radius=8)
        ctk.CTkLabel(
            bloco,
            text=titulo,
            font=("Segoe UI", 14, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(12, 4))
        label = ctk.CTkLabel(
            bloco,
            text=texto,
            font=("Segoe UI", 13),
            text_color=cores.PRETO,
            justify="left",
            anchor="w",
        )
        label.pack(fill="x", padx=14, pady=(0, 12))
        bloco.valor_label = label
        return bloco

    def carregar_documentos(self):
        self.documentos = listar_documentos_emitidos()
        self.bloco_total.valor_label.configure(text=str(total_documentos_emitidos()))
        self.renderizar_documentos()

    def documentos_filtrados(self):
        termo = normalizar_texto_busca(self.termo_pesquisa.get())
        if not termo:
            return self.documentos[:20]

        filtrados = []
        for documento in self.documentos:
            texto = " ".join(
                str(documento.get(chave) or "")
                for chave in ("tipo_documento", "titulo_documento", "caminho_arquivo", "usuario_emissor")
            )
            if termo in normalizar_texto_busca(texto):
                filtrados.append(documento)
        return filtrados[:50]

    def renderizar_documentos(self):
        for widget in self.frame_lista.winfo_children():
            widget.destroy()

        documentos = self.documentos_filtrados()
        if not documentos:
            ctk.CTkLabel(
                self.frame_lista,
                text="Nenhum documento emitido encontrado.",
                font=fontes.TEXTO,
                text_color=cores.CINZA,
            ).pack(pady=28)
            return

        for documento in documentos:
            self.criar_linha(documento).pack(fill="x", padx=10, pady=5)

    def criar_linha(self, documento):
        linha = ctk.CTkFrame(self.frame_lista, fg_color=cores.BRANCO, corner_radius=8)
        linha.grid_columnconfigure(0, weight=1)

        caminho = Path(documento.get("caminho_arquivo") or "")
        titulo = documento.get("titulo_documento") or documento.get("tipo_documento") or "Documento"
        detalhe = f"{formatar_data_hora(documento.get('data_emissao'))} | {caminho.name or '-'}"

        ctk.CTkLabel(
            linha,
            text=titulo,
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
            anchor="w",
        ).grid(row=0, column=0, padx=12, pady=(9, 0), sticky="ew")
        ctk.CTkLabel(
            linha,
            text=detalhe,
            font=("Segoe UI", 11),
            text_color=cores.CINZA,
            anchor="w",
        ).grid(row=1, column=0, padx=12, pady=(0, 9), sticky="ew")
        self.botao(
            linha,
            "ABRIR",
            lambda item=documento: self.abrir_documento(item),
            largura=88,
            estado="normal" if caminho.exists() and caminho.is_file() else "disabled",
        ).grid(row=0, column=1, rowspan=2, padx=12, pady=8)
        return linha

    def abrir_documento(self, documento):
        caminho = Path(documento.get("caminho_arquivo") or "")
        if not caminho.exists() or not caminho.is_file():
            messagebox.showerror("SIGM", "Arquivo nao encontrado.", parent=self)
            return
        os.startfile(caminho)

    def abrir_historico(self):
        if self.janela_historico is not None and self.janela_historico.winfo_exists():
            self.janela_historico.lift()
            self.janela_historico.focus_force()
            return
        self.janela_historico = HistoricoDocumentos(self, None, "Todos os membros")

    def focar_pesquisa(self):
        self.entrada_pesquisa.focus_set()

    def botao(self, master, texto, comando, cor=None, hover=None, largura=150, estado="normal"):
        return ctk.CTkButton(
            master,
            text=texto,
            width=largura,
            height=36,
            fg_color=cor or cores.AZUL_PRINCIPAL,
            hover_color=hover or cores.AZUL_ESCURO,
            font=("Segoe UI", 12, "bold"),
            command=comando,
            state=estado,
        )
