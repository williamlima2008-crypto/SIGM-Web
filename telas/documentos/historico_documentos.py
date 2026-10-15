import os
import subprocess
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from banco.database import (
    excluir_registro_documento,
    listar_documentos_emitidos,
    listar_documentos_emitidos_por_membro,
)
from componentes.cabecalho_igreja import CabecalhoIgreja
from config import cores, fontes
from utils.auditoria import registrar_acao
from utils.formatadores import formatar_data_hora, normalizar_texto_busca
from utils.janelas import configurar_janela_principal


class HistoricoDocumentos(ctk.CTkToplevel):
    LARGURA_DATA = 120
    LARGURA_USUARIO = 120
    LARGURA_SITUACAO = 145
    LARGURA_ACOES = 285

    def __init__(self, master, id_membro=None, nome_membro="Todos os membros"):
        super().__init__(master)

        self.id_membro = id_membro
        self.nome_membro = nome_membro or "Todos os membros"
        self.documentos = []
        self.termo_pesquisa = ctk.StringVar(value="")

        self.title("Histórico de Documentos - SIGM")
        configurar_janela_principal(self, 1120, 680, 960, 580, master)
        self.configure(fg_color=cores.FUNDO)

        self.criar_interface()
        self.carregar_documentos()

    def criar_interface(self):
        ctk.CTkLabel(
            self,
            text="Histórico de Documentos",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(24, 4))

        self.cabecalho_igreja = CabecalhoIgreja(self)
        self.cabecalho_igreja.pack(fill="x", padx=24, pady=(0, 10))

        ctk.CTkLabel(
            self,
            text=self.nome_membro,
            font=("Segoe UI", 15, "bold"),
            text_color=cores.PRETO,
        ).pack(pady=(0, 14))

        frame_pesquisa = ctk.CTkFrame(self, fg_color="transparent")
        frame_pesquisa.pack(fill="x", padx=34, pady=(0, 10))
        frame_pesquisa.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            frame_pesquisa,
            text="Pesquisar documentos:",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=0, column=0, padx=(0, 10), sticky="w")

        entrada_pesquisa = ctk.CTkEntry(
            frame_pesquisa,
            textvariable=self.termo_pesquisa,
            height=34,
        )
        entrada_pesquisa.grid(row=0, column=1, sticky="ew")
        self.termo_pesquisa.trace_add("write", self.ao_pesquisar)

        self.frame_lista = ctk.CTkScrollableFrame(self, corner_radius=10)
        self.frame_lista.pack(
            padx=24,
            pady=(0, 14),
            fill="both",
            expand=True,
        )

        frame_botoes = ctk.CTkFrame(self, fg_color="transparent")
        frame_botoes.pack(fill="x", padx=24, pady=(0, 18))

        ctk.CTkButton(
            frame_botoes,
            text="ATUALIZAR",
            width=130,
            height=38,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            command=self.carregar_documentos,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            frame_botoes,
            text="FECHAR",
            width=130,
            height=38,
            fg_color=cores.CINZA,
            hover_color="#444444",
            command=self.destroy,
        ).pack(side="right", padx=8)

    def carregar_documentos(self):
        if self.id_membro is None:
            self.documentos = listar_documentos_emitidos()
        else:
            self.documentos = listar_documentos_emitidos_por_membro(self.id_membro)
        self.renderizar_documentos()

    def ao_pesquisar(self, *_args):
        self.renderizar_documentos()

    def renderizar_documentos(self):
        for widget in self.frame_lista.winfo_children():
            widget.destroy()

        if not self.documentos:
            ctk.CTkLabel(
                self.frame_lista,
                text="Nenhum documento emitido para este membro.",
                font=fontes.TEXTO,
                text_color=cores.CINZA,
            ).pack(pady=34)
            return

        documentos = self.filtrar_documentos()
        if not documentos:
            ctk.CTkLabel(
                self.frame_lista,
                text="Nenhum documento encontrado.",
                font=fontes.TEXTO,
                text_color=cores.CINZA,
            ).pack(pady=34)
            return

        self.criar_cabecalho()

        for documento in documentos:
            self.criar_linha_documento(documento)

    def filtrar_documentos(self):
        termo = self.normalizar_texto(self.termo_pesquisa.get())
        if not termo:
            return self.documentos

        documentos_filtrados = []
        for documento in self.documentos:
            texto_busca = " ".join(
                (
                    documento.get("tipo_documento") or "",
                    documento.get("titulo_documento") or "",
                    Path(documento.get("caminho_arquivo") or "").name,
                    documento.get("usuario_emissor") or "",
                    self.formatar_data(documento.get("data_emissao")),
                    self.obter_situacao(documento),
                )
            )

            if termo in self.normalizar_texto(texto_busca):
                documentos_filtrados.append(documento)

        return documentos_filtrados

    def criar_cabecalho(self):
        cabecalho = ctk.CTkFrame(
            self.frame_lista,
            fg_color=cores.AZUL_PRINCIPAL,
            corner_radius=8,
        )
        cabecalho.pack(fill="x", padx=10, pady=(10, 5))
        self.configurar_grid_linha(cabecalho)

        colunas = [
            ("Data e hora", self.LARGURA_DATA),
            ("Documento", 100),
            ("Usuário", self.LARGURA_USUARIO),
            ("Situação", self.LARGURA_SITUACAO),
            ("Ações", self.LARGURA_ACOES),
        ]

        for indice, (titulo, largura) in enumerate(colunas):
            ctk.CTkLabel(
                cabecalho,
                text=titulo,
                width=largura,
                text_color=cores.BRANCO,
                font=("Segoe UI", 12, "bold"),
                anchor="w",
            ).grid(row=0, column=indice, padx=4, pady=8, sticky="ew")

    def criar_linha_documento(self, documento):
        caminho_texto = documento.get("caminho_arquivo") or ""
        caminho = Path(caminho_texto)
        arquivo_disponivel = self.arquivo_disponivel(documento)
        nome_arquivo = caminho.name if caminho_texto else "-"
        situacao = self.obter_situacao(documento)
        cor_texto = cores.PRETO if arquivo_disponivel else cores.VERMELHO

        linha = ctk.CTkFrame(
            self.frame_lista,
            fg_color=cores.BRANCO,
            corner_radius=8,
        )
        linha.pack(fill="x", padx=10, pady=4)
        self.configurar_grid_linha(linha)

        ctk.CTkLabel(
            linha,
            text=self.formatar_data(documento.get("data_emissao")),
            width=self.LARGURA_DATA,
            anchor="w",
            font=("Segoe UI", 12),
            text_color=cor_texto,
        ).grid(row=0, column=0, padx=4, pady=8, sticky="w")

        frame_documento = ctk.CTkFrame(linha, fg_color="transparent")
        frame_documento.grid(row=0, column=1, padx=4, pady=7, sticky="ew")
        frame_documento.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame_documento,
            text=documento.get("titulo_documento") or documento.get("tipo_documento") or "-",
            anchor="w",
            font=("Segoe UI", 12, "bold"),
            text_color=cor_texto,
        ).grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            frame_documento,
            text=self.encurtar_nome_arquivo(nome_arquivo),
            anchor="w",
            font=("Segoe UI", 10),
            text_color=cores.CINZA,
        ).grid(row=1, column=0, sticky="ew")

        ctk.CTkLabel(
            linha,
            text=documento.get("usuario_emissor") or "-",
            width=self.LARGURA_USUARIO,
            anchor="w",
            font=("Segoe UI", 12),
            text_color=cor_texto,
        ).grid(row=0, column=2, padx=4, pady=8, sticky="w")

        ctk.CTkLabel(
            linha,
            text=situacao,
            width=self.LARGURA_SITUACAO,
            anchor="w",
            font=("Segoe UI", 12),
            text_color=cor_texto,
        ).grid(row=0, column=3, padx=4, pady=8, sticky="w")

        frame_acoes = ctk.CTkFrame(linha, fg_color="transparent")
        frame_acoes.grid(row=0, column=4, padx=4, pady=6, sticky="ew")
        frame_acoes.grid_propagate(False)
        frame_acoes.configure(width=self.LARGURA_ACOES, height=34)

        acoes = [
            (
                "ABRIR",
                56,
                lambda doc=documento: self.abrir_documento(doc),
                arquivo_disponivel,
                cores.AZUL_PRINCIPAL,
                cores.AZUL_ESCURO,
            ),
            (
                "IMPRIMIR",
                72,
                lambda doc=documento: self.reimprimir_documento(doc),
                arquivo_disponivel,
                cores.VERDE,
                "#1F7A45",
            ),
            (
                "PASTA",
                56,
                lambda doc=documento: self.abrir_pasta_documento(doc),
                arquivo_disponivel,
                cores.AZUL_PRINCIPAL,
                cores.AZUL_ESCURO,
            ),
            (
                "EXCLUIR",
                68,
                lambda doc=documento: self.excluir_documento(doc),
                True,
                cores.VERMELHO,
                "#A71D2A",
            ),
        ]

        for texto, largura, comando, habilitado, cor, hover in acoes:
            ctk.CTkButton(
                frame_acoes,
                text=texto,
                width=largura,
                height=30,
                fg_color=cor,
                hover_color=hover,
                font=("Segoe UI", 10, "bold"),
                state="normal" if habilitado else "disabled",
                command=comando,
            ).pack(side="left", padx=2)

    def configurar_grid_linha(self, linha):
        linha.grid_columnconfigure(0, minsize=self.LARGURA_DATA, weight=0)
        linha.grid_columnconfigure(1, minsize=160, weight=1)
        linha.grid_columnconfigure(2, minsize=self.LARGURA_USUARIO, weight=0)
        linha.grid_columnconfigure(3, minsize=self.LARGURA_SITUACAO, weight=0)
        linha.grid_columnconfigure(4, minsize=self.LARGURA_ACOES, weight=0)

    def arquivo_disponivel(self, documento):
        caminho = Path(documento.get("caminho_arquivo") or "")
        return caminho.exists() and caminho.is_file()

    def obter_situacao(self, documento):
        if self.arquivo_disponivel(documento):
            return "Disponível"
        return "Arquivo não encontrado"

    @staticmethod
    def encurtar_nome_arquivo(nome_arquivo):
        texto = str(nome_arquivo or "-")
        limite = 54
        if len(texto) <= limite:
            return texto
        return f"{texto[:24]}...{texto[-24:]}"

    def obter_caminho_existente(self, documento):
        caminho = Path(documento.get("caminho_arquivo") or "")
        if caminho.exists() and caminho.is_file():
            return caminho

        messagebox.showerror(
            "SIGM",
            "Arquivo não encontrado.",
            parent=self,
        )
        return None

    def abrir_documento(self, documento):
        caminho = self.obter_caminho_existente(documento)
        if caminho is None:
            return

        try:
            os.startfile(caminho)
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Não foi possível abrir o PDF.\n\nErro: {erro}",
                parent=self,
            )

    def reimprimir_documento(self, documento):
        caminho = self.obter_caminho_existente(documento)
        if caminho is None:
            return

        try:
            os.startfile(caminho, "print")
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Não foi possível enviar o PDF para impressão.\n\nErro: {erro}",
                parent=self,
            )
            return

        registrar_acao(
            "PDF_IMPRESSAO",
            f"{documento.get('titulo_documento') or documento.get('tipo_documento') or 'Documento'} enviado para impressao.",
            modulo="Documentos",
            registro_id=documento.get("id"),
            detalhes=f"Arquivo: {caminho}",
        )

    def abrir_pasta_documento(self, documento):
        caminho = self.obter_caminho_existente(documento)
        if caminho is None:
            return

        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", f"/select,{caminho}"])
            else:
                os.startfile(caminho.parent)
        except Exception:
            try:
                os.startfile(caminho.parent)
            except Exception as erro:
                messagebox.showerror(
                    "Erro no SIGM",
                    f"Não foi possível abrir a pasta.\n\nErro: {erro}",
                    parent=self,
                )

    def excluir_documento(self, documento):
        confirmar = messagebox.askyesno(
            "Confirmar exclusão",
            (
                "Deseja excluir este registro do histórico?\n"
                "O arquivo PDF continuará salvo no computador."
            ),
            parent=self,
        )

        if not confirmar:
            return

        try:
            excluir_registro_documento(documento["id"])
            registrar_acao(
                "HISTORICO_DOCUMENTO_EXCLUIDO",
                f"Registro do historico excluido: {documento.get('titulo_documento') or documento.get('tipo_documento') or 'Documento'}.",
                modulo="Documentos",
                registro_id=documento.get("id"),
                detalhes=f"Arquivo: {documento.get('caminho_arquivo') or ''}",
            )
            self.carregar_documentos()
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Não foi possível excluir o registro.\n\nErro: {erro}",
                parent=self,
            )

    @staticmethod
    def formatar_data(valor):
        return formatar_data_hora(valor)

    @staticmethod
    def normalizar_texto(valor):
        return normalizar_texto_busca(valor)
