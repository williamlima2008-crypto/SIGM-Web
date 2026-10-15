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
from pathlib import Path
from tkinter import messagebox

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None

from config import cores, fontes
from banco.database import (
    buscar_data_funcao_membro,
    buscar_membro_por_id,
    excluir_membro,
    registrar_documento_emitido,
)
from componentes.cabecalho_igreja import CabecalhoIgreja
from documentos.gerar_documentos import (
    TIPO_CARTA_RECOMENDACAO,
    TIPO_FICHA_CADASTRAL,
    TIPO_PEDIDO_MEMBRAMENTO,
    TIPO_PEDIDO_RECONCILIACAO,
    gerar_e_abrir_carta_recomendacao,
    gerar_e_abrir_documento_oficial_final,
)
from documentos.integrador_documentos import buscar_caminho_foto_membro
from telas.cadastro_membro import CadastroMembro
from telas.arquivos_membro import ArquivosMembro
from telas.dossie_membro import DossieMembro
from telas.documentos.editor_carta_recomendacao import EditorCartaRecomendacao
from telas.documentos.editor_ficha_cadastral import EditorFichaCadastral
from telas.documentos.editor_membramento import EditorMembramento
from telas.documentos.editor_reconciliacao import EditorReconciliacao
from telas.documentos.historico_documentos import HistoricoDocumentos
from utils.auditoria import registrar_acao
from utils.janelas import configurar_janela_principal, configurar_modal
from utils.sessao import obter_sessao



CAMPOS_MEMBRO = {
    "id": 0,
    "nome": 1,
    "rg": 2,
    "orgao_emissor": 3,
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
    "data_batismo_espirito_santo": 29,
    "ministerio": 17,
    "cargo": 18,
    "status": 19,
    "observacoes": 20,
    "nome_pai": 21,
    "nome_mae": 22,
    "cidade_nascimento": 23,
    "estado_nascimento": 24,
    "nome_conjuge": 25,
    "data_nascimento_conjuge": 26,
    "grau_instrucao": 27,
    "curso_teologico": 28,
    "cep": 30,
}


