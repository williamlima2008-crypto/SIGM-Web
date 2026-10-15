import csv
import os
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from banco.database import conectar, interpretar_data_nascimento
from componentes.cabecalho_igreja import CabecalhoIgreja
from config import cores, fontes
from utils.auditoria import registrar_acao
from utils.caminhos import caminho_dados
from utils.formatadores import formatar_data_hora
from utils.janelas import configurar_janela_principal


PASTA_RELATORIOS = caminho_dados("relatorios", criar_pai=False)


class Relatorios(ctk.CTkToplevel):
    TIPOS = (
        "Lista de todos os membros",
        "Membros ativos",
        "Congregados",
        "Visitantes",
        "Aniversariantes do mes",
        "Documentos emitidos",
        "Arquivos anexados",
    )

    def __init__(self, master):
        super().__init__(master)

        self.dados = []
        self.colunas = []

        self.title("Relatorios - SIGM")
        configurar_janela_principal(self, 1120, 720, 940, 620, master)
        self.configure(fg_color=cores.FUNDO)

        self.criar_interface()
        self.visualizar()

    def criar_interface(self):
        ctk.CTkLabel(
            self,
            text="Relatorios",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(22, 8))

        CabecalhoIgreja(self).pack(fill="x", padx=24, pady=(0, 12))

        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.pack(fill="x", padx=24, pady=(0, 10))

        ctk.CTkLabel(
            barra,
            text="Relatorio:",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(side="left", padx=(0, 8))
        self.combo_tipo = ctk.CTkComboBox(barra, values=list(self.TIPOS), width=260, height=34)
        self.combo_tipo.set(self.TIPOS[0])
        self.combo_tipo.pack(side="left", padx=4)

        self.botao(barra, "VISUALIZAR", self.visualizar).pack(side="left", padx=5)
        self.botao(barra, "EXPORTAR PDF", self.exportar_pdf).pack(side="left", padx=5)
        self.botao(barra, "EXPORTAR EXCEL", self.exportar_excel).pack(side="left", padx=5)
        self.botao(barra, "FECHAR", self.destroy, cor=cores.CINZA, hover="#444444").pack(side="right", padx=5)

        self.frame_lista = ctk.CTkScrollableFrame(self, corner_radius=8)
        self.frame_lista.pack(fill="both", expand=True, padx=24, pady=(0, 18))

    def visualizar(self):
        self.colunas, self.dados = self.carregar_relatorio(self.combo_tipo.get())
        self.renderizar()

    def carregar_relatorio(self, tipo):
        if tipo == "Lista de todos os membros":
            return self.relatorio_membros()
        if tipo == "Membros ativos":
            return self.relatorio_membros(status="Membro")
        if tipo == "Congregados":
            return self.relatorio_membros(status="Congregado")
        if tipo == "Visitantes":
            return self.relatorio_membros(status="Visitante")
        if tipo == "Aniversariantes do mes":
            return self.relatorio_aniversariantes()
        if tipo == "Documentos emitidos":
            return self.relatorio_documentos()
        if tipo == "Arquivos anexados":
            return self.relatorio_arquivos()
        return [], []

    def relatorio_membros(self, status=None):
        sql = """
            SELECT id, nome, status, celular, telefone, cidade, cargo
            FROM membros
        """
        parametros = []
        if status:
            sql += " WHERE status = ?"
            parametros.append(status)
        sql += " ORDER BY nome ASC"

        conexao = conectar()
        cursor = conexao.cursor()
        cursor.execute(sql, parametros)
        dados = [
            [id_membro, nome or "", status_membro or "", celular or telefone or "", cidade or "", cargo or ""]
            for id_membro, nome, status_membro, celular, telefone, cidade, cargo in cursor.fetchall()
        ]
        conexao.close()
        return ["ID", "Nome", "Status", "Contato", "Cidade", "Funcao"], dados

    def relatorio_aniversariantes(self):
        conexao = conectar()
        cursor = conexao.cursor()
        cursor.execute("""
            SELECT nome, data_nascimento, celular, telefone
            FROM membros
            WHERE data_nascimento IS NOT NULL
            AND TRIM(data_nascimento) <> ''
        """)
        mes = date.today().month
        dados = []
        for nome, data_nascimento, celular, telefone in cursor.fetchall():
            nascimento = interpretar_data_nascimento(data_nascimento)
            if nascimento is None or nascimento.month != mes:
                continue
            dados.append([nome or "", nascimento.strftime("%d/%m/%Y"), celular or telefone or ""])
        conexao.close()
        dados.sort(key=lambda item: (int(item[1][:2]), item[0]))
        return ["Nome", "Nascimento", "Contato"], dados

    def relatorio_documentos(self):
        conexao = conectar()
        cursor = conexao.cursor()
        cursor.execute("""
            SELECT d.titulo_documento, d.data_emissao, d.usuario_emissor, m.nome
            FROM documentos_emitidos d
            LEFT JOIN membros m ON m.id = d.membro_id
            ORDER BY d.data_emissao DESC, d.id DESC
        """)
        dados = [
            [titulo or "", formatar_data_hora(data), usuario or "", membro or ""]
            for titulo, data, usuario, membro in cursor.fetchall()
        ]
        conexao.close()
        return ["Documento", "Data", "Usuario", "Membro"], dados

    def relatorio_arquivos(self):
        conexao = conectar()
        cursor = conexao.cursor()
        cursor.execute("""
            SELECT a.tipo_arquivo, a.titulo, a.data_anexo, a.usuario_responsavel, m.nome
            FROM arquivos_membro a
            LEFT JOIN membros m ON m.id = a.membro_id
            ORDER BY a.data_anexo DESC, a.id DESC
        """)
        dados = [
            [tipo or "", titulo or "", formatar_data_hora(data), usuario or "", membro or ""]
            for tipo, titulo, data, usuario, membro in cursor.fetchall()
        ]
        conexao.close()
        return ["Tipo", "Titulo", "Data", "Usuario", "Membro"], dados

    def renderizar(self):
        for widget in self.frame_lista.winfo_children():
            widget.destroy()

        if not self.dados:
            ctk.CTkLabel(
                self.frame_lista,
                text="Nenhum registro encontrado.",
                font=fontes.TEXTO,
                text_color=cores.CINZA,
            ).pack(pady=28)
            return

        cabecalho = ctk.CTkFrame(self.frame_lista, fg_color=cores.AZUL_PRINCIPAL, corner_radius=8)
        cabecalho.pack(fill="x", padx=10, pady=(10, 5))
        for indice, coluna in enumerate(self.colunas):
            cabecalho.grid_columnconfigure(indice, weight=1)
            ctk.CTkLabel(
                cabecalho,
                text=coluna,
                font=("Segoe UI", 12, "bold"),
                text_color=cores.BRANCO,
                anchor="w",
            ).grid(row=0, column=indice, padx=8, pady=8, sticky="ew")

        for linha_dados in self.dados[:300]:
            linha = ctk.CTkFrame(self.frame_lista, fg_color=cores.BRANCO, corner_radius=8)
            linha.pack(fill="x", padx=10, pady=3)
            for indice, valor in enumerate(linha_dados):
                linha.grid_columnconfigure(indice, weight=1)
                ctk.CTkLabel(
                    linha,
                    text=str(valor) if valor else "-",
                    font=("Segoe UI", 11),
                    text_color=cores.PRETO,
                    anchor="w",
                    wraplength=230,
                ).grid(row=0, column=indice, padx=8, pady=7, sticky="ew")

    def caminho_saida(self, extensao):
        PASTA_RELATORIOS.mkdir(parents=True, exist_ok=True)
        nome = self.combo_tipo.get().lower().replace(" ", "_")
        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        return PASTA_RELATORIOS / f"{nome}_{data_hora}.{extensao}"

    def exportar_pdf(self):
        if not self.colunas:
            self.visualizar()
        caminho = self.caminho_saida("pdf")
        pdf = canvas.Canvas(str(caminho), pagesize=landscape(A4))
        largura, altura = landscape(A4)
        y = altura - 44
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, y, self.combo_tipo.get())
        y -= 28
        pdf.setFont("Helvetica-Bold", 9)
        x_inicial = 40
        largura_coluna = (largura - 80) / max(len(self.colunas), 1)
        for indice, coluna in enumerate(self.colunas):
            pdf.drawString(x_inicial + indice * largura_coluna, y, str(coluna)[:28])
        y -= 16
        pdf.setFont("Helvetica", 8)
        for linha in self.dados:
            if y < 40:
                pdf.showPage()
                y = altura - 44
                pdf.setFont("Helvetica", 8)
            for indice, valor in enumerate(linha):
                pdf.drawString(x_inicial + indice * largura_coluna, y, str(valor or "")[:32])
            y -= 14
        pdf.save()
        registrar_acao("RELATORIO_EXPORTADO", f"Relatorio exportado em PDF: {self.combo_tipo.get()}", modulo="Relatorios", detalhes=str(caminho))
        self.abrir_arquivo(caminho)
        messagebox.showinfo("SIGM", f"Relatorio exportado:\n{caminho}", parent=self)

    def exportar_excel(self):
        if not self.colunas:
            self.visualizar()
        try:
            import openpyxl
        except ImportError:
            caminho = self.caminho_saida("csv")
            with caminho.open("w", newline="", encoding="utf-8-sig") as arquivo:
                escritor = csv.writer(arquivo, delimiter=";")
                escritor.writerow(self.colunas)
                escritor.writerows(self.dados)
            registrar_acao("RELATORIO_EXPORTADO", f"Relatorio exportado em CSV: {self.combo_tipo.get()}", modulo="Relatorios", detalhes=str(caminho))
            self.abrir_arquivo(caminho)
            messagebox.showinfo("SIGM", f"Excel indisponivel; CSV exportado:\n{caminho}", parent=self)
            return

        caminho = self.caminho_saida("xlsx")
        planilha = openpyxl.Workbook()
        aba = planilha.active
        aba.title = "Relatorio"
        aba.append(self.colunas)
        for linha in self.dados:
            aba.append(linha)
        planilha.save(caminho)
        registrar_acao("RELATORIO_EXPORTADO", f"Relatorio exportado em Excel: {self.combo_tipo.get()}", modulo="Relatorios", detalhes=str(caminho))
        self.abrir_arquivo(caminho)
        messagebox.showinfo("SIGM", f"Relatorio exportado:\n{caminho}", parent=self)

    def abrir_arquivo(self, caminho):
        """Abre o arquivo exportado no programa padrao do Windows (leitor de PDF, Excel etc.)."""
        try:
            os.startfile(caminho)
        except Exception:
            pass  # se nao conseguir abrir automaticamente, o caminho ja foi mostrado na mensagem

    def botao(self, master, texto, comando, cor=None, hover=None):
        return ctk.CTkButton(
            master,
            text=texto,
            width=135,
            height=36,
            fg_color=cor or cores.AZUL_PRINCIPAL,
            hover_color=hover or cores.AZUL_ESCURO,
            font=("Segoe UI", 12, "bold"),
            command=comando,
        )
