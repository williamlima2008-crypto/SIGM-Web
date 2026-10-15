import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import os

try:
    import fitz
    from PIL import Image, ImageTk
except ImportError:
    fitz = None
    Image = None
    ImageTk = None

from config import cores, fontes
from banco.database import buscar_igreja, buscar_membro_por_id
from componentes.cabecalho_igreja import CabecalhoIgreja
from documentos.ficha_cadastral_pdf import MODELO_FICHA_CADASTRAL
from documentos.gerar_documentos import gerar_pdf_documento
from utils.auditoria import registrar_acao
from utils.janelas import configurar_janela_principal


TIPO_FICHA_CADASTRAL = "Ficha Cadastral"

CAMPOS_PADRAO = [
    ("congregacao", "Congregacao"),
    ("numero", "Numero"),
    ("dirigente", "Dirigente"),
    ("nome_membro", "Nome do membro"),
    ("rg", "RG"),
    ("cpf", "CPF"),
    ("cidade", "Cidade"),
    ("estado", "Estado"),
    ("cargo", "Cargo"),
    ("ministerio", "Ministerio"),
    ("igreja_origem", "Igreja de origem"),
    ("cidade_origem", "Cidade de origem"),
    ("estado_origem", "Estado de origem"),
    ("trouxe_carta", "Trouxe carta?"),
    ("trouxe_familia", "Trouxe familia?"),
]

CAMPOS_FICHA_CADASTRAL = [
    ("congregacao", "Congregacao"),
    ("dirigente", "Dirigente"),
    ("nome_membro", "Nome do membro"),
    ("rg", "RG"),
    ("cpf", "CPF"),
    ("data_nascimento", "Data de nascimento"),
    ("estado_civil", "Estado civil"),
    ("profissao", "Profissao"),
    ("telefone", "Telefone"),
    ("celular", "Celular"),
    ("email", "E-mail"),
    ("endereco", "Endereco"),
    ("numero", "Numero"),
    ("bairro", "Bairro"),
    ("cidade", "Cidade"),
    ("estado", "Estado"),
    ("batismo_aguas", "Batismo nas aguas"),
    ("ministerio", "Ministerio"),
    ("cargo", "Cargo"),
    ("status", "Status"),
]

CAMPOS_VISUAIS_FICHA_CADASTRAL = [
    "nome_membro",
    "rg",
    "cpf",
    "celular",
    "email",
]

POSICOES_TESTE_FICHA_CADASTRAL = {
    "nome_membro": (100, 300, 520, 36),
    "rg": (100, 350, 240, 36),
    "cpf": (380, 350, 240, 36),
    "celular": (100, 400, 240, 36),
    "email": (100, 450, 520, 36),
}

ROTULOS_TESTE_FICHA_CADASTRAL = {
    "nome_membro": "Nome do membro",
    "rg": "RG",
    "cpf": "CPF",
    "celular": "Celular",
    "email": "E-mail",
}

ZOOM_FICHA_CADASTRAL = 1.25

DADOS_MEMBRO_POR_CAMPO = {
    "nome_membro": 1,
    "rg": 2,
    "cpf": 4,
    "data_nascimento": 5,
    "estado_civil": 6,
    "profissao": 7,
    "telefone": 8,
    "celular": 9,
    "email": 10,
    "endereco": 11,
    "numero": 12,
    "bairro": 13,
    "cidade": 14,
    "estado": 15,
    "batismo_aguas": 16,
    "ministerio": 17,
    "cargo": 18,
    "status": 19,
}


