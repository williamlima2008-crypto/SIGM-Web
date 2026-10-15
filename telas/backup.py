import os
import zipfile
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from banco.database import buscar_configuracoes_igreja
from componentes.cabecalho_igreja import CabecalhoIgreja
from config import cores, fontes
from utils.auditoria import registrar_acao
from utils.caminhos import base_dados, caminho_dados
from utils.janelas import configurar_janela_principal


PASTA_BACKUP = caminho_dados("backup", criar_pai=False)
ITENS_BACKUP = (
    "sigm.db",
    "fotos_membros",
    "arquivos_membros",
    "documentos_gerados",
    "relatorios",
)


def deve_ignorar_backup(caminho):
    nome = caminho.name.lower()
    return nome.endswith((".tmp", ".temp", ".log")) or "__pycache__" in caminho.parts


def adicionar_caminho_ao_zip(arquivo_zip, caminho, base):
    if not caminho.exists():
        return
    if caminho.is_file():
        if not deve_ignorar_backup(caminho):
            arquivo_zip.write(caminho, caminho.relative_to(base))
        return
    for arquivo in caminho.rglob("*"):
        if arquivo.is_file() and not deve_ignorar_backup(arquivo):
            arquivo_zip.write(arquivo, arquivo.relative_to(base))


def caminhos_logo_assinatura_carimbo():
    configuracoes = buscar_configuracoes_igreja()
    caminhos = []
    for campo in ("logotipo", "assinatura_pastor", "carimbo"):
        valor = str(configuracoes.get(campo) or "").strip()
        if not valor:
            continue
        caminho = Path(valor)
        if not caminho.is_absolute():
            caminho = base_dados() / caminho
        if caminho.exists() and caminho.is_file():
            caminhos.append(caminho)
    return caminhos


def criar_arquivo_backup():
    PASTA_BACKUP.mkdir(parents=True, exist_ok=True)
    destino = PASTA_BACKUP / f"SIGM_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    base = base_dados()
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as arquivo_zip:
        for item in ITENS_BACKUP:
            adicionar_caminho_ao_zip(arquivo_zip, base / item, base)
        for caminho in caminhos_logo_assinatura_carimbo():
            adicionar_caminho_ao_zip(arquivo_zip, caminho, base)
    return destino