class FichaMembro(ctk.CTkToplevel):

    def __init__(self, master, id_membro, ao_alterar=None):
        super().__init__(master)

        self.id_membro = id_membro
        self.ao_alterar = ao_alterar
        self.janela_edicao = None
        self.janela_documentos = None
        self.janela_editor_ficha_cadastral = None
        self.janela_editor_membramento = None
        self.janela_editor_reconciliacao = None
        self.janela_historico_documentos = None
        self.janela_arquivos_membro = None
        self.janela_dossie_membro = None
        self.imagem_foto = None

        self.title("Ficha do Membro - SIGM")
        configurar_janela_principal(self, 980, 780, 920, 700, master)
        self.configure(fg_color=cores.FUNDO)

        self.criar_interface()

    def carregar_dados_membro(self):
        self.membro = buscar_membro_por_id(self.id_membro)
        self.data_funcao = buscar_data_funcao_membro(self.id_membro)
        return self.membro

    def valor_membro(self, chave):
        if chave == "data_funcao":
            return self.data_funcao

        indice = CAMPOS_MEMBRO.get(chave)
        if indice is None or self.membro is None or len(self.membro) <= indice:
            return ""

        return self.membro[indice] or ""

    def criar_foto(self, master):
        frame = ctk.CTkFrame(master, width=104, height=104, fg_color=cores.FUNDO, corner_radius=8)
        frame.pack_propagate(False)

        caminho_foto = buscar_caminho_foto_membro(self.id_membro)
        if Image is None or not caminho_foto or not Path(caminho_foto).exists():
            ctk.CTkLabel(
                frame,
                text="Sem foto\ncadastrada",
                font=("Segoe UI", 11, "bold"),
                text_color=cores.CINZA,
            ).place(relx=0.5, rely=0.5, anchor="center")
            return frame

        try:
            imagem = Image.open(caminho_foto)
            imagem = ImageOps.contain(imagem, (95, 95))
            self.imagem_foto = ctk.CTkImage(light_image=imagem, dark_image=imagem, size=(95, 95))
            ctk.CTkLabel(frame, image=self.imagem_foto, text="").place(relx=0.5, rely=0.5, anchor="center")
        except Exception:
            ctk.CTkLabel(
                frame,
                text="Foto nao\ncarregada",
                font=("Segoe UI", 11, "bold"),
                text_color=cores.CINZA,
            ).place(relx=0.5, rely=0.5, anchor="center")

        return frame

    def criar_interface(self):
        self.carregar_dados_membro()

        if self.membro is None:
            messagebox.showerror("SIGM", "Membro não encontrado.")
            self.destroy()
            return

        ctk.CTkLabel(
            self,
            text="Ficha do Membro",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL
        ).pack(pady=(25, 10))

        self.cabecalho_igreja = CabecalhoIgreja(self)
        self.cabecalho_igreja.pack(fill="x", padx=30, pady=(0, 10))

        frame_foto = ctk.CTkFrame(self, fg_color="transparent")
        frame_foto.pack(padx=30, pady=(0, 6), anchor="w")
        self.criar_foto(frame_foto).pack(anchor="w")

        frame = ctk.CTkScrollableFrame(
            self,
            corner_radius=10
        )

        frame.pack(padx=30,
            pady=10,
            fill="both",
            expand=True
        )

        campos = [
            ("ID", self.valor_membro("id")),
            ("Nome", self.valor_membro("nome")),
            ("RG", self.valor_membro("rg")),
            ("Órgão Emissor", self.valor_membro("orgao_emissor")),
            ("CPF", self.valor_membro("cpf")),
            ("Data de Nascimento", self.valor_membro("data_nascimento")),
            ("Cidade de Nascimento", self.valor_membro("cidade_nascimento")),
            ("Estado de Nascimento", self.valor_membro("estado_nascimento")),
            ("Estado Civil", self.valor_membro("estado_civil")),
            ("Conjuge", self.valor_membro("nome_conjuge")),
            ("Nascimento do Conjuge", self.valor_membro("data_nascimento_conjuge")),
            ("Profissão", self.valor_membro("profissao")),
            ("Pai", self.valor_membro("nome_pai")),
            ("Mae", self.valor_membro("nome_mae")),
            ("Grau de instrucao escolar", self.valor_membro("grau_instrucao")),
            ("Telefone", self.valor_membro("telefone")),
            ("Celular", self.valor_membro("celular")),
            ("E-mail", self.valor_membro("email")),
            ("Endereço", self.valor_membro("endereco")),
            ("Número", self.valor_membro("numero")),
            ("Bairro", self.valor_membro("bairro")),
            ("Cidade", self.valor_membro("cidade")),
            ("Estado", self.valor_membro("estado")),
            ("CEP", self.valor_membro("cep")),
            ("Batismo nas Águas", self.valor_membro("batismo_aguas")),
            ("Batismo no Espírito Santo", self.valor_membro("data_batismo_espirito_santo")),
            ("Ministério", self.valor_membro("ministerio")),
            ("Cargo/Função", self.valor_membro("cargo")),
            ("Data da Função Atual", self.valor_membro("data_funcao")),
            ("Curso teologico", self.valor_membro("curso_teologico")),
            ("Status", self.valor_membro("status")),
            ("Observações", self.valor_membro("observacoes")),
        ]

        for nome_campo, valor in campos:
            linha = ctk.CTkFrame(frame, fg_color=cores.BRANCO, corner_radius=8)
            linha.pack(fill="x", padx=15, pady=5)

            ctk.CTkLabel(
                linha,
                text=f"{nome_campo}:",
                width=180,
                anchor="w",
                font=("Segoe UI", 13, "bold"),
                text_color=cores.AZUL_PRINCIPAL
            ).grid(row=0, column=0, padx=10, pady=8)

            ctk.CTkLabel(
                linha,
                text=str(valor) if valor else "-",
                anchor="w",
                font=("Segoe UI", 13),
                text_color=cores.PRETO
            ).grid(row=0, column=1, padx=10, pady=8, sticky="w")

        frame_botoes = ctk.CTkFrame(self, fg_color="transparent")
        frame_botoes.pack(
            fill="x",
            padx=20,
            pady=(10,20)
        )

        ctk.CTkButton(
            frame_botoes,
            text="EDITAR",
            width=130,
            height=38,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            command=self.editar_membro
        ).grid(row=0, column=0, padx=8)

        ctk.CTkButton(
            frame_botoes,
            text="EXCLUIR",
            width=130,
            height=38,
            fg_color=cores.VERMELHO,
            hover_color="#A71D2A",
            command=self.excluir
        ).grid(row=0, column=1, padx=8)

        ctk.CTkButton(
            frame_botoes,
            text="GERAR PDF",
            width=130,
            height=38,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            command=self.abrir_selecao_documentos
        ).grid(row=0, column=2, padx=8)

        ctk.CTkButton(
            frame_botoes,
            text="FECHAR",
            width=130,
            height=38,
            fg_color=cores.CINZA,
            hover_color="#444444",
            command=self.destroy
        ).grid(row=0, column=4, padx=8)

        ctk.CTkButton(
            frame_botoes,
            text="HISTÓRICO DE DOCUMENTOS",
            width=210,
            height=38,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            command=self.abrir_historico_documentos
        ).grid(row=0, column=3, padx=8)

        ctk.CTkButton(
            frame_botoes,
            text="ARQUIVOS DO MEMBRO",
            width=190,
            height=38,
            fg_color=cores.VERDE,
            hover_color="#1F7A45",
            command=self.abrir_arquivos_membro
        ).grid(row=1, column=0, columnspan=2, padx=8, pady=(10, 0), sticky="w")

        ctk.CTkButton(
            frame_botoes,
            text="ABRIR DOSSIÊ DIGITAL",
            width=190,
            height=38,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            command=self.abrir_dossie_membro
        ).grid(row=1, column=2, columnspan=2, padx=8, pady=(10, 0), sticky="w")

    def editar_membro(self):
        if self.janela_edicao is not None and self.janela_edicao.winfo_exists():
            self.janela_edicao.lift()
            self.janela_edicao.focus_force()
            return

        self.janela_edicao = CadastroMembro(
            self,
            id_membro=self.id_membro,
            ao_salvar=self.atualizar_ficha
        )

    def atualizar_ficha(self):
        self.carregar_dados_membro()

        if self.membro is None:
            messagebox.showerror("SIGM", "Membro não encontrado.")
            self.destroy()
            return

        self.janela_edicao = None

        for widget in self.winfo_children():
            widget.destroy()

        self.criar_interface()

        if self.ao_alterar:
            self.ao_alterar()

    def excluir(self):
        confirmar = messagebox.askyesno(
            "Confirmar exclusão",
            "Tem certeza que deseja excluir este membro?\n\nEssa ação não poderá ser desfeita."
        )

        if not confirmar:
            return

        try:
            nome_membro = self.membro[1] if self.membro else f"ID {self.id_membro}"
            excluir_membro(self.id_membro)
            registrar_acao(
                "EXCLUSAO_MEMBRO",
                f"Membro {nome_membro} excluido.",
                modulo="Membros",
                registro_id=self.id_membro,
            )

            if self.ao_alterar:
                self.ao_alterar()

            messagebox.showinfo("SIGM", "Membro excluído com sucesso!")
            self.destroy()

        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Não foi possível excluir o membro.\n\nErro: {erro}"
            )

    def abrir_selecao_documentos(self):
        if self.janela_documentos is not None and self.janela_documentos.winfo_exists():
            self.janela_documentos.lift()
            self.janela_documentos.focus_force()
            return

        janela = ctk.CTkToplevel(self)
        self.janela_documentos = janela

        janela.title("Documentos Oficiais - SIGM")
        janela.geometry("720x520")
        janela.resizable(False, False)
        janela.configure(fg_color=cores.FUNDO)

        configurar_modal(janela, self)

        ctk.CTkLabel(
            janela,
            text="Documentos Oficiais",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL
        ).pack(pady=(25, 8))

        CabecalhoIgreja(janela).pack(fill="x", padx=28, pady=(0, 12))

        ctk.CTkLabel(
            janela,
            text="Escolha editar o formulario ou gerar a versao final para impressao.",
            font=("Segoe UI", 13),
            text_color=cores.CINZA
        ).pack(pady=(0, 14))

        documentos = [
            TIPO_FICHA_CADASTRAL,
            TIPO_PEDIDO_MEMBRAMENTO,
            TIPO_PEDIDO_RECONCILIACAO,
        ]

        for tipo in documentos:
            linha = ctk.CTkFrame(janela, fg_color=cores.BRANCO, corner_radius=8)
            linha.pack(fill="x", padx=28, pady=6)
            linha.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                linha,
                text=tipo,
                anchor="w",
                font=("Segoe UI", 13, "bold"),
                text_color=cores.AZUL_PRINCIPAL
            ).grid(row=0, column=0, padx=14, pady=10, sticky="ew")

            ctk.CTkButton(
                linha,
                text="EDITAR",
                width=95,
                height=38,
                fg_color=cores.AZUL_PRINCIPAL,
                hover_color=cores.AZUL_ESCURO,
                command=lambda tipo_documento=tipo: self.gerar_documento_oficial(
                    tipo_documento,
                    final=False
                )
            ).grid(row=0, column=1, padx=(8, 4), pady=10)

            ctk.CTkButton(
                linha,
                text="FINAL",
                width=95,
                height=38,
                fg_color=cores.VERDE,
                hover_color="#1F7A45",
                command=lambda tipo_documento=tipo: self.gerar_documento_oficial(
                    tipo_documento,
                    final=True
                )
            ).grid(row=0, column=2, padx=(4, 14), pady=10)

        # Carta de Recomendacao: "EDITAR" abre uma telinha pra informar o
        # texto de "Apresentamos a Assembleia de Deus em" antes de gerar;
        # "GERAR" gera direto, com essa parte em branco (para preencher a
        # mao). Os demais campos (Sexo, Cidade/data) continuam em branco
        # no PDF gerado em ambos os casos.
        linha_carta = ctk.CTkFrame(janela, fg_color=cores.BRANCO, corner_radius=8)
        linha_carta.pack(fill="x", padx=28, pady=6)
        linha_carta.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            linha_carta,
            text=TIPO_CARTA_RECOMENDACAO,
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL
        ).grid(row=0, column=0, padx=14, pady=10, sticky="ew")

        ctk.CTkButton(
            linha_carta,
            text="EDITAR",
            width=95,
            height=38,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            command=self.abrir_editor_carta_recomendacao,
        ).grid(row=0, column=1, padx=(8, 4), pady=10)

        ctk.CTkButton(
            linha_carta,
            text="GERAR",
            width=95,
            height=38,
            fg_color=cores.VERDE,
            hover_color="#1F7A45",
            command=self.gerar_carta_recomendacao,
        ).grid(row=0, column=2, padx=(4, 14), pady=10)

    def abrir_editor_carta_recomendacao(self):
        if self.janela_documentos is not None and self.janela_documentos.winfo_exists():
            self.janela_documentos.destroy()
            self.janela_documentos = None

        EditorCartaRecomendacao(self, self.id_membro, ao_gerar=self.gerar_carta_recomendacao)

    def gerar_documento_oficial(self, tipo_documento, final=False):
        membro = buscar_membro_por_id(self.id_membro)
        if membro is None:
            messagebox.showerror("SIGM", "Membro nao encontrado.")
            return

        if tipo_documento == TIPO_FICHA_CADASTRAL and not final:
            self.abrir_editor_ficha_cadastral()
            return

        if tipo_documento == TIPO_PEDIDO_MEMBRAMENTO:
            self.abrir_editor_membramento()
            return

        if tipo_documento == TIPO_PEDIDO_RECONCILIACAO:
            self.abrir_editor_reconciliacao()
            return

        try:
            caminho = gerar_e_abrir_documento_oficial_final(
                tipo_documento,
                self.id_membro
            )
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel gerar o documento.\n\nErro: {erro}"
            )
            return

        if self.janela_documentos is not None and self.janela_documentos.winfo_exists():
            self.janela_documentos.destroy()

        self.janela_documentos = None
        self.ultimo_documento_gerado = caminho
        id_documento = None
        try:
            sessao = obter_sessao() or {}
            id_documento = registrar_documento_emitido(
                membro_id=self.id_membro,
                tipo_documento=tipo_documento,
                titulo_documento=tipo_documento,
                caminho_arquivo=str(caminho),
                usuario_emissor=sessao.get("nome") or sessao.get("login") or "",
                observacao="PDF final gerado",
            )
            registrar_acao(
                "DOCUMENTO_HISTORICO_REGISTRADO",
                f"{tipo_documento} registrado no historico.",
                modulo="Documentos",
                registro_id=id_documento,
                detalhes=f"Arquivo: {caminho}",
            )
        except Exception as erro:
            registrar_acao(
                "FALHA_REGISTRO_HISTORICO_DOCUMENTO",
                f"Falha ao registrar historico de {tipo_documento}.",
                modulo="Documentos",
                registro_id=self.id_membro,
                detalhes=str(erro),
            )
        registrar_acao(
            "PDF_GERADO",
            f"{tipo_documento} gerado para {membro[1]}.",
            modulo="Documentos",
            registro_id=id_documento or self.id_membro,
            detalhes=f"Arquivo: {caminho}",
        )

    def gerar_carta_recomendacao(self, apresentar_em="", dados_override=None):
        membro = buscar_membro_por_id(self.id_membro)
        if membro is None:
            messagebox.showerror("SIGM", "Membro nao encontrado.")
            return

        try:
            caminho = gerar_e_abrir_carta_recomendacao(
                self.id_membro, apresentar_em=apresentar_em, dados_override=dados_override,
            )
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel gerar a Carta de Recomendacao.\n\nErro: {erro}"
            )
            return

        if self.janela_documentos is not None and self.janela_documentos.winfo_exists():
            self.janela_documentos.destroy()

        self.janela_documentos = None
        self.ultimo_documento_gerado = caminho
        id_documento = None
        try:
            sessao = obter_sessao() or {}
            id_documento = registrar_documento_emitido(
                membro_id=self.id_membro,
                tipo_documento=TIPO_CARTA_RECOMENDACAO,
                titulo_documento=TIPO_CARTA_RECOMENDACAO,
                caminho_arquivo=str(caminho),
                usuario_emissor=sessao.get("nome") or sessao.get("login") or "",
                observacao="PDF gerado",
            )
            registrar_acao(
                "DOCUMENTO_HISTORICO_REGISTRADO",
                f"{TIPO_CARTA_RECOMENDACAO} registrado no historico.",
                modulo="Documentos",
                registro_id=id_documento,
                detalhes=f"Arquivo: {caminho}",
            )
        except Exception as erro:
            registrar_acao(
                "FALHA_REGISTRO_HISTORICO_DOCUMENTO",
                f"Falha ao registrar historico de {TIPO_CARTA_RECOMENDACAO}.",
                modulo="Documentos",
                registro_id=self.id_membro,
                detalhes=str(erro),
            )
        registrar_acao(
            "PDF_GERADO",
            f"{TIPO_CARTA_RECOMENDACAO} gerado para {membro[1]}.",
            modulo="Documentos",
            registro_id=id_documento or self.id_membro,
            detalhes=f"Arquivo: {caminho}",
        )

    def abrir_editor_ficha_cadastral(self):
        if (
            self.janela_editor_ficha_cadastral is not None
            and self.janela_editor_ficha_cadastral.winfo_exists()
        ):
            self.janela_editor_ficha_cadastral.lift()
            self.janela_editor_ficha_cadastral.focus_force()
            return

        self.janela_editor_ficha_cadastral = EditorFichaCadastral(
            self,
            self.id_membro,
        )

        if self.janela_documentos is not None and self.janela_documentos.winfo_exists():
            self.janela_documentos.destroy()

        self.janela_documentos = None

    def abrir_editor_membramento(self):
        if (
            self.janela_editor_membramento is not None
            and self.janela_editor_membramento.winfo_exists()
        ):
            self.janela_editor_membramento.lift()
            self.janela_editor_membramento.focus_force()
            return

        self.janela_editor_membramento = EditorMembramento(
            self,
            self.id_membro,
        )

        if self.janela_documentos is not None and self.janela_documentos.winfo_exists():
            self.janela_documentos.destroy()

        self.janela_documentos = None

    def abrir_editor_reconciliacao(self):
        if (
            self.janela_editor_reconciliacao is not None
            and self.janela_editor_reconciliacao.winfo_exists()
        ):
            self.janela_editor_reconciliacao.lift()
            self.janela_editor_reconciliacao.focus_force()
            return

        self.janela_editor_reconciliacao = EditorReconciliacao(
            self,
            self.id_membro,
        )

        if self.janela_documentos is not None and self.janela_documentos.winfo_exists():
            self.janela_documentos.destroy()

        self.janela_documentos = None

    def abrir_historico_documentos(self):
        if (
            self.janela_historico_documentos is not None
            and self.janela_historico_documentos.winfo_exists()
        ):
            self.janela_historico_documentos.lift()
            self.janela_historico_documentos.focus_force()
            return

        membro = buscar_membro_por_id(self.id_membro)
        if membro is None:
            messagebox.showerror("SIGM", "Membro nao encontrado.")
            return

        self.janela_historico_documentos = HistoricoDocumentos(
            self,
            self.id_membro,
            membro[1],
        )

    def abrir_arquivos_membro(self):
        if (
            self.janela_arquivos_membro is not None
            and self.janela_arquivos_membro.winfo_exists()
        ):
            self.janela_arquivos_membro.lift()
            self.janela_arquivos_membro.focus_force()
            return

        membro = buscar_membro_por_id(self.id_membro)
        if membro is None:
            messagebox.showerror("SIGM", "Membro nao encontrado.")
            return

        self.janela_arquivos_membro = ArquivosMembro(
            self,
            self.id_membro,
            membro[1],
        )

    def abrir_dossie_membro(self):
        if (
            self.janela_dossie_membro is not None
            and self.janela_dossie_membro.winfo_exists()
        ):
            self.janela_dossie_membro.lift()
            self.janela_dossie_membro.focus_force()
            return

        membro = buscar_membro_por_id(self.id_membro)
        if membro is None:
            messagebox.showerror("SIGM", "Membro nao encontrado.")
            return

        self.janela_dossie_membro = DossieMembro(
            self,
            self.id_membro,
        )
