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
from datetime import datetime
from tkinter import messagebox

from config import cores, fontes, configuracoes
from componentes.barra_superior import BarraSuperior
from componentes.cabecalho_igreja import CabecalhoIgreja
from componentes.menu_lateral import MenuLateral
from componentes.barra_status import BarraStatus
from componentes.card import Card

from telas.consulta_membros import ConsultaMembros
from telas.aniversariantes import Aniversariantes
from telas.backup import Backup
from telas.central_documentos import CentralDocumentos
from telas.configuracao_igreja import ConfiguracoesIgreja
from telas.log_auditoria import LogAuditoria
from telas.pre_cadastros import PreCadastros
from telas.relatorios import Relatorios
from telas.usuarios import Usuarios
from banco.database import (
    buscar_configuracoes_igreja,
    listar_arquivos_anexados_recentes,
    listar_documentos_emitidos_recentes,
    proximos_aniversariantes,
    total_arquivos_anexados,
    total_documentos_emitidos,
    total_documentos_emitidos_hoje,
    total_membros,
    total_por_status,
    ultimos_membros_cadastrados,
)
from utils.janelas import configurar_janela_principal, configurar_modal
from utils.auditoria import registrar_acao
from utils.caminhos import caminho_dados
from utils.sessao import limpar_sessao, obter_sessao, usuario_eh_administrador
from config.versao import DESENVOLVEDOR, NOME_COMPLETO, VERSAO


PASTA_BACKUP = caminho_dados("backup", criar_pai=False)


