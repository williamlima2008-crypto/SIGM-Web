import os
import re
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from banco.database import conectar, registrar_documento_emitido
from componentes.cabecalho_igreja import CabecalhoIgreja
from config import cores, fontes
from documentos.renderizador_pdf import gerar_pdf_final
from utils.auditoria import registrar_acao
from utils.caminhos import caminho_dados
from utils.janelas import configurar_janela_principal


PASTA_SAIDA = caminho_dados("documentos_gerados", criar_pai=False)
CAMPOS_MEMBRO_ALIASES = {
    "nome_membro": "nome",
    "rua": "endereco",
    "residencial": "telefone",
    "uf": "estado",
    "ministerio_membro": "ministerio",
}


class BaseEditorDocumento(ctk.CTkToplevel):
    titulo_janela = "Editor de Documento - SIGM"
    largura_label = 190

    def __init__(self, master, id_membro, documento, dados_iniciais):
        super().__init__(master)

        self.id_membro = id_membro
        self.documento = documento
        self.dados_iniciais = dict(dados_iniciais or {})
        self.campos = {}
        self.caminho_ultimo_pdf = None

        self.title(self.titulo_janela)
        configurar_janela_principal(self, 940, 740, 840, 660, master)
        self.configure(fg_color=cores.FUNDO)

        self.criar_interface()
        self.carregar_dados_iniciais()

    def criar_interface(self):
        ctk.CTkLabel(
            self,
            text=self.documento.titulo,
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(24, 8))

        self.cabecalho_igreja = CabecalhoIgreja(self)
        self.cabecalho_igreja.pack(fill="x", padx=28, pady=(0, 10))

        self.frame_formulario = ctk.CTkScrollableFrame(self, corner_radius=10)
        self.frame_formulario.pack(
            padx=28,
            pady=(8, 10),
            fill="both",
            expand=True,
        )

        self.criar_campos()
        self.criar_botoes()

    def criar_campos(self):
        raise NotImplementedError

    def criar_botoes(self):
        frame_botoes = ctk.CTkFrame(self, fg_color="transparent")
        frame_botoes.pack(fill="x", padx=24, pady=(0, 18))

        ctk.CTkButton(
            frame_botoes,
            text="SALVAR ALTERAÇÕES",
            width=170,
            height=38,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            command=self.salvar_alteracoes,
        ).grid(row=0, column=0, padx=8)

        ctk.CTkButton(
            frame_botoes,
            text="SALVAR COMO PDF",
            width=170,
            height=38,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            command=self.salvar_como_pdf,
        ).grid(row=0, column=1, padx=8)

        ctk.CTkButton(
            frame_botoes,
            text="IMPRIMIR",
            width=130,
            height=38,
            fg_color=cores.VERDE,
            hover_color="#1F7A45",
            command=self.imprimir,
        ).grid(row=0, column=2, padx=8)

        ctk.CTkButton(
            frame_botoes,
            text="CANCELAR",
            width=130,
            height=38,
            fg_color=cores.CINZA,
            hover_color="#444444",
            command=self.destroy,
        ).grid(row=0, column=3, padx=8)

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
            width=self.largura_label,
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=0, column=0, padx=(12, 8), pady=9, sticky="w")

        entrada = ctk.CTkEntry(linha, height=34)
        entrada.grid(row=0, column=1, padx=(0, 12), pady=9, sticky="ew")
        self.campos[chave] = entrada
        return entrada

    def criar_campo_multilinha(self, chave, rotulo, altura=110, parent=None):
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

    def carregar_dados_iniciais(self):
        for chave, campo in self.campos.items():
            valor = str(self.dados_iniciais.get(chave) or "")

            if isinstance(campo, ctk.CTkTextbox):
                campo.delete("1.0", "end")
                campo.insert("1.0", valor)
            else:
                campo.delete(0, "end")
                campo.insert(0, valor)

        self.apos_carregar_dados()

    def apos_carregar_dados(self):
        pass

    def obter_dados_iniciais(self):
        return dict(self.dados_iniciais)

    def restaurar_dados(self):
        self.dados_iniciais = self.obter_dados_iniciais()
        self.carregar_dados_iniciais()
        self.caminho_ultimo_pdf = None
        messagebox.showinfo("SIGM", "Dados restaurados com sucesso.")

    def coletar_dados(self):
        dados = dict(self.dados_iniciais)

        for chave, campo in self.campos.items():
            if isinstance(campo, ctk.CTkTextbox):
                dados[chave] = campo.get("1.0", "end").strip()
            else:
                dados[chave] = campo.get().strip()

        return dados

    def obter_colunas_membros(self):
        conexao = conectar()
        try:
            cursor = conexao.cursor()
            cursor.execute("PRAGMA table_info(membros)")
            return {
                str(coluna[1]).lower(): str(coluna[1])
                for coluna in cursor.fetchall()
            }
        finally:
            conexao.close()

    @staticmethod
    def citar_identificador_sqlite(nome):
        return '"' + str(nome).replace('"', '""') + '"'

    def mapear_campo_para_membro(self, chave):
        return CAMPOS_MEMBRO_ALIASES.get(chave, chave)

    def campos_editaveis_para_cadastro(self, dados):
        return {
            self.mapear_campo_para_membro(chave): dados.get(chave, "")
            for chave in self.campos
        }

    def salvar_dados_membro(self, dados_cadastro):
        colunas = self.obter_colunas_membros()
        dados_persistentes = {}
        campos_sem_persistencia = []

        for coluna, valor in dados_cadastro.items():
            if coluna == "id":
                continue

            coluna_real = colunas.get(str(coluna).lower())
            if coluna_real:
                dados_persistentes[coluna_real] = valor
            elif str(valor or "").strip():
                campos_sem_persistencia.append(coluna)

        if not dados_persistentes:
            return [], campos_sem_persistencia

        atribuicoes = ", ".join(
            f"{self.citar_identificador_sqlite(coluna)} = ?"
            for coluna in dados_persistentes
        )
        valores = list(dados_persistentes.values()) + [self.id_membro]

        conexao = conectar()
        try:
            cursor = conexao.cursor()
            cursor.execute(
                f"""
                UPDATE membros
                SET {atribuicoes}
                WHERE id = ?
                """,
                valores,
            )
            conexao.commit()
        finally:
            conexao.close()

        return list(dados_persistentes), campos_sem_persistencia

    def salvar_alteracoes(self):
        if not self.validar_antes_de_gerar():
            return

        dados = self.coletar_dados()
        dados_cadastro = self.campos_editaveis_para_cadastro(dados)

        try:
            campos_salvos, campos_sem_persistencia = self.salvar_dados_membro(
                dados_cadastro
            )
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel salvar as alteracoes.\n\nErro: {erro}",
            )
            return

        self.dados_iniciais.update(dados)
        self.caminho_ultimo_pdf = None

        if campos_salvos:
            mensagem = "Alteracoes salvas no SIGM."
        else:
            mensagem = "Nenhum campo foi salvo no cadastro do membro."

        if campos_sem_persistencia:
            mensagem += (
                "\n\nAlguns campos deste documento ainda nao possuem "
                "rascunho persistente e ficaram salvos apenas nesta janela."
            )
        if not campos_salvos and not campos_sem_persistencia:
            mensagem = "Nao havia campos do cadastro para salvar."

        messagebox.showinfo("SIGM", mensagem)

    def salvar_como_pdf(self):
        if not self.validar_antes_de_gerar():
            return

        try:
            caminho_pdf = self.gerar_pdf_final()
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel gerar o PDF.\n\nErro: {erro}",
            )
            return

        self.caminho_ultimo_pdf = caminho_pdf
        id_documento = self.registrar_emissao_documento(caminho_pdf, "PDF salvo")
        registrar_acao(
            "PDF_GERADO",
            f"{self.documento.titulo} gerado para {self.dados_iniciais.get('nome_membro') or 'membro'}.",
            modulo="Documentos",
            registro_id=id_documento or self.id_membro,
            detalhes=f"Arquivo: {caminho_pdf}",
        )
        messagebox.showinfo("SIGM", f"PDF gerado com sucesso!\n\nArquivo:\n{caminho_pdf}")
        self.abrir_pdf(caminho_pdf)

    def imprimir(self):
        if not self.validar_antes_de_gerar():
            return

        try:
            caminho_pdf = self.caminho_ultimo_pdf or self.gerar_pdf_final()
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel gerar o PDF para impressao.\n\nErro: {erro}",
            )
            return

        self.caminho_ultimo_pdf = caminho_pdf

        try:
            os.startfile(caminho_pdf, "print")
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel enviar o PDF para impressao.\n\nErro: {erro}",
            )
            return

        id_documento = self.registrar_emissao_documento(caminho_pdf, "Enviado para impressao")
        registrar_acao(
            "PDF_IMPRESSAO",
            f"{self.documento.titulo} enviado para impressao.",
            modulo="Documentos",
            registro_id=id_documento or self.id_membro,
            detalhes=f"Arquivo: {caminho_pdf}",
        )
        messagebox.showinfo("SIGM", "Documento enviado para impressao.")

    def validar_antes_de_gerar(self):
        return True

    def gerar_pdf_final(self):
        caminho_saida = self.criar_caminho_saida()
        return gerar_pdf_final(
            self.documento.modelo_pdf,
            caminho_saida,
            self.coletar_dados(),
            self.documento.mapeamento,
        )

    def registrar_emissao_documento(self, caminho_pdf, observacao=""):
        caminho_completo = Path(caminho_pdf).resolve()

        try:
            id_documento = registrar_documento_emitido(
                membro_id=self.id_membro,
                tipo_documento=self.documento.codigo,
                titulo_documento=self.documento.titulo,
                caminho_arquivo=str(caminho_completo),
                data_emissao=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                usuario_emissor=self.obter_usuario_emissor(),
                observacao=observacao,
            )
            registrar_acao(
                "DOCUMENTO_HISTORICO_REGISTRADO",
                f"{self.documento.titulo} registrado no historico.",
                modulo="Documentos",
                registro_id=id_documento,
                detalhes=f"Arquivo: {caminho_completo}",
            )
            return id_documento
        except Exception as erro:
            messagebox.showwarning(
                "SIGM",
                "O documento foi gerado, mas nao foi possivel registrar "
                f"no historico.\n\nErro: {erro}",
            )
            return None

    def obter_usuario_emissor(self):
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

    def criar_caminho_saida(self):
        PASTA_SAIDA.mkdir(parents=True, exist_ok=True)

        nome_membro = self.dados_iniciais.get("nome_membro") or "membro"
        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = (
            f"{self.documento.codigo}_"
            f"{self.limpar_nome_arquivo(nome_membro)}_"
            f"{data_hora}.pdf"
        )
        return PASTA_SAIDA / nome_arquivo

    def abrir_pdf(self, caminho_pdf):
        try:
            os.startfile(caminho_pdf)
        except Exception:
            pass

    @staticmethod
    def limpar_nome_arquivo(valor):
        texto = str(valor or "").strip()
        texto = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", texto)
        texto = re.sub(r"\s+", "_", texto)
        texto = texto.strip("._")
        return texto or "documento"
