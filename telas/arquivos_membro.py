import os
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from banco.database import (
    atualizar_titulo_arquivo_membro,
    excluir_registro_arquivo,
    listar_arquivos_membro,
    registrar_arquivo_membro,
)
from componentes.cabecalho_igreja import CabecalhoIgreja
from config import cores, fontes
from utils.auditoria import registrar_acao
from utils.caminhos import caminho_dados
from utils.formatadores import formatar_data_hora, normalizar_texto_busca
from utils.janelas import configurar_janela_principal, configurar_modal


PASTA_ARQUIVOS_MEMBROS = caminho_dados("arquivos_membros", criar_pai=False)
EXTENSOES_PERMITIDAS = {".pdf", ".png", ".jpg", ".jpeg"}
TIPOS_ARQUIVO = [
    "RG",
    "CPF",
    "Certidao de Batismo",
    "Carta de Mudanca",
    "Certificado",
    "Comprovante de Endereco",
    "Foto",
    "Outro",
]


class ArquivosMembro(ctk.CTkToplevel):
    LARGURA_DATA = 115
    LARGURA_TIPO = 130
    LARGURA_ARQUIVO = 180
    LARGURA_USUARIO = 120
    LARGURA_SITUACAO = 145
    LARGURA_ACOES = 390

    def __init__(self, master, id_membro, nome_membro):
        super().__init__(master)

        self.id_membro = id_membro
        self.nome_membro = nome_membro or "Membro"
        self.arquivos = []
        self.termo_pesquisa = ctk.StringVar(value="")

        self.title("Arquivos do Membro - SIGM")
        configurar_janela_principal(self, 1320, 720, 1160, 620, master)
        self.configure(fg_color=cores.FUNDO)

        self.criar_interface()
        self.carregar_arquivos()

    def criar_interface(self):
        ctk.CTkLabel(
            self,
            text="Arquivos do Membro",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(22, 4))

        self.cabecalho_igreja = CabecalhoIgreja(self)
        self.cabecalho_igreja.pack(fill="x", padx=24, pady=(0, 10))

        ctk.CTkLabel(
            self,
            text=self.nome_membro,
            font=("Segoe UI", 15, "bold"),
            text_color=cores.PRETO,
        ).pack(pady=(0, 14))

        frame_topo = ctk.CTkFrame(self, fg_color="transparent")
        frame_topo.pack(fill="x", padx=28, pady=(0, 10))
        frame_topo.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            frame_topo,
            text="Pesquisar arquivos:",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=0, column=0, padx=(0, 10), sticky="w")

        entrada_pesquisa = ctk.CTkEntry(
            frame_topo,
            textvariable=self.termo_pesquisa,
            height=34,
        )
        entrada_pesquisa.grid(row=0, column=1, sticky="ew")
        self.termo_pesquisa.trace_add("write", self.ao_pesquisar)

        ctk.CTkButton(
            frame_topo,
            text="ANEXAR ARQUIVO",
            width=160,
            height=34,
            fg_color=cores.VERDE,
            hover_color="#1F7A45",
            command=self.anexar_arquivo,
        ).grid(row=0, column=2, padx=(12, 0))

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
            command=self.carregar_arquivos,
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

    def carregar_arquivos(self):
        self.arquivos = listar_arquivos_membro(self.id_membro)
        self.renderizar_arquivos()

    def ao_pesquisar(self, *_args):
        self.renderizar_arquivos()

    def renderizar_arquivos(self):
        for widget in self.frame_lista.winfo_children():
            widget.destroy()

        if not self.arquivos:
            ctk.CTkLabel(
                self.frame_lista,
                text="Nenhum arquivo anexado para este membro.",
                font=fontes.TEXTO,
                text_color=cores.CINZA,
            ).pack(pady=34)
            return

        arquivos = self.filtrar_arquivos()
        if not arquivos:
            ctk.CTkLabel(
                self.frame_lista,
                text="Nenhum arquivo encontrado.",
                font=fontes.TEXTO,
                text_color=cores.CINZA,
            ).pack(pady=34)
            return

        self.criar_cabecalho()
        for arquivo in arquivos:
            self.criar_linha_arquivo(arquivo)

    def filtrar_arquivos(self):
        termo = self.normalizar_texto(self.termo_pesquisa.get())
        if not termo:
            return self.arquivos

        encontrados = []
        for arquivo in self.arquivos:
            texto_busca = " ".join(
                (
                    arquivo.get("tipo_arquivo") or "",
                    arquivo.get("titulo") or "",
                    arquivo.get("nome_original") or "",
                    Path(arquivo.get("caminho_arquivo") or "").name,
                    self.formatar_data(arquivo.get("data_anexo")),
                    arquivo.get("usuario_responsavel") or "",
                    self.obter_situacao(arquivo),
                )
            )
            if termo in self.normalizar_texto(texto_busca):
                encontrados.append(arquivo)

        return encontrados

    def criar_cabecalho(self):
        cabecalho = ctk.CTkFrame(
            self.frame_lista,
            fg_color=cores.AZUL_PRINCIPAL,
            corner_radius=8,
        )
        cabecalho.pack(fill="x", padx=10, pady=(10, 5))
        self.configurar_grid_linha(cabecalho)

        colunas = [
            ("Data", self.LARGURA_DATA),
            ("Tipo", self.LARGURA_TIPO),
            ("Titulo", 140),
            ("Arquivo", self.LARGURA_ARQUIVO),
            ("Usuario", self.LARGURA_USUARIO),
            ("Situacao", self.LARGURA_SITUACAO),
            ("Acoes", self.LARGURA_ACOES),
        ]

        for indice, (titulo, largura) in enumerate(colunas):
            ctk.CTkLabel(
                cabecalho,
                text=titulo,
                width=largura,
                anchor="w",
                font=("Segoe UI", 12, "bold"),
                text_color=cores.BRANCO,
            ).grid(row=0, column=indice, padx=4, pady=8, sticky="ew")

    def criar_linha_arquivo(self, arquivo):
        disponivel = self.arquivo_disponivel(arquivo)
        situacao = self.obter_situacao(arquivo)
        cor_texto = cores.PRETO if disponivel else cores.VERMELHO
        caminho = Path(arquivo.get("caminho_arquivo") or "")

        linha = ctk.CTkFrame(
            self.frame_lista,
            fg_color=cores.BRANCO,
            corner_radius=8,
        )
        linha.pack(fill="x", padx=10, pady=4)
        self.configurar_grid_linha(linha)

        valores = [
            (self.formatar_data(arquivo.get("data_anexo")), self.LARGURA_DATA),
            (arquivo.get("tipo_arquivo") or "-", self.LARGURA_TIPO),
        ]

        for indice, (valor, largura) in enumerate(valores):
            ctk.CTkLabel(
                linha,
                text=valor,
                width=largura,
                anchor="w",
                font=("Segoe UI", 12),
                text_color=cor_texto,
            ).grid(row=0, column=indice, padx=4, pady=8, sticky="w")

        ctk.CTkLabel(
            linha,
            text=arquivo.get("titulo") or "-",
            anchor="w",
            font=("Segoe UI", 12, "bold"),
            text_color=cor_texto,
        ).grid(row=0, column=2, padx=4, pady=8, sticky="ew")

        ctk.CTkLabel(
            linha,
            text=self.encurtar_texto(caminho.name or arquivo.get("nome_original") or "-"),
            width=self.LARGURA_ARQUIVO,
            anchor="w",
            font=("Segoe UI", 12),
            text_color=cor_texto,
        ).grid(row=0, column=3, padx=4, pady=8, sticky="w")

        ctk.CTkLabel(
            linha,
            text=arquivo.get("usuario_responsavel") or "-",
            width=self.LARGURA_USUARIO,
            anchor="w",
            font=("Segoe UI", 12),
            text_color=cor_texto,
        ).grid(row=0, column=4, padx=4, pady=8, sticky="w")

        ctk.CTkLabel(
            linha,
            text=situacao,
            width=self.LARGURA_SITUACAO,
            anchor="w",
            font=("Segoe UI", 12),
            text_color=cor_texto,
        ).grid(row=0, column=5, padx=4, pady=8, sticky="w")

        frame_acoes = ctk.CTkFrame(linha, fg_color="transparent")
        frame_acoes.grid(row=0, column=6, padx=4, pady=6, sticky="ew")
        frame_acoes.grid_propagate(False)
        frame_acoes.configure(width=self.LARGURA_ACOES, height=34)

        acoes = [
            ("ABRIR", 58, self.abrir_arquivo, disponivel, cores.AZUL_PRINCIPAL, cores.AZUL_ESCURO),
            ("ABRIR PASTA", 98, self.abrir_pasta_arquivo, disponivel, cores.AZUL_PRINCIPAL, cores.AZUL_ESCURO),
            ("RENOMEAR TITULO", 128, self.renomear_titulo, True, cores.VERDE, "#1F7A45"),
            ("EXCLUIR", 70, self.excluir_arquivo, True, cores.VERMELHO, "#A71D2A"),
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
                command=lambda cmd=comando, item=arquivo: cmd(item),
            ).pack(side="left", padx=2)

    def configurar_grid_linha(self, linha):
        linha.grid_columnconfigure(0, minsize=self.LARGURA_DATA, weight=0)
        linha.grid_columnconfigure(1, minsize=self.LARGURA_TIPO, weight=0)
        linha.grid_columnconfigure(2, minsize=140, weight=1)
        linha.grid_columnconfigure(3, minsize=self.LARGURA_ARQUIVO, weight=0)
        linha.grid_columnconfigure(4, minsize=self.LARGURA_USUARIO, weight=0)
        linha.grid_columnconfigure(5, minsize=self.LARGURA_SITUACAO, weight=0)
        linha.grid_columnconfigure(6, minsize=self.LARGURA_ACOES, weight=0)

    def anexar_arquivo(self):
        caminho_origem = filedialog.askopenfilename(
            parent=self,
            title="Selecionar arquivo",
            filetypes=[
                ("Arquivos permitidos", "*.pdf *.png *.jpg *.jpeg"),
                ("PDF", "*.pdf"),
                ("Imagens", "*.png *.jpg *.jpeg"),
            ],
        )

        if not caminho_origem:
            return

        caminho_origem = Path(caminho_origem)
        extensao = caminho_origem.suffix.lower()
        if extensao not in EXTENSOES_PERMITIDAS:
            messagebox.showwarning(
                "SIGM",
                "Formato nao permitido.\n\nUse apenas PDF, PNG, JPG ou JPEG.",
                parent=self,
            )
            return

        dados = self.solicitar_dados_anexo(caminho_origem)
        if not dados:
            return

        try:
            caminho_destino = self.copiar_arquivo_para_membro(
                caminho_origem,
                dados["tipo_arquivo"],
            )
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel copiar o arquivo.\n\nErro: {erro}",
                parent=self,
            )
            return

        try:
            id_arquivo = registrar_arquivo_membro(
                membro_id=self.id_membro,
                tipo_arquivo=dados["tipo_arquivo"],
                titulo=dados["titulo"],
                nome_original=caminho_origem.name,
                caminho_arquivo=str(caminho_destino),
                usuario_responsavel=self.obter_usuario_responsavel(),
                observacao=dados["observacao"],
            )
            registrar_acao(
                "ARQUIVO_ANEXADO",
                f"Arquivo {dados['titulo']} anexado ao membro {self.nome_membro}.",
                modulo="Arquivos do Membro",
                registro_id=id_arquivo,
                detalhes=f"Arquivo: {caminho_destino}",
            )
        except Exception as erro:
            try:
                caminho_destino.unlink(missing_ok=True)
            except Exception:
                pass

            messagebox.showerror(
                "Erro no SIGM",
                f"O arquivo foi copiado, mas nao foi possivel registrar no banco.\n\nErro: {erro}",
                parent=self,
            )
            return

        self.carregar_arquivos()
        messagebox.showinfo("SIGM", "Arquivo anexado com sucesso.", parent=self)

    def solicitar_dados_anexo(self, caminho_origem):
        janela = ctk.CTkToplevel(self)
        janela.title("Anexar Arquivo - SIGM")
        janela.geometry("480x430")
        janela.resizable(False, False)
        janela.configure(fg_color=cores.FUNDO)
        configurar_modal(janela, self)
        janela.grab_set()

        resultado = {"dados": None}

        ctk.CTkLabel(
            janela,
            text="Dados do Arquivo",
            font=fontes.SUBTITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(22, 12))

        frame = ctk.CTkFrame(janela, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=(0, 10))
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Tipo:", anchor="w").grid(row=0, column=0, sticky="w", pady=8)
        tipo = ctk.CTkComboBox(frame, values=TIPOS_ARQUIVO, width=250)
        tipo.set(TIPOS_ARQUIVO[0])
        tipo.grid(row=0, column=1, sticky="ew", pady=8)

        ctk.CTkLabel(frame, text="Titulo:", anchor="w").grid(row=1, column=0, sticky="w", pady=8)
        titulo = ctk.CTkEntry(frame)
        titulo.insert(0, caminho_origem.stem)
        titulo.grid(row=1, column=1, sticky="ew", pady=8)

        ctk.CTkLabel(frame, text="Observacao:", anchor="w").grid(row=2, column=0, sticky="nw", pady=8)
        observacao = ctk.CTkTextbox(frame, height=120)
        observacao.grid(row=2, column=1, sticky="ew", pady=8)

        def confirmar():
            tipo_arquivo = tipo.get().strip()
            titulo_arquivo = titulo.get().strip()
            if not tipo_arquivo or not titulo_arquivo:
                messagebox.showwarning(
                    "SIGM",
                    "Informe o tipo e o titulo do arquivo.",
                    parent=janela,
                )
                return

            resultado["dados"] = {
                "tipo_arquivo": tipo_arquivo,
                "titulo": titulo_arquivo,
                "observacao": observacao.get("1.0", "end").strip(),
            }
            janela.destroy()

        frame_botoes = ctk.CTkFrame(janela, fg_color="transparent")
        frame_botoes.pack(fill="x", padx=24, pady=(0, 18))

        ctk.CTkButton(
            frame_botoes,
            text="ANEXAR",
            width=130,
            fg_color=cores.VERDE,
            hover_color="#1F7A45",
            command=confirmar,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            frame_botoes,
            text="CANCELAR",
            width=130,
            fg_color=cores.CINZA,
            hover_color="#444444",
            command=janela.destroy,
        ).pack(side="right", padx=6)

        self.wait_window(janela)
        return resultado["dados"]

    def copiar_arquivo_para_membro(self, caminho_origem, tipo_arquivo):
        pasta_destino = self.obter_pasta_destino(caminho_origem)
        pasta_destino.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_base = self.limpar_nome_arquivo(tipo_arquivo)
        extensao = caminho_origem.suffix.lower()
        caminho_destino = pasta_destino / f"{nome_base}_{timestamp}{extensao}"

        contador = 1
        while caminho_destino.exists():
            caminho_destino = pasta_destino / f"{nome_base}_{timestamp}_{contador}{extensao}"
            contador += 1

        shutil.copy2(caminho_origem, caminho_destino)
        return caminho_destino

    def obter_pasta_destino(self, caminho_origem):
        extensao = caminho_origem.suffix.lower()
        if extensao == ".pdf":
            subpasta = "documentos"
        elif extensao in {".png", ".jpg", ".jpeg"}:
            subpasta = "imagens"
        else:
            subpasta = "outros"

        return (
            PASTA_ARQUIVOS_MEMBROS
            / f"membro_{int(self.id_membro):06d}"
            / subpasta
        )

    def abrir_arquivo(self, arquivo):
        caminho = self.obter_caminho_existente(arquivo)
        if caminho is None:
            return

        try:
            os.startfile(caminho)
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel abrir o arquivo.\n\nErro: {erro}",
                parent=self,
            )

    def abrir_pasta_arquivo(self, arquivo):
        caminho = self.obter_caminho_existente(arquivo)
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
                    f"Nao foi possivel abrir a pasta.\n\nErro: {erro}",
                    parent=self,
                )

    def renomear_titulo(self, arquivo):
        novo_titulo = self.solicitar_novo_titulo(arquivo.get("titulo") or "")
        if not novo_titulo:
            return

        try:
            atualizar_titulo_arquivo_membro(arquivo["id"], novo_titulo)
            registrar_acao(
                "TITULO_ARQUIVO_ALTERADO",
                f"Titulo de arquivo alterado para {novo_titulo}.",
                modulo="Arquivos do Membro",
                registro_id=arquivo.get("id"),
                detalhes=f"Titulo anterior: {arquivo.get('titulo') or ''}",
            )
            self.carregar_arquivos()
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel renomear o titulo.\n\nErro: {erro}",
                parent=self,
            )

    def solicitar_novo_titulo(self, titulo_atual):
        janela = ctk.CTkToplevel(self)
        janela.title("Renomear Titulo - SIGM")
        janela.geometry("420x190")
        janela.resizable(False, False)
        janela.configure(fg_color=cores.FUNDO)
        configurar_modal(janela, self)
        janela.grab_set()

        resultado = {"titulo": None}

        ctk.CTkLabel(
            janela,
            text="Renomear Titulo",
            font=fontes.SUBTITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(20, 10))

        entrada = ctk.CTkEntry(janela, width=340)
        entrada.insert(0, titulo_atual)
        entrada.pack(pady=(0, 14))
        entrada.focus_set()

        def confirmar():
            titulo = entrada.get().strip()
            if not titulo:
                messagebox.showwarning("SIGM", "Informe o novo titulo.", parent=janela)
                return
            resultado["titulo"] = titulo
            janela.destroy()

        frame_botoes = ctk.CTkFrame(janela, fg_color="transparent")
        frame_botoes.pack(fill="x", padx=34)

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
        return resultado["titulo"]

    def excluir_arquivo(self, arquivo):
        opcao = self.solicitar_tipo_exclusao()
        if not opcao:
            return

        caminho = Path(arquivo.get("caminho_arquivo") or "")

        try:
            if opcao == "arquivo" and caminho.exists():
                caminho.unlink()

            excluir_registro_arquivo(arquivo["id"])
            if opcao == "arquivo":
                registrar_acao(
                    "ARQUIVO_REGISTRO_E_FISICO_EXCLUIDOS",
                    f"Registro e arquivo fisico excluidos: {arquivo.get('titulo') or arquivo.get('tipo_arquivo') or 'arquivo'}.",
                    modulo="Arquivos do Membro",
                    registro_id=arquivo.get("id"),
                    detalhes=f"Arquivo: {caminho}",
                )
            else:
                registrar_acao(
                    "REGISTRO_ARQUIVO_EXCLUIDO",
                    f"Registro de arquivo excluido: {arquivo.get('titulo') or arquivo.get('tipo_arquivo') or 'arquivo'}.",
                    modulo="Arquivos do Membro",
                    registro_id=arquivo.get("id"),
                    detalhes=f"Arquivo: {caminho}",
                )
            self.carregar_arquivos()
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel excluir o arquivo.\n\nErro: {erro}",
                parent=self,
            )

    def solicitar_tipo_exclusao(self):
        janela = ctk.CTkToplevel(self)
        janela.title("Excluir Arquivo - SIGM")
        janela.geometry("500x240")
        janela.resizable(False, False)
        janela.configure(fg_color=cores.FUNDO)
        configurar_modal(janela, self)
        janela.grab_set()

        resultado = {"opcao": None}

        ctk.CTkLabel(
            janela,
            text="Excluir arquivo",
            font=fontes.SUBTITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(22, 8))

        ctk.CTkLabel(
            janela,
            text=(
                "Escolha como deseja excluir este item.\n"
                "O arquivo fisico so sera apagado se voce confirmar essa opcao."
            ),
            font=fontes.TEXTO,
            text_color=cores.PRETO,
            justify="center",
        ).pack(padx=24, pady=(0, 16))

        def escolher(opcao):
            resultado["opcao"] = opcao
            janela.destroy()

        frame_botoes = ctk.CTkFrame(janela, fg_color="transparent")
        frame_botoes.pack(fill="x", padx=18)

        ctk.CTkButton(
            frame_botoes,
            text="SOMENTE REGISTRO",
            width=145,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            command=lambda: escolher("registro"),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            frame_botoes,
            text="REGISTRO E ARQUIVO",
            width=155,
            fg_color=cores.VERMELHO,
            hover_color="#A71D2A",
            command=lambda: escolher("arquivo"),
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
        return resultado["opcao"]

    def obter_caminho_existente(self, arquivo):
        caminho = Path(arquivo.get("caminho_arquivo") or "")
        if caminho.exists() and caminho.is_file():
            return caminho

        messagebox.showerror(
            "SIGM",
            "Arquivo nao encontrado.",
            parent=self,
        )
        return None

    def arquivo_disponivel(self, arquivo):
        caminho = Path(arquivo.get("caminho_arquivo") or "")
        return caminho.exists() and caminho.is_file()

    def obter_situacao(self, arquivo):
        if self.arquivo_disponivel(arquivo):
            return "Disponivel"
        return "Arquivo nao encontrado"

    def obter_usuario_responsavel(self):
        janela = self
        visitados = set()

        while janela is not None and id(janela) not in visitados:
            visitados.add(id(janela))
            usuario_logado = getattr(janela, "usuario_logado", None)

            if isinstance(usuario_logado, dict):
                return (
                    usuario_logado.get("nome")
                    or usuario_logado.get("usuario")
                    or ""
                )

            if usuario_logado:
                return str(usuario_logado)

            janela = getattr(janela, "master", None)

        return ""

    @staticmethod
    def formatar_data(valor):
        return formatar_data_hora(valor)

    @staticmethod
    def limpar_nome_arquivo(valor):
        texto = str(valor or "").strip().lower()
        texto = unicodedata.normalize("NFD", texto)
        texto = "".join(
            caractere
            for caractere in texto
            if unicodedata.category(caractere) != "Mn"
        )
        texto = re.sub(r"[^a-z0-9]+", "_", texto)
        texto = texto.strip("_")
        return texto or "arquivo"

    @staticmethod
    def encurtar_texto(valor, limite=36):
        texto = str(valor or "-")
        if len(texto) <= limite:
            return texto
        return f"{texto[:16]}...{texto[-16:]}"

    @staticmethod
    def normalizar_texto(valor):
        return normalizar_texto_busca(valor)
