"""
==========================================================
SIGM - Sistema de Gestão de Membros

Arquivo: editor_carta_recomendacao.py
Descrição: Editor completo da Carta de Recomendação, no mesmo padrão
visual dos outros editores de documentos (Ficha Cadastral, Pedido de
Membramento, Pedido de Reconciliação) - título, cabeçalho da igreja,
seções com campos editáveis e barra de botões.

Diferente dos outros editores, este não herda de BaseEditorDocumento
(que é construído em torno de PDFs escaneados com campos de
formulário/AcroForm) - a Carta de Recomendação é gerada sobrepondo
texto a uma foto/digitalização do formulário
(documentos/carta_recomendacao_pdf.py), então este editor apenas
coleta os valores dos campos e repassa para essa geração.

Desenvolvido por:
William Lima

"Servindo à Igreja com organização e excelência."
==========================================================
"""
import os
from tkinter import messagebox

import customtkinter as ctk

from componentes.cabecalho_igreja import CabecalhoIgreja
from config import cores, fontes
from documentos.integrador_documentos import montar_dados_documento
from utils.janelas import configurar_janela_principal

CAMPOS_CARTA_RECOMENDACAO = [
    ("nome_membro", "Nome do membro"),
    ("cargo", "Cargo"),
    ("sexo", "Sexo"),
    ("setor_campo", "Setor n."),
    ("congregacao", "Congregação"),
]


class EditorCartaRecomendacao(ctk.CTkToplevel):
    """Editor completo da Carta de Recomendação, com todos os campos editáveis."""

    def __init__(self, master, id_membro, ao_gerar=None):
        super().__init__(master)

        self.id_membro = id_membro
        self.ao_gerar = ao_gerar
        self.campos = {}

        self.title("Editor da Carta de Recomendação - SIGM")
        configurar_janela_principal(self, 900, 720, 820, 620, master)
        self.configure(fg_color=cores.FUNDO)

        self.criar_interface()
        self.carregar_dados_iniciais()

    def criar_interface(self):
        ctk.CTkLabel(
            self,
            text="Carta de Recomendação",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(24, 8))

        self.cabecalho_igreja = CabecalhoIgreja(self)
        self.cabecalho_igreja.pack(fill="x", padx=28, pady=(0, 10))

        self.frame_formulario = ctk.CTkScrollableFrame(self, corner_radius=10)
        self.frame_formulario.pack(padx=28, pady=(8, 10), fill="both", expand=True)

        self.criar_campos()
        self.criar_botoes()

    def criar_secao(self, titulo):
        secao = ctk.CTkFrame(self.frame_formulario, fg_color="transparent")
        secao.pack(fill="x", padx=8, pady=(12, 4))

        ctk.CTkLabel(
            secao,
            text=titulo,
            anchor="w",
            font=("Segoe UI", 15, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(fill="x", padx=6, pady=(0, 4))

        return secao

    def criar_campo_texto(self, chave, rotulo, parent=None):
        container = parent or self.frame_formulario
        linha = ctk.CTkFrame(container, fg_color=cores.BRANCO, corner_radius=8)
        linha.pack(fill="x", padx=14, pady=5)
        linha.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            linha,
            text=rotulo,
            width=190,
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=0, column=0, padx=(12, 8), pady=9, sticky="w")

        entrada = ctk.CTkEntry(linha, height=34)
        entrada.grid(row=0, column=1, padx=(0, 12), pady=9, sticky="ew")
        self.campos[chave] = entrada
        return entrada

    def criar_campo_multilinha(self, chave, rotulo, altura=100, parent=None):
        container = parent or self.frame_formulario
        bloco = ctk.CTkFrame(container, fg_color=cores.BRANCO, corner_radius=8)
        bloco.pack(fill="x", padx=14, pady=5)

        ctk.CTkLabel(
            bloco,
            text=rotulo,
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(fill="x", padx=12, pady=(10, 3))

        texto = ctk.CTkTextbox(bloco, height=altura)
        texto.pack(fill="x", padx=12, pady=(0, 12))
        self.campos[chave] = texto
        return texto

    def criar_campos(self):
        secao_membro = self.criar_secao("Dados do Membro")
        for chave, rotulo in CAMPOS_CARTA_RECOMENDACAO:
            self.criar_campo_texto(chave, rotulo, parent=secao_membro)

        secao_apresentacao = self.criar_secao("Apresentação")
        self.criar_campo_multilinha(
            "apresentar_em", "Apresentamos à Assembléia de Deus em:",
            altura=90, parent=secao_apresentacao,
        )

        ctk.CTkLabel(
            secao_apresentacao,
            text=(
                "Sexo e o destino da apresentação não vêm do cadastro do membro - "
                "preencha manualmente se quiser que apareçam no PDF."
            ),
            anchor="w",
            font=("Segoe UI", 11),
            text_color=cores.CINZA,
            wraplength=760,
            justify="left",
        ).pack(fill="x", padx=14, pady=(2, 10))

    def criar_botoes(self):
        frame_botoes = ctk.CTkFrame(self, fg_color="transparent")
        frame_botoes.pack(fill="x", padx=24, pady=(0, 18))

        ctk.CTkButton(
            frame_botoes,
            text="GERAR PDF",
            width=170,
            height=38,
            fg_color=cores.VERDE,
            hover_color="#1F7A45",
            command=self.gerar,
        ).grid(row=0, column=0, padx=8)

        ctk.CTkButton(
            frame_botoes,
            text="CANCELAR",
            width=130,
            height=38,
            fg_color=cores.CINZA,
            hover_color="#444444",
            command=self.destroy,
        ).grid(row=0, column=1, padx=8)

    def carregar_dados_iniciais(self):
        dados = montar_dados_documento(self.id_membro)
        for chave, campo in self.campos.items():
            valor = str(dados.get(chave) or "")
            if isinstance(campo, ctk.CTkTextbox):
                campo.delete("1.0", "end")
                campo.insert("1.0", valor)
            else:
                campo.delete(0, "end")
                campo.insert(0, valor)

    def coletar_dados(self):
        dados = {}
        for chave, campo in self.campos.items():
            if isinstance(campo, ctk.CTkTextbox):
                dados[chave] = campo.get("1.0", "end").strip()
            else:
                dados[chave] = campo.get().strip()
        return dados

    def gerar(self):
        dados = self.coletar_dados()
        apresentar_em = dados.pop("apresentar_em", "")

        if not self.ao_gerar:
            messagebox.showerror("SIGM", "Não foi possível gerar o documento.")
            return

        try:
            self.ao_gerar(apresentar_em=apresentar_em, dados_override=dados)
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Não foi possível gerar a Carta de Recomendação.\n\nErro: {erro}",
            )
            return

        self.destroy()
