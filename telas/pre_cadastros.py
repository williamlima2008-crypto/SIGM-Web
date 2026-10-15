import threading

import customtkinter as ctk
from tkinter import filedialog, messagebox

from banco.database import (
    CAMPOS_CADASTRAIS_PRE_CADASTRO,
    atualizar_dados_pre_cadastro,
    atualizar_status_pre_cadastro,
    buscar_pre_cadastro_por_id,
    listar_campos_faltantes_pre_cadastro,
    listar_pre_cadastros,
)
from componentes.cabecalho_igreja import CabecalhoIgreja
from config import cores, fontes
from servicos.importador_pre_cadastro_json import (
    ImportacaoPreCadastroErro,
    importar_pre_cadastros_json,
)
from servicos.sincronizacao_pre_cadastro_online import sincronizar_pre_cadastros_online
from servicos.aprovacao_pre_cadastro import (
    aprovar_pre_cadastro,
    atualizar_membro_existente_com_pre_cadastro,
    maior_nivel_duplicidade,
    rejeitar_pre_cadastro,
)
from servicos.duplicidade_membros import detectar_duplicidades_pre_cadastro
from telas.ficha_membro import FichaMembro
from utils.auditoria import registrar_acao
from utils.janelas import configurar_janela_principal, configurar_modal
from utils.sessao import obter_sessao


STATUS_FILTROS = {
    "Todos": None,
    "Pendente": "pendente",
    "Aprovado": "aprovado",
    "Rejeitado": "rejeitado",
    "Duplicado": "duplicado",
}

ROTULOS_CAMPOS = {
    "nome": "Nome",
    "rg": "RG",
    "orgao_emissor": "Orgao emissor",
    "cpf": "CPF",
    "data_nascimento": "Data de nascimento",
    "cidade_nascimento": "Cidade de nascimento",
    "estado_nascimento": "Estado de nascimento",
    "estado_civil": "Estado civil",
    "nome_conjuge": "Nome do conjuge",
    "data_nascimento_conjuge": "Nascimento do conjuge",
    "profissao": "Profissao",
    "nome_pai": "Nome do pai",
    "nome_mae": "Nome da mae",
    "grau_instrucao": "Grau de instrucao",
    "telefone": "Telefone",
    "celular": "Celular",
    "email": "E-mail",
    "endereco": "Endereco",
    "numero": "Numero",
    "bairro": "Bairro",
    "cidade": "Cidade",
    "estado": "Estado",
    "cep": "CEP",
    "batismo_aguas": "Batismo nas aguas",
    "batismo_espirito_santo": "Batismo no Espirito Santo",
    "ministerio": "Ministerio",
    "cargo": "Cargo",
    "data_funcao": "Data da funcao",
    "curso_teologico": "Curso teologico",
    "status_membro": "Status do membro",
    "congregacao": "Congregacao",
    "dirigente": "Dirigente",
    "setor_campo": "Setor/Campo",
    "igreja_local_batismo_aguas": "Igreja do batismo nas aguas",
    "igreja_local_batismo_espirito_santo": "Igreja do batismo no Espirito Santo",
    "recados_outros": "Recados/outros",
    "nome_titular_lgpd": "Nome do titular LGPD",
    "observacoes": "Observacoes",
    "caminho_foto": "Caminho da foto",
    "id": "ID",
    "remote_id": "Remote ID",
    "identificador_publico_igreja": "Identificador publico da igreja",
    "payload_json": "Payload JSON",
    "status": "Status do pre-cadastro",
    "membro_id_aprovado": "Membro aprovado",
    "motivo_rejeicao": "Motivo da rejeicao",
    "duplicidade_membro_id": "Membro duplicado",
    "recebido_em": "Recebido em",
    "revisado_em": "Revisado em",
    "usuario_revisor": "Usuario revisor",
    "origem": "Origem",
    "atualizado_em": "Atualizado em",
}

SECOES_CAMPOS = (
    ("Dados pessoais", (
        "nome",
        "rg",
        "orgao_emissor",
        "cpf",
        "data_nascimento",
        "cidade_nascimento",
        "estado_nascimento",
        "estado_civil",
        "profissao",
        "grau_instrucao",
    )),
    ("Filiacao e familia", (
        "nome_pai",
        "nome_mae",
        "nome_conjuge",
        "data_nascimento_conjuge",
    )),
    ("Contato", (
        "telefone",
        "celular",
        "recados_outros",
        "email",
    )),
    ("Endereco", (
        "endereco",
        "numero",
        "bairro",
        "cidade",
        "estado",
        "cep",
    )),
    ("Dados eclesiasticos", (
        "batismo_aguas",
        "batismo_espirito_santo",
        "ministerio",
        "cargo",
        "data_funcao",
        "curso_teologico",
        "status_membro",
        "congregacao",
        "dirigente",
        "setor_campo",
        "igreja_local_batismo_aguas",
        "igreja_local_batismo_espirito_santo",
    )),
    ("Informacoes adicionais", (
        "nome_titular_lgpd",
        "observacoes",
        "caminho_foto",
    )),
)

CAMPOS_TECNICOS_DETALHE = (
    "id",
    "remote_id",
    "identificador_publico_igreja",
    "status",
    "membro_id_aprovado",
    "motivo_rejeicao",
    "duplicidade_membro_id",
    "recebido_em",
    "revisado_em",
    "usuario_revisor",
    "origem",
    "atualizado_em",
    "payload_json",
)