class Dashboard(ctk.CTkToplevel):

    def __init__(self, master, usuario_logado):
        super().__init__(master)

        self.master = master
        self.usuario_logado = usuario_logado
        self.janelas_membros = None
        self.janela_configuracoes = None
        self.janela_usuarios = None
        self.janela_auditoria = None
        self.janela_documentos = None
        self.janela_aniversariantes = None
        self.janela_relatorios = None
        self.janela_backup = None
        self.janela_pre_cadastros = None

        self.title("Dashboard - SIGM")
        configurar_janela_principal(self, 1280, 760, 1100, 680, master)
        self.configure(fg_color=cores.FUNDO)

        self.protocol("WM_DELETE_WINDOW", self.sair)
        self.criar_interface()

    def criar_interface(self):
        sessao = obter_sessao() or self.usuario_logado or {}
        nome = sessao.get("nome", "")
        perfil = sessao.get("perfil", "")
        indicadores = self.carregar_indicadores(nome, perfil)

        BarraSuperior(
            self,
            titulo="",
            usuario=nome,
            comando_trocar_usuario=self.trocar_usuario,
            comando_sair=self.sair,
        ).pack(fill="x")

        area_central = ctk.CTkFrame(self, fg_color=cores.FUNDO)
        area_central.pack(fill="both", expand=True)

        MenuLateral(
            area_central,
            comandos={
                "membros": self.abrir_membros,
                "pre_cadastros": self.abrir_pre_cadastros,
                "configuracoes": self.abrir_configuracoes,
                "documentos": self.abrir_documentos,
                "usuarios": self.abrir_usuarios,
                "aniversariantes": self.abrir_aniversariantes,
                "relatorios": self.abrir_relatorios,
                "auditoria": self.abrir_auditoria,
                "backup": self.abrir_backup,
                "sobre": self.abrir_sobre,
            },
            itens_ocultos=[] if usuario_eh_administrador() else ["usuarios", "auditoria"],
        ).pack(side="left", fill="y")

        conteudo = ctk.CTkFrame(
            area_central,
            fg_color=cores.FUNDO
        )
        conteudo.pack(side="left", fill="both", expand=True, padx=25, pady=25)

        self.cabecalho_igreja = CabecalhoIgreja(conteudo, tamanho="grande")
        self.cabecalho_igreja.pack(fill="x", pady=(0, 16))

        corpo_dashboard = ctk.CTkScrollableFrame(
            conteudo,
            fg_color="transparent",
            corner_radius=0,
        )
        corpo_dashboard.pack(fill="both", expand=True)

        saudacao = self.pegar_saudacao()

        titulo = ctk.CTkLabel(
            corpo_dashboard,
            text=f"{saudacao}, {nome}!",
            font=("Segoe UI", 28, "bold"),
            text_color=cores.PRETO
        )
        titulo.pack(anchor="w", pady=(0, 5))

        data_atual = datetime.now().strftime("%d/%m/%Y - %H:%M")

        subtitulo = ctk.CTkLabel(
            corpo_dashboard,
            text=f"Painel geral do sistema • {data_atual}",
            font=fontes.TEXTO,
            text_color=cores.CINZA
        )
        subtitulo.pack(anchor="w", pady=(0, 25))

        frame_cards = ctk.CTkFrame(corpo_dashboard, fg_color="transparent")
        frame_cards.pack(fill="x")

        frame_cards.grid_columnconfigure(0, weight=1)
        frame_cards.grid_columnconfigure(1, weight=1)
        frame_cards.grid_columnconfigure(2, weight=1)

        Card(
            frame_cards,
            titulo="Total de Membros",
            valor=total_membros(),
            icone="👥",
            comando=self.abrir_membros
        ).grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        Card(
            frame_cards,
            titulo="Membros Ativos",
            valor=total_por_status("Membro"),
            icone="✅",
            comando=self.abrir_membros
        ).grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        Card(
            frame_cards,
            titulo="Visitantes",
            valor=total_por_status("Visitante"),
            icone="🆕",
            comando=self.abrir_membros
        ).grid(row=0, column=2, padx=10, pady=10, sticky="nsew")

        Card(
            frame_cards,
            titulo="Congregados",
            valor=total_por_status("Congregado"),
            icone="🏛️",
            comando=self.abrir_membros
        ).grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        Card(
            frame_cards,
            titulo="PDFs Emitidos",
            valor=indicadores["total_pdfs"],
            icone="📄",
            comando=self.abrir_documentos
        ).grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

        Card(
            frame_cards,
            titulo="Backup",
            valor=indicadores["status_backup"],
            icone="💾",
            comando=self.abrir_backup
        ).grid(row=1, column=2, padx=10, pady=10, sticky="nsew")

        painel = ctk.CTkFrame(corpo_dashboard, corner_radius=10, fg_color=cores.BRANCO)
        painel.pack(fill="x", pady=(25, 0))
        painel.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(
            painel,
            text="Painel Inteligente",
            font=("Segoe UI", 20, "bold"),
            text_color=cores.AZUL_PRINCIPAL
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=20, pady=(18, 10))

        self.criar_bloco_inteligente(
            painel,
            "Usuario logado",
            [
                f"Nome: {indicadores['usuario_nome'] or '-'}",
                f"Perfil: {indicadores['usuario_perfil'] or '-'}",
                f"Acesso: {data_atual}",
            ],
            1,
            0,
        )
        self.criar_bloco_inteligente(
            painel,
            "Documentos e arquivos",
            [
                f"Documentos emitidos hoje: {indicadores['documentos_hoje']}",
                f"Total de PDFs emitidos: {indicadores['total_pdfs']}",
                f"Arquivos anexados: {indicadores['total_arquivos']}",
            ],
            1,
            1,
        )
        self.criar_bloco_inteligente(
            painel,
            "Ultimo backup",
            indicadores["ultimo_backup"],
            1,
            2,
        )
        self.criar_bloco_inteligente(
            painel,
            "Ultimos membros cadastrados",
            indicadores["ultimos_membros"],
            2,
            0,
        )
        self.criar_bloco_inteligente(
            painel,
            "Proximos aniversariantes",
            indicadores["aniversariantes"],
            2,
            1,
        )
        self.criar_bloco_inteligente(
            painel,
            "Atividades recentes",
            indicadores["atividades"],
            2,
            2,
        )

        BarraStatus(
            self,
            usuario=nome,
            perfil=perfil,
            versao=configuracoes.VERSAO
        ).pack(side="bottom", fill="x")

        self.bind("<Control-m>", lambda event: self.abrir_membros())
        self.bind("<Escape>", lambda event: self.sair())

    def carregar_indicadores(self, nome_usuario, perfil_usuario):
        ultimos_membros = ultimos_membros_cadastrados(5)
        documentos_recentes = listar_documentos_emitidos_recentes(5)
        arquivos_recentes = listar_arquivos_anexados_recentes(5)

        return {
            "usuario_nome": nome_usuario,
            "usuario_perfil": perfil_usuario,
            "documentos_hoje": total_documentos_emitidos_hoje(),
            "total_pdfs": total_documentos_emitidos(),
            "total_arquivos": total_arquivos_anexados(),
            "ultimo_backup": self.obter_ultimo_backup(),
            "status_backup": self.obter_status_backup(),
            "ultimos_membros": self.formatar_ultimos_membros(ultimos_membros),
            "aniversariantes": self.formatar_aniversariantes(
                proximos_aniversariantes(5)
            ),
            "atividades": self.formatar_atividades_recentes(
                documentos_recentes,
                arquivos_recentes,
                ultimos_membros,
            ),
        }

    def criar_bloco_inteligente(self, master, titulo, itens, linha, coluna):
        bloco = ctk.CTkFrame(
            master,
            fg_color=cores.FUNDO,
            corner_radius=8,
            border_width=1,
            border_color="#D8E3F2",
        )
        bloco.grid(row=linha, column=coluna, padx=10, pady=10, sticky="nsew")
        bloco.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            bloco,
            text=titulo,
            font=("Segoe UI", 15, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))

        lista_itens = itens or ["Nenhum registro encontrado."]
        for indice, item in enumerate(lista_itens[:6], start=1):
            ctk.CTkLabel(
                bloco,
                text=str(item),
                font=("Segoe UI", 12),
                text_color=cores.PRETO,
                anchor="w",
                justify="left",
                wraplength=290,
            ).grid(row=indice, column=0, sticky="ew", padx=14, pady=(0, 5))

    def obter_ultimo_backup(self):
        if not PASTA_BACKUP.exists():
            return ["Nenhum backup encontrado.", "Pasta backup nao localizada."]

        arquivos = [
            caminho
            for caminho in PASTA_BACKUP.rglob("*")
            if caminho.is_file()
        ]

        if not arquivos:
            return ["Nenhum backup encontrado.", "Pasta backup vazia."]

        ultimo = max(arquivos, key=lambda caminho: caminho.stat().st_mtime)
        data = datetime.fromtimestamp(ultimo.stat().st_mtime)
        tamanho = self.formatar_tamanho_arquivo(ultimo.stat().st_size)

        return [
            f"Arquivo: {ultimo.name}",
            f"Data: {data.strftime('%d/%m/%Y %H:%M')}",
            f"Tamanho: {tamanho}",
        ]

    def obter_status_backup(self):
        if not PASTA_BACKUP.exists():
            return "Sem backup"

        for caminho in PASTA_BACKUP.rglob("*"):
            if caminho.is_file():
                return "OK"

        return "Sem backup"

    def formatar_ultimos_membros(self, membros):
        if not membros:
            return ["Nenhum membro cadastrado."]

        return [
            f"#{membro['id']} - {membro['nome'] or '-'} ({membro['status'] or '-'})"
            for membro in membros
        ]

    def formatar_aniversariantes(self, aniversariantes):
        if not aniversariantes:
            return ["Nenhum aniversario encontrado."]

        linhas = []
        for item in aniversariantes:
            data = item["proximo"].strftime("%d/%m")
            dias = int(item["dias"])
            complemento = "hoje" if dias == 0 else f"em {dias} dia(s)"
            linhas.append(f"{data} - {item['nome'] or '-'} ({complemento})")

        return linhas

    def formatar_atividades_recentes(self, documentos, arquivos, membros):
        atividades = []

        for documento in documentos:
            atividades.append({
                "data": self.converter_data_hora(documento.get("data")),
                "texto": (
                    f"PDF: {documento.get('titulo') or '-'}"
                    f" - {documento.get('membro') or 'Membro'}"
                ),
            })

        for arquivo in arquivos:
            atividades.append({
                "data": self.converter_data_hora(arquivo.get("data")),
                "texto": (
                    f"Arquivo: {arquivo.get('titulo') or arquivo.get('tipo') or '-'}"
                    f" - {arquivo.get('membro') or 'Membro'}"
                ),
            })

        atividades.sort(
            key=lambda item: item["data"] or datetime.min,
            reverse=True,
        )

        linhas = [
            f"{self.formatar_data_hora(item['data'])} - {item['texto']}"
            for item in atividades[:4]
        ]

        for membro in membros[:2]:
            linhas.append(
                f"Cadastro: #{membro['id']} - {membro['nome'] or '-'}"
            )

        return linhas or ["Nenhuma atividade recente."]

    @staticmethod
    def converter_data_hora(valor):
        texto = str(valor or "").strip()
        if not texto:
            return None

        for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(texto, formato)
            except ValueError:
                pass

        return None

    @staticmethod
    def formatar_data_hora(valor):
        if valor is None:
            return "Sem data"
        return valor.strftime("%d/%m %H:%M")

    @staticmethod
    def formatar_tamanho_arquivo(tamanho):
        if tamanho < 1024:
            return f"{tamanho} B"
        if tamanho < 1024 * 1024:
            return f"{tamanho / 1024:.1f} KB"
        return f"{tamanho / (1024 * 1024):.1f} MB"

    def pegar_saudacao(self):
        hora = datetime.now().hour

        if hora < 12:
            return "Bom dia"
        elif hora < 18:
            return "Boa tarde"
        else:
            return "Boa noite"

    def abrir_membros(self):
        ConsultaMembros(self)

    def abrir_pre_cadastros(self):
        if (
            self.janela_pre_cadastros is not None
            and self.janela_pre_cadastros.winfo_exists()
        ):
            self.janela_pre_cadastros.lift()
            self.janela_pre_cadastros.focus_force()
            return

        self.janela_pre_cadastros = PreCadastros(self)

    def abrir_documentos(self):
        if self.janela_documentos is not None and self.janela_documentos.winfo_exists():
            self.janela_documentos.lift()
            self.janela_documentos.focus_force()
            return

        self.janela_documentos = CentralDocumentos(self)

    def abrir_aniversariantes(self):
        if self.janela_aniversariantes is not None and self.janela_aniversariantes.winfo_exists():
            self.janela_aniversariantes.lift()
            self.janela_aniversariantes.focus_force()
            return

        self.janela_aniversariantes = Aniversariantes(self)

    def abrir_relatorios(self):
        if self.janela_relatorios is not None and self.janela_relatorios.winfo_exists():
            self.janela_relatorios.lift()
            self.janela_relatorios.focus_force()
            return

        self.janela_relatorios = Relatorios(self)

    def abrir_backup(self):
        if self.janela_backup is not None and self.janela_backup.winfo_exists():
            self.janela_backup.lift()
            self.janela_backup.focus_force()
            return

        self.janela_backup = Backup(self)

    def abrir_configuracoes(self):
        if (
            self.janela_configuracoes is not None
            and self.janela_configuracoes.winfo_exists()
        ):
            self.janela_configuracoes.lift()
            self.janela_configuracoes.focus_force()
            return

        self.janela_configuracoes = ConfiguracoesIgreja(self)

    def abrir_usuarios(self):
        if not usuario_eh_administrador():
            messagebox.showwarning(
                "SIGM",
                "Apenas o Administrador pode acessar o gerenciamento de usuarios.",
                parent=self,
            )
            return

        if (
            self.janela_usuarios is not None
            and self.janela_usuarios.winfo_exists()
        ):
            self.janela_usuarios.lift()
            self.janela_usuarios.focus_force()
            return

        self.janela_usuarios = Usuarios(self)

    def abrir_auditoria(self):
        if not usuario_eh_administrador():
            messagebox.showwarning(
                "SIGM",
                "Apenas o Administrador pode acessar o Log de Auditoria.",
                parent=self,
            )
            return

        if (
            self.janela_auditoria is not None
            and self.janela_auditoria.winfo_exists()
        ):
            self.janela_auditoria.lift()
            self.janela_auditoria.focus_force()
            return

        self.janela_auditoria = LogAuditoria(self)

    def abrir_sobre(self):
        dados_igreja = buscar_configuracoes_igreja()
        janela = ctk.CTkToplevel(self)
        janela.title("Sobre - SIGM")
        janela.geometry("620x460")
        janela.resizable(False, False)
        janela.configure(fg_color=cores.FUNDO)
        configurar_modal(janela, self)
        janela.grab_set()

        ctk.CTkLabel(
            janela,
            text=NOME_COMPLETO,
            font=fontes.SUBTITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(24, 8))

        textos = [
            f"Versão: {VERSAO}",
            "Sistema para gestão de membros, documentos e arquivos da igreja.",
            f"Desenvolvedor: {DESENVOLVEDOR}",
            "Tecnologias: Python, CustomTkinter, SQLite, ReportLab, PyMuPDF e pypdf.",
            "Licenciado para uso da igreja configurada.",
        ]

        igreja = dados_igreja.get("nome_igreja")
        local = " - ".join(
            parte
            for parte in (dados_igreja.get("cidade"), dados_igreja.get("estado"))
            if parte
        )
        if igreja:
            textos.append(f"Igreja: {igreja}")
        if local:
            textos.append(f"Local: {local}")

        ctk.CTkLabel(
            janela,
            text="\n\n".join(textos),
            font=fontes.TEXTO,
            text_color=cores.PRETO,
            justify="left",
            wraplength=540,
        ).pack(fill="both", expand=True, padx=34, pady=(8, 20))

        ctk.CTkButton(
            janela,
            text="FECHAR",
            width=120,
            fg_color=cores.CINZA,
            hover_color="#444444",
            command=janela.destroy,
        ).pack(pady=(0, 22))

    def trocar_usuario(self):
        confirmar = messagebox.askyesno(
            "Trocar usuario",
            "Deseja trocar de usuario?\nA sessao atual sera encerrada.",
            parent=self,
        )

        if not confirmar:
            return

        registrar_acao(
            "TROCA_USUARIO",
            "Troca de usuario solicitada.",
            modulo="Autenticacao",
        )
        self.fechar_janelas_internas()
        limpar_sessao()
        master = self.master
        self.destroy()

        from telas.tela_login import TelaLogin

        TelaLogin(master)

    def sair(self):
        confirmar = messagebox.askyesno(
            "Sair",
            "Deseja sair do SIGM?",
            parent=self,
        )

        if not confirmar:
            return

        registrar_acao(
            "LOGOUT",
            "Logout realizado.",
            modulo="Autenticacao",
        )
        self.fechar_janelas_internas()
        limpar_sessao()
        self.destroy()
        self.master.destroy()

    def fechar_janelas_internas(self):
        for janela in list(self.winfo_children()):
            if isinstance(janela, ctk.CTkToplevel) and janela.winfo_exists():
                janela.destroy()
