from datetime import date

import customtkinter as ctk

from banco.database import conectar, interpretar_data_nascimento
from componentes.cabecalho_igreja import CabecalhoIgreja
from config import cores, fontes
from utils.formatadores import normalizar_texto_busca
from utils.janelas import configurar_janela_principal


MESES = [
    ("01", "Janeiro"),
    ("02", "Fevereiro"),
    ("03", "Marco"),
    ("04", "Abril"),
    ("05", "Maio"),
    ("06", "Junho"),
    ("07", "Julho"),
    ("08", "Agosto"),
    ("09", "Setembro"),
    ("10", "Outubro"),
    ("11", "Novembro"),
    ("12", "Dezembro"),
]


class Aniversariantes(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)

        self.membros = []
        self.termo_pesquisa = ctk.StringVar(value="")
        self.mes_atual = str(date.today().month).zfill(2)

        self.title("Aniversariantes - SIGM")
        configurar_janela_principal(self, 1040, 700, 880, 600, master)
        self.configure(fg_color=cores.FUNDO)

        self.criar_interface()
        self.carregar_membros()

    def criar_interface(self):
        ctk.CTkLabel(
            self,
            text="Aniversariantes",
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL,
        ).pack(pady=(22, 8))

        CabecalhoIgreja(self).pack(fill="x", padx=24, pady=(0, 12))

        filtros = ctk.CTkFrame(self, fg_color="transparent")
        filtros.pack(fill="x", padx=24, pady=(0, 10))
        filtros.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            filtros,
            text="Pesquisar:",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")
        entrada = ctk.CTkEntry(filtros, textvariable=self.termo_pesquisa, height=34)
        entrada.grid(row=0, column=1, sticky="ew")
        self.termo_pesquisa.trace_add("write", lambda *_args: self.renderizar())

        ctk.CTkLabel(
            filtros,
            text="Mes:",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=0, column=2, padx=(16, 8), sticky="w")
        self.combo_mes = ctk.CTkComboBox(
            filtros,
            values=[nome for _numero, nome in MESES],
            height=34,
            width=150,
            command=lambda _valor: self.renderizar(),
        )
        self.combo_mes.set(dict(MESES)[self.mes_atual])
        self.combo_mes.grid(row=0, column=3, sticky="e")

        self.frame_resumo = ctk.CTkFrame(self, fg_color=cores.BRANCO, corner_radius=8)
        self.frame_resumo.pack(fill="x", padx=24, pady=(0, 10))

        self.label_hoje = self.label_resumo(self.frame_resumo, "Hoje: 0")
        self.label_hoje.pack(side="left", padx=14, pady=12)
        self.label_mes = self.label_resumo(self.frame_resumo, "Mes: 0")
        self.label_mes.pack(side="left", padx=14, pady=12)

        self.frame_lista = ctk.CTkScrollableFrame(self, corner_radius=8)
        self.frame_lista.pack(fill="both", expand=True, padx=24, pady=(0, 12))

        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.pack(fill="x", padx=24, pady=(0, 18))
        self.botao(rodape, "ATUALIZAR", self.carregar_membros).pack(side="left", padx=5)
        self.botao(rodape, "FECHAR", self.destroy, cor=cores.CINZA, hover="#444444").pack(side="right", padx=5)

    def label_resumo(self, master, texto):
        return ctk.CTkLabel(
            master,
            text=texto,
            font=("Segoe UI", 14, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        )

    def carregar_membros(self):
        conexao = conectar()
        cursor = conexao.cursor()
        cursor.execute("""
            SELECT id, nome, data_nascimento, telefone, celular
            FROM membros
            WHERE data_nascimento IS NOT NULL
            AND TRIM(data_nascimento) <> ''
        """)
        self.membros = []
        for id_membro, nome, data_nascimento, telefone, celular in cursor.fetchall():
            nascimento = interpretar_data_nascimento(data_nascimento)
            if nascimento is None:
                continue
            self.membros.append({
                "id": id_membro,
                "nome": nome or "",
                "data_nascimento": data_nascimento or "",
                "nascimento": nascimento,
                "telefone": telefone or "",
                "celular": celular or "",
            })
        conexao.close()
        self.renderizar()

    def mes_selecionado(self):
        nome = self.combo_mes.get()
        for numero, descricao in MESES:
            if descricao == nome:
                return numero
        return self.mes_atual

    def membros_filtrados(self):
        mes = int(self.mes_selecionado())
        termo = normalizar_texto_busca(self.termo_pesquisa.get())
        membros = [
            membro for membro in self.membros
            if membro["nascimento"].month == mes
        ]
        if termo:
            membros = [
                membro for membro in membros
                if termo in normalizar_texto_busca(
                    f"{membro['nome']} {membro['telefone']} {membro['celular']}"
                )
            ]
        membros.sort(key=lambda item: (item["nascimento"].day, item["nome"]))
        return membros

    def renderizar(self):
        for widget in self.frame_lista.winfo_children():
            widget.destroy()

        hoje = date.today()
        total_hoje = sum(
            1 for membro in self.membros
            if membro["nascimento"].day == hoje.day and membro["nascimento"].month == hoje.month
        )
        membros = self.membros_filtrados()
        self.label_hoje.configure(text=f"Aniversariantes de hoje: {total_hoje}")
        self.label_mes.configure(text=f"Aniversariantes do mes: {len(membros)}")

        if not membros:
            ctk.CTkLabel(
                self.frame_lista,
                text="Nenhum aniversariante encontrado.",
                font=fontes.TEXTO,
                text_color=cores.CINZA,
            ).pack(pady=28)
            return

        for membro in membros:
            self.criar_linha(membro).pack(fill="x", padx=10, pady=5)

    def criar_linha(self, membro):
        linha = ctk.CTkFrame(self.frame_lista, fg_color=cores.BRANCO, corner_radius=8)
        linha.grid_columnconfigure(0, weight=1)
        nascimento = membro["nascimento"]
        idade = self.idade(nascimento)
        contato = membro["celular"] or membro["telefone"] or "-"

        ctk.CTkLabel(
            linha,
            text=membro["nome"] or "-",
            font=("Segoe UI", 13, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
            anchor="w",
        ).grid(row=0, column=0, padx=12, pady=(9, 0), sticky="ew")
        ctk.CTkLabel(
            linha,
            text=f"{nascimento.strftime('%d/%m/%Y')} | {idade} anos | {contato}",
            font=("Segoe UI", 12),
            text_color=cores.PRETO,
            anchor="w",
        ).grid(row=1, column=0, padx=12, pady=(0, 9), sticky="ew")
        return linha

    @staticmethod
    def idade(nascimento):
        hoje = date.today()
        anos = hoje.year - nascimento.year
        if (hoje.month, hoje.day) < (nascimento.month, nascimento.day):
            anos -= 1
        return max(anos, 0)

    def botao(self, master, texto, comando, cor=None, hover=None):
        return ctk.CTkButton(
            master,
            text=texto,
            width=130,
            height=36,
            fg_color=cor or cores.AZUL_PRINCIPAL,
            hover_color=hover or cores.AZUL_ESCURO,
            font=("Segoe UI", 12, "bold"),
            command=comando,
        )
