import re
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None

from banco.database import garantir_coluna_foto_membro
from config import cores
from documentos.catalogo_documentos import (
    DOCUMENTO_FICHA_CADASTRAL,
    obter_documento_oficial,
)
from documentos.datas import separar_data_documento
from documentos.integrador_documentos import montar_dados_documento
from telas.documentos.base_editor_documento import BaseEditorDocumento


GRUPOS_FICHA_CADASTRAL = [
    ("Dados Pessoais", [
    ("nome_membro", "Nome do membro"),
    ("rg", "RG"),
        ("orgao_emissor", "Orgao emissor"),
    ("cpf", "CPF"),
        ("data_nascimento", "Data de nascimento"),
        ("cidade_nascimento", "Cidade de nascimento"),
        ("estado_nascimento", "Estado de nascimento"),
        ("estado_civil", "Estado civil"),
        ("nome_conjuge", "Nome do conjuge"),
        ("data_nascimento_conjuge", "Data de nascimento do conjuge"),
        ("profissao", "Profissao"),
        ("nome_pai", "Nome do pai"),
        ("nome_mae", "Nome da mae"),
    ("status", "Status"),
    ]),
    ("Dados Ministeriais", [
        ("congregacao", "Congregacao"),
        ("dirigente", "Dirigente"),
        ("batismo_aguas", "Batismo nas aguas"),
        ("igreja_local_batismo_aguas", "Igreja/Local do batismo nas aguas"),
        ("data_batismo_espirito_santo", "Data do batismo no Espirito Santo"),
        ("igreja_local_batismo_espirito_santo", "Igreja/Local do batismo no Espirito Santo"),
        ("ministerio", "Ministerio"),
        ("cargo", "Cargo"),
    ]),
    ("Endereco", [
        ("endereco", "Endereco"),
        ("numero", "Numero"),
        ("bairro", "Bairro"),
        ("cidade", "Cidade"),
        ("estado", "Estado"),
        ("cep", "CEP"),
    ]),
    ("Contato", [
        ("telefone", "Telefone"),
        ("celular", "Celular"),
        ("email", "E-mail"),
    ]),
]


