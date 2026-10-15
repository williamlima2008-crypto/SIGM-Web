from dataclasses import replace
from datetime import date, datetime
from tkinter import BooleanVar, StringVar, messagebox

import customtkinter as ctk

from config import cores
from documentos.catalogo_documentos import (
    DOCUMENTO_PEDIDO_MEMBRAMENTO,
    obter_documento_oficial,
)
from documentos.integrador_documentos import montar_dados_documento
from telas.documentos.base_editor_documento import BaseEditorDocumento


MESES = [
    "janeiro",
    "fevereiro",
    "marco",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]


MAPEAMENTO_PEDIDO_MEMBRAMENTO = {
    "codigo": "pedido_membramento",
    "titulo": "Pedido para Apresentacao / Membramento",
    "modelo": "pedido_membramento.pdf",
    "campos": [
        {"nome": "congregacao", "pagina": 0, "x": 80, "y": 640, "tamanho": 10},
        {"nome": "numero", "pagina": 0, "x": 354, "y": 640, "tamanho": 10},
        {"nome": "dirigente", "pagina": 0, "x": 80, "y": 622, "tamanho": 10},
        {"nome": "nome_membro", "pagina": 0, "x": 80, "y": 601, "tamanho": 10},
        {"nome": "igreja_origem", "pagina": 0, "x": 112, "y": 581, "tamanho": 10},
        {"nome": "cidade_origem", "pagina": 0, "x": 66, "y": 562, "tamanho": 10},
        {"nome": "estado_origem", "pagina": 0, "x": 372, "y": 562, "tamanho": 10},
        {
            "nome": "trouxe_carta_sim",
            "tipo": "checkbox",
            "pagina": 0,
            "x": 185,
            "y": 543,
            "largura": 11,
            "altura": 11,
        },
        {
            "nome": "trouxe_carta_nao",
            "tipo": "checkbox",
            "pagina": 0,
            "x": 250,
            "y": 543,
            "largura": 11,
            "altura": 11,
        },
        {
            "nome": "trouxe_familia_sim",
            "tipo": "checkbox",
            "pagina": 0,
            "x": 144,
            "y": 520,
            "largura": 11,
            "altura": 11,
        },
        {
            "nome": "trouxe_familia_nao",
            "tipo": "checkbox",
            "pagina": 0,
            "x": 208,
            "y": 520,
            "largura": 11,
            "altura": 11,
        },
        {
            "nome": "observacoes",
            "pagina": 0,
            "x": 20,
            "y": 421,
            "tamanho": 9,
            "multilinha": True,
            "altura_linha": 24,
            "max_linhas": 5,
            "max_caracteres": 86,
        },
        {"nome": "dirigente_local", "pagina": 0, "x": 35, "y": 289, "tamanho": 8},
        {"nome": "pastor_setorial", "pagina": 0, "x": 230, "y": 289, "tamanho": 8},
        {
            "nome": "data_documento_extenso",
            "pagina": 0,
            "x": 78,
            "y": 212,
            "tamanho": 11,
            "limpar": True,
            "limpar_x": 76,
            "limpar_y": 207,
            "limpar_largura": 340,
            "limpar_altura": 19,
        },
    ],
}


CAMPOS_AUTOMATICOS = [
    ("nome_membro", "Nome do membro"),
    ("congregacao", "Congregacao"),
    ("numero_congregacao", "Numero da Congregacao"),
    ("campo_setor", "Campo / Setor"),
    ("dirigente_local", "Dirigente Local"),
    ("cidade_documento", "Cidade"),
    ("estado_documento", "Estado"),
    ("data_documento_visual", "Data do documento"),
    ("pastor_presidente", "Pastor Presidente"),
    ("pastor_setorial", "Pastor Setorial"),
]


