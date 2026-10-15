import customtkinter as ctk
from tkinter import filedialog, messagebox

from banco.database import (
    CAMPOS_CONFIGURACOES_IGREJA,
    buscar_configuracoes_igreja,
    garantir_configuracoes_igreja,
    salvar_configuracoes_igreja,
)
from componentes.cabecalho_igreja import CabecalhoIgreja, atualizar_cabecalhos_igreja
from config import cores, fontes
from telas.configuracao_online_igreja import ConfiguracaoOnlineIgreja
from utils.auditoria import registrar_acao
from utils.janelas import configurar_janela_principal, trazer_para_frente


class ConfiguracoesIgreja(ctk.CTkToplevel):
    CAMPOS_OBRIGATORIOS = {
        "nome_igreja": "Nome da Igreja",
        "ministerio": "Ministério",
        "cidade": "Cidade",
        "estado": "Estado",
    }

    ROTULOS_CAMPOS = {
        "nome_igreja": "Nome da Igreja",
        "ministerio": "Ministerio",
        "convencao": "Convencao",
        "setor": "Setor",
        "congregacao_sede": "Congregacao Sede",
        "cidade": "Cidade",
        "estado": "Estado",
        "pastor_presidente": "Pastor Presidente",
        "pastor_setorial": "Pastor Setorial",
        "primeiro_secretario": "Primeiro Secretario",
        "segundo_secretario": "Segundo Secretario",
        "terceiro_secretario": "Terceiro Secretario",
        "telefone": "Telefone",
        "whatsapp": "WhatsApp",
        "email": "E-mail",
        "site": "Site",
        "tema": "Tema",
        "rua": "Endereco",
        "numero": "Numero",
        "complemento": "Complemento",
        "bairro": "Bairro",
        "cep": "CEP",
        "cidade_endereco": "Cidade do Endereco",
        "estado_endereco": "Estado do Endereco",
        "logotipo": "Logotipo",
        "carimbo": "Carimbo",
        "assinatura_pastor": "Assinatura do Pastor",
        "congregacao_local_nome": "Nome da Congregacao Local",
        "congregacao_local_dirigente": "Dirigente Local",
        "congregacao_local_numero": "Numero da Congregacao",
        "congregacao_local_campo_setor": "Campo/Setor",
        "congregacao_local_cidade": "Cidade da Congregacao",
        "congregacao_local_estado": "Estado da Congregacao",
        "congregacao_local_rua": "Rua da Congregacao",
        "congregacao_local_numero_endereco": "Numero da Congregacao",
        "congregacao_local_bairro": "Bairro da Congregacao",
        "congregacao_local_cep": "CEP da Congregacao",
        "congregacao_local_telefone": "Telefone da Congregacao",
        "congregacao_local_whatsapp": "WhatsApp da Congregacao",
        "congregacao_local_email": "E-mail da Congregacao",
        "versiculo_institucional": "Versiculo institucional",
    }
    GRUPOS_AUDITORIA = {
        "DADOS_INSTITUCIONAIS_ALTERADOS": (
            "Dados institucionais da igreja alterados.",
            {
                "nome_igreja",
                "ministerio",
                "convencao",
                "setor",
                "congregacao_sede",
                "cidade",
                "estado",
                "versiculo_institucional",
            },
        ),
        "LIDERANCA_IGREJA_ALTERADA": (
            "Dados de lideranca da igreja alterados.",
            {
                "pastor_presidente",
                "pastor_setorial",
                "primeiro_secretario",
                "segundo_secretario",
                "terceiro_secretario",
            },
        ),
        "CONTATOS_IGREJA_ALTERADOS": (
            "Contatos da igreja alterados.",
            {"telefone", "whatsapp", "email", "site"},
        ),
        "ENDERECO_IGREJA_ALTERADO": (
            "Endereco da igreja alterado.",
            {
                "rua",
                "numero",
                "complemento",
                "bairro",
                "cep",
                "cidade_endereco",
                "estado_endereco",
            },
        ),
        "DADOS_CONGREGACAO_LOCAL_ALTERADOS": (
            "Dados da congregacao local alterados.",
            {
                campo
                for campo in CAMPOS_CONFIGURACOES_IGREJA
                if campo.startswith("congregacao_local_")
            },
        ),
    }

    def __init__(self, master):
        super().__init__(master)

        self.campos = {}
        self.carregando_dados = False
        self.salvamento_automatico_id = None
        self.ultima_assinatura_salva = None
        self.janela_configuracao_online = None

        self.title("Configurações da Igreja - SIGM")
        configurar_janela_principal(self, 1080, 780, 960, 680, master)
        self.configure(fg_color=cores.FUNDO)

        garantir_configuracoes_igreja()

        self.criar_interface()
        self.carregar_dados()
        trazer_para_frente(self)

    def criar_interface(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            self,
            text="Configurações da Igreja",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL
        ).grid(row=0, column=0, padx=30, pady=(25, 15), sticky="ew")

        self.cabecalho_igreja = CabecalhoIgreja(self)
        self.cabecalho_igreja.grid(row=1, column=0, padx=30, pady=(0, 12), sticky="ew")

        abas = ctk.CTkTabview(self, width=940, height=460)
        abas.grid(row=2, column=0, padx=30, pady=10, sticky="nsew")

        aba_identificacao = abas.add("Identificação")
        aba_lideranca = abas.add("Liderança")
        aba_contatos = abas.add("Contatos")
        aba_congregacao_local = abas.add("Congregação Local")
        aba_endereco = abas.add("Endereço")
        aba_visual = abas.add("Identidade Visual")
        aba_sistema = abas.add("Sistema")

        self.criar_campos(
            aba_identificacao,
            [
                ("nome_igreja", "Nome da Igreja"),
                ("ministerio", "Ministério"),
                ("convencao", "Convenção"),
                ("setor", "Setor"),
                ("congregacao_sede", "Congregação Sede"),
                ("cidade", "Cidade"),
                ("estado", "Estado"),
            ]
        )

        self.criar_campos(
            aba_lideranca,
            [
                ("pastor_presidente", "Pastor Presidente"),
                ("pastor_setorial", "Pastor Setorial"),
                ("primeiro_secretario", "Primeiro Secretário"),
                ("segundo_secretario", "Segundo Secretário"),
                ("terceiro_secretario", "Terceiro Secretário"),
            ]
        )

        self.criar_campos(
            aba_contatos,
            [
                ("telefone", "Telefone"),
                ("whatsapp", "WhatsApp"),
                ("email", "E-mail"),
                ("site", "Site"),
            ]
        )

        self.criar_campos(
            aba_congregacao_local,
            [
                ("congregacao_local_nome", "Nome da Congregação Local"),
                ("congregacao_local_dirigente", "Dirigente Local"),
                ("congregacao_local_numero", "Número da Congregação"),
                ("congregacao_local_campo_setor", "Campo/Setor"),
                ("congregacao_local_cidade", "Cidade da Congregação"),
                ("congregacao_local_estado", "Estado da Congregação"),
                ("congregacao_local_rua", "Rua"),
                ("congregacao_local_numero_endereco", "Número"),
                ("congregacao_local_bairro", "Bairro"),
                ("congregacao_local_cep", "CEP"),
                ("congregacao_local_telefone", "Telefone"),
                ("congregacao_local_whatsapp", "WhatsApp"),
                ("congregacao_local_email", "E-mail"),
            ]
        )

        self.criar_campos(
            aba_endereco,
            [
                ("rua", "Endereço"),
                ("numero", "Número"),
                ("complemento", "Complemento"),
                ("bairro", "Bairro"),
                ("cep", "CEP"),
                ("cidade_endereco", "Cidade"),
                ("estado_endereco", "Estado"),
            ]
        )

        self.criar_campos_imagem(
            aba_visual,
            [
                ("logotipo", "Logotipo da Igreja"),
                ("carimbo", "Carimbo"),
                ("assinatura_pastor", "Assinatura do Pastor"),
            ]
        )

        self.criar_campos(
            aba_sistema,
            [
                ("tema", "Tema futuro"),
                ("versiculo_institucional", "Versículo institucional opcional"),
            ]
        )

        frame_botoes = ctk.CTkFrame(self, fg_color="transparent")
        frame_botoes.grid(row=3, column=0, padx=30, pady=(10, 8), sticky="ew")

        ctk.CTkButton(
            frame_botoes,
            text="SALVAR",
            width=150,
            height=40,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            font=fontes.BOTAO,
            command=self.salvar
        ).grid(row=0, column=0, padx=8)

        ctk.CTkButton(
            frame_botoes,
            text="RESTAURAR",
            width=150,
            height=40,
            fg_color=cores.CINZA,
            hover_color="#444444",
            font=fontes.BOTAO,
            command=self.carregar_dados
        ).grid(row=0, column=1, padx=8)

        ctk.CTkButton(
            frame_botoes,
            text="CANCELAR",
            width=150,
            height=40,
            fg_color=cores.VERMELHO,
            hover_color="#A71D2A",
            font=fontes.BOTAO,
            command=self.destroy
        ).grid(row=0, column=2, padx=8)

        ctk.CTkButton(
            frame_botoes,
            text="PRE-CADASTRO ONLINE",
            width=210,
            height=40,
            fg_color=cores.VERDE,
            hover_color="#1F7A45",
            font=fontes.BOTAO,
            command=self.abrir_configuracao_online,
        ).grid(row=0, column=3, padx=8)

        self.status_salvamento = ctk.CTkLabel(
            self,
            text="Alterações salvas automaticamente no banco.",
            font=("Segoe UI", 12),
            text_color=cores.CINZA,
        )
        self.status_salvamento.grid(row=4, column=0, padx=30, pady=(0, 10), sticky="ew")

        self.bind("<Control-s>", lambda event: self.salvar())
        self.bind("<Escape>", lambda event: self.destroy())

    def criar_area_rolavel(self, aba):
        frame = ctk.CTkScrollableFrame(aba, corner_radius=10)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        frame.grid_columnconfigure(1, weight=1)
        return frame

    def criar_campos(self, aba, campos):
        frame = self.criar_area_rolavel(aba)

        for linha, (chave, rotulo) in enumerate(campos):
            ctk.CTkLabel(
                frame,
                text=rotulo,
                width=190,
                anchor="w",
                font=("Segoe UI", 13, "bold"),
                text_color=cores.AZUL_PRINCIPAL
            ).grid(row=linha, column=0, padx=(20, 10), pady=8, sticky="w")

            entrada = ctk.CTkEntry(
                frame,
                height=36,
                placeholder_text=rotulo
            )
            entrada.grid(row=linha, column=1, padx=(0, 20), pady=8, sticky="ew")
            entrada.bind("<KeyRelease>", self.agendar_salvamento_automatico)
            entrada.bind("<FocusOut>", self.agendar_salvamento_automatico)
            self.campos[chave] = entrada

    def criar_campos_imagem(self, aba, campos):
        frame = self.criar_area_rolavel(aba)
        frame.grid_columnconfigure(1, weight=1)

        for linha, (chave, rotulo) in enumerate(campos):
            ctk.CTkLabel(
                frame,
                text=rotulo,
                width=190,
                anchor="w",
                font=("Segoe UI", 13, "bold"),
                text_color=cores.AZUL_PRINCIPAL
            ).grid(row=linha, column=0, padx=(20, 10), pady=8, sticky="w")

            entrada = ctk.CTkEntry(
                frame,
                height=36,
                placeholder_text=rotulo
            )
            entrada.grid(row=linha, column=1, padx=(0, 10), pady=8, sticky="ew")
            entrada.bind("<KeyRelease>", self.agendar_salvamento_automatico)
            entrada.bind("<FocusOut>", self.agendar_salvamento_automatico)
            self.campos[chave] = entrada

            ctk.CTkButton(
                frame,
                text="Selecionar",
                width=110,
                height=36,
                fg_color=cores.AZUL_PRINCIPAL,
                hover_color=cores.AZUL_ESCURO,
                command=lambda campo=chave: self.selecionar_imagem(campo)
            ).grid(row=linha, column=2, padx=(0, 20), pady=8)

    def selecionar_imagem(self, campo):
        caminho = filedialog.askopenfilename(
            parent=self,
            title="Selecionar imagem",
            filetypes=[
                ("Imagens", "*.png *.jpg *.jpeg *.bmp"),
                ("Todos os arquivos", "*.*"),
            ]
        )

        if not caminho:
            return

        self.campos[campo].delete(0, "end")
        self.campos[campo].insert(0, caminho)
        self.agendar_salvamento_automatico()

    def limpar_campos(self):
        for campo in self.campos.values():
            campo.delete(0, "end")

    def carregar_dados(self):
        self.cancelar_salvamento_automatico()
        self.carregando_dados = True
        dados = buscar_configuracoes_igreja()
        self.limpar_campos()

        for campo in CAMPOS_CONFIGURACOES_IGREJA:
            if campo in self.campos:
                self.campos[campo].insert(0, dados.get(campo, ""))
        self.ultima_assinatura_salva = self.assinar_dados(dados)
        self.carregando_dados = False
        self.atualizar_status("Dados carregados do banco.")

    def montar_dados(self):
        dados = buscar_configuracoes_igreja()
        for campo, widget in self.campos.items():
            dados[campo] = widget.get().strip()
        return dados

    def salvar(self, exibir_mensagem=True):
        dados = self.montar_dados()
        if not self.validar_campos_obrigatorios(dados, exibir_mensagem):
            return

        assinatura = self.assinar_dados(dados)
        if assinatura == self.ultima_assinatura_salva:
            if exibir_mensagem:
                messagebox.showinfo(
                    "SIGM",
                    "As configuracoes ja estao salvas no banco.",
                    parent=self,
                )
            self.atualizar_status("Alteracoes salvas automaticamente no banco.")
            return

        try:
            dados_anteriores = buscar_configuracoes_igreja()
            campos_alterados = self.obter_campos_alterados(dados_anteriores, dados)
            detalhes_alteracao = self.montar_detalhes_alteracao(campos_alterados)
            salvar_configuracoes_igreja(dados)
            self.ultima_assinatura_salva = assinatura
            registrar_acao(
                "CONFIGURACOES_IGREJA_ALTERADAS",
                "Configuracoes da igreja alteradas.",
                modulo="Configuracoes",
                registro_id=1,
                detalhes=detalhes_alteracao,
            )

            if dados_anteriores.get("logotipo") != dados.get("logotipo"):
                registrar_acao(
                    "LOGOTIPO_ALTERADO",
                    "Logotipo da igreja alterado.",
                    modulo="Configuracoes",
                    registro_id=1,
                    detalhes=self.montar_detalhes_alteracao(["logotipo"]),
                )

            if dados_anteriores.get("carimbo") != dados.get("carimbo"):
                registrar_acao(
                    "CARIMBO_ALTERADO",
                    "Carimbo da igreja alterado.",
                    modulo="Configuracoes",
                    registro_id=1,
                    detalhes=self.montar_detalhes_alteracao(["carimbo"]),
                )

            if dados_anteriores.get("assinatura_pastor") != dados.get("assinatura_pastor"):
                registrar_acao(
                    "ASSINATURA_PASTOR_ALTERADA",
                    "Assinatura do pastor alterada.",
                    modulo="Configuracoes",
                    registro_id=1,
                    detalhes=self.montar_detalhes_alteracao(["assinatura_pastor"]),
                )

            self.registrar_grupos_alterados(campos_alterados)

            atualizar_cabecalhos_igreja(self)
            self.atualizar_status("Alteracoes salvas automaticamente no banco.")
            if exibir_mensagem:
                messagebox.showinfo(
                    "SIGM",
                    "Configuracoes da igreja salvas com sucesso.",
                    parent=self,
                )
        except Exception as erro:
            self.atualizar_status("Nao foi possivel salvar automaticamente.")
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel salvar as configuracoes.\n\nErro: {erro}",
                parent=self,
            )

    def agendar_salvamento_automatico(self, *_args):
        if self.carregando_dados:
            return

        self.atualizar_status("Salvando alteracoes...")
        if self.salvamento_automatico_id is not None:
            self.after_cancel(self.salvamento_automatico_id)

        self.salvamento_automatico_id = self.after(
            900,
            self.salvar_automaticamente,
        )

    def cancelar_salvamento_automatico(self):
        if self.salvamento_automatico_id is None:
            return

        self.after_cancel(self.salvamento_automatico_id)
        self.salvamento_automatico_id = None

    def salvar_automaticamente(self):
        self.salvamento_automatico_id = None
        self.salvar(exibir_mensagem=False)

    def atualizar_status(self, texto):
        if hasattr(self, "status_salvamento"):
            self.status_salvamento.configure(text=texto)

    def abrir_configuracao_online(self):
        if (
            self.janela_configuracao_online is not None
            and self.janela_configuracao_online.winfo_exists()
        ):
            self.janela_configuracao_online.lift()
            self.janela_configuracao_online.focus_force()
            return

        self.janela_configuracao_online = ConfiguracaoOnlineIgreja(self)

    def validar_campos_obrigatorios(self, dados, exibir_mensagem=True):
        faltando = [
            rotulo
            for campo, rotulo in self.CAMPOS_OBRIGATORIOS.items()
            if not str(dados.get(campo, "")).strip()
        ]
        if not faltando:
            return True

        self.atualizar_status("Preencha os campos obrigatorios antes de salvar.")
        if exibir_mensagem:
            messagebox.showwarning(
                "SIGM",
                "Preencha os campos obrigatorios:\n\n" + "\n".join(faltando),
                parent=self,
            )
        return False

    @staticmethod
    def assinar_dados(dados):
        return tuple(
            (campo, str(dados.get(campo, "")))
            for campo in CAMPOS_CONFIGURACOES_IGREJA
        )

    @classmethod
    def obter_campos_alterados(cls, dados_anteriores, dados_novos):
        return [
            campo
            for campo in CAMPOS_CONFIGURACOES_IGREJA
            if str(dados_anteriores.get(campo, "") or "")
            != str(dados_novos.get(campo, "") or "")
        ]

    @classmethod
    def montar_detalhes_alteracao(cls, campos_alterados):
        rotulos = [
            cls.ROTULOS_CAMPOS.get(campo, campo)
            for campo in campos_alterados
        ]
        if not rotulos:
            return ""

        return "Campos alterados: " + ", ".join(rotulos)

    def registrar_grupos_alterados(self, campos_alterados):
        conjunto_campos = set(campos_alterados)
        for acao, (descricao, campos_grupo) in self.GRUPOS_AUDITORIA.items():
            alterados_grupo = [
                campo
                for campo in CAMPOS_CONFIGURACOES_IGREJA
                if campo in campos_grupo and campo in conjunto_campos
            ]
            if not alterados_grupo:
                continue

            registrar_acao(
                acao,
                descricao,
                modulo="Configuracoes",
                registro_id=1,
                detalhes=self.montar_detalhes_alteracao(alterados_grupo),
            )