class EditorFichaCadastral(BaseEditorDocumento):
    titulo_janela = "Editor da Ficha Cadastral - SIGM"
    chaves_foto = ("foto", "foto_membro", "caminho_foto", "foto_path")
    tamanho_previa_foto = (140, 170)

    def __init__(self, master, id_membro):
        documento = obter_documento_oficial(DOCUMENTO_FICHA_CADASTRAL)
        dados_iniciais = self.montar_dados_iniciais(id_membro)
        self.caminho_foto_selecionada = ""
        self.imagem_foto = None
        self.label_foto = None

        super().__init__(master, id_membro, documento, dados_iniciais)

    def montar_dados_iniciais(self, id_membro):
        dados = montar_dados_documento(id_membro)
        dados["ministerio"] = dados.get("ministerio_membro", "")
        dados.setdefault("cep", "")
        return dados

    def obter_dados_iniciais(self):
        return self.montar_dados_iniciais(self.id_membro)

    def criar_campos(self):
        self.criar_quadro_foto()

        for titulo, campos in GRUPOS_FICHA_CADASTRAL:
            secao = self.criar_secao(titulo)

            for chave, rotulo in campos:
                entrada = self.criar_campo_texto(chave, rotulo, parent=secao)
                self.vincular_mascara(chave, entrada)

        secao_observacoes = self.criar_secao("Observacoes")
        self.criar_campo_multilinha(
            "observacoes",
            "Observacoes",
            altura=130,
            parent=secao_observacoes,
        )

    def criar_quadro_foto(self):
        quadro = ctk.CTkFrame(self.frame_formulario, fg_color=cores.BRANCO, corner_radius=8)
        quadro.pack(fill="x", padx=14, pady=(8, 12))
        quadro.grid_columnconfigure(1, weight=1)

        moldura = ctk.CTkFrame(quadro, fg_color="#F4F4F4", corner_radius=8)
        moldura.grid(row=0, column=0, padx=14, pady=14, sticky="nw")

        self.label_foto = ctk.CTkLabel(
            moldura,
            text="Sem foto\ncadastrada",
            width=140,
            height=170,
            text_color=cores.CINZA,
            font=("Segoe UI", 13, "bold"),
        )
        self.label_foto.pack(padx=8, pady=8)

        ctk.CTkLabel(
            quadro,
            text="Foto do membro",
            anchor="w",
            font=("Segoe UI", 15, "bold"),
            text_color=cores.AZUL_PRINCIPAL,
        ).grid(row=0, column=1, padx=(8, 14), pady=(18, 2), sticky="new")

        ctk.CTkLabel(
            quadro,
            text="Use uma foto apenas para esta Ficha Cadastral ou mantenha a foto ja cadastrada.",
            anchor="w",
            wraplength=560,
            font=("Segoe UI", 12),
            text_color=cores.CINZA,
        ).grid(row=0, column=1, padx=(8, 14), pady=(48, 14), sticky="new")

        ctk.CTkButton(
            quadro,
            text="Selecionar Foto",
            width=150,
            height=34,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            command=self.selecionar_foto,
        ).grid(row=0, column=1, padx=(8, 14), pady=(96, 14), sticky="nw")

    def apos_carregar_dados(self):
        for chave in self.campos:
            self.aplicar_mascara(chave)

        self.atualizar_foto()

    def vincular_mascara(self, chave, entrada):
        if chave not in self.mascaras():
            return

        entrada.bind(
            "<KeyRelease>",
            lambda _evento, nome_campo=chave: self.aplicar_mascara(nome_campo),
        )

    def aplicar_mascara(self, chave):
        mascaras = self.mascaras()
        if chave not in mascaras:
            return

        campo = self.campos.get(chave)
        if campo is None:
            return

        valor = campo.get()
        novo_valor = mascaras[chave](valor)

        if valor == novo_valor:
            return

        campo.delete(0, "end")
        campo.insert(0, novo_valor)

    def mascaras(self):
        return {
            "cpf": self.mascara_cpf,
            "rg": self.mascara_rg,
            "telefone": self.mascara_telefone,
            "celular": self.mascara_celular,
            "cep": self.mascara_cep,
            "data_nascimento": self.mascara_data,
            "data_nascimento_conjuge": self.mascara_data,
            "batismo_aguas": self.mascara_data,
            "data_batismo_espirito_santo": self.mascara_data,
        }

    def obter_caminho_foto_atual(self):
        if self.caminho_foto_selecionada:
            return self.caminho_foto_selecionada

        caminho_foto = ""
        for chave in self.chaves_foto:
            if self.dados_iniciais.get(chave):
                caminho_foto = self.dados_iniciais[chave]
                break

        return caminho_foto

    def criar_imagem_previa(self, caminho):
        if Image is None:
            return None

        largura_previa, altura_previa = self.tamanho_previa_foto

        with Image.open(caminho) as imagem:
            imagem = ImageOps.exif_transpose(imagem)
            imagem = imagem.convert("RGBA")
            imagem.thumbnail((largura_previa, altura_previa))

            previa = Image.new("RGBA", self.tamanho_previa_foto, (244, 244, 244, 255))
            x = (largura_previa - imagem.width) // 2
            y = (altura_previa - imagem.height) // 2
            previa.paste(imagem, (x, y), imagem)

        return previa

    def selecionar_foto(self):
        caminho = filedialog.askopenfilename(
            parent=self,
            title="Selecionar Foto",
            filetypes=[
                ("Imagens PNG/JPG", "*.png *.jpg *.jpeg"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
            ],
        )

        if not caminho:
            return

        if Path(caminho).suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            messagebox.showwarning("SIGM", "Selecione uma imagem PNG, JPG ou JPEG.")
            return

        self.caminho_foto_selecionada = caminho
        self.atualizar_foto()

    def atualizar_foto(self):
        if self.label_foto is None:
            return

        caminho_foto = self.obter_caminho_foto_atual()

        if Image is None or not caminho_foto:
            self.label_foto.configure(image=None, text="Sem foto\ncadastrada")
            self.imagem_foto = None
            return

        caminho = Path(caminho_foto)
        if not caminho.exists():
            self.label_foto.configure(image=None, text="Foto nao\nencontrada")
            self.imagem_foto = None
            return

        try:
            imagem = self.criar_imagem_previa(caminho)
            if imagem is None:
                raise ValueError("Pillow indisponivel")

            self.imagem_foto = ctk.CTkImage(
                light_image=imagem,
                dark_image=imagem,
                size=self.tamanho_previa_foto,
            )
            self.label_foto.configure(image=self.imagem_foto, text="")
        except Exception:
            self.label_foto.configure(image=None, text="Foto nao\ncarregada")
            self.imagem_foto = None

    def coletar_dados(self):
        dados = super().coletar_dados()

        cidade_nascimento = str(dados.get("cidade_nascimento", "") or "").strip()
        estado_nascimento = str(dados.get("estado_nascimento", "") or "").strip()
        if cidade_nascimento and estado_nascimento:
            dados["cidade_estado_nascimento"] = f"{cidade_nascimento} - {estado_nascimento}"
        else:
            dados["cidade_estado_nascimento"] = cidade_nascimento or estado_nascimento

        dados["pai"] = dados.get("nome_pai", "")
        dados["mae"] = dados.get("nome_mae", "")
        dados["conjuge"] = dados.get("nome_conjuge", "")
        dados["batismo_espirito_santo"] = dados.get(
            "data_batismo_espirito_santo",
            "",
        )
        dia, mes, ano = separar_data_documento(dados["batismo_espirito_santo"])
        dados["batismo_espirito_santo_dia"] = dia
        dados["batismo_espirito_santo_mes"] = mes
        dados["batismo_espirito_santo_ano"] = ano

        if self.caminho_foto_selecionada:
            for chave in self.chaves_foto:
                dados[chave] = self.caminho_foto_selecionada

        return dados

    def campos_editaveis_para_cadastro(self, dados):
        dados_cadastro = super().campos_editaveis_para_cadastro(dados)

        if self.caminho_foto_selecionada:
            coluna_foto = garantir_coluna_foto_membro()
            dados_cadastro[coluna_foto] = self.caminho_foto_selecionada

        return dados_cadastro

    def restaurar_dados(self):
        self.caminho_foto_selecionada = ""
        super().restaurar_dados()

    def validar_antes_de_gerar(self):
        dados = self.coletar_dados()
        erros = []

        if not dados.get("nome_membro"):
            erros.append("Informe o nome do membro.")

        self.validar_data(dados, "data_nascimento", "Data de nascimento", erros)
        self.validar_data(
            dados,
            "data_nascimento_conjuge",
            "Data de nascimento do conjuge",
            erros,
        )
        self.validar_data(dados, "batismo_aguas", "Batismo nas aguas", erros)
        self.validar_data(
            dados,
            "data_batismo_espirito_santo",
            "Batismo no Espirito Santo",
            erros,
        )
        self.validar_cpf(dados, erros)
        self.validar_quantidade_digitos(dados, "rg", "RG", 5, 9, erros)
        self.validar_quantidade_digitos(dados, "telefone", "Telefone", 10, 11, erros)
        self.validar_quantidade_digitos(dados, "celular", "Celular", 10, 11, erros)
        self.validar_quantidade_digitos(dados, "cep", "CEP", 8, 8, erros)
        self.validar_email(dados, erros)

        if erros:
            messagebox.showwarning("SIGM", "\n".join(erros))
            return False

        return True

    def validar_data(self, dados, chave, rotulo, erros):
        valor = dados.get(chave, "")
        if not valor:
            return

        if len(self.digitos(valor)) != 8:
            erros.append(f"{rotulo} deve estar no formato DD/MM/AAAA.")
            return

        try:
            datetime.strptime(valor, "%d/%m/%Y")
        except ValueError:
            erros.append(f"{rotulo} invalida.")

    def validar_cpf(self, dados, erros):
        cpf = self.digitos(dados.get("cpf", ""))
        if not cpf:
            return

        if len(cpf) != 11 or not self.cpf_valido(cpf):
            erros.append("CPF invalido.")

    def validar_quantidade_digitos(
        self,
        dados,
        chave,
        rotulo,
        minimo,
        maximo,
        erros,
    ):
        valor = dados.get(chave, "")
        if not valor:
            return

        quantidade = len(self.digitos(valor))
        if quantidade < minimo or quantidade > maximo:
            if minimo == maximo:
                erros.append(f"{rotulo} deve ter {minimo} digitos.")
            else:
                erros.append(f"{rotulo} deve ter entre {minimo} e {maximo} digitos.")

    def validar_email(self, dados, erros):
        email = dados.get("email", "")
        if not email:
            return

        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            erros.append("E-mail invalido.")

    @staticmethod
    def digitos(valor):
        return re.sub(r"\D", "", str(valor or ""))

    @classmethod
    def mascara_cpf(cls, valor):
        digitos = cls.digitos(valor)[:11]
        if len(digitos) <= 3:
            return digitos
        if len(digitos) <= 6:
            return f"{digitos[:3]}.{digitos[3:]}"
        if len(digitos) <= 9:
            return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:]}"
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"

    @classmethod
    def mascara_rg(cls, valor):
        digitos = cls.digitos(valor)[:9]
        if len(digitos) <= 2:
            return digitos
        if len(digitos) <= 5:
            return f"{digitos[:2]}.{digitos[2:]}"
        if len(digitos) <= 8:
            return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:]}"
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}-{digitos[8:]}"

    @classmethod
    def mascara_telefone(cls, valor):
        digitos = cls.digitos(valor)[:10]
        if len(digitos) <= 2:
            return digitos
        if len(digitos) <= 6:
            return f"({digitos[:2]}) {digitos[2:]}"
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"

    @classmethod
    def mascara_celular(cls, valor):
        digitos = cls.digitos(valor)[:11]
        if len(digitos) <= 2:
            return digitos
        if len(digitos) <= 7:
            return f"({digitos[:2]}) {digitos[2:]}"
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"

    @classmethod
    def mascara_cep(cls, valor):
        digitos = cls.digitos(valor)[:8]
        if len(digitos) <= 5:
            return digitos
        return f"{digitos[:5]}-{digitos[5:]}"

    @classmethod
    def mascara_data(cls, valor):
        digitos = cls.digitos(valor)[:8]
        if len(digitos) <= 2:
            return digitos
        if len(digitos) <= 4:
            return f"{digitos[:2]}/{digitos[2:]}"
        return f"{digitos[:2]}/{digitos[2:4]}/{digitos[4:]}"

    @staticmethod
    def cpf_valido(cpf):
        if len(cpf) != 11 or cpf == cpf[0] * 11:
            return False

        soma = sum(int(cpf[indice]) * (10 - indice) for indice in range(9))
        digito_1 = (soma * 10) % 11
        if digito_1 == 10:
            digito_1 = 0

        soma = sum(int(cpf[indice]) * (11 - indice) for indice in range(10))
        digito_2 = (soma * 10) % 11
        if digito_2 == 10:
            digito_2 = 0

        return digito_1 == int(cpf[9]) and digito_2 == int(cpf[10])