class EditorDocumento(ctk.CTkToplevel):

    def __init__(self, master, id_membro):
        super().__init__(master)

        self.id_membro = id_membro
        self.membro = buscar_membro_por_id(id_membro)
        self.igreja = buscar_igreja()

        self.title("Editor de Documento - SIGM")
        configurar_janela_principal(self, 980, 760, 880, 680, master)
        self.configure(fg_color=cores.FUNDO)

        self.criar_interface()
        self.carregar_dados()

    def criar_interface(self):
        ctk.CTkLabel(
            self,
            text="Editor de Documento",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL
        ).pack(pady=(25, 10))

        self.cabecalho_igreja = CabecalhoIgreja(self)
        self.cabecalho_igreja.pack(fill="x", padx=30, pady=(0, 10))

        self.tipo_documento = ctk.CTkComboBox(
            self,
            values=[
                "Pedido para Reconciliação",
                "Pedido para Apresentação / Membramento",
                "Ficha Cadastral"
            ],
            width=500,
            height=35,
            command=self.ao_trocar_tipo
        )
        self.tipo_documento.set("Pedido para Reconciliação")
        self.tipo_documento.pack(pady=10)

        frame = ctk.CTkScrollableFrame(self, corner_radius=10)
        frame.pack(padx=30, pady=10, fill="both", expand=True)
        self.frame_formulario = frame

        self.campos = {}
        self.imagens_pdf = []

        nomes_campos = [
            ("congregacao", "Congregação"),
            ("numero", "Número"),
            ("dirigente", "Dirigente"),
            ("nome_membro", "Nome do membro"),
            ("rg", "RG"),
            ("cpf", "CPF"),
            ("cidade", "Cidade"),
            ("estado", "Estado"),
            ("cargo", "Cargo"),
            ("ministerio", "Ministério"),
            ("igreja_origem", "Igreja de origem"),
            ("cidade_origem", "Cidade de origem"),
            ("estado_origem", "Estado de origem"),
            ("trouxe_carta", "Trouxe carta?"),
            ("trouxe_familia", "Trouxe família?"),
        ]

        for chave, texto in nomes_campos:
            entrada = ctk.CTkEntry(frame, placeholder_text=texto, height=35)
            entrada.pack(fill="x", padx=25, pady=6)
            self.campos[chave] = entrada

        self.observacoes = ctk.CTkTextbox(frame, height=150)
        self.observacoes.pack(fill="both", expand=True, padx=25, pady=12)
        self.reconstruir_formulario()

        frame_botoes = ctk.CTkFrame(self, fg_color="transparent")
        frame_botoes.pack(pady=15)

        ctk.CTkButton(
            frame_botoes,
            text="RESTAURAR DADOS",
            width=180,
            height=38,
            command=self.restaurar_dados
        ).grid(row=0, column=0, padx=8)

        ctk.CTkButton(
            frame_botoes,
            text="GERAR PDF",
            width=180,
            height=38,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            command=self.gerar_pdf
        ).grid(row=0, column=1, padx=8)

        ctk.CTkButton(
            frame_botoes,
            text="FECHAR",
            width=120,
            height=38,
            fg_color=cores.CINZA,
            command=self.destroy
        ).grid(row=0, column=2, padx=8)

    def campos_do_tipo_atual(self):
        if self.tipo_documento.get() == TIPO_FICHA_CADASTRAL:
            return CAMPOS_FICHA_CADASTRAL

        return CAMPOS_PADRAO

    def ao_trocar_tipo(self, _tipo=None):
        self.reconstruir_formulario()
        self.carregar_dados()

    def reconstruir_formulario(self):
        for widget in self.frame_formulario.winfo_children():
            widget.destroy()

        self.campos = {}
        self.observacoes = None
        self.imagens_pdf = []

        if self.tipo_documento.get() == TIPO_FICHA_CADASTRAL:
            self.criar_editor_visual_ficha_cadastral()
            return

        self.criar_formulario_padrao()

    def criar_formulario_padrao(self):
        for chave, texto in self.campos_do_tipo_atual():
            ctk.CTkLabel(
                self.frame_formulario,
                text=texto,
                anchor="w"
            ).pack(fill="x", padx=25, pady=(8, 0))

            entrada = ctk.CTkEntry(
                self.frame_formulario,
                placeholder_text=texto,
                height=35
            )
            entrada.pack(fill="x", padx=25, pady=(2, 4))
            self.campos[chave] = entrada

        ctk.CTkLabel(
            self.frame_formulario,
            text="Observacoes",
            anchor="w"
        ).pack(fill="x", padx=25, pady=(10, 0))

        self.observacoes = ctk.CTkTextbox(self.frame_formulario, height=150)
        self.observacoes.pack(fill="both", expand=True, padx=25, pady=(2, 12))

    def criar_editor_visual_ficha_cadastral(self):
        if fitz is None or Image is None or ImageTk is None:
            ctk.CTkLabel(
                self.frame_formulario,
                text=(
                    "Para usar o editor visual da Ficha Cadastral, "
                    "instale as dependencias PyMuPDF e Pillow."
                ),
                text_color=cores.AZUL_PRINCIPAL,
                wraplength=720,
                justify="center"
            ).pack(padx=25, pady=30)
            return

        if not MODELO_FICHA_CADASTRAL.exists():
            ctk.CTkLabel(
                self.frame_formulario,
                text=f"Modelo nao encontrado: {MODELO_FICHA_CADASTRAL}",
                text_color=cores.AZUL_PRINCIPAL,
                wraplength=720,
                justify="center"
            ).pack(padx=25, pady=30)
            return

        documento = fitz.open(str(MODELO_FICHA_CADASTRAL))
        matriz = fitz.Matrix(ZOOM_FICHA_CADASTRAL, ZOOM_FICHA_CADASTRAL)

        try:
            for indice_pagina, pagina in enumerate(documento):
                pixmap = pagina.get_pixmap(matrix=matriz, alpha=False)
                imagem = Image.frombytes(
                    "RGB",
                    (pixmap.width, pixmap.height),
                    pixmap.samples
                )
                imagem_tk = ImageTk.PhotoImage(imagem)
                self.imagens_pdf.append(imagem_tk)

                canvas_pdf = tk.Canvas(
                    self.frame_formulario,
                    width=pixmap.width,
                    height=pixmap.height,
                    bg="white",
                    highlightthickness=0,
                    bd=0
                )
                canvas_pdf.pack(padx=20, pady=15)
                canvas_pdf.create_image(0, 0, anchor="nw", image=imagem_tk)

                self.criar_campos_sobre_pagina_ficha(canvas_pdf, indice_pagina)
        finally:
            documento.close()

    def criar_campos_sobre_pagina_ficha(self, canvas_pdf, indice_pagina):
        if indice_pagina != 0:
            return

        for chave in CAMPOS_VISUAIS_FICHA_CADASTRAL:
            x_tela, y_tela, largura_tela, altura_tela = POSICOES_TESTE_FICHA_CADASTRAL[chave]

            entrada = tk.Entry(
                canvas_pdf,
                bg="white",
                fg="black",
                insertbackground="black",
                relief="solid",
                bd=3,
                font=("Arial", 12)
            )
            entrada.insert(0, ROTULOS_TESTE_FICHA_CADASTRAL[chave])

            item_campo = canvas_pdf.create_window(
                x=x_tela,
                y=y_tela,
                anchor="nw",
                window=entrada,
                width=largura_tela,
                height=altura_tela
            )
            canvas_pdf.tag_raise(item_campo)
            self.campos[chave] = entrada

        if self.campos:
            primeiro_campo = self.campos[CAMPOS_VISUAIS_FICHA_CADASTRAL[0]]
            primeiro_campo.focus_set()

    def carregar_dados(self):
        if self.membro is None:
            return

        for chave, campo in self.campos.items():
            campo.delete(0, "end")

            indice = DADOS_MEMBRO_POR_CAMPO.get(chave)
            if indice is not None:
                campo.insert(0, self.membro[indice] or "")

        if self.observacoes is not None:
            self.observacoes.delete("1.0", "end")
            self.observacoes.insert("1.0", self.membro[20] or "")

    def restaurar_dados(self):
        self.carregar_dados()

    def gerar_pdf(self):
        dados = {}

        if self.tipo_documento.get() == TIPO_FICHA_CADASTRAL and not self.campos:
            messagebox.showerror(
                "SIGM",
                "Nao foi possivel carregar os campos da Ficha Cadastral."
            )
            return

        for chave, campo in self.campos.items():
            dados[chave] = campo.get().strip()

        if self.observacoes is not None:
            dados["observacoes"] = self.observacoes.get("1.0", "end").strip()
        else:
            dados["observacoes"] = ""

        caminho = gerar_pdf_documento(
            self.tipo_documento.get(),
            dados,
            self.igreja
        )
        registrar_acao(
            "PDF_GERADO",
            f"{self.tipo_documento.get()} gerado.",
            modulo="Documentos",
            registro_id=self.id_membro,
            detalhes=f"Arquivo: {caminho}",
        )

        messagebox.showinfo(
            "SIGM",
            f"PDF gerado com sucesso!\n\nArquivo:\n{caminho}"
        )

        try:
            os.startfile(caminho)
        except Exception:
            pass
