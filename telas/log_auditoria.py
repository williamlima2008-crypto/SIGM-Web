import os
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from banco.database import (
    buscar_configuracoes_igreja,
    buscar_log_auditoria_por_id,
    listar_logs_auditoria,
)
from componentes.cabecalho_igreja import CabecalhoIgreja
from config import cores, fontes
from utils.auditoria import registrar_acao
from utils.caminhos import caminho_dados
from utils.janelas import configurar_janela_principal, configurar_modal
from utils.sessao import obter_sessao, usuario_eh_administrador


PASTA_RELATORIOS = caminho_dados("relatorios", criar_pai=False)


class LogAuditoria(ctk.CTkToplevel):
    LARGURA_DATA = 140
    LARGURA_USUARIO = 150
    LARGURA_ACAO = 175
    LARGURA_MODULO = 135

    def __init__(self, master):
        super().__init__(master)

        if not usuario_eh_administrador():
            messagebox.showwarning(
                "SIGM",
                "Apenas o Administrador pode acessar o Log de Auditoria.",
                parent=master,
            )
            self.destroy()
            return

        self.logs = []
        self.id_selecionado = None
        self.termo = ctk.StringVar(value="")
        self.usuario = ctk.StringVar(value="")
        self.acao = ctk.StringVar(value="")
        self.modulo = ctk.StringVar(value="")
        self.data_inicial = ctk.StringVar(value="")
        self.data_final = ctk.StringVar(value="")

        self.title("Log de Auditoria - SIGM")
        configurar_janela_principal(self, 1260, 740, 1080, 640, master)
        self.configure(fg_color=cores.FUNDO)

        self.criar_interface()
        self.carregar_logs()

    def criar_interface(self):
        ctk.CTkLabel(
            self,
            text="Log de Auditoria",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(22, 8))

        self.cabecalho_igreja = CabecalhoIgreja(self)
        self.cabecalho_igreja.pack(fill="x", padx=24, pady=(0, 12))

        filtros = ctk.CTkFrame(self, fg_color="transparent")
        filtros.pack(fill="x", padx=24, pady=(0, 10))
        filtros.grid_columnconfigure((1, 3, 5), weight=1)

        self.criar_campo_filtro(filtros, "Pesquisa:", self.termo, 0, 0)
        self.criar_campo_filtro(filtros, "Usuario:", self.usuario, 0, 2)
        self.criar_campo_filtro(filtros, "Acao:", self.acao, 0, 4)
        self.criar_campo_filtro(filtros, "Modulo:", self.modulo, 1, 0)
        self.criar_campo_filtro(filtros, "Data inicial:", self.data_inicial, 1, 2, "YYYY-MM-DD")
        self.criar_campo_filtro(filtros, "Data final:", self.data_final, 1, 4, "YYYY-MM-DD")

        self.frame_lista = ctk.CTkScrollableFrame(self, corner_radius=10)
        self.frame_lista.pack(padx=24, pady=(0, 14), fill="both", expand=True)

        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(fill="x", padx=24, pady=(0, 18))

        acoes = [
            ("ATUALIZAR", self.carregar_logs, cores.AZUL_PRINCIPAL, cores.AZUL_ESCURO),
            ("LIMPAR FILTROS", self.limpar_filtros, cores.CINZA, "#444444"),
            ("VER DETALHES", self.ver_detalhes, cores.AZUL_PRINCIPAL, cores.AZUL_ESCURO),
            ("EXPORTAR PDF", self.exportar_pdf, cores.VERDE, "#1F7A45"),
        ]

        for texto, comando, cor, hover in acoes:
            ctk.CTkButton(
                botoes,
                text=texto,
                width=145,
                height=38,
                fg_color=cor,
                hover_color=hover,
                command=comando,
            ).pack(side="left", padx=6)

        ctk.CTkButton(
            botoes,
            text="FECHAR",
            width=130,
            height=38,
            fg_color=cores.CINZA,
            hover_color="#444444",
            command=self.destroy,
        ).pack(side="right", padx=6)

        self.bind("<Return>", lambda _event: self.carregar_logs())
        self.bind("<Escape>", lambda _event: self.destroy())

    def criar_campo_filtro(self, master, rotulo, variavel, linha, coluna, placeholder=""):
        ctk.CTkLabel(
            master,
            text=rotulo,
            font=("Segoe UI", 12, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=linha, column=coluna, padx=(0, 6), pady=5, sticky="w")

        entrada = ctk.CTkEntry(master, textvariable=variavel, height=34, placeholder_text=placeholder)
        entrada.grid(row=linha, column=coluna + 1, padx=(0, 12), pady=5, sticky="ew")
        return entrada

    def carregar_logs(self):
        self.id_selecionado = None
        try:
            self.logs = listar_logs_auditoria(
                termo=self.termo.get(),
                acao=self.acao.get(),
                usuario=self.usuario.get(),
                modulo=self.modulo.get(),
                data_inicial=self.data_inicial.get(),
                data_final=self.data_final.get(),
                limite=1000,
            )
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel carregar o log de auditoria.\n\nErro: {erro}",
                parent=self,
            )
            self.logs = []

        self.renderizar_logs()

    def renderizar_logs(self):
        for widget in self.frame_lista.winfo_children():
            widget.destroy()

        if not self.logs:
            ctk.CTkLabel(
                self.frame_lista,
                text="Nenhum registro de auditoria encontrado.",
                font=fontes.TEXTO,
                text_color=cores.CINZA,
            ).pack(pady=36)
            return

        self.criar_cabecalho()
        for log in self.logs:
            self.criar_linha_log(log)

    def criar_cabecalho(self):
        linha = ctk.CTkFrame(self.frame_lista, fg_color=cores.AZUL_PRINCIPAL, corner_radius=8)
        linha.pack(fill="x", padx=10, pady=(10, 5))
        self.configurar_grid_linha(linha)

        colunas = [
            ("Data e hora", self.LARGURA_DATA),
            ("Usuario", self.LARGURA_USUARIO),
            ("Acao", self.LARGURA_ACAO),
            ("Modulo", self.LARGURA_MODULO),
            ("Descricao", 260),
        ]

        for indice, (texto, largura) in enumerate(colunas):
            ctk.CTkLabel(
                linha,
                text=texto,
                width=largura,
                anchor="w",
                font=("Segoe UI", 12, "bold"),
                text_color=cores.BRANCO,
            ).grid(row=0, column=indice, padx=4, pady=8, sticky="ew")

    def criar_linha_log(self, log):
        linha = ctk.CTkFrame(self.frame_lista, fg_color=cores.BRANCO, corner_radius=8)
        linha.pack(fill="x", padx=10, pady=4)
        self.configurar_grid_linha(linha)

        usuario = log.get("usuario_nome") or log.get("usuario_login") or "-"
        valores = [
            (self.formatar_data(log.get("data_hora")), self.LARGURA_DATA),
            (usuario, self.LARGURA_USUARIO),
            (log.get("acao") or "-", self.LARGURA_ACAO),
            (log.get("modulo") or "-", self.LARGURA_MODULO),
            (log.get("descricao") or "-", 260),
        ]

        for indice, (valor, largura) in enumerate(valores):
            label = ctk.CTkLabel(
                linha,
                text=self.encurtar(valor, 72 if indice == 4 else 28),
                width=largura,
                anchor="w",
                font=("Segoe UI", 12),
                text_color=cores.PRETO,
            )
            label.grid(row=0, column=indice, padx=4, pady=8, sticky="ew")
            label.bind("<Button-1>", lambda _event, item=log: self.selecionar_log(item))
            label.bind("<Double-Button-1>", lambda _event, item=log: self.ver_detalhes(item.get("id")))

        linha.bind("<Button-1>", lambda _event, item=log: self.selecionar_log(item))
        linha.bind("<Double-Button-1>", lambda _event, item=log: self.ver_detalhes(item.get("id")))

    def configurar_grid_linha(self, linha):
        linha.grid_columnconfigure(0, minsize=self.LARGURA_DATA, weight=0)
        linha.grid_columnconfigure(1, minsize=self.LARGURA_USUARIO, weight=0)
        linha.grid_columnconfigure(2, minsize=self.LARGURA_ACAO, weight=0)
        linha.grid_columnconfigure(3, minsize=self.LARGURA_MODULO, weight=0)
        linha.grid_columnconfigure(4, minsize=260, weight=1)

    def selecionar_log(self, log):
        self.id_selecionado = log.get("id")

    def limpar_filtros(self):
        for variavel in (
            self.termo,
            self.usuario,
            self.acao,
            self.modulo,
            self.data_inicial,
            self.data_final,
        ):
            variavel.set("")
        self.carregar_logs()

    def ver_detalhes(self, id_log=None):
        id_log = id_log or self.id_selecionado
        if not id_log:
            messagebox.showwarning("SIGM", "Selecione um registro.", parent=self)
            return

        log = buscar_log_auditoria_por_id(id_log)
        if not log:
            messagebox.showerror("SIGM", "Registro nao encontrado.", parent=self)
            return

        janela = ctk.CTkToplevel(self)
        janela.title("Detalhes do Log - SIGM")
        janela.geometry("720x560")
        janela.minsize(620, 480)
        janela.configure(fg_color=cores.FUNDO)
        configurar_modal(janela, self)
        janela.grab_set()

        ctk.CTkLabel(
            janela,
            text="Detalhes do Registro",
            font=fontes.SUBTITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(20, 10))

        frame = ctk.CTkScrollableFrame(janela, corner_radius=10)
        frame.pack(fill="both", expand=True, padx=24, pady=(0, 14))
        frame.grid_columnconfigure(1, weight=1)

        campos = [
            ("ID", log.get("id")),
            ("Data e hora", self.formatar_data(log.get("data_hora"))),
            ("Usuario", log.get("usuario_nome") or "-"),
            ("Login", log.get("usuario_login") or "-"),
            ("Acao", log.get("acao") or "-"),
            ("Modulo", log.get("modulo") or "-"),
            ("Descricao", log.get("descricao") or "-"),
            ("Registro relacionado", log.get("registro_id") or "-"),
            ("Detalhes tecnicos", log.get("detalhes") or "-"),
        ]

        for linha, (rotulo, valor) in enumerate(campos):
            ctk.CTkLabel(
                frame,
                text=f"{rotulo}:",
                width=160,
                anchor="nw",
                font=("Segoe UI", 13, "bold"),
                text_color=cores.AZUL_PRINCIPAL,
            ).grid(row=linha, column=0, padx=(12, 8), pady=7, sticky="nw")

            ctk.CTkLabel(
                frame,
                text=str(valor),
                anchor="nw",
                justify="left",
                wraplength=470,
                font=("Segoe UI", 13),
                text_color=cores.PRETO,
            ).grid(row=linha, column=1, padx=(0, 12), pady=7, sticky="ew")

        ctk.CTkButton(
            janela,
            text="FECHAR",
            width=120,
            fg_color=cores.CINZA,
            hover_color="#444444",
            command=janela.destroy,
        ).pack(pady=(0, 18))

    def exportar_pdf(self):
        if not self.logs:
            messagebox.showwarning("SIGM", "Nao ha registros para exportar.", parent=self)
            return

        PASTA_RELATORIOS.mkdir(parents=True, exist_ok=True)
        caminho = PASTA_RELATORIOS / f"log_auditoria_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        try:
            self.gerar_pdf(caminho, list(self.logs))
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel exportar o PDF.\n\nErro: {erro}",
                parent=self,
            )
            return

        registrar_acao(
            "LOG_AUDITORIA_EXPORTADO",
            "Log de auditoria exportado em PDF.",
            modulo="Auditoria",
            detalhes=f"Arquivo: {caminho}",
        )

        abrir = messagebox.askyesno(
            "SIGM",
            f"PDF exportado com sucesso.\n\nArquivo:\n{caminho}\n\nDeseja abrir agora?",
            parent=self,
        )
        if abrir:
            try:
                os.startfile(caminho)
            except Exception as erro:
                messagebox.showerror(
                    "Erro no SIGM",
                    f"Nao foi possivel abrir o PDF.\n\nErro: {erro}",
                    parent=self,
                )

    def gerar_pdf(self, caminho, logs):
        dados_igreja = buscar_configuracoes_igreja()
        sessao = obter_sessao() or {}
        pdf = canvas.Canvas(str(caminho), pagesize=landscape(A4))
        largura, altura = landscape(A4)

        def cabecalho():
            pdf.setFont("Helvetica-Bold", 15)
            pdf.drawString(36, altura - 34, "Log de Auditoria do SIGM")
            pdf.setFont("Helvetica", 9)
            igreja = dados_igreja.get("nome_igreja") or "Igreja nao cadastrada"
            local = " - ".join(
                parte
                for parte in (dados_igreja.get("cidade"), dados_igreja.get("estado"))
                if parte
            )
            periodo = self.descrever_periodo()
            pdf.drawString(36, altura - 50, f"Igreja: {igreja}")
            pdf.drawString(36, altura - 64, f"Local: {local or '-'}")
            pdf.drawString(36, altura - 78, f"Periodo filtrado: {periodo}")
            pdf.drawString(36, altura - 92, f"Exportado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            pdf.drawString(36, altura - 106, f"Usuario: {sessao.get('nome') or sessao.get('login') or '-'}")

        def cabecalho_tabela(y):
            pdf.setFillColor(colors.HexColor("#0B5ED7"))
            pdf.rect(36, y - 4, largura - 72, 18, fill=1, stroke=0)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 8)
            x = 42
            for titulo, tamanho in self.colunas_pdf():
                pdf.drawString(x, y, titulo)
                x += tamanho
            pdf.setFillColor(colors.black)

        cabecalho()
        y = altura - 132
        cabecalho_tabela(y)
        y -= 20
        pdf.setFont("Helvetica", 7)

        for log in logs:
            if y < 38:
                pdf.showPage()
                cabecalho()
                y = altura - 132
                cabecalho_tabela(y)
                y -= 20
                pdf.setFont("Helvetica", 7)

            valores = [
                self.formatar_data(log.get("data_hora")),
                log.get("usuario_nome") or log.get("usuario_login") or "-",
                log.get("acao") or "-",
                log.get("modulo") or "-",
                log.get("descricao") or "-",
            ]
            x = 42
            for valor, tamanho in zip(valores, [92, 110, 130, 90, 360]):
                pdf.drawString(x, y, self.encurtar(valor, max(12, int(tamanho / 5))))
                x += tamanho
            y -= 13

        pdf.save()

    @staticmethod
    def colunas_pdf():
        return [
            ("Data e hora", 92),
            ("Usuario", 110),
            ("Acao", 130),
            ("Modulo", 90),
            ("Descricao", 360),
        ]

    def descrever_periodo(self):
        inicio = self.data_inicial.get().strip()
        fim = self.data_final.get().strip()
        if inicio and fim:
            return f"{inicio} a {fim}"
        if inicio:
            return f"A partir de {inicio}"
        if fim:
            return f"Ate {fim}"
        return "Todos os registros filtrados"

    @staticmethod
    def formatar_data(valor):
        texto = str(valor or "").strip()
        if not texto:
            return "-"
        for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(texto, formato).strftime("%d/%m/%Y %H:%M:%S")
            except ValueError:
                pass
        return texto

    @staticmethod
    def encurtar(valor, limite):
        texto = str(valor or "")
        if len(texto) <= limite:
            return texto
        return f"{texto[:limite - 3]}..."
