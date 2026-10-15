import os
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None

from banco.database import (
    buscar_data_funcao_membro,
    buscar_membro_por_id,
    listar_arquivos_membro,
    listar_documentos_emitidos_por_membro,
)
from componentes.cabecalho_igreja import CabecalhoIgreja
from config import cores, fontes
from documentos.integrador_documentos import buscar_caminho_foto_membro
from telas.arquivos_membro import ArquivosMembro
from telas.cadastro_membro import CadastroMembro
from telas.documentos.editor_ficha_cadastral import EditorFichaCadastral
from telas.documentos.editor_membramento import EditorMembramento
from telas.documentos.editor_reconciliacao import EditorReconciliacao
from telas.documentos.historico_documentos import HistoricoDocumentos
from utils.janelas import configurar_janela_principal


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


class DossieMembro(ctk.CTkToplevel):

    def __init__(self, master, id_membro):
        super().__init__(master)

        self.id_membro = id_membro
        self.membro = None
        self.documentos = []
        self.arquivos = []
        self.imagem_foto = None
        self.janela_edicao = None
        self.janela_historico = None
        self.janela_arquivos = None
        self.janela_editor_ficha = None
        self.janela_editor_membramento = None
        self.janela_editor_reconciliacao = None

        self.title("Dossie Digital do Membro - SIGM")
        configurar_janela_principal(self, 1240, 780, 980, 620, master)
        self.configure(fg_color=cores.FUNDO)

        self.carregar_dados()

        if self.membro is None:
            messagebox.showerror("SIGM", "Membro nao encontrado.", parent=self)
            self.destroy()
            return

        self.criar_interface()
        self.bind("<FocusIn>", lambda _event: self.atualizar_resumos())

    def carregar_dados(self):
        self.membro = buscar_membro_por_id(self.id_membro)
        if self.membro is None:
            return

        self.documentos = listar_documentos_emitidos_por_membro(self.id_membro)
        self.arquivos = listar_arquivos_membro(self.id_membro)

    def criar_interface(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            self,
            text=f"Dossie Digital do Membro - {self.valor('nome')}",
            font=("Segoe UI", 15, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=0, column=0, padx=20, pady=(6, 3), sticky="ew")

        self.cabecalho_igreja = CabecalhoIgreja(self, tamanho="compacto")
        self.cabecalho_igreja.grid(row=1, column=0, padx=20, pady=(0, 4), sticky="ew")

        self.criar_cabecalho()
        self.criar_abas()

    def criar_cabecalho(self):
        cabecalho = ctk.CTkFrame(self, fg_color=cores.BRANCO, corner_radius=8)
        cabecalho.grid(row=2, column=0, padx=20, pady=(0, 4), sticky="ew")
        cabecalho.grid_columnconfigure(1, weight=1)

        self.criar_foto(cabecalho).grid(row=0, column=0, padx=10, pady=6, sticky="n")

        dados = ctk.CTkFrame(cabecalho, fg_color="transparent")
        dados.grid(row=0, column=1, padx=(0, 10), pady=6, sticky="nsew")
        dados.grid_columnconfigure((0, 1, 2, 3), weight=1)

        itens = [
            ("ID", self.valor("id")),
            ("Status", self.valor("status")),
            ("Telefone", self.valor("telefone") or self.valor("celular")),
            ("E-mail", self.valor("email")),
            ("Cargo", self.valor("cargo")),
            ("Data funcao", buscar_data_funcao_membro(self.id_membro)),
            ("Ministerio", self.valor("ministerio")),
        ]

        for indice, (rotulo, valor) in enumerate(itens):
            self.criar_bloco_info(dados, rotulo, valor).grid(
                row=indice // 4,
                column=indice % 4,
                padx=4,
                pady=4,
                sticky="ew",
            )

    def criar_foto(self, master):
        frame = ctk.CTkFrame(master, width=104, height=104, fg_color=cores.FUNDO, corner_radius=8)
        frame.grid_propagate(False)

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

    def criar_bloco_info(self, master, rotulo, valor):
        frame = ctk.CTkFrame(master, fg_color=cores.FUNDO, corner_radius=8)
        ctk.CTkLabel(
            frame,
            text=rotulo,
            font=("Segoe UI", 10, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
            anchor="w",
        ).pack(fill="x", padx=7, pady=(3, 0))
        ctk.CTkLabel(
            frame,
            text=str(valor) if valor else "-",
            font=("Segoe UI", 12),
            text_color=cores.PRETO,
            anchor="w",
        ).pack(fill="x", padx=7, pady=(0, 3))
        return frame

    def criar_abas(self):
        self.abas = ctk.CTkTabview(self, fg_color=cores.BRANCO, segmented_button_fg_color=cores.FUNDO)
        self.abas.grid(row=3, column=0, padx=20, pady=(0, 10), sticky="nsew")

        nomes_abas = [
            "RESUMO",
            "DADOS COMPLETOS",
            "DOCUMENTOS OFICIAIS",
            "HISTORICO DE DOCUMENTOS",
            "ARQUIVOS DO MEMBRO",
            "OBSERVACOES",
        ]

        for nome in nomes_abas:
            self.abas.add(nome)

        self.criar_aba_resumo()
        self.criar_aba_dados_completos()
        self.criar_aba_documentos_oficiais()
        self.criar_aba_historico()
        self.criar_aba_arquivos()
        self.criar_aba_observacoes()

    def frame_rolavel(self, nome_aba):
        frame = ctk.CTkScrollableFrame(self.abas.tab(nome_aba), fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        frame.grid_columnconfigure((0, 1), weight=1)
        return frame

    def criar_aba_resumo(self):
        frame = self.frame_rolavel("RESUMO")
        self.cards_resumo = {}

        dados_cards = [
            ("Dados pessoais", f"CPF: {self.valor('cpf') or '-'}\nNascimento: {self.valor('data_nascimento') or '-'}"),
            ("Contato", f"Telefone: {self.valor('telefone') or '-'}\nCelular: {self.valor('celular') or '-'}\nEmail: {self.valor('email') or '-'}"),
            ("Endereco", self.texto_endereco()),
            ("Dados ministeriais", f"Ministerio: {self.valor('ministerio') or '-'}\nCargo: {self.valor('cargo') or '-'}"),
            ("Situacao do membro", self.valor("status") or "-"),
            ("Documentos emitidos", str(len(self.documentos))),
            ("Arquivos anexados", str(len(self.arquivos))),
        ]

        for indice, (titulo, texto) in enumerate(dados_cards):
            card = self.criar_card(frame, titulo, texto)
            card.grid(row=indice // 2, column=indice % 2, padx=8, pady=8, sticky="nsew")
            self.cards_resumo[titulo] = card

        acoes = ctk.CTkFrame(frame, fg_color="transparent")
        acoes.grid(row=4, column=0, columnspan=2, pady=(18, 8), sticky="w")

        self.botao(acoes, "EDITAR MEMBRO", self.abrir_edicao).pack(side="left", padx=5)
        self.botao(acoes, "GERAR DOCUMENTO", lambda: self.abas.set("DOCUMENTOS OFICIAIS")).pack(side="left", padx=5)
        self.botao(acoes, "HISTORICO", self.abrir_historico_completo).pack(side="left", padx=5)
        self.botao(acoes, "ARQUIVOS", self.abrir_arquivos_completo, cor=cores.VERDE, hover="#1F7A45").pack(side="left", padx=5)

    def criar_card(self, master, titulo, texto):
        card = ctk.CTkFrame(master, fg_color=cores.BRANCO, corner_radius=8, border_width=1, border_color=cores.CINZA_CLARO)
        ctk.CTkLabel(
            card,
            text=titulo,
            font=("Segoe UI", 15, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(12, 4))
        label = ctk.CTkLabel(
            card,
            text=texto or "-",
            font=("Segoe UI", 13),
            text_color=cores.PRETO,
            justify="left",
            anchor="w",
        )
        label.pack(fill="x", padx=14, pady=(0, 12))
        card.valor_label = label
        return card

    def criar_aba_dados_completos(self):
        frame = self.frame_rolavel("DADOS COMPLETOS")

        secoes = [
            ("Dados pessoais", [("Nome", "nome"), ("RG", "rg"), ("Orgao emissor", "orgao_emissor"), ("CPF", "cpf"), ("Nascimento", "data_nascimento"), ("Cidade de nascimento", "cidade_nascimento"), ("Estado de nascimento", "estado_nascimento"), ("Estado civil", "estado_civil"), ("Profissao", "profissao"), ("Grau de instrucao escolar", "grau_instrucao")]),
            ("Contato", [("Telefone", "telefone"), ("Celular", "celular"), ("E-mail", "email")]),
            ("Endereco", [("Endereco", "endereco"), ("Numero", "numero"), ("Bairro", "bairro"), ("Cidade", "cidade"), ("Estado", "estado"), ("CEP", "cep")]),
            ("Dados familiares", [("Estado civil", "estado_civil"), ("Nome do conjuge", "nome_conjuge"), ("Nascimento do conjuge", "data_nascimento_conjuge"), ("Nome do pai", "nome_pai"), ("Nome da mae", "nome_mae")]),
            ("Dados ministeriais", [("Batismo nas aguas", "batismo_aguas"), ("Ministerio", "ministerio"), ("Cargo", "cargo"), ("Data da funcao atual", "data_funcao"), ("Curso teologico", "curso_teologico")]),
            ("Situacao", [("Status", "status")]),
            ("Observacoes", [("Observacoes", "observacoes")]),
        ]

        linha = 0
        for titulo, campos in secoes:
            bloco = ctk.CTkFrame(frame, fg_color=cores.BRANCO, corner_radius=8, border_width=1, border_color=cores.CINZA_CLARO)
            bloco.grid(row=linha, column=0, columnspan=2, padx=8, pady=8, sticky="ew")
            bloco.grid_columnconfigure(1, weight=1)
            linha += 1

            ctk.CTkLabel(
                bloco,
                text=titulo,
                font=("Segoe UI", 15, "bold"),
                text_color=cores.AZUL_PRINCIPAL,
            ).grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 4), sticky="w")

            for indice, (rotulo, chave) in enumerate(campos, start=1):
                ctk.CTkLabel(
                    bloco,
                    text=f"{rotulo}:",
                    width=150,
                    anchor="w",
                    font=("Segoe UI", 12, "bold"),
                    text_color=cores.AZUL_PRINCIPAL,
                ).grid(row=indice, column=0, padx=12, pady=5, sticky="w")
                ctk.CTkLabel(
                    bloco,
                    text=self.valor(chave) or "-",
                    anchor="w",
                    font=("Segoe UI", 12),
                    text_color=cores.PRETO,
                    justify="left",
                ).grid(row=indice, column=1, padx=12, pady=5, sticky="ew")

        self.botao(frame, "EDITAR CADASTRO", self.abrir_edicao).grid(row=linha, column=0, padx=8, pady=12, sticky="w")

    def criar_aba_documentos_oficiais(self):
        frame = self.frame_rolavel("DOCUMENTOS OFICIAIS")

        documentos = [
            ("Ficha Cadastral", self.abrir_editor_ficha),
            ("Pedido para Apresentacao / Membramento", self.abrir_editor_membramento),
            ("Pedido para Reconciliacao", self.abrir_editor_reconciliacao),
        ]

        for indice, (titulo, comando) in enumerate(documentos):
            linha = ctk.CTkFrame(frame, fg_color=cores.BRANCO, corner_radius=8, border_width=1, border_color=cores.CINZA_CLARO)
            linha.grid(row=indice, column=0, columnspan=2, padx=8, pady=8, sticky="ew")
            linha.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                linha,
                text=titulo,
                font=("Segoe UI", 14, "bold"),
                text_color=cores.AZUL_PRINCIPAL,
                anchor="w",
            ).grid(row=0, column=0, padx=14, pady=12, sticky="ew")
            self.botao(linha, "ABRIR EDITOR", comando).grid(row=0, column=1, padx=14, pady=12)

    def criar_aba_historico(self):
        frame = self.frame_rolavel("HISTORICO DE DOCUMENTOS")
        self.frame_historico_lista = frame
        self.renderizar_historico_resumo()

    def renderizar_historico_resumo(self):
        frame = self.frame_historico_lista
        for widget in frame.winfo_children():
            widget.destroy()

        self.botao(frame, "ABRIR HISTORICO COMPLETO", self.abrir_historico_completo).grid(row=0, column=0, padx=8, pady=8, sticky="w")

        if not self.documentos:
            ctk.CTkLabel(frame, text="Nenhum documento emitido para este membro.", font=fontes.TEXTO, text_color=cores.CINZA).grid(row=1, column=0, padx=8, pady=20, sticky="w")
            return

        for indice, documento in enumerate(self.documentos[:5], start=1):
            caminho = Path(documento.get("caminho_arquivo") or "")
            disponivel = caminho.exists() and caminho.is_file()
            linha = self.criar_linha_resumo(
                frame,
                documento.get("titulo_documento") or documento.get("tipo_documento") or "-",
                f"{self.formatar_data(documento.get('data_emissao'))} | {'Disponivel' if disponivel else 'Arquivo nao encontrado'}",
            )
            linha.grid(row=indice, column=0, columnspan=2, padx=8, pady=5, sticky="ew")
            self.botao(
                linha,
                "ABRIR",
                lambda item=documento: self.abrir_caminho(item.get("caminho_arquivo")),
                estado="normal" if disponivel else "disabled",
            ).grid(row=0, column=1, padx=10, pady=8)

    def criar_aba_arquivos(self):
        frame = self.frame_rolavel("ARQUIVOS DO MEMBRO")
        self.frame_arquivos_lista = frame
        self.renderizar_arquivos_resumo()

    def renderizar_arquivos_resumo(self):
        frame = self.frame_arquivos_lista
        for widget in frame.winfo_children():
            widget.destroy()

        botoes = ctk.CTkFrame(frame, fg_color="transparent")
        botoes.grid(row=0, column=0, padx=8, pady=8, sticky="w")
        self.botao(botoes, "ANEXAR NOVO", self.anexar_novo_arquivo, cor=cores.VERDE, hover="#1F7A45").pack(side="left", padx=4)
        self.botao(botoes, "VER TODOS", self.abrir_arquivos_completo).pack(side="left", padx=4)

        if not self.arquivos:
            ctk.CTkLabel(frame, text="Nenhum arquivo anexado para este membro.", font=fontes.TEXTO, text_color=cores.CINZA).grid(row=1, column=0, padx=8, pady=20, sticky="w")
            return

        for indice, arquivo in enumerate(self.arquivos[:5], start=1):
            caminho = Path(arquivo.get("caminho_arquivo") or "")
            disponivel = caminho.exists() and caminho.is_file()
            linha = self.criar_linha_resumo(
                frame,
                f"{arquivo.get('tipo_arquivo') or '-'} | {arquivo.get('titulo') or '-'}",
                f"{self.formatar_data(arquivo.get('data_anexo'))} | {'Disponivel' if disponivel else 'Arquivo nao encontrado'}",
            )
            linha.grid(row=indice, column=0, columnspan=2, padx=8, pady=5, sticky="ew")
            self.botao(
                linha,
                "ABRIR",
                lambda item=arquivo: self.abrir_caminho(item.get("caminho_arquivo")),
                estado="normal" if disponivel else "disabled",
            ).grid(row=0, column=1, padx=10, pady=8)

    def criar_linha_resumo(self, master, titulo, subtitulo):
        linha = ctk.CTkFrame(master, fg_color=cores.BRANCO, corner_radius=8, border_width=1, border_color=cores.CINZA_CLARO)
        linha.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            linha,
            text=titulo,
            font=("Segoe UI", 13, "bold"),
            text_color=cores.PRETO,
            anchor="w",
        ).grid(row=0, column=0, padx=12, pady=(8, 0), sticky="ew")
        ctk.CTkLabel(
            linha,
            text=subtitulo,
            font=("Segoe UI", 11),
            text_color=cores.CINZA,
            anchor="w",
        ).grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")
        return linha

    def criar_aba_observacoes(self):
        frame = self.frame_rolavel("OBSERVACOES")
        ctk.CTkLabel(
            frame,
            text=self.valor("observacoes") or "Sem observacoes cadastradas.",
            font=fontes.TEXTO,
            text_color=cores.PRETO,
            justify="left",
            anchor="nw",
        ).grid(row=0, column=0, columnspan=2, padx=8, pady=10, sticky="nsew")
        self.botao(frame, "EDITAR OBSERVACOES", self.abrir_edicao).grid(row=1, column=0, padx=8, pady=10, sticky="w")

    def atualizar_resumos(self):
        self.carregar_dados()
        if hasattr(self, "cards_resumo"):
            self.cards_resumo["Documentos emitidos"].valor_label.configure(text=str(len(self.documentos)))
            self.cards_resumo["Arquivos anexados"].valor_label.configure(text=str(len(self.arquivos)))
        if hasattr(self, "frame_historico_lista"):
            self.renderizar_historico_resumo()
        if hasattr(self, "frame_arquivos_lista"):
            self.renderizar_arquivos_resumo()

    def reconstruir_interface(self):
        self.carregar_dados()
        if self.membro is None:
            messagebox.showerror("SIGM", "Membro nao encontrado.", parent=self)
            self.destroy()
            return

        self.janela_edicao = None
        for widget in self.winfo_children():
            widget.destroy()
        self.criar_interface()

    def abrir_edicao(self):
        if self.janela_edicao is not None and self.janela_edicao.winfo_exists():
            self.janela_edicao.lift()
            self.janela_edicao.focus_force()
            return

        self.janela_edicao = CadastroMembro(
            self,
            id_membro=self.id_membro,
            ao_salvar=self.reconstruir_interface,
        )

    def abrir_editor_ficha(self):
        if self.janela_editor_ficha is not None and self.janela_editor_ficha.winfo_exists():
            self.janela_editor_ficha.lift()
            self.janela_editor_ficha.focus_force()
            return
        self.janela_editor_ficha = EditorFichaCadastral(self, self.id_membro)

    def abrir_editor_membramento(self):
        if self.janela_editor_membramento is not None and self.janela_editor_membramento.winfo_exists():
            self.janela_editor_membramento.lift()
            self.janela_editor_membramento.focus_force()
            return
        self.janela_editor_membramento = EditorMembramento(self, self.id_membro)

    def abrir_editor_reconciliacao(self):
        if self.janela_editor_reconciliacao is not None and self.janela_editor_reconciliacao.winfo_exists():
            self.janela_editor_reconciliacao.lift()
            self.janela_editor_reconciliacao.focus_force()
            return
        self.janela_editor_reconciliacao = EditorReconciliacao(self, self.id_membro)

    def abrir_historico_completo(self):
        if self.janela_historico is not None and self.janela_historico.winfo_exists():
            self.janela_historico.lift()
            self.janela_historico.focus_force()
            return
        self.janela_historico = HistoricoDocumentos(self, self.id_membro, self.valor("nome"))

    def abrir_arquivos_completo(self):
        if self.janela_arquivos is not None and self.janela_arquivos.winfo_exists():
            self.janela_arquivos.lift()
            self.janela_arquivos.focus_force()
            return
        self.janela_arquivos = ArquivosMembro(self, self.id_membro, self.valor("nome"))
        self.janela_arquivos.protocol("WM_DELETE_WINDOW", self.fechar_arquivos_completo)

    def anexar_novo_arquivo(self):
        self.abrir_arquivos_completo()
        self.janela_arquivos.after(200, self.executar_anexo_pela_central)

    def executar_anexo_pela_central(self):
        if self.janela_arquivos is None or not self.janela_arquivos.winfo_exists():
            return
        self.janela_arquivos.anexar_arquivo()
        self.atualizar_resumos()

    def fechar_arquivos_completo(self):
        if self.janela_arquivos is not None and self.janela_arquivos.winfo_exists():
            self.janela_arquivos.destroy()
        self.janela_arquivos = None
        self.atualizar_resumos()

    def abrir_caminho(self, caminho_arquivo):
        caminho = Path(caminho_arquivo or "")
        if not caminho.exists() or not caminho.is_file():
            messagebox.showerror("SIGM", "Arquivo nao encontrado.", parent=self)
            return
        try:
            os.startfile(caminho)
        except Exception as erro:
            messagebox.showerror("Erro no SIGM", f"Nao foi possivel abrir o arquivo.\n\nErro: {erro}", parent=self)

    def botao(self, master, texto, comando, cor=None, hover=None, estado="normal"):
        return ctk.CTkButton(
            master,
            text=texto,
            width=135,
            height=34,
            fg_color=cor or cores.AZUL_PRINCIPAL,
            hover_color=hover or cores.AZUL_ESCURO,
            font=("Segoe UI", 12, "bold"),
            state=estado,
            command=comando,
        )

    def valor(self, chave):
        if chave == "data_funcao":
            return buscar_data_funcao_membro(self.id_membro)

        indice = CAMPOS_MEMBRO.get(chave)
        if indice is None or self.membro is None or len(self.membro) <= indice:
            return ""
        return self.membro[indice] or ""

    def texto_endereco(self):
        partes = [
            self.valor("endereco"),
            self.valor("numero"),
            self.valor("bairro"),
            self.valor("cidade"),
            self.valor("estado"),
            self.valor("cep"),
        ]
        return ", ".join(parte for parte in partes if parte) or "-"

    @staticmethod
    def formatar_data(valor):
        texto = str(valor or "").strip()
        if not texto:
            return "-"
        for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                from datetime import datetime

                return datetime.strptime(texto, formato).strftime("%d/%m/%Y %H:%M")
            except ValueError:
                pass
        return texto
