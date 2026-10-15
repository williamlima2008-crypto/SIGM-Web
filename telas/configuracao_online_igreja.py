import os
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from banco.database import (
    buscar_configuracao_online_igreja,
    salvar_configuracao_online_igreja,
)
from componentes.cabecalho_igreja import CabecalhoIgreja
from config import cores, fontes
from servicos.identidade_online_igreja import (
    API_BASE_URL_PADRAO,
    STATUS_ATIVACAO_ATIVADA,
    IdentidadeOnlineIgrejaErro,
    ativar_integracao_online_igreja,
    mascarar_chave_sincronizacao,
    montar_url_formulario,
    testar_ou_recuperar_integracao_online_igreja,
)
from servicos.cliente_sigm_online import SIGMOnlineConexaoErro, SIGMOnlineErro, SIGMOnlineTimeoutErro
from utils.auditoria import registrar_acao
from utils.caminhos import aplicacao_empacotada, caminho_dados
from utils.janelas import configurar_janela_principal
from utils.qrcode_igreja import QRCodeIgrejaErro, gerar_qrcode_igreja


class ConfiguracaoOnlineIgreja(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)

        self.configuracao = {}
        self.qr_image = None
        self.ativo = ctk.IntVar(value=0)
        self.mostrar_atalhos_desenvolvimento = not aplicacao_empacotada()
        self.botao_copiar_chave = None
        self.botao_gerar_qrcode = None
        self.botao_copiar_link_publico = None
        self.botao_testar_conexao = None

        self.title("Pre-cadastro Online - SIGM")
        configurar_janela_principal(self, 980, 760, 860, 640, master)
        self.configure(fg_color=cores.FUNDO)
        self.transient(master)

        self.criar_interface()
        self.carregar_configuracao()

    def criar_interface(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            self,
            text="Pre-cadastro Online",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=0, column=0, padx=30, pady=(24, 10), sticky="ew")

        CabecalhoIgreja(self).grid(row=1, column=0, padx=30, pady=(0, 12), sticky="ew")

        conteudo = ctk.CTkScrollableFrame(self, corner_radius=10, fg_color="transparent")
        conteudo.grid(row=2, column=0, padx=30, pady=(0, 14), sticky="nsew")
        conteudo.grid_columnconfigure(0, weight=1)

        self.criar_secao_identidade(conteudo)
        self.criar_secao_integracao(conteudo)

        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.grid(row=3, column=0, padx=30, pady=(0, 20), sticky="ew")

        self.botao(
            botoes,
            "FECHAR",
            self.destroy,
            cor=cores.CINZA,
            hover="#444444",
        ).pack(side="right", padx=5)

        self.bind("<Escape>", lambda _event: self.destroy())

    def criar_secao_identidade(self, master):
        secao = self.criar_secao(master, "IDENTIDADE ONLINE")
        self.label_aviso_identidade = ctk.CTkLabel(
            secao,
            text="Identidade online ainda nao inicializada.",
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.VERMELHO,
        )
        self.label_aviso_identidade.grid(
            row=1,
            column=0,
            columnspan=3 if self.mostrar_atalhos_desenvolvimento else 2,
            padx=14,
            pady=(2, 8),
            sticky="ew",
        )
        self.identificador_publico = self.linha_somente_leitura(
            secao,
            2,
            "Identificador Publico:",
        )
        self.chave_sincronizacao = self.linha_chave_sincronizacao(
            secao,
            3,
        )
        self.label_estado = self.linha_texto(secao, 4, "Status:", "-")

        frame_botoes = ctk.CTkFrame(secao, fg_color="transparent")
        frame_botoes.grid(
            row=5,
            column=0,
            columnspan=3 if self.mostrar_atalhos_desenvolvimento else 2,
            padx=14,
            pady=(8, 12),
            sticky="w",
        )

        self.botao_inicializar = self.botao(
            frame_botoes,
            "ATIVAR INTEGRAÇÃO",
            self.inicializar_identidade,
            largura=220,
        )
        self.botao_inicializar.pack(side="left", padx=(0, 8))

    def criar_secao_integracao(self, master):
        secao = self.criar_secao(master, "INTEGRACAO ONLINE")
        secao.grid_columnconfigure(1, weight=1)

        self.label_status_integracao = self.linha_status_integracao(secao, 1)
        self.api_base_url = self.linha_somente_leitura_com_observacao(
            secao,
            2,
            "API Base URL",
        )
        self.formulario_url = self.linha_somente_leitura_com_observacao(
            secao,
            3,
            "URL Pública",
        )

        frame_botoes = ctk.CTkFrame(secao, fg_color="transparent")
        frame_botoes.grid(row=4, column=0, columnspan=2, padx=14, pady=(8, 12), sticky="w")

        self.botao_gerar_qrcode = self.botao(
            frame_botoes,
            "Gerar QR Code",
            self.gerar_qrcode,
            largura=145,
            cor=cores.VERDE,
            hover="#1F7A45",
            estado="disabled",
        )
        self.botao_gerar_qrcode.pack(side="left", padx=(0, 8))
        self.botao_copiar_link_publico = self.botao(
            frame_botoes,
            "Copiar Link",
            self.copiar_link,
            largura=130,
            estado="disabled",
        )
        self.botao_copiar_link_publico.pack(side="left", padx=(0, 8))
        self.botao_testar_conexao = self.botao(
            frame_botoes,
            "Testar Conexão",
            self.ativar_ou_testar_conexao,
            largura=145,
            estado="disabled",
        )
        self.botao_testar_conexao.pack(side="left", padx=(0, 8))

        self.label_qrcode = ctk.CTkLabel(
            secao,
            text="QR Code ainda nao gerado.",
            width=260,
            height=260,
            fg_color=cores.BRANCO,
            corner_radius=8,
            font=fontes.TEXTO,
            text_color=cores.CINZA,
        )
        self.label_qrcode.grid(row=5, column=0, columnspan=2, padx=14, pady=(0, 12))

    def criar_secao(self, master, titulo):
        secao = ctk.CTkFrame(master, fg_color=cores.BRANCO, corner_radius=8)
        secao.pack(fill="x", padx=10, pady=10)
        secao.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            secao,
            text=titulo,
            font=("Segoe UI", 16, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, padx=14, pady=(12, 8), sticky="ew")
        return secao

    def linha_somente_leitura(self, master, linha, rotulo):
        ctk.CTkLabel(
            master,
            text=rotulo,
            width=210,
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=linha, column=0, padx=(14, 8), pady=8, sticky="w")

        entrada = ctk.CTkEntry(master, height=36, state="disabled")
        entrada.grid(row=linha, column=1, padx=(0, 14), pady=8, sticky="ew")
        return entrada

    def linha_somente_leitura_com_observacao(self, master, linha, rotulo):
        ctk.CTkLabel(
            master,
            text=rotulo,
            width=210,
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=linha, column=0, padx=(14, 8), pady=(8, 2), sticky="w")

        frame = ctk.CTkFrame(master, fg_color="transparent")
        frame.grid(row=linha, column=1, padx=(0, 14), pady=(8, 2), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        entrada = ctk.CTkEntry(frame, height=36, state="disabled")
        entrada.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            frame,
            text="(somente leitura)",
            anchor="w",
            font=("Segoe UI", 11),
            text_color=cores.CINZA,
        ).grid(row=1, column=0, pady=(2, 0), sticky="w")
        return entrada

    def linha_status_integracao(self, master, linha):
        ctk.CTkLabel(
            master,
            text="Status:",
            width=210,
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=linha, column=0, padx=(14, 8), pady=6, sticky="w")

        label = ctk.CTkLabel(
            master,
            text="Não conectado",
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.VERMELHO,
        )
        label.grid(row=linha, column=1, padx=(0, 14), pady=6, sticky="ew")
        return label

    def linha_chave_sincronizacao(self, master, linha):
        ctk.CTkLabel(
            master,
            text="Chave de Sincronizacao:",
            width=210,
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=linha, column=0, padx=(14, 8), pady=8, sticky="w")

        entrada = ctk.CTkEntry(master, height=36, state="disabled")
        padx_entrada = (0, 8) if self.mostrar_atalhos_desenvolvimento else (0, 14)
        entrada.grid(row=linha, column=1, padx=padx_entrada, pady=8, sticky="ew")

        if self.mostrar_atalhos_desenvolvimento:
            self.botao_copiar_chave = self.botao(
                master,
                "Copiar Chave",
                self.copiar_chave_sincronizacao,
                largura=130,
                estado="disabled",
            )
            self.botao_copiar_chave.grid(row=linha, column=2, padx=(0, 14), pady=8, sticky="e")

        return entrada

    def linha_texto(self, master, linha, rotulo, valor):
        ctk.CTkLabel(
            master,
            text=rotulo,
            width=210,
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=linha, column=0, padx=(14, 8), pady=6, sticky="nw")

        label = ctk.CTkLabel(
            master,
            text=valor,
            anchor="w",
            justify="left",
            wraplength=640,
            font=("Segoe UI", 13),
            text_color=cores.PRETO,
        )
        label.grid(row=linha, column=1, padx=(0, 14), pady=6, sticky="ew")
        return label

    def linha_entrada(self, master, linha, rotulo):
        ctk.CTkLabel(
            master,
            text=rotulo,
            width=210,
            anchor="w",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=linha, column=0, padx=(14, 8), pady=8, sticky="w")
        entrada = ctk.CTkEntry(master, height=36)
        entrada.grid(row=linha, column=1, padx=(0, 14), pady=8, sticky="ew")
        return entrada

    def carregar_configuracao(self):
        self.configuracao = buscar_configuracao_online_igreja()
        identificador = self.configuracao.get("identificador_publico") or ""
        chave = self.configuracao.get("chave_sincronizacao") or ""
        configurado = bool(identificador and chave)
        ativado = configurado and int(self.configuracao.get("ativo") or 0) == 1

        self.label_estado.configure(text="Configurado" if configurado else "Nao configurado")
        self.label_aviso_identidade.configure(
            text=(
                "Identidade online ativada."
                if ativado
                else "Identidade online criada. Ativacao pendente."
                if configurado
                else "Identidade online ainda nao inicializada."
            ),
            text_color=cores.VERDE if ativado else cores.AMARELO if configurado else cores.VERMELHO,
        )
        self.preencher_somente_leitura(self.identificador_publico, identificador or "Nao gerado")
        self.preencher_somente_leitura(self.chave_sincronizacao, mascarar_chave_sincronizacao(chave))
        self.botao_inicializar.configure(
            text="INTEGRAÇÃO ATIVA" if ativado else "ATIVAR INTEGRAÇÃO",
            state="disabled" if ativado else "normal",
        )
        if self.botao_copiar_chave is not None:
            self.botao_copiar_chave.configure(state="normal" if chave else "disabled")
        if self.botao_gerar_qrcode is not None:
            self.botao_gerar_qrcode.configure(state="normal" if ativado else "disabled")
        if self.botao_copiar_link_publico is not None:
            self.botao_copiar_link_publico.configure(state="normal" if ativado else "disabled")
        if self.botao_testar_conexao is not None:
            self.botao_testar_conexao.configure(
                text="Testar Conexão" if ativado else "Ativar Integração",
                state="normal" if configurado else "disabled",
            )

        api_base_url = API_BASE_URL_PADRAO
        dados_link = dict(self.configuracao or {})
        dados_link["api_base_url"] = api_base_url
        dados_link["formulario_url"] = ""
        url_publica = montar_url_formulario(dados_link)
        self.preencher_somente_leitura(self.api_base_url, api_base_url)
        self.preencher_somente_leitura(self.formulario_url, url_publica or "Não gerada")
        status_visual = (
            "Conectado"
            if ativado
            else "Ativação pendente"
            if configurado
            else "Não conectado"
        )
        self.atualizar_status_integracao(status_visual, ativado)
        self.ativo.set(int(self.configuracao.get("ativo") or 0))

        self.atualizar_preview_qrcode()

    def preencher_entrada(self, entrada, valor):
        entrada.delete(0, "end")
        entrada.insert(0, str(valor or ""))

    def preencher_somente_leitura(self, entrada, valor):
        entrada.configure(state="normal")
        entrada.delete(0, "end")
        entrada.insert(0, str(valor or ""))
        entrada.configure(state="disabled")

    def montar_dados_tela(self):
        dados = dict(self.configuracao or {})
        formulario_url = self.formulario_url.get().strip()
        if formulario_url == "Não gerada":
            formulario_url = ""
        dados["api_base_url"] = self.api_base_url.get().strip() or API_BASE_URL_PADRAO
        dados["formulario_url"] = formulario_url
        dados["ativo"] = int(self.ativo.get() or 0)
        return dados

    def atualizar_status_integracao(self, texto, conectado):
        self.label_status_integracao.configure(
            text=texto,
            text_color=cores.VERDE if conectado else cores.VERMELHO,
        )

    def salvar_configuracao(self):
        try:
            self.configuracao = salvar_configuracao_online_igreja(self.montar_dados_tela())
            registrar_acao(
                "CONFIGURACAO_ONLINE_IGREJA_ATUALIZADA",
                "Configuracao online da igreja atualizada.",
                modulo="Pre-cadastros",
                registro_id=1,
                detalhes="Campos atualizados: api_base_url, formulario_url, ativo",
            )
            self.carregar_configuracao()
            messagebox.showinfo("SIGM", "Configuracao online salva com sucesso.", parent=self)
        except Exception:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel salvar a configuracao online.\n\nErro: {erro}",
                parent=self,
            )

    def inicializar_identidade(self):
        confirmar = messagebox.askyesno(
            "Ativar integracao online",
            (
                "Deseja criar a identidade online desta instalacao e ativar a "
                "integracao no SIGM Online?"
            ),
            parent=self,
        )
        if not confirmar:
            return

        try:
            resultado = ativar_integracao_online_igreja()
            self.configuracao = resultado["configuracao"]
            registrar_acao(
                "IDENTIDADE_ONLINE_IGREJA_INICIALIZADA",
                "Identidade online da igreja ativada.",
                modulo="Pre-cadastros",
                registro_id=1,
                detalhes=f"Status: {resultado.get('status') or STATUS_ATIVACAO_ATIVADA}",
            )
            self.carregar_configuracao()
            messagebox.showinfo("SIGM", "Integração online ativada com sucesso.", parent=self)
        except IdentidadeOnlineIgrejaErro as erro:
            messagebox.showwarning("SIGM", str(erro), parent=self)
        except (SIGMOnlineConexaoErro, SIGMOnlineTimeoutErro):
            self.configuracao = buscar_configuracao_online_igreja()
            self.carregar_configuracao()
            messagebox.showwarning(
                "SIGM",
                (
                    "A identidade foi criada, mas não foi possível concluir a ativação online. "
                    "Tente novamente quando houver conexão."
                ),
                parent=self,
            )
        except SIGMOnlineErro as erro:
            self.configuracao = buscar_configuracao_online_igreja()
            self.carregar_configuracao()
            messagebox.showwarning("SIGM", erro.mensagem_diagnostico(), parent=self)
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                "Nao foi possivel ativar a integracao online. Tente novamente.",
                parent=self,
            )

    def gerar_qrcode(self):
        dados = salvar_configuracao_online_igreja(self.montar_dados_tela())
        url = montar_url_formulario(dados)
        if not url:
            messagebox.showwarning("SIGM", "Informe primeiro a URL publica do formulario.", parent=self)
            self.configuracao = dados
            self.carregar_configuracao()
            return

        caminho = caminho_dados("qrcodes", "qrcode_pre_cadastro_igreja.png")
        try:
            caminho_gerado = gerar_qrcode_igreja(url, caminho)
            self.configuracao = salvar_configuracao_online_igreja({"qr_code_path": caminho_gerado})
            registrar_acao(
                "QRCODE_PRE_CADASTRO_GERADO",
                "QR Code de pre-cadastro gerado.",
                modulo="Pre-cadastros",
                registro_id=1,
                detalhes="Conteudo: URL publica do formulario com identificador publico.",
            )
            self.carregar_configuracao()
            messagebox.showinfo("SIGM", "QR Code gerado com sucesso.", parent=self)
        except QRCodeIgrejaErro as erro:
            messagebox.showwarning("SIGM", str(erro), parent=self)
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel gerar o QR Code.\n\nErro: {erro}",
                parent=self,
            )

    def atualizar_preview_qrcode(self):
        caminho = self.configuracao.get("qr_code_path") or ""
        if not caminho or not Path(caminho).exists():
            self.label_qrcode.configure(image=None, text="QR Code ainda nao gerado.")
            self.qr_image = None
            return

        try:
            imagem = Image.open(caminho)
            self.qr_image = ctk.CTkImage(light_image=imagem, dark_image=imagem, size=(260, 260))
            self.label_qrcode.configure(image=self.qr_image, text="")
        except Exception:
            self.label_qrcode.configure(image=None, text="Nao foi possivel carregar a imagem.")
            self.qr_image = None

    def abrir_imagem(self):
        caminho = self.configuracao.get("qr_code_path") or ""
        if not caminho or not Path(caminho).exists():
            messagebox.showwarning("SIGM", "QR Code ainda nao foi gerado.", parent=self)
            return

        try:
            os.startfile(caminho)
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel abrir a imagem.\n\nErro: {erro}",
                parent=self,
            )

    def copiar_link(self):
        url = montar_url_formulario(self.montar_dados_tela())
        if not url:
            messagebox.showwarning("SIGM", "Informe primeiro a URL publica do formulario.", parent=self)
            return

        self.clipboard_clear()
        self.clipboard_append(url)
        messagebox.showinfo("SIGM", "Link publico copiado.", parent=self)

    def ativar_ou_testar_conexao(self):
        if int((self.configuracao or {}).get("ativo") or 0) != 1:
            self.inicializar_identidade()
            return

        self.testar_conexao()

    def testar_conexao(self):
        dados = self.montar_dados_tela()
        identificador = dados.get("identificador_publico") or ""
        chave = dados.get("chave_sincronizacao") or ""
        if not identificador or not chave:
            self.atualizar_status_integracao("Não conectado", False)
            messagebox.showwarning("SIGM", "Inicialize primeiro a identidade online.", parent=self)
            return

        try:
            resultado = testar_ou_recuperar_integracao_online_igreja()
            self.configuracao = resultado.get("configuracao") or self.configuracao
            self.atualizar_status_integracao("Conectado", True)
            self.carregar_configuracao()
            mensagem = (
                "Integração online reativada com sucesso."
                if resultado.get("recuperada")
                else "Conexão com o SIGM Online realizada com sucesso."
            )
            messagebox.showinfo("SIGM", mensagem, parent=self)
        except IdentidadeOnlineIgrejaErro as erro:
            self.atualizar_status_integracao("Não conectado", False)
            messagebox.showwarning("SIGM", str(erro), parent=self)
        except SIGMOnlineErro as erro:
            self.atualizar_status_integracao("Não conectado", False)
            messagebox.showwarning("SIGM", erro.mensagem_diagnostico(), parent=self)
        except Exception:
            self.atualizar_status_integracao("Não conectado", False)
            messagebox.showerror(
                "Erro no SIGM",
                "Não foi possível testar a conexão com o SIGM Online.",
                parent=self,
            )

    def copiar_chave_sincronizacao(self):
        chave = str((self.configuracao or {}).get("chave_sincronizacao") or "")
        if not chave:
            messagebox.showwarning("SIGM", "Chave de sincronizacao ainda nao foi gerada.", parent=self)
            return

        self.clipboard_clear()
        self.clipboard_append(chave)
        messagebox.showinfo("SIGM", "Chave copiada para a área de transferência.", parent=self)

    def acao_futura(self):
        messagebox.showinfo("SIGM", "Funcionalidade reservada para uma etapa futura.", parent=self)

    def botao(self, master, texto, comando, cor=None, hover=None, largura=150, estado="normal"):
        return ctk.CTkButton(
            master,
            text=texto,
            width=largura,
            height=38,
            fg_color=cor or cores.AZUL_PRINCIPAL,
            hover_color=hover or cores.AZUL_ESCURO,
            font=("Segoe UI", 12, "bold"),
            command=comando,
            state=estado,
        )