class PreCadastros(ctk.CTkToplevel):
    LARGURA_NOME = 230
    LARGURA_CPF = 120
    LARGURA_CELULAR = 140
    LARGURA_EMAIL = 220
    LARGURA_STATUS = 110
    LARGURA_RECEBIDO = 150
    LARGURA_FALTANTES = 120

    def __init__(self, master):
        super().__init__(master)

        self.pre_cadastros = []
        self.pre_cadastros_filtrados = []
        self.id_selecionado = None
        self.janela_detalhes = None
        self.sincronizacao_em_andamento = False
        self.termo_pesquisa = ctk.StringVar(value="")
        self.status_filtro = ctk.StringVar(value="Todos")

        self.title("Pre-cadastros - SIGM")
        configurar_janela_principal(self, 1280, 760, 1100, 640, master)
        self.configure(fg_color=cores.FUNDO)

        self.criar_interface()
        self.carregar_pre_cadastros()

    def criar_interface(self):
        ctk.CTkLabel(
            self,
            text="Pre-cadastros",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(22, 8))

        CabecalhoIgreja(self).pack(fill="x", padx=24, pady=(0, 12))

        filtros = ctk.CTkFrame(self, fg_color="transparent")
        filtros.pack(fill="x", padx=24, pady=(0, 10))
        filtros.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            filtros,
            text="Pesquisa:",
            font=("Segoe UI", 12, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=0, column=0, padx=(0, 6), pady=5, sticky="w")

        entrada = ctk.CTkEntry(
            filtros,
            textvariable=self.termo_pesquisa,
            height=36,
            placeholder_text="Nome, CPF, telefone, celular, e-mail ou remote_id",
        )
        entrada.grid(row=0, column=1, padx=(0, 12), pady=5, sticky="ew")
        entrada.bind("<KeyRelease>", lambda _event: self.aplicar_filtros())

        ctk.CTkLabel(
            filtros,
            text="Status:",
            font=("Segoe UI", 12, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=0, column=2, padx=(0, 6), pady=5, sticky="w")

        ctk.CTkComboBox(
            filtros,
            variable=self.status_filtro,
            values=list(STATUS_FILTROS),
            width=150,
            height=36,
            command=lambda _valor: self.carregar_pre_cadastros(),
        ).grid(row=0, column=3, padx=(0, 0), pady=5, sticky="w")

        self.frame_lista = ctk.CTkScrollableFrame(self, corner_radius=10)
        self.frame_lista.pack(fill="both", expand=True, padx=24, pady=(0, 14))

        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(fill="x", padx=24, pady=(0, 18))

        self.botao(botoes, "ATUALIZAR", self.carregar_pre_cadastros).pack(side="left", padx=5)
        self.botao_sincronizar = self.botao(
            botoes,
            "SINCRONIZAR",
            self.iniciar_sincronizacao_online,
            cor=cores.VERDE,
            hover="#1F7A45",
            largura=145,
        )
        self.botao_sincronizar.pack(side="left", padx=5)
        self.botao(botoes, "IMPORTAR JSON", self.importar_json, cor=cores.VERDE, hover="#1F7A45", largura=145).pack(side="left", padx=5)
        self.botao(botoes, "LIMPAR FILTROS", self.limpar_filtros, cor=cores.CINZA, hover="#444444", largura=145).pack(side="left", padx=5)
        self.botao(botoes, "VER DETALHES", self.ver_detalhes, largura=145).pack(side="left", padx=5)
        self.botao(botoes, "FECHAR", self.destroy, cor=cores.CINZA, hover="#444444").pack(side="right", padx=5)

        self.bind("<Return>", lambda _event: self.ver_detalhes())
        self.bind("<Escape>", lambda _event: self.destroy())

    def botao(self, master, texto, comando, cor=None, hover=None, largura=130, estado="normal"):
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

    def carregar_pre_cadastros(self):
        self.id_selecionado = None
        status = STATUS_FILTROS.get(self.status_filtro.get())
        try:
            self.pre_cadastros = listar_pre_cadastros(status=status)
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel carregar os pre-cadastros.\n\nErro: {erro}",
                parent=self,
            )
            self.pre_cadastros = []
        self.aplicar_filtros()

    def importar_json(self):
        caminho = filedialog.askopenfilename(
            parent=self,
            title="Importar pre-cadastros JSON",
            filetypes=[
                ("Arquivos JSON", "*.json"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if not caminho:
            return

        try:
            relatorio = importar_pre_cadastros_json(caminho)
        except ImportacaoPreCadastroErro as erro:
            self.carregar_pre_cadastros()
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel importar o arquivo JSON.\n\nErro: {erro}",
                parent=self,
            )
            return
        except Exception as erro:
            self.carregar_pre_cadastros()
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel importar os pre-cadastros.\n\nErro: {erro}",
                parent=self,
            )
            return

        self.carregar_pre_cadastros()
        messagebox.showinfo(
            "SIGM",
            (
                "Importacao concluida.\n\n"
                f"Lidos: {relatorio.get('total_lido', 0)}\n"
                f"Novos: {relatorio.get('inseridos', 0)}\n"
                f"Ja existentes: {relatorio.get('ignorados', 0)}\n"
                f"Invalidos: {relatorio.get('invalidos', 0)}"
            ),
            parent=self,
        )

    def iniciar_sincronizacao_online(self):
        if self.sincronizacao_em_andamento:
            return

        self.sincronizacao_em_andamento = True
        self.definir_estado_sincronizacao("disabled", "SINCRONIZANDO...")

        thread = threading.Thread(
            target=self.executar_sincronizacao_online,
            daemon=True,
        )
        thread.start()

    def executar_sincronizacao_online(self):
        try:
            relatorio = sincronizar_pre_cadastros_online()
            self.after(0, lambda: self.finalizar_sincronizacao_online(relatorio, None))
        except Exception:
            self.after(0, lambda: self.finalizar_sincronizacao_online(None, True))

    def finalizar_sincronizacao_online(self, relatorio, erro):
        self.sincronizacao_em_andamento = False
        self.definir_estado_sincronizacao("normal", "SINCRONIZAR")

        if erro:
            messagebox.showerror(
                "Erro no SIGM",
                "Nao foi possivel sincronizar os pre-cadastros. Tente novamente.",
                parent=self,
            )
            return

        if relatorio and relatorio.get("sucesso"):
            self.carregar_pre_cadastros()

        mensagem = (relatorio or {}).get("mensagem_usuario") or (
            "Nao foi possivel sincronizar os pre-cadastros. Tente novamente."
        )
        titulo = "SIGM" if relatorio and relatorio.get("sucesso") else "Erro no SIGM"
        if relatorio and relatorio.get("sucesso"):
            messagebox.showinfo(titulo, mensagem, parent=self)
        else:
            messagebox.showwarning(titulo, mensagem, parent=self)

    def definir_estado_sincronizacao(self, estado, texto):
        botao = getattr(self, "botao_sincronizar", None)
        if botao is not None and botao.winfo_exists():
            botao.configure(state=estado, text=texto)

    def aplicar_filtros(self):
        termo = self.normalizar_texto(self.termo_pesquisa.get())
        if not termo:
            self.pre_cadastros_filtrados = list(self.pre_cadastros)
        else:
            self.pre_cadastros_filtrados = [
                registro
                for registro in self.pre_cadastros
                if self.registro_contem_termo(registro, termo)
            ]
        self.renderizar_lista()

    def registro_contem_termo(self, registro, termo):
        campos = (
            "nome",
            "cpf",
            "telefone",
            "celular",
            "email",
            "remote_id",
        )
        return any(
            termo in self.normalizar_texto(registro.get(campo))
            for campo in campos
        )

    def renderizar_lista(self):
        for widget in self.frame_lista.winfo_children():
            widget.destroy()

        if not self.pre_cadastros_filtrados:
            ctk.CTkLabel(
                self.frame_lista,
                text="Nenhum pre-cadastro encontrado.",
                font=fontes.TEXTO,
                text_color=cores.CINZA,
            ).pack(pady=36)
            return

        self.criar_cabecalho_lista()
        for registro in self.pre_cadastros_filtrados:
            self.criar_linha_lista(registro)

    def criar_cabecalho_lista(self):
        linha = ctk.CTkFrame(self.frame_lista, fg_color=cores.AZUL_PRINCIPAL, corner_radius=8)
        linha.pack(fill="x", padx=10, pady=(10, 5))
        self.configurar_grid_linha(linha)
        colunas = [
            ("Nome", self.LARGURA_NOME),
            ("CPF", self.LARGURA_CPF),
            ("Celular", self.LARGURA_CELULAR),
            ("E-mail", self.LARGURA_EMAIL),
            ("Status", self.LARGURA_STATUS),
            ("Recebido em", self.LARGURA_RECEBIDO),
            ("Campos faltantes", self.LARGURA_FALTANTES),
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

    def criar_linha_lista(self, registro):
        selecionado = registro.get("id") == self.id_selecionado
        linha = ctk.CTkFrame(
            self.frame_lista,
            fg_color="#EAF2FF" if selecionado else cores.BRANCO,
            corner_radius=8,
            border_width=1 if selecionado else 0,
            border_color=cores.AZUL_PRINCIPAL,
        )
        linha.pack(fill="x", padx=10, pady=4)
        self.configurar_grid_linha(linha)

        valores = [
            (registro.get("nome") or "-", self.LARGURA_NOME, 34),
            (registro.get("cpf") or "-", self.LARGURA_CPF, 18),
            (registro.get("celular") or "-", self.LARGURA_CELULAR, 20),
            (registro.get("email") or "-", self.LARGURA_EMAIL, 30),
            (self.formatar_status(registro.get("status")), self.LARGURA_STATUS, 18),
            (registro.get("recebido_em") or "-", self.LARGURA_RECEBIDO, 22),
            (self.resumo_campos_faltantes(registro.get("id")), self.LARGURA_FALTANTES, 18),
        ]

        for indice, (valor, largura, limite) in enumerate(valores):
            label = ctk.CTkLabel(
                linha,
                text=self.encurtar(valor, limite),
                width=largura,
                anchor="w",
                font=("Segoe UI", 12),
                text_color=cores.PRETO,
            )
            label.grid(row=0, column=indice, padx=4, pady=8, sticky="ew")
            label.bind("<Button-1>", lambda _event, item=registro: self.selecionar_registro(item))
            label.bind("<Double-Button-1>", lambda _event, item=registro: self.ver_detalhes(item.get("id")))

        linha.bind("<Button-1>", lambda _event, item=registro: self.selecionar_registro(item))
        linha.bind("<Double-Button-1>", lambda _event, item=registro: self.ver_detalhes(item.get("id")))

    def configurar_grid_linha(self, linha):
        larguras = (
            self.LARGURA_NOME,
            self.LARGURA_CPF,
            self.LARGURA_CELULAR,
            self.LARGURA_EMAIL,
            self.LARGURA_STATUS,
            self.LARGURA_RECEBIDO,
            self.LARGURA_FALTANTES,
        )
        for indice, largura in enumerate(larguras):
            linha.grid_columnconfigure(indice, minsize=largura, weight=1 if indice in (0, 3) else 0)

    def selecionar_registro(self, registro):
        self.id_selecionado = registro.get("id")
        self.renderizar_lista()

    def limpar_filtros(self):
        self.termo_pesquisa.set("")
        self.status_filtro.set("Todos")
        self.carregar_pre_cadastros()

    def ver_detalhes(self, pre_cadastro_id=None):
        pre_cadastro_id = pre_cadastro_id or self.id_selecionado
        if not pre_cadastro_id:
            messagebox.showwarning("SIGM", "Selecione um pre-cadastro.", parent=self)
            return

        registro = buscar_pre_cadastro_por_id(pre_cadastro_id)
        if not registro:
            messagebox.showerror("SIGM", "Pre-cadastro nao encontrado.", parent=self)
            return

        if self.janela_detalhes is not None and self.janela_detalhes.winfo_exists():
            self.janela_detalhes.destroy()

        self.janela_detalhes = DetalhesPreCadastro(self, registro, self.atualizar_apos_edicao)

    def atualizar_apos_edicao(self, pre_cadastro_id):
        self.carregar_pre_cadastros()
        self.id_selecionado = pre_cadastro_id
        self.renderizar_lista()
        if self.janela_detalhes is not None and self.janela_detalhes.winfo_exists():
            self.janela_detalhes.atualizar_dados(pre_cadastro_id)

    def atualizar_apos_status(self, pre_cadastro_id):
        self.carregar_pre_cadastros()
        self.id_selecionado = pre_cadastro_id
        self.renderizar_lista()
        if self.janela_detalhes is not None and self.janela_detalhes.winfo_exists():
            self.janela_detalhes.atualizar_dados(pre_cadastro_id)

    def resumo_campos_faltantes(self, pre_cadastro_id):
        faltantes = listar_campos_faltantes_pre_cadastro(pre_cadastro_id)
        quantidade = len(faltantes)
        if quantidade == 0:
            return "Completo"
        if quantidade == 1:
            return "1 faltante"
        return f"{quantidade} faltantes"

    @staticmethod
    def normalizar_texto(valor):
        return str(valor or "").strip().lower()

    @staticmethod
    def encurtar(valor, limite):
        texto = str(valor or "")
        if len(texto) <= limite:
            return texto
        return texto[: max(limite - 3, 1)] + "..."

    @staticmethod
    def formatar_status(status):
        texto = str(status or "pendente").strip().lower()
        return {
            "pendente": "Pendente",
            "aprovado": "Aprovado",
            "rejeitado": "Rejeitado",
            "duplicado": "Duplicado",
        }.get(texto, texto.title() if texto else "Pendente")


def confirmar_e_atualizar_membro_existente(janela, registro, candidato, ao_concluir=None, depois=None):
    """Pergunta e, se confirmado, atualiza o membro existente com o pre-cadastro."""
    membro_id = candidato.get("membro_id")
    nome = candidato.get("nome") or "membro"
    confirmar = messagebox.askyesno(
        "Atualizar cadastro existente",
        (
            f"Atualizar o cadastro de {nome} (ID {membro_id}) com os dados deste pre-cadastro?\n\n"
            "Campos preenchidos no pre-cadastro substituem os atuais.\n"
            "Campos vazios mantem o que ja esta no SIGM.\n"
            "Nenhum membro novo sera criado."
        ),
        parent=janela,
    )
    if not confirmar:
        return False

    sessao = obter_sessao() or {}
    resultado = atualizar_membro_existente_com_pre_cadastro(
        registro.get("id"),
        membro_id,
        usuario_revisor=sessao.get("nome") or sessao.get("login") or "",
    )
    if not resultado.get("sucesso"):
        messagebox.showerror("SIGM", resultado.get("mensagem") or "Nao foi possivel atualizar.", parent=janela)
        return False

    messagebox.showinfo("SIGM", f"Cadastro de {nome} atualizado com sucesso.", parent=janela)
    if ao_concluir:
        ao_concluir(registro.get("id"))
    if depois:
        depois()
    return True


class DetalhesPreCadastro(ctk.CTkToplevel):
    def __init__(self, master, registro, ao_salvar=None):
        super().__init__(master)
        self.registro = registro
        self.ao_salvar = ao_salvar
        self.candidatos_duplicidade = []
        self.janela_duplicidades = None
        self.janela_membro_aprovado = None
        self.aprovacao_em_andamento = False

        self.title("Detalhes do Pre-cadastro - SIGM")
        configurar_janela_principal(self, 1080, 760, 900, 640, master)
        self.configure(fg_color=cores.FUNDO)
        self.transient(master)
        self.grab_set()

        self.criar_interface()

    def atualizar_dados(self, pre_cadastro_id):
        registro = buscar_pre_cadastro_por_id(pre_cadastro_id)
        if not registro:
            return
        self.registro = registro
        self.candidatos_duplicidade = []
        for widget in self.winfo_children():
            widget.destroy()
        self.criar_interface()

    def criar_interface(self):
        self.candidatos_duplicidade = detectar_duplicidades_pre_cadastro(self.registro)

        ctk.CTkLabel(
            self,
            text="Detalhes do Pre-cadastro",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(22, 8))

        CabecalhoIgreja(self).pack(fill="x", padx=24, pady=(0, 12))

        faltantes = set(listar_campos_faltantes_pre_cadastro(self.registro.get("id")))
        resumo = self.texto_resumo_faltantes(faltantes)
        ctk.CTkLabel(
            self,
            text=resumo,
            font=("Segoe UI", 13, "bold"),
            text_color=cores.VERMELHO if faltantes else cores.VERDE,
        ).pack(fill="x", padx=24, pady=(0, 8))

        ctk.CTkLabel(
            self,
            text=self.texto_resumo_duplicidade(),
            font=("Segoe UI", 13, "bold"),
            text_color=self.cor_resumo_duplicidade(),
        ).pack(fill="x", padx=24, pady=(0, 8))

        conteudo = ctk.CTkScrollableFrame(self, corner_radius=10)
        conteudo.pack(fill="both", expand=True, padx=24, pady=(0, 14))
        conteudo.grid_columnconfigure(0, weight=1)

        for titulo, campos in SECOES_CAMPOS:
            self.criar_secao(conteudo, titulo, campos, faltantes)

        self.criar_secao(conteudo, "Dados tecnicos do pre-cadastro", CAMPOS_TECNICOS_DETALHE, set())

        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(fill="x", padx=24, pady=(0, 18))

        status_atual = self.status_atual()
        aprovado = status_atual == "aprovado" and self.registro.get("membro_id_aprovado")
        pendente = status_atual == "pendente"

        self.botao(botoes, "EDITAR DADOS", self.editar_dados, largura=145).pack(side="left", padx=5)
        self.botao(botoes, "ANALISAR DUPLICIDADES", self.analisar_duplicidades, largura=190).pack(side="left", padx=5)
        if pendente and self.candidatos_duplicidade:
            self.botao(
                botoes,
                "ATUALIZAR CADASTRO EXISTENTE",
                self.atualizar_cadastro_existente,
                cor=cores.AMARELO,
                hover="#D39E00",
                largura=250,
            ).pack(side="left", padx=5)
        self.botao_aprovar = self.botao(
            botoes,
            "APROVAR E CADASTRAR",
            self.aprovar_e_cadastrar,
            cor=cores.VERDE,
            hover="#1F7A45",
            largura=190,
            estado="normal" if pendente else "disabled",
        )
        self.botao_aprovar.pack(side="left", padx=5)
        self.botao_rejeitar = self.botao(
            botoes,
            "REJEITAR",
            self.rejeitar,
            cor=cores.VERMELHO,
            hover="#A71D2A",
            largura=120,
            estado="normal" if pendente else "disabled",
        )
        self.botao_rejeitar.pack(side="left", padx=5)
        if aprovado:
            self.botao(
                botoes,
                "ABRIR MEMBRO CADASTRADO",
                self.abrir_membro_aprovado,
                largura=220,
            ).pack(side="left", padx=5)
        self.botao(botoes, "FECHAR", self.destroy, cor=cores.CINZA, hover="#444444").pack(side="right", padx=5)

        self.bind("<Escape>", lambda _event: self.destroy())

    def criar_secao(self, master, titulo, campos, faltantes):
        secao = ctk.CTkFrame(master, fg_color=cores.BRANCO, corner_radius=8)
        secao.pack(fill="x", padx=10, pady=8)
        secao.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            secao,
            text=titulo,
            font=("Segoe UI", 15, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, padx=14, pady=(12, 6), sticky="ew")

        for linha, campo in enumerate(campos, start=1):
            faltante = campo in faltantes
            fundo = "#FFF8E1" if faltante else "transparent"

            ctk.CTkLabel(
                secao,
                text=f"{ROTULOS_CAMPOS.get(campo, campo)}:",
                width=220,
                anchor="w",
                font=("Segoe UI", 12, "bold"),
                text_color=cores.AZUL_PRINCIPAL,
            ).grid(row=linha, column=0, padx=(14, 8), pady=4, sticky="nw")

            valor = self.registro.get(campo)
            texto = str(valor) if valor not in (None, "") else "Campo nao preenchido"
            ctk.CTkLabel(
                secao,
                text=texto,
                anchor="w",
                justify="left",
                wraplength=720,
                font=("Segoe UI", 12),
                text_color=cores.VERMELHO if faltante else cores.PRETO,
                fg_color=fundo,
                corner_radius=6,
            ).grid(row=linha, column=1, padx=(0, 14), pady=4, sticky="ew")

    def editar_dados(self):
        EditarPreCadastro(self, self.registro, self.ao_salvar)

    def analisar_duplicidades(self):
        if self.janela_duplicidades is not None and self.janela_duplicidades.winfo_exists():
            self.janela_duplicidades.destroy()

        self.janela_duplicidades = AnaliseDuplicidadesPreCadastro(
            self,
            self.registro,
            self.candidatos_duplicidade,
            self.ao_salvar,
        )

    def atualizar_cadastro_existente(self):
        candidatos = [
            c for c in self.candidatos_duplicidade
            if c.get("nivel") in ("alto", "medio")
        ] or list(self.candidatos_duplicidade)
        if len(candidatos) == 1:
            confirmar_e_atualizar_membro_existente(
                self, self.registro, candidatos[0], self.ao_salvar,
                depois=lambda: self.atualizar_dados(self.registro.get("id")),
            )
            return
        # Mais de um candidato: o usuario escolhe qual membro atualizar.
        self.analisar_duplicidades()

    def abrir_membro_aprovado(self):
        membro_id = self.registro.get("membro_id_aprovado")
        if not membro_id:
            messagebox.showwarning("SIGM", "Este pre-cadastro ainda nao possui membro aprovado.", parent=self)
            return

        if self.janela_membro_aprovado is not None and self.janela_membro_aprovado.winfo_exists():
            self.janela_membro_aprovado.destroy()
        self.janela_membro_aprovado = FichaMembro(self, membro_id)

    def aprovar_e_cadastrar(self):
        if self.aprovacao_em_andamento:
            return

        self.aprovacao_em_andamento = True
        self.definir_estado_botao_aprovar("disabled")
        try:
            pre_cadastro_id = self.registro.get("id")
            registro = buscar_pre_cadastro_por_id(pre_cadastro_id)
            if not registro:
                messagebox.showerror("SIGM", "Pre-cadastro nao encontrado.", parent=self)
                return

            self.registro = registro
            status = self.status_atual()
            if status == "aprovado":
                messagebox.showinfo("SIGM", "Este pre-cadastro ja foi aprovado.", parent=self)
                self.atualizar_dados(pre_cadastro_id)
                return
            if status == "rejeitado":
                messagebox.showwarning("SIGM", "Pre-cadastro rejeitado nao pode ser aprovado.", parent=self)
                return
            if status == "duplicado":
                messagebox.showwarning("SIGM", "Pre-cadastro duplicado nao pode ser aprovado.", parent=self)
                return

            if not str(registro.get("nome") or "").strip():
                messagebox.showwarning("SIGM", "Informe o nome antes de aprovar.", parent=self)
                return

            faltantes = listar_campos_faltantes_pre_cadastro(pre_cadastro_id)
            if faltantes and not self.confirmar_campos_faltantes(len(faltantes)):
                return

            duplicidades = detectar_duplicidades_pre_cadastro(registro)
            nivel = maior_nivel_duplicidade(duplicidades)
            permitir_duplicidade = False
            if nivel == "alto":
                messagebox.showerror(
                    "SIGM",
                    (
                        "Este pre-cadastro possui risco alto de duplicidade.\n\n"
                        "Use o botao ATUALIZAR CADASTRO EXISTENTE para atualizar o membro\n"
                        "que ja esta no SIGM, ou analise as duplicidades."
                    ),
                    parent=self,
                )
                return
            if nivel == "medio":
                permitir_duplicidade = self.confirmar_duplicidade(nivel, len(duplicidades))
                if not permitir_duplicidade:
                    return
            elif nivel == "baixo":
                self.avisar_duplicidade_baixa(len(duplicidades))

            if not self.confirmar_aprovacao_final():
                return

            resultado = aprovar_pre_cadastro(
                pre_cadastro_id,
                usuario_revisor=self.usuario_revisor(),
                permitir_duplicidade=permitir_duplicidade,
            )
            if not resultado.get("sucesso"):
                messagebox.showerror("SIGM", resultado.get("mensagem") or "Nao foi possivel aprovar.", parent=self)
                self.atualizar_dados(pre_cadastro_id)
                return

            membro_id = resultado.get("membro_id")
            nome = registro.get("nome") or "Membro"
            messagebox.showinfo(
                "SIGM",
                f"{nome} foi cadastrado como membro oficial.\n\nID do membro: {membro_id}",
                parent=self,
            )
            if self.ao_salvar:
                self.ao_salvar(pre_cadastro_id)
            self.atualizar_dados(pre_cadastro_id)
        finally:
            self.aprovacao_em_andamento = False
            if self.winfo_exists() and self.status_atual() == "pendente":
                self.definir_estado_botao_aprovar("normal")

    def rejeitar(self):
        pre_cadastro_id = self.registro.get("id")
        registro = buscar_pre_cadastro_por_id(pre_cadastro_id)
        if not registro:
            messagebox.showerror("SIGM", "Pre-cadastro nao encontrado.", parent=self)
            return

        self.registro = registro
        status = self.status_atual()
        if status == "aprovado":
            messagebox.showwarning("SIGM", "Pre-cadastro aprovado nao pode ser rejeitado.", parent=self)
            return
        if status == "rejeitado":
            messagebox.showinfo("SIGM", "Este pre-cadastro ja foi rejeitado.", parent=self)
            return
        if status == "duplicado":
            messagebox.showwarning("SIGM", "Pre-cadastro duplicado nao pode ser rejeitado.", parent=self)
            return

        confirmar = messagebox.askyesno(
            "Confirmar rejeicao",
            "Deseja rejeitar este pre-cadastro?\n\nO registro permanecera no historico.",
            parent=self,
        )
        if not confirmar:
            return

        motivo = ctk.CTkInputDialog(
            text="Informe um motivo curto para a rejeicao:",
            title="Motivo da rejeicao",
        ).get_input()
        if motivo is None:
            return

        resultado = rejeitar_pre_cadastro(
            pre_cadastro_id,
            motivo=motivo,
            usuario_revisor=self.usuario_revisor(),
        )
        if not resultado.get("sucesso"):
            messagebox.showerror("SIGM", resultado.get("mensagem") or "Nao foi possivel rejeitar.", parent=self)
            self.atualizar_dados(pre_cadastro_id)
            return

        messagebox.showinfo("SIGM", "Pre-cadastro rejeitado com sucesso.", parent=self)
        if self.ao_salvar:
            self.ao_salvar(pre_cadastro_id)
        self.atualizar_dados(pre_cadastro_id)

    def confirmar_campos_faltantes(self, quantidade):
        return messagebox.askyesno(
            "Campos nao preenchidos",
            (
                f"Este pre-cadastro ainda possui {quantidade} "
                f"{'campo nao preenchido' if quantidade == 1 else 'campos nao preenchidos'}.\n\n"
                "O secretario podera completar depois.\n\n"
                "Deseja aprovar mesmo assim?"
            ),
            parent=self,
        )

    def confirmar_duplicidade(self, nivel, quantidade):
        return messagebox.askyesno(
            "Possivel duplicidade",
            (
                f"Foram encontradas {quantidade} possiveis duplicidades "
                f"com risco {nivel}.\n\n"
                "Pode ser coincidencia familiar ou de contato compartilhado.\n"
                "Revise os candidatos antes de continuar.\n\n"
                "Aprovar mesmo assim?"
            ),
            parent=self,
        )

    def avisar_duplicidade_baixa(self, quantidade):
        messagebox.showinfo(
            "SIGM",
            (
                f"Foram encontrados {quantidade} sinais informativos de possivel duplicidade.\n\n"
                "Endereco, cidade, sobrenome ou nome parecido nao bloqueiam a aprovacao."
            ),
            parent=self,
        )

    def confirmar_aprovacao_final(self):
        return messagebox.askyesno(
            "Aprovar e cadastrar",
            (
                "Deseja transformar este pre-cadastro em um membro oficial do SIGM?\n\n"
                "O membro sera criado no cadastro principal.\n"
                "O pre-cadastro sera marcado como aprovado e permanecera no historico."
            ),
            parent=self,
        )

    def definir_estado_botao_aprovar(self, estado):
        botao = getattr(self, "botao_aprovar", None)
        if botao is not None and botao.winfo_exists():
            botao.configure(state=estado)

    def usuario_revisor(self):
        sessao = obter_sessao() or {}
        return sessao.get("nome") or sessao.get("login") or ""

    def status_atual(self):
        return str(self.registro.get("status") or "pendente").strip().lower()

    def botao(self, master, texto, comando, cor=None, hover=None, largura=130, estado="normal"):
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

    @staticmethod
    def texto_resumo_faltantes(faltantes):
        quantidade = len(faltantes)
        if quantidade == 0:
            return "Este pre-cadastro esta completo."
        if quantidade == 1:
            return "Este pre-cadastro possui 1 campo nao preenchido."
        return f"Este pre-cadastro possui {quantidade} campos nao preenchidos."

    def maior_nivel_duplicidade(self):
        if not self.candidatos_duplicidade:
            return ""
        return self.candidatos_duplicidade[0].get("nivel") or ""

    def texto_resumo_duplicidade(self):
        quantidade = len(self.candidatos_duplicidade)
        if quantidade == 0:
            return "Nenhuma possivel duplicidade encontrada."
        if quantidade == 1:
            return "Encontrada 1 possivel duplicidade."
        return f"Encontradas {quantidade} possiveis duplicidades."

    def cor_resumo_duplicidade(self):
        nivel = self.maior_nivel_duplicidade()
        if nivel == "alto":
            return cores.VERMELHO
        if nivel == "medio":
            return "#9A6700"
        return cores.VERDE


class AnaliseDuplicidadesPreCadastro(ctk.CTkToplevel):
    def __init__(self, master, registro, candidatos, ao_marcar=None):
        super().__init__(master)
        self.registro = registro
        self.candidatos = list(candidatos or [])
        self.ao_marcar = ao_marcar
        self.candidato_selecionado = None
        self.janela_ficha = None

        self.title("Analise de Duplicidades - SIGM")
        self.geometry("980x620")
        self.minsize(820, 520)
        self.configure(fg_color=cores.FUNDO)
        configurar_modal(self, master)
        self.grab_set()

        self.criar_interface()

    def criar_interface(self):
        ctk.CTkLabel(
            self,
            text="Analise de Duplicidades",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(22, 8))

        ctk.CTkLabel(
            self,
            text=self.texto_resumo(),
            font=("Segoe UI", 13, "bold"),
            text_color=self.cor_resumo(),
        ).pack(fill="x", padx=24, pady=(0, 10))

        self.frame_lista = ctk.CTkScrollableFrame(self, corner_radius=10)
        self.frame_lista.pack(fill="both", expand=True, padx=24, pady=(0, 14))

        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(fill="x", padx=24, pady=(0, 18))
        self.botao(botoes, "ABRIR FICHA DO MEMBRO", self.abrir_ficha_membro, largura=190).pack(side="left", padx=5)
        self.botao(botoes, "ATUALIZAR MEMBRO SELECIONADO", self.atualizar_membro_selecionado, cor=cores.VERDE, hover="#1F7A45", largura=250).pack(side="left", padx=5)
        self.botao(botoes, "MARCAR COMO DUPLICADO", self.marcar_como_duplicado, cor=cores.AMARELO, hover="#D39E00", largura=200).pack(side="left", padx=5)
        self.botao(botoes, "FECHAR", self.destroy, cor=cores.CINZA, hover="#444444").pack(side="right", padx=5)

        self.renderizar_candidatos()
        self.bind("<Escape>", lambda _event: self.destroy())

    def renderizar_candidatos(self):
        for widget in self.frame_lista.winfo_children():
            widget.destroy()

        if not self.candidatos:
            ctk.CTkLabel(
                self.frame_lista,
                text="Nenhuma possivel duplicidade encontrada.",
                font=fontes.TEXTO,
                text_color=cores.CINZA,
            ).pack(pady=36)
            return

        self.criar_cabecalho()
        for candidato in self.candidatos:
            self.criar_linha(candidato)

    def criar_cabecalho(self):
        linha = ctk.CTkFrame(self.frame_lista, fg_color=cores.AZUL_PRINCIPAL, corner_radius=8)
        linha.pack(fill="x", padx=10, pady=(10, 5))
        self.configurar_grid_linha(linha)
        colunas = (
            "Nome",
            "CPF",
            "Nascimento",
            "Celular",
            "E-mail",
            "Nivel",
            "Pontos",
            "Motivos",
        )
        for indice, texto in enumerate(colunas):
            ctk.CTkLabel(
                linha,
                text=texto,
                anchor="w",
                font=("Segoe UI", 12, "bold"),
                text_color=cores.BRANCO,
            ).grid(row=0, column=indice, padx=4, pady=8, sticky="ew")

    def criar_linha(self, candidato):
        selecionado = self.candidato_selecionado is candidato
        linha = ctk.CTkFrame(
            self.frame_lista,
            fg_color="#EAF2FF" if selecionado else cores.BRANCO,
            corner_radius=8,
            border_width=1 if selecionado else 0,
            border_color=cores.AZUL_PRINCIPAL,
        )
        linha.pack(fill="x", padx=10, pady=4)
        self.configurar_grid_linha(linha)

        valores = (
            candidato.get("nome") or "-",
            candidato.get("cpf") or "-",
            candidato.get("data_nascimento") or "-",
            candidato.get("celular") or "-",
            candidato.get("email") or "-",
            self.formatar_nivel(candidato.get("nivel")),
            str(candidato.get("pontuacao") or 0),
            "; ".join(candidato.get("motivos") or []),
        )
        limites = (24, 14, 12, 14, 22, 52, 8, 42)
        for indice, valor in enumerate(valores):
            label = ctk.CTkLabel(
                linha,
                text=self.encurtar(valor, limites[indice]),
                anchor="w",
                font=("Segoe UI", 12),
                text_color=cores.PRETO,
            )
            label.grid(row=0, column=indice, padx=4, pady=8, sticky="ew")
            label.bind("<Button-1>", lambda _event, item=candidato: self.selecionar(item))
            label.bind("<Double-Button-1>", lambda _event, item=candidato: self.abrir_ficha_membro(item))

        linha.bind("<Button-1>", lambda _event, item=candidato: self.selecionar(item))
        linha.bind("<Double-Button-1>", lambda _event, item=candidato: self.abrir_ficha_membro(item))

    def configurar_grid_linha(self, linha):
        pesos = (2, 0, 0, 0, 2, 1, 0, 3)
        larguras = (170, 110, 105, 120, 170, 230, 65, 260)
        for indice, largura in enumerate(larguras):
            linha.grid_columnconfigure(indice, minsize=largura, weight=pesos[indice])

    def selecionar(self, candidato):
        self.candidato_selecionado = candidato
        self.renderizar_candidatos()

    def abrir_ficha_membro(self, candidato=None):
        candidato = candidato or self.candidato_selecionado
        if not candidato:
            messagebox.showwarning("SIGM", "Selecione um candidato.", parent=self)
            return

        membro_id = candidato.get("membro_id")
        if not membro_id:
            messagebox.showerror("SIGM", "Membro candidato invalido.", parent=self)
            return

        if self.janela_ficha is not None and self.janela_ficha.winfo_exists():
            self.janela_ficha.destroy()

        self.janela_ficha = FichaMembro(self, membro_id)

    def atualizar_membro_selecionado(self):
        candidato = self.candidato_selecionado
        if not candidato and len(self.candidatos) == 1:
            candidato = self.candidatos[0]
        if not candidato:
            messagebox.showwarning("SIGM", "Selecione o membro que sera atualizado.", parent=self)
            return
        confirmar_e_atualizar_membro_existente(
            self, self.registro, candidato, self.ao_marcar,
            depois=self.fechar_apos_atualizar,
        )

    def fechar_apos_atualizar(self):
        master = self.master
        self.destroy()
        try:
            if master is not None and master.winfo_exists() and hasattr(master, "atualizar_dados"):
                master.atualizar_dados(self.registro.get("id"))
        except Exception:
            pass

    def marcar_como_duplicado(self):
        candidato = self.candidato_selecionado
        if not candidato:
            messagebox.showwarning("SIGM", "Selecione um candidato.", parent=self)
            return

        confirmar = messagebox.askyesno(
            "Confirmar duplicidade",
            "Marcar este pre-cadastro como duplicado do membro selecionado?",
            parent=self,
        )
        if not confirmar:
            return

        sessao = obter_sessao() or {}
        atualizado = atualizar_status_pre_cadastro(
            self.registro.get("id"),
            "duplicado",
            duplicidade_membro_id=candidato.get("membro_id"),
            usuario_revisor=sessao.get("nome") or sessao.get("login") or "",
        )
        if not atualizado:
            messagebox.showerror("SIGM", "Pre-cadastro nao encontrado.", parent=self)
            return

        registrar_acao(
            "PRE_CADASTRO_MARCADO_DUPLICADO",
            "Pre-cadastro marcado como duplicado.",
            modulo="Pre-cadastros",
            registro_id=self.registro.get("id"),
            detalhes=f"Membro relacionado: {candidato.get('membro_id')}",
        )
        messagebox.showinfo("SIGM", "Pre-cadastro marcado como duplicado.", parent=self)
        if self.ao_marcar:
            self.ao_marcar(atualizado.get("id"))
        self.destroy()

    def texto_resumo(self):
        quantidade = len(self.candidatos)
        if quantidade == 0:
            return "Nenhuma possivel duplicidade encontrada."
        if quantidade == 1:
            return "Encontrada 1 possivel duplicidade."
        return f"Encontradas {quantidade} possiveis duplicidades."

    def cor_resumo(self):
        if not self.candidatos:
            return cores.VERDE
        nivel = self.candidatos[0].get("nivel")
        if nivel == "alto":
            return cores.VERMELHO
        if nivel == "medio":
            return "#9A6700"
        return cores.VERDE

    def botao(self, master, texto, comando, cor=None, hover=None, largura=130):
        return ctk.CTkButton(
            master,
            text=texto,
            width=largura,
            height=38,
            fg_color=cor or cores.AZUL_PRINCIPAL,
            hover_color=hover or cores.AZUL_ESCURO,
            font=("Segoe UI", 12, "bold"),
            command=comando,
        )

    @staticmethod
    def formatar_nivel(nivel):
        texto = str(nivel or "").strip().lower()
        if texto == "alto":
            return "Alto - bloqueio por documento igual"
        if texto == "medio":
            return "Medio - possivel coincidencia familiar ou de contato"
        if texto == "baixo":
            return "Baixo - informativo"
        return "-"

    @staticmethod
    def encurtar(valor, limite):
        texto = str(valor or "")
        if len(texto) <= limite:
            return texto
        return texto[: max(limite - 3, 1)] + "..."


class EditarPreCadastro(ctk.CTkToplevel):
    def __init__(self, master, registro, ao_salvar=None):
        super().__init__(master)
        self.registro = registro
        self.ao_salvar = ao_salvar
        self.campos = {}

        self.title("Editar Pre-cadastro - SIGM")
        self.geometry("980x720")
        self.minsize(820, 620)
        self.configure(fg_color=cores.FUNDO)
        configurar_modal(self, master)
        self.grab_set()

        self.criar_interface()

    def criar_interface(self):
        ctk.CTkLabel(
            self,
            text="Editar dados do Pre-cadastro",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(22, 8))

        ctk.CTkLabel(
            self,
            text="A edicao altera apenas os campos cadastrais locais. O status do fluxo permanece inalterado.",
            font=("Segoe UI", 12),
            text_color=cores.CINZA,
        ).pack(fill="x", padx=24, pady=(0, 10))

        conteudo = ctk.CTkScrollableFrame(self, corner_radius=10)
        conteudo.pack(fill="both", expand=True, padx=24, pady=(0, 14))

        for titulo, campos in SECOES_CAMPOS:
            self.criar_secao_edicao(conteudo, titulo, campos)

        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(fill="x", padx=24, pady=(0, 18))
        self.botao(botoes, "SALVAR", self.salvar, cor=cores.VERDE, hover="#1F7A45").pack(side="left", padx=5)
        self.botao(botoes, "CANCELAR", self.destroy, cor=cores.CINZA, hover="#444444").pack(side="left", padx=5)

        self.bind("<Control-s>", lambda _event: self.salvar())
        self.bind("<Escape>", lambda _event: self.destroy())

    def criar_secao_edicao(self, master, titulo, campos):
        secao = ctk.CTkFrame(master, fg_color=cores.BRANCO, corner_radius=8)
        secao.pack(fill="x", padx=10, pady=8)
        secao.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            secao,
            text=titulo,
            font=("Segoe UI", 15, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, padx=14, pady=(12, 6), sticky="ew")

        for linha, campo in enumerate(campos, start=1):
            ctk.CTkLabel(
                secao,
                text=f"{ROTULOS_CAMPOS.get(campo, campo)}:",
                width=220,
                anchor="w",
                font=("Segoe UI", 12, "bold"),
                text_color=cores.AZUL_PRINCIPAL,
            ).grid(row=linha, column=0, padx=(14, 8), pady=5, sticky="nw")

            if campo == "observacoes":
                entrada = ctk.CTkTextbox(secao, height=90)
                entrada.insert("1.0", str(self.registro.get(campo) or ""))
            else:
                entrada = ctk.CTkEntry(secao, height=34)
                entrada.insert(0, str(self.registro.get(campo) or ""))
            entrada.grid(row=linha, column=1, padx=(0, 14), pady=5, sticky="ew")
            self.campos[campo] = entrada

    def salvar(self):
        dados = {}
        for campo, widget in self.campos.items():
            if isinstance(widget, ctk.CTkTextbox):
                dados[campo] = widget.get("1.0", "end").strip()
            else:
                dados[campo] = widget.get().strip()

        try:
            atualizado = atualizar_dados_pre_cadastro(self.registro.get("id"), dados)
        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Nao foi possivel salvar o pre-cadastro.\n\nErro: {erro}",
                parent=self,
            )
            return

        if not atualizado:
            messagebox.showerror("SIGM", "Pre-cadastro nao encontrado.", parent=self)
            return

        messagebox.showinfo("SIGM", "Pre-cadastro atualizado com sucesso.", parent=self)
        if self.ao_salvar:
            self.ao_salvar(atualizado.get("id"))
        self.destroy()

    def botao(self, master, texto, comando, cor=None, hover=None, largura=130):
        return ctk.CTkButton(
            master,
            text=texto,
            width=largura,
            height=38,
            fg_color=cor or cores.AZUL_PRINCIPAL,
            hover_color=hover or cores.AZUL_ESCURO,
            font=("Segoe UI", 12, "bold"),
            command=comando,
        )