class EditorMembramento(BaseEditorDocumento):
    titulo_janela = "Editor do Pedido de Membramento - SIGM"

    def __init__(self, master, id_membro):
        self.campos_leitura = {}
        self.usar_data_atual_var = None
        self.trouxe_carta_var = None
        self.trouxe_familia_var = None
        self.campo_data_documento = None

        documento = replace(
            obter_documento_oficial(DOCUMENTO_PEDIDO_MEMBRAMENTO),
            titulo="Pedido para Apresentacao / Membramento",
            mapeamento=MAPEAMENTO_PEDIDO_MEMBRAMENTO,
        )
        dados_iniciais = self.montar_dados_iniciais(id_membro)

        super().__init__(master, id_membro, documento, dados_iniciais)

    def montar_dados_iniciais(self, id_membro):
        dados = montar_dados_documento(id_membro)
        hoje = date.today()

        dados["numero"] = dados.get("numero_congregacao", "")
        dados["dirigente"] = dados.get("dirigente_local") or dados.get("dirigente", "")
        dados["cidade_documento"] = (
            dados.get("local_cidade")
            or dados.get("cidade_congregacao")
            or dados.get("cidade_igreja")
            or dados.get("cidade")
            or "Guarulhos"
        )
        dados["estado_documento"] = (
            dados.get("estado_congregacao")
            or dados.get("estado_igreja")
            or dados.get("estado")
            or ""
        )
        dados["local_cidade"] = dados["cidade_documento"]
        dados["local_estado"] = dados["estado_documento"]
        dados["data_documento_visual"] = hoje.strftime("%d/%m/%Y")

        dados.setdefault("igreja_origem", "")
        dados.setdefault("cidade_origem", "")
        dados.setdefault("estado_origem", "")
        dados.setdefault("trouxe_carta", "")
        dados.setdefault("trouxe_familia", "")
        dados.setdefault("observacoes", "")

        return dados

    def obter_dados_iniciais(self):
        return self.montar_dados_iniciais(self.id_membro)

    def criar_campos(self):
        self.usar_data_atual_var = BooleanVar(value=True)
        self.trouxe_carta_var = StringVar(value=self.dados_iniciais.get("trouxe_carta", ""))
        self.trouxe_familia_var = StringVar(value=self.dados_iniciais.get("trouxe_familia", ""))

        secao_auto = self.criar_secao("Campos automaticos")
        for chave, rotulo in CAMPOS_AUTOMATICOS:
            self.criar_campo_leitura(chave, rotulo, parent=secao_auto)

        self.criar_bloco_data()

        secao_editavel = self.criar_secao("Campos editaveis")
        self.criar_campo_texto("igreja_origem", "Igreja de origem", parent=secao_editavel)
        self.criar_campo_texto("cidade_origem", "Cidade de origem", parent=secao_editavel)
        self.criar_campo_texto("estado_origem", "Estado de origem", parent=secao_editavel)
        self.criar_grupo_opcoes(
            "Trouxe carta?",
            self.trouxe_carta_var,
            parent=secao_editavel,
        )
        self.criar_grupo_opcoes(
            "Veio com familia?",
            self.trouxe_familia_var,
            parent=secao_editavel,
        )
        self.criar_campo_multilinha(
            "observacoes",
            "Observacoes",
            altura=130,
            parent=secao_editavel,
        )

    def criar_campo_leitura(self, chave, rotulo, parent=None):
        container = parent or self.frame_formulario
        linha = ctk.CTkFrame(container, fg_color=cores.BRANCO, corner_radius=8)
        linha.pack(fill="x", padx=14, pady=5)
        linha.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            linha,
            text=rotulo,
            width=self.largura_label,
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=0, column=0, padx=(12, 8), pady=9, sticky="w")

        entrada = ctk.CTkEntry(linha, height=34)
        entrada.grid(row=0, column=1, padx=(0, 12), pady=9, sticky="ew")
        self.campos_leitura[chave] = entrada
        return entrada

    def criar_bloco_data(self):
        secao = self.criar_secao("Data do Documento")
        bloco = ctk.CTkFrame(secao, fg_color=cores.BRANCO, corner_radius=8)
        bloco.pack(fill="x", padx=14, pady=5)
        bloco.grid_columnconfigure(1, weight=1)

        ctk.CTkCheckBox(
            bloco,
            text="Usar data atual",
            variable=self.usar_data_atual_var,
            command=self.atualizar_estado_data,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
        ).grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 4), sticky="w")

        ctk.CTkLabel(
            bloco,
            text="Data:",
            width=self.largura_label,
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=1, column=0, padx=(12, 8), pady=(4, 10), sticky="w")

        self.campo_data_documento = ctk.CTkEntry(bloco, height=34)
        self.campo_data_documento.grid(
            row=1,
            column=1,
            padx=(0, 12),
            pady=(4, 10),
            sticky="ew",
        )
        self.campo_data_documento.bind("<KeyRelease>", self.aplicar_mascara_data)

    def criar_grupo_opcoes(self, rotulo, variavel, parent=None):
        container = parent or self.frame_formulario
        linha = ctk.CTkFrame(container, fg_color=cores.BRANCO, corner_radius=8)
        linha.pack(fill="x", padx=14, pady=5)
        linha.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            linha,
            text=rotulo,
            width=self.largura_label,
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=0, column=0, padx=(12, 8), pady=9, sticky="w")

        opcoes = ctk.CTkFrame(linha, fg_color="transparent")
        opcoes.grid(row=0, column=1, padx=(0, 12), pady=9, sticky="w")

        ctk.CTkRadioButton(
            opcoes,
            text="Sim",
            variable=variavel,
            value="sim",
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
        ).pack(side="left", padx=(0, 28))

        ctk.CTkRadioButton(
            opcoes,
            text="Nao",
            variable=variavel,
            value="nao",
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
        ).pack(side="left")

    def apos_carregar_dados(self):
        self.carregar_campos_leitura()
        self.carregar_data_documento()
        self.trouxe_carta_var.set(self.dados_iniciais.get("trouxe_carta", ""))
        self.trouxe_familia_var.set(self.dados_iniciais.get("trouxe_familia", ""))

    def carregar_campos_leitura(self):
        for chave, entrada in self.campos_leitura.items():
            entrada.configure(state="normal")
            entrada.delete(0, "end")
            entrada.insert(0, str(self.dados_iniciais.get(chave) or ""))
            entrada.configure(state="disabled")

    def carregar_data_documento(self):
        self.usar_data_atual_var.set(True)
        self.atualizar_campo_data(date.today().strftime("%d/%m/%Y"))
        self.atualizar_estado_data()

    def atualizar_campo_data(self, valor):
        self.campo_data_documento.configure(state="normal")
        self.campo_data_documento.delete(0, "end")
        self.campo_data_documento.insert(0, valor)

    def atualizar_estado_data(self):
        if self.usar_data_atual_var.get():
            self.atualizar_campo_data(date.today().strftime("%d/%m/%Y"))
            self.campo_data_documento.configure(state="disabled")
            return

        self.campo_data_documento.configure(state="normal")

    def aplicar_mascara_data(self, _evento=None):
        if self.usar_data_atual_var.get():
            return

        valor = self.campo_data_documento.get()
        novo_valor = self.mascara_data(valor)

        if valor == novo_valor:
            return

        self.campo_data_documento.delete(0, "end")
        self.campo_data_documento.insert(0, novo_valor)

    def validar_antes_de_gerar(self):
        if not self.coletar_dados().get("nome_membro"):
            messagebox.showwarning("SIGM", "Informe o nome do membro.")
            return False

        if self.usar_data_atual_var.get():
            return True

        if self.obter_data_informada() is None:
            messagebox.showwarning("SIGM", "Data do documento invalida.")
            return False

        return True

    def coletar_dados(self):
        dados = super().coletar_dados()

        trouxe_carta = self.trouxe_carta_var.get()
        trouxe_familia = self.trouxe_familia_var.get()
        data_documento = self.obter_data_documento()
        cidade = dados.get("local_cidade") or dados.get("cidade_documento") or "Guarulhos"

        dados["numero"] = dados.get("numero_congregacao", "")
        dados["dirigente"] = dados.get("dirigente_local") or dados.get("dirigente", "")
        dados["trouxe_carta"] = self.texto_opcao(trouxe_carta)
        dados["trouxe_carta_sim"] = trouxe_carta == "sim"
        dados["trouxe_carta_nao"] = trouxe_carta == "nao"
        dados["trouxe_familia"] = self.texto_opcao(trouxe_familia)
        dados["trouxe_familia_sim"] = trouxe_familia == "sim"
        dados["trouxe_familia_nao"] = trouxe_familia == "nao"
        dados["local_dia"] = data_documento.strftime("%d")
        dados["local_mes"] = MESES[data_documento.month - 1]
        dados["local_ano"] = data_documento.strftime("%Y")
        dados["data_documento"] = data_documento.strftime("%d/%m/%Y")
        dados["data_documento_extenso"] = (
            f"{cidade}, {dados['local_dia']} de {dados['local_mes']} "
            f"de {dados['local_ano']}"
        )

        return dados

    def campos_editaveis_para_cadastro(self, dados):
        dados_cadastro = super().campos_editaveis_para_cadastro(dados)
        dados_cadastro["trouxe_carta"] = dados.get("trouxe_carta", "")
        dados_cadastro["trouxe_familia"] = dados.get("trouxe_familia", "")
        dados_cadastro["data_documento"] = dados.get("data_documento", "")
        return dados_cadastro

    def obter_data_documento(self):
        if self.usar_data_atual_var.get():
            return date.today()

        return self.obter_data_informada() or date.today()

    def obter_data_informada(self):
        valor = self.campo_data_documento.get().strip()

        try:
            return datetime.strptime(valor, "%d/%m/%Y").date()
        except ValueError:
            return None

    @staticmethod
    def texto_opcao(valor):
        if valor == "sim":
            return "Sim"
        if valor == "nao":
            return "Nao"
        return ""

    @staticmethod
    def mascara_data(valor):
        digitos = "".join(caractere for caractere in str(valor or "") if caractere.isdigit())[:8]
        if len(digitos) <= 2:
            return digitos
        if len(digitos) <= 4:
            return f"{digitos[:2]}/{digitos[2:]}"
        return f"{digitos[:2]}/{digitos[2:4]}/{digitos[4:]}"
