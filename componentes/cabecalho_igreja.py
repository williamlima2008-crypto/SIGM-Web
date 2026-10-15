from pathlib import Path

import customtkinter as ctk

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None

from banco.database import buscar_configuracoes_igreja
from config import cores
from utils.caminhos import base_dados, caminho_recurso


LOGO_PADRAO = caminho_recurso("assets", "logo", "logo.png")


class CabecalhoIgreja(ctk.CTkFrame):

    def __init__(self, master, tamanho="pequeno"):
        super().__init__(
            master,
            fg_color=cores.BRANCO,
            corner_radius=8,
            border_width=1,
            border_color="#D8E3F2",
        )

        self.tamanho = tamanho
        self.logo_tk = None
        self.logo_label = None
        self.nome_label = None
        self.dados_label = None

        if tamanho == "grande":
            self.tamanho_logo = (92, 92)
            self.altura_nome = 34
            self.altura_dados = 76
        elif tamanho == "compacto":
            self.tamanho_logo = (42, 42)
            self.altura_nome = None
            self.altura_dados = None
        else:
            self.tamanho_logo = (58, 58)
            self.altura_nome = None
            self.altura_dados = None
        self.criar_interface()
        self.atualizar()

    def criar_interface(self):
        self.grid_columnconfigure(1, weight=1)
        padding_vertical = 6 if self.tamanho == "compacto" else 12
        padding_horizontal = 10 if self.tamanho == "compacto" else 14

        self.logo_label = ctk.CTkLabel(
            self,
            text="SIGM",
            width=self.tamanho_logo[0],
            height=self.tamanho_logo[1],
            font=("Segoe UI", 15, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
            fg_color=cores.FUNDO,
            corner_radius=8,
        )
        self.logo_label.grid(row=0, column=0, padx=padding_horizontal, pady=padding_vertical, sticky="w")

        sticky_textos = "nsew" if self.tamanho == "grande" else "ew"
        textos = ctk.CTkFrame(self, fg_color="transparent")
        textos.grid(row=0, column=1, padx=(0, padding_horizontal), pady=padding_vertical, sticky=sticky_textos)
        textos.grid_columnconfigure(0, weight=1)
        if self.tamanho == "grande":
            textos.bind("<Configure>", self.ajustar_wraplength)

        if self.tamanho == "grande":
            fonte_nome = ("Segoe UI", 20, "bold")
            fonte_dados = ("Segoe UI", 13)
            wraplength = 920
        elif self.tamanho == "compacto":
            fonte_nome = ("Segoe UI", 13, "bold")
            fonte_dados = ("Segoe UI", 10)
            wraplength = 760
        else:
            fonte_nome = ("Segoe UI", 15, "bold")
            fonte_dados = ("Segoe UI", 11)
            wraplength = 720

        opcoes_nome = {}
        if self.altura_nome:
            opcoes_nome["height"] = self.altura_nome

        self.nome_label = ctk.CTkLabel(
            textos,
            text="Igreja nao cadastrada",
            font=fonte_nome,
            text_color=cores.AZUL_PRINCIPAL,
            anchor="w",
            **opcoes_nome,
        )
        self.nome_label.grid(row=0, column=0, sticky="ew")

        opcoes_dados = {}
        if self.altura_dados:
            opcoes_dados["height"] = self.altura_dados

        self.dados_label = ctk.CTkLabel(
            textos,
            text="Configure os dados da igreja em Configuracoes.",
            font=fonte_dados,
            text_color=cores.CINZA,
            anchor="w",
            justify="left",
            wraplength=wraplength,
            **opcoes_dados,
        )
        self.dados_label.grid(row=1, column=0, pady=(2 if self.tamanho == "compacto" else 4, 0), sticky="ew")

    def ajustar_wraplength(self, event=None):
        if not self.dados_label:
            return

        largura = event.width if event else self.winfo_width()
        self.dados_label.configure(wraplength=max(largura - 4, 220))

    def atualizar(self):
        dados = buscar_configuracoes_igreja()
        nome = dados.get("nome_igreja") or "Igreja nao cadastrada"
        detalhes = self.montar_detalhes(dados)

        self.nome_label.configure(text=nome)
        self.dados_label.configure(
            text=detalhes or "Configure os dados da igreja em Configuracoes."
        )
        self.atualizar_logo(dados.get("logotipo"))

    def montar_detalhes(self, dados):
        linha_ministerio = " | ".join(
            parte
            for parte in (
                dados.get("ministerio"),
                dados.get("convencao"),
                f"Setor {dados.get('setor')}" if dados.get("setor") else "",
                f"Sede: {dados.get('congregacao_sede')}"
                if dados.get("congregacao_sede")
                else "",
            )
            if parte
        )
        local = " - ".join(
            parte
            for parte in (dados.get("cidade"), dados.get("estado"))
            if parte
        )
        contatos = " | ".join(
            parte
            for parte in (
                dados.get("telefone"),
                dados.get("email"),
                dados.get("site"),
            )
            if parte
        )
        linha_local = " | ".join(parte for parte in (local, contatos) if parte)
        linha_lideranca = " | ".join(
            parte
            for parte in (
                f"Pastor Presidente: {dados.get('pastor_presidente')}"
                if dados.get("pastor_presidente")
                else "",
                f"Pastor Setorial: {dados.get('pastor_setorial')}"
                if dados.get("pastor_setorial")
                else "",
                f"Dirigente: {dados.get('congregacao_local_dirigente')}"
                if dados.get("congregacao_local_dirigente")
                else "",
            )
            if parte
        )

        return "\n".join(
            parte
            for parte in (linha_ministerio, linha_local, linha_lideranca)
            if parte
        )

    def atualizar_logo(self, caminho_logo):
        caminho = self.obter_caminho_logo(caminho_logo)

        if not caminho:
            self.logo_tk = None
            self.logo_label.configure(image=None, text="SIGM")
            return

        try:
            imagem = self.criar_imagem(caminho)
            self.logo_tk = ctk.CTkImage(
                light_image=imagem,
                dark_image=imagem,
                size=self.tamanho_logo,
            )
            self.logo_label.configure(image=self.logo_tk, text="")
        except Exception:
            self.logo_tk = None
            self.logo_label.configure(image=None, text="SIGM")

    def obter_caminho_logo(self, caminho_logo):
        candidatos = []
        if caminho_logo:
            caminho = Path(str(caminho_logo)).expanduser()
            if not caminho.is_absolute():
                caminho = base_dados() / caminho
            candidatos.append(caminho)

        candidatos.append(LOGO_PADRAO)

        for candidato in candidatos:
            try:
                if candidato.exists() and candidato.is_file() and candidato.stat().st_size > 0:
                    return candidato
            except OSError:
                pass

        return None

    def criar_imagem(self, caminho):
        if Image is None:
            raise RuntimeError("Pillow indisponivel")

        largura, altura = self.tamanho_logo

        with Image.open(caminho) as imagem:
            imagem = ImageOps.exif_transpose(imagem)
            imagem = imagem.convert("RGBA")
            imagem = ImageOps.contain(imagem, self.tamanho_logo)

            fundo = Image.new("RGBA", self.tamanho_logo, (255, 255, 255, 0))
            x = (largura - imagem.width) // 2
            y = (altura - imagem.height) // 2
            fundo.paste(imagem, (x, y), imagem)

        return fundo


def atualizar_cabecalhos_igreja(janela):
    raiz = janela
    while getattr(raiz, "master", None) is not None:
        raiz = raiz.master

    def percorrer(widget):
        if isinstance(widget, CabecalhoIgreja):
            widget.atualizar()

        for filho in widget.winfo_children():
            percorrer(filho)

    percorrer(raiz)