class Backup(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)

        self.title("Backup - SIGM")
        configurar_janela_principal(self, 900, 620, 760, 520, master)
        self.configure(fg_color=cores.FUNDO)

        self.criar_interface()
        self.atualizar_status()

    def criar_interface(self):
        ctk.CTkLabel(
            self,
            text="Backup",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(22, 8))

        CabecalhoIgreja(self).pack(fill="x", padx=24, pady=(0, 12))

        painel = ctk.CTkFrame(self, fg_color=cores.BRANCO, corner_radius=8)
        painel.pack(fill="both", expand=True, padx=24, pady=(0, 12))

        self.label_status = ctk.CTkLabel(
            painel,
            text="",
            font=("Segoe UI", 13),
            text_color=cores.PRETO,
            justify="left",
            anchor="nw",
        )
        self.label_status.pack(fill="both", expand=True, padx=18, pady=18)

        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.pack(fill="x", padx=24, pady=(0, 18))

        self.botao(rodape, "CRIAR BACKUP ZIP", self.criar_backup, cor=cores.VERDE, hover="#1F7A45", largura=170).pack(side="left", padx=5)
        self.botao(rodape, "ABRIR PASTA", self.abrir_pasta_backup).pack(side="left", padx=5)
        self.botao(rodape, "RESTAURAR BACKUP", self.restaurar_backup, cor=cores.VERMELHO, hover="#A71D2A", largura=160).pack(side="left", padx=5)
        self.botao(rodape, "ATUALIZAR", self.atualizar_status).pack(side="left", padx=5)
        self.botao(rodape, "FECHAR", self.destroy, cor=cores.CINZA, hover="#444444").pack(side="right", padx=5)

    def atualizar_status(self):
        PASTA_BACKUP.mkdir(parents=True, exist_ok=True)
        ultimo = self.ultimo_backup()
        linhas = [
            f"Pasta de dados: {base_dados()}",
            f"Pasta de backups: {PASTA_BACKUP}",
            "",
            "Itens incluidos:",
            "- sigm.db",
            "- fotos_membros/",
            "- arquivos_membros/",
            "- documentos_gerados/",
            "- relatorios/",
            "- logo, assinatura e carimbo configurados",
            "",
        ]
        if ultimo:
            data = datetime.fromtimestamp(ultimo.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
            linhas.append(f"Ultimo backup: {ultimo.name}")
            linhas.append(f"Data: {data}")
            linhas.append(f"Tamanho: {self.formatar_tamanho(ultimo.stat().st_size)}")
        else:
            linhas.append("Ultimo backup: nenhum backup encontrado.")
        self.label_status.configure(text="\n".join(linhas))

    def ultimo_backup(self):
        if not PASTA_BACKUP.exists():
            return None
        arquivos = [arquivo for arquivo in PASTA_BACKUP.glob("SIGM_backup_*.zip") if arquivo.is_file()]
        if not arquivos:
            return None
        return max(arquivos, key=lambda arquivo: arquivo.stat().st_mtime)

    def caminhos_logo_assinatura_carimbo(self):
        return caminhos_logo_assinatura_carimbo()

    def criar_backup(self):
        try:
            destino = criar_arquivo_backup()
            registrar_acao("BACKUP_CRIADO", "Backup ZIP criado.", modulo="Backup", detalhes=str(destino))
            self.atualizar_status()
            messagebox.showinfo("SIGM", f"Backup criado com sucesso:\n{destino}", parent=self)
        except Exception as erro:
            messagebox.showerror("Erro no SIGM", f"Nao foi possivel criar o backup.\n\nErro: {erro}", parent=self)

    def adicionar_ao_zip(self, arquivo_zip, caminho, base):
        adicionar_caminho_ao_zip(arquivo_zip, caminho, base)

    @staticmethod
    def deve_ignorar(caminho):
        return deve_ignorar_backup(caminho)

    def abrir_pasta_backup(self):
        PASTA_BACKUP.mkdir(parents=True, exist_ok=True)
        os.startfile(PASTA_BACKUP)

    def restaurar_backup(self):
        caminho = filedialog.askopenfilename(
            parent=self,
            title="Selecionar backup do SIGM",
            filetypes=[("Backup ZIP", "*.zip")],
            initialdir=str(PASTA_BACKUP),
        )
        if not caminho:
            return

        confirmar = messagebox.askyesno(
            "Restaurar backup",
            "A restauracao substituirá dados atuais por arquivos do backup selecionado.\n\nDeseja continuar?",
            parent=self,
        )
        if not confirmar:
            return

        try:
            self.extrair_backup_seguro(Path(caminho))
            registrar_acao("BACKUP_RESTAURADO", "Backup ZIP restaurado.", modulo="Backup", detalhes=str(caminho))
            self.atualizar_status()
            messagebox.showinfo("SIGM", "Backup restaurado com sucesso. Reinicie o SIGM para recarregar todos os dados.", parent=self)
        except Exception as erro:
            messagebox.showerror("Erro no SIGM", f"Nao foi possivel restaurar o backup.\n\nErro: {erro}", parent=self)

    def extrair_backup_seguro(self, caminho_zip):
        destino = base_dados().resolve()
        with zipfile.ZipFile(caminho_zip, "r") as arquivo_zip:
            for membro in arquivo_zip.infolist():
                caminho_destino = (destino / membro.filename).resolve()
                if not str(caminho_destino).startswith(str(destino)):
                    raise ValueError("Backup contem caminho invalido.")
            arquivo_zip.extractall(destino)

    @staticmethod
    def formatar_tamanho(tamanho):
        if tamanho < 1024:
            return f"{tamanho} B"
        if tamanho < 1024 * 1024:
            return f"{tamanho / 1024:.1f} KB"
        return f"{tamanho / (1024 * 1024):.1f} MB"

    def botao(self, master, texto, comando, cor=None, hover=None, largura=130):
        return ctk.CTkButton(
            master,
            text=texto,
            width=largura,
            height=36,
            fg_color=cor or cores.AZUL_PRINCIPAL,
            hover_color=hover or cores.AZUL_ESCURO,
            font=("Segoe UI", 12, "bold"),
            command=comando,
        )
