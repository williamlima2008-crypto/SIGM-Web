"""
==========================================================
SIGM - Sistema de Gestão de Membros

Arquivo: cadastro_membro.py
Descrição: Cadastro e edição de membro (uma unica tela para os dois
modos), incluindo dados pessoais, contato, endereço, dados da igreja,
observações e foto do membro.

Desenvolvido por:
William Lima

"Servindo à Igreja com organização e excelência."
==========================================================
"""


import shutil
import unicodedata
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None

from config import cores, fontes
from banco.database import (
    atualizar_membro,
    buscar_data_funcao_membro,
    buscar_membro_por_id,
    cadastrar_membro,
    conectar,
    garantir_coluna_foto_membro,
)
from componentes.cabecalho_igreja import CabecalhoIgreja
from documentos.datas import separar_data_documento
from documentos.integrador_documentos import (
    EXTENSOES_FOTO_MEMBRO,
    PASTA_FOTOS_MEMBROS,
    buscar_caminho_foto_membro,
)
from utils.auditoria import registrar_acao
from utils.janelas import configurar_janela_principal


FUNCOES_ATUAIS = [
    "Nenhuma",
    "Cooperador",
    "Diácono",
    "Presbítero",
    "Evangelista",
    "Pastor",
]
FUNCOES_NORMALIZADAS = {
    "": "Nenhuma",
    "nenhuma": "Nenhuma",
    "cooperador": "Cooperador",
    "diacono": "Diácono",
    "diácono": "Diácono",
    "presbitero": "Presbítero",
    "presbítero": "Presbítero",
    "evangelista": "Evangelista",
    "pastor": "Pastor",
}


class CadastroMembro(ctk.CTkToplevel):

    def __init__(self, master, id_membro=None, ao_salvar=None):
        super().__init__(master)

        self.id_membro = id_membro
        self.ao_salvar = ao_salvar
        self.modo_edicao = id_membro is not None

        # Estado da foto do membro: caminho recem-selecionado nesta sessao
        # (ainda nao salvo) e caminho ja cadastrado anteriormente (se
        # estiver editando um membro que ja possui foto).
        self.caminho_foto_selecionada = ""
        self.caminho_foto_existente = (
            buscar_caminho_foto_membro(self.id_membro) if self.modo_edicao else ""
        )
        self.imagem_foto = None
        self.label_foto = None

        self.title("Cadastro de Membro - SIGM")
        configurar_janela_principal(self, 1080, 760, 980, 680, master)
        self.configure(fg_color=cores.FUNDO)

        self.criar_interface()

        if self.modo_edicao:
            self.carregar_dados_membro()

        self.atualizar_previa_foto()
        self.assinatura_inicial = self.assinar_dados()
        self.protocol("WM_DELETE_WINDOW", self.cancelar)

    def criar_interface(self):
        titulo_texto = "Editar Membro" if self.modo_edicao else "Cadastro de Membros"
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            self,
            text=titulo_texto,
            font=fontes.TITULO,
            text_color=cores.AZUL_PRINCIPAL
        ).grid(row=0, column=0, padx=30, pady=(25, 15), sticky="ew")

        self.cabecalho_igreja = CabecalhoIgreja(self)
        self.cabecalho_igreja.grid(row=1, column=0, padx=30, pady=(0, 12), sticky="ew")

        abas = ctk.CTkTabview(self, width=900, height=360)
        abas.grid(row=2, column=0, padx=30, pady=10, sticky="nsew")

        aba_pessoal = self.criar_aba_rolavel(abas, "Dados Pessoais")
        aba_contato = self.criar_aba_rolavel(abas, "Contato")
        aba_endereco = self.criar_aba_rolavel(abas, "Endereço")
        aba_igreja = self.criar_aba_rolavel(abas, "Dados da Igreja")
        aba_obs = self.criar_aba_rolavel(abas, "Observações")

        self.criar_quadro_foto(aba_pessoal)

        self.campo(aba_pessoal, "nome", "Nome completo")
        self.campo(aba_pessoal, "rg", "RG")
        self.campo(aba_pessoal, "orgao", "Órgão emissor")
        self.campo(aba_pessoal, "cpf", "CPF")
        self.campo(aba_pessoal, "nascimento", "Data de nascimento")
        self.campo(aba_pessoal, "cidade_nascimento", "Cidade de nascimento")
        self.campo(aba_pessoal, "estado_nascimento", "Estado / UF de nascimento")
        self.campo(aba_pessoal, "estado_civil", "Estado civil")
        self.campo(aba_pessoal, "nome_conjuge", "Nome do conjuge")
        self.campo(
            aba_pessoal, "data_nascimento_conjuge",
            "Data de nascimento do conjuge (DD/MM/AAAA)",
        ).bind("<KeyRelease>", self.aplicar_mascara_data_nascimento_conjuge)
        self.campo(aba_pessoal, "profissao", "Profissão")
        self.campo(aba_pessoal, "nome_pai", "Nome do pai")
        self.campo(aba_pessoal, "nome_mae", "Nome da mae")
        self.campo(aba_pessoal, "grau_instrucao", "Grau de instrucao escolar")

        self.campo(aba_contato, "telefone", "Telefone")
        self.campo(aba_contato, "celular", "Celular / WhatsApp")
        self.campo(aba_contato, "email", "E-mail")

        self.campo(aba_endereco, "endereco", "Rua / Logradouro")
        self.campo(aba_endereco, "numero", "Número")
        self.campo(aba_endereco, "bairro", "Bairro")
        self.campo(aba_endereco, "cidade", "Cidade")
        self.campo(aba_endereco, "estado", "Estado / UF")
        self.campo(aba_endereco, "cep", "CEP").bind("<KeyRelease>", self.aplicar_mascara_cep)

        self.campo(aba_igreja, "batismo_aguas", "Data do batismo nas águas (DD/MM/AAAA)")
        self.campo(
            aba_igreja, "data_batismo_espirito_santo",
            "Data do batismo no Espirito Santo (DD/MM/AAAA)",
        ).bind("<KeyRelease>", self.aplicar_mascara_data_batismo_espirito_santo)
        self.campo(aba_igreja, "ministerio", "Ministério")

        ctk.CTkLabel(
            aba_igreja, text="Cargo / Função atual", anchor="w",
            font=("Segoe UI", 12, "bold"), text_color=cores.AZUL_PRINCIPAL,
        ).pack(fill="x", padx=30, pady=(8, 0))
        self.cargo = ctk.CTkComboBox(aba_igreja, values=FUNCOES_ATUAIS, height=35)
        self.cargo.set("Nenhuma")
        self.cargo.pack(fill="x", padx=30, pady=(2, 6))

        self.campo(
            aba_igreja, "data_funcao", "Data da função atual (DD/MM/AAAA)",
        ).bind("<KeyRelease>", self.aplicar_mascara_data_funcao)
        self.campo(aba_igreja, "curso_teologico", "Curso teologico")

        ctk.CTkLabel(
            aba_igreja, text="Status do membro", anchor="w",
            font=("Segoe UI", 12, "bold"), text_color=cores.AZUL_PRINCIPAL,
        ).pack(fill="x", padx=30, pady=(8, 0))
        self.status = ctk.CTkComboBox(
            aba_igreja,
            values=["Membro", "Congregado", "Visitante", "Em discipulado", "Inativo"],
            height=35,
        )
        self.status.set("Membro")
        self.status.pack(fill="x", padx=30, pady=(2, 6))

        ctk.CTkLabel(
            aba_obs, text="Observações", anchor="w",
            font=("Segoe UI", 12, "bold"), text_color=cores.AZUL_PRINCIPAL,
        ).pack(fill="x", padx=30, pady=(15, 0))
        self.observacoes = ctk.CTkTextbox(aba_obs, height=230)
        self.observacoes.pack(fill="both", expand=True, padx=30, pady=(4, 20))

        frame_botoes = ctk.CTkFrame(self, fg_color="transparent")
        frame_botoes.grid(row=3, column=0, padx=30, pady=(10, 25), sticky="ew")

        ctk.CTkButton(
            frame_botoes,
            text="SALVAR",
            width=260,
            height=45,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            font=fontes.BOTAO,
            command=self.salvar
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            frame_botoes,
            text="CANCELAR",
            width=150,
            height=45,
            fg_color=cores.CINZA,
            hover_color="#444444",
            font=fontes.BOTAO,
            command=self.cancelar,
        ).pack(side="left")

        self.nome.focus_set()
        self.bind("<Control-s>", lambda event: self.salvar())
        self.bind("<Escape>", lambda event: self.cancelar())

    def criar_aba_rolavel(self, abas, nome):
        aba = abas.add(nome)
        frame = ctk.CTkScrollableFrame(aba, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        return frame

    def campo(self, aba, atributo, rotulo, **kwargs):
        """
        Cria um rotulo FIXO (sempre visivel, mesmo com o campo ja
        preenchido) acima de um CTkEntry. Corrige o problema em que o
        nome do campo era apenas o placeholder_text: como todo
        placeholder desaparece assim que o campo recebe um valor, os
        campos ficavam sem identificacao depois de preenchidos (por
        exemplo, apos sincronizar dados vindos do SIGM Online).

        O widget criado e salvo em self.<atributo>, exatamente como
        antes, para nao quebrar o restante do arquivo.
        """
        ctk.CTkLabel(
            aba, text=rotulo, anchor="w",
            font=("Segoe UI", 12, "bold"), text_color=cores.AZUL_PRINCIPAL,
        ).pack(fill="x", padx=30, pady=(8, 0))

        entrada = ctk.CTkEntry(aba, height=35, **kwargs)
        entrada.pack(fill="x", padx=30, pady=(2, 6))
        setattr(self, atributo, entrada)
        return entrada

    def criar_quadro_foto(self, aba_pessoal):
        """
        Secao de foto do membro, disponivel tanto no cadastro novo
        quanto na edicao (antes so existia no editor do documento
        Ficha Cadastral, nunca no cadastro do membro em si).
        """
        quadro = ctk.CTkFrame(aba_pessoal, fg_color=cores.BRANCO, corner_radius=8)
        quadro.pack(fill="x", padx=30, pady=(4, 14))
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
            text="Selecione uma foto para o cadastro do membro (PNG ou JPG).",
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

        self.caminho_foto_selecionada = caminho
        self.atualizar_previa_foto()

    def atualizar_previa_foto(self):
        if self.label_foto is None:
            return

        caminho_foto = self.caminho_foto_selecionada or self.caminho_foto_existente

        if Image is None or not caminho_foto or not Path(caminho_foto).exists():
            self.label_foto.configure(image=None, text="Sem foto\ncadastrada")
            self.imagem_foto = None
            return

        try:
            tamanho = (140, 170)
            with Image.open(caminho_foto) as imagem_original:
                imagem_original = ImageOps.exif_transpose(imagem_original)
                imagem_original = imagem_original.convert("RGBA")
                imagem_original.thumbnail(tamanho)

                previa = Image.new("RGBA", tamanho, (244, 244, 244, 255))
                x = (tamanho[0] - imagem_original.width) // 2
                y = (tamanho[1] - imagem_original.height) // 2
                previa.paste(imagem_original, (x, y), imagem_original)

            self.imagem_foto = ctk.CTkImage(light_image=previa, dark_image=previa, size=tamanho)
            self.label_foto.configure(image=self.imagem_foto, text="")
        except Exception:
            self.label_foto.configure(image=None, text="Foto nao\ncarregada")
            self.imagem_foto = None

    def salvar_foto_membro(self, id_membro):
        """
        Copia a foto escolhida para a pasta de dados do sistema
        (fotos_membros/foto_<id>.<extensao>) e grava o caminho na
        coluna de foto do membro no banco. So e chamado quando uma
        nova foto foi de fato selecionada nesta sessao.
        """
        if not self.caminho_foto_selecionada:
            return

        try:
            extensao = Path(self.caminho_foto_selecionada).suffix.lower()
            if extensao not in EXTENSOES_FOTO_MEMBRO:
                extensao = ".jpg"

            PASTA_FOTOS_MEMBROS.mkdir(parents=True, exist_ok=True)

            # Remove fotos antigas do mesmo membro para nao acumular arquivos orfaos
            for arquivo_antigo in PASTA_FOTOS_MEMBROS.glob(f"foto_{id_membro}.*"):
                try:
                    arquivo_antigo.unlink()
                except OSError:
                    pass

            destino = PASTA_FOTOS_MEMBROS / f"foto_{id_membro}{extensao}"
            shutil.copyfile(self.caminho_foto_selecionada, destino)

            coluna_foto = garantir_coluna_foto_membro()
            conexao = conectar()
            cursor = conexao.cursor()
            cursor.execute(
                f"UPDATE membros SET {coluna_foto} = ? WHERE id = ?",
                (str(destino), id_membro),
            )
            conexao.commit()
            conexao.close()

            self.caminho_foto_existente = str(destino)
            self.caminho_foto_selecionada = ""
        except Exception as erro:
            messagebox.showwarning(
                "SIGM",
                f"O membro foi salvo, mas houve um problema ao salvar a foto.\n\nErro: {erro}",
                parent=self,
            )

    def carregar_dados_membro(self):
        membro = buscar_membro_por_id(self.id_membro)

        if membro is None:
            messagebox.showerror("SIGM", "Membro não encontrado.")
            self.destroy()
            return

        self.nome.insert(0, membro[1] or "")
        self.rg.insert(0, membro[2] or "")
        self.orgao.insert(0, membro[3] or "")
        self.cpf.insert(0, membro[4] or "")
        self.nascimento.insert(0, membro[5] or "")
        self.estado_civil.insert(0, membro[6] or "")
        self.profissao.insert(0, membro[7] or "")
        self.nome_pai.insert(0, membro[21] if len(membro) > 21 and membro[21] else "")
        self.nome_mae.insert(0, membro[22] if len(membro) > 22 and membro[22] else "")
        self.cidade_nascimento.insert(0, membro[23] if len(membro) > 23 and membro[23] else "")
        self.estado_nascimento.insert(0, membro[24] if len(membro) > 24 and membro[24] else "")
        self.nome_conjuge.insert(0, membro[25] if len(membro) > 25 and membro[25] else "")
        self.data_nascimento_conjuge.insert(0, membro[26] if len(membro) > 26 and membro[26] else "")
        self.grau_instrucao.insert(0, membro[27] if len(membro) > 27 and membro[27] else "")
        self.telefone.insert(0, membro[8] or "")
        self.celular.insert(0, membro[9] or "")
        self.email.insert(0, membro[10] or "")
        self.endereco.insert(0, membro[11] or "")
        self.numero.insert(0, membro[12] or "")
        self.bairro.insert(0, membro[13] or "")
        self.cidade.insert(0, membro[14] or "")
        self.estado.insert(0, membro[15] or "")
        self.cep.insert(0, membro[30] if len(membro) > 30 and membro[30] else "")
        self.batismo_aguas.insert(0, membro[16] or "")
        self.data_batismo_espirito_santo.insert(
            0,
            membro[29] if len(membro) > 29 and membro[29] else "",
        )
        self.ministerio.insert(0, membro[17] or "")
        self.cargo.set(self.normalizar_funcao(membro[18] or ""))
        self.data_funcao.insert(0, buscar_data_funcao_membro(self.id_membro))
        self.curso_teologico.insert(0, membro[28] if len(membro) > 28 and membro[28] else "")

        if membro[19]:
            self.status.set(membro[19])

        self.observacoes.insert("1.0", membro[20] or "")

    def montar_dados(self):
        return {
            "nome": self.nome.get().strip(),
            "rg": self.rg.get().strip(),
            "orgao_emissor": self.orgao.get().strip(),
            "cpf": self.cpf.get().strip(),
            "data_nascimento": self.nascimento.get().strip(),
            "cidade_nascimento": self.cidade_nascimento.get().strip(),
            "estado_nascimento": self.estado_nascimento.get().strip(),
            "estado_civil": self.estado_civil.get().strip(),
            "nome_conjuge": self.nome_conjuge.get().strip(),
            "data_nascimento_conjuge": self.data_nascimento_conjuge.get().strip(),
            "profissao": self.profissao.get().strip(),
            "nome_pai": self.nome_pai.get().strip(),
            "nome_mae": self.nome_mae.get().strip(),
            "grau_instrucao": self.grau_instrucao.get().strip(),
            "telefone": self.telefone.get().strip(),
            "celular": self.celular.get().strip(),
            "email": self.email.get().strip(),
            "endereco": self.endereco.get().strip(),
            "numero": self.numero.get().strip(),
            "bairro": self.bairro.get().strip(),
            "cidade": self.cidade.get().strip(),
            "estado": self.estado.get().strip(),
            "cep": self.formatar_cep(self.cep.get()),
            "batismo_aguas": self.batismo_aguas.get().strip(),
            "data_batismo_espirito_santo": self.data_batismo_espirito_santo.get().strip(),
            "ministerio": self.ministerio.get().strip(),
            "cargo": self.normalizar_funcao(self.cargo.get()),
            "data_funcao": self.data_funcao.get().strip(),
            "curso_teologico": self.curso_teologico.get().strip(),
            "status": self.status.get(),
            "observacoes": self.observacoes.get("1.0", "end").strip()
        }

    def assinar_dados(self):
        dados = self.montar_dados()
        assinatura = tuple(
            (chave, str(dados.get(chave, "")))
            for chave in sorted(dados)
        )
        return assinatura + (("_foto_selecionada", self.caminho_foto_selecionada),)

    def possui_alteracoes_nao_salvas(self):
        return self.assinar_dados() != getattr(self, "assinatura_inicial", None)

    def cancelar(self):
        if self.possui_alteracoes_nao_salvas():
            confirmar = messagebox.askyesno(
                "SIGM",
                "Existem alterações não salvas. Deseja fechar sem salvar?",
                parent=self,
            )
            if not confirmar:
                return

        self.destroy()

    def salvar(self):
        if self.nome.get().strip() == "":
            messagebox.showwarning("SIGM", "O campo Nome completo é obrigatório.")
            return

        dados = self.montar_dados()
        if not self.validar_data_funcao(dados):
            return
        if not self.validar_data_nascimento_conjuge(dados):
            return
        if not self.validar_data_batismo_espirito_santo(dados):
            return
        if not self.validar_cep(dados):
            return

        try:
            if self.modo_edicao:
                membro_anterior = buscar_membro_por_id(self.id_membro)
                observacoes_anteriores = membro_anterior[20] if membro_anterior else ""
                atualizar_membro(self.id_membro, dados)
                self.salvar_foto_membro(self.id_membro)
                registrar_acao(
                    "EDICAO_MEMBRO",
                    f"Membro {dados['nome']} atualizado.",
                    modulo="Membros",
                    registro_id=self.id_membro,
                    detalhes=(
                        f"Funcao atual: {dados.get('cargo') or 'Nenhuma'}; "
                        f"Data da funcao: {dados.get('data_funcao') or ''}"
                    ),
                )
                if str(observacoes_anteriores or "") != str(dados.get("observacoes") or ""):
                    registrar_acao(
                        "ALTERACAO_OBSERVACOES_MEMBRO",
                        f"Observacoes do membro {dados['nome']} foram alteradas.",
                        modulo="Membros",
                        registro_id=self.id_membro,
                    )
                messagebox.showinfo("SIGM", "Dados salvos com sucesso.")
            else:
                id_membro = cadastrar_membro(dados)
                self.salvar_foto_membro(id_membro)
                registrar_acao(
                    "CADASTRO_MEMBRO",
                    f"Membro {dados['nome']} cadastrado.",
                    modulo="Membros",
                    registro_id=id_membro,
                )
                messagebox.showinfo("SIGM", "Dados salvos com sucesso.")

            if self.ao_salvar:
                self.ao_salvar()

            self.destroy()

        except Exception as erro:
            messagebox.showerror(
                "Erro no SIGM",
                f"Não foi possível salvar o membro.\n\nErro: {erro}"
            )

    @staticmethod
    def normalizar_funcao(valor):
        texto = str(valor or "").strip().lower()
        texto = unicodedata.normalize("NFD", texto)
        texto = "".join(
            caractere
            for caractere in texto
            if unicodedata.category(caractere) != "Mn"
        )
        return FUNCOES_NORMALIZADAS.get(texto, "Nenhuma")

    @staticmethod
    def digitos(valor):
        return "".join(
            caractere
            for caractere in str(valor or "")
            if caractere.isdigit()
        )

    def aplicar_mascara_data_funcao(self, _evento=None):
        valor = self.data_funcao.get()
        novo_valor = self.formatar_data_digitada(valor)

        if valor == novo_valor:
            return

        self.data_funcao.delete(0, "end")
        self.data_funcao.insert(0, novo_valor)

    def aplicar_mascara_data_nascimento_conjuge(self, _evento=None):
        valor = self.data_nascimento_conjuge.get()
        novo_valor = self.formatar_data_digitada(valor)

        if valor == novo_valor:
            return

        self.data_nascimento_conjuge.delete(0, "end")
        self.data_nascimento_conjuge.insert(0, novo_valor)

    def aplicar_mascara_data_batismo_espirito_santo(self, _evento=None):
        valor = self.data_batismo_espirito_santo.get()
        novo_valor = self.formatar_data_digitada(valor)

        if valor == novo_valor:
            return

        self.data_batismo_espirito_santo.delete(0, "end")
        self.data_batismo_espirito_santo.insert(0, novo_valor)

    def aplicar_mascara_cep(self, _evento=None):
        valor = self.cep.get()
        novo_valor = self.formatar_cep(valor)

        if valor == novo_valor:
            return

        self.cep.delete(0, "end")
        self.cep.insert(0, novo_valor)

    def formatar_data_digitada(self, valor):
        digitos = self.digitos(valor)[:8]

        if len(digitos) <= 2:
            novo_valor = digitos
        elif len(digitos) <= 4:
            novo_valor = f"{digitos[:2]}/{digitos[2:]}"
        else:
            novo_valor = f"{digitos[:2]}/{digitos[2:4]}/{digitos[4:]}"

        return novo_valor

    @classmethod
    def formatar_cep(cls, valor):
        digitos = cls.digitos(valor)[:8]

        if len(digitos) <= 5:
            return digitos

        return f"{digitos[:5]}-{digitos[5:]}"

    def validar_data_funcao(self, dados):
        data_funcao = dados.get("data_funcao", "")
        if not data_funcao:
            return True

        if separar_data_documento(data_funcao) != ("", "", ""):
            return True

        messagebox.showwarning(
            "SIGM",
            "Data da função atual inválida. Use DD/MM/AAAA.",
            parent=self,
        )
        return False

    def validar_data_nascimento_conjuge(self, dados):
        data_conjuge = dados.get("data_nascimento_conjuge", "")
        if not data_conjuge:
            return True

        if separar_data_documento(data_conjuge) != ("", "", ""):
            return True

        messagebox.showwarning(
            "SIGM",
            "Data de nascimento do conjuge invalida. Use DD/MM/AAAA.",
            parent=self,
        )
        return False

    def validar_data_batismo_espirito_santo(self, dados):
        data_batismo = dados.get("data_batismo_espirito_santo", "")
        if not data_batismo:
            return True

        if separar_data_documento(data_batismo) != ("", "", ""):
            return True

        messagebox.showwarning(
            "SIGM",
            "Data do batismo no Espirito Santo invalida. Use DD/MM/AAAA.",
            parent=self,
        )
        return False

    def validar_cep(self, dados):
        cep = dados.get("cep", "")
        if not cep:
            return True

        if len(self.digitos(cep)) == 8:
            return True

        messagebox.showwarning(
            "SIGM",
            "CEP invalido. Use 00000-000.",
            parent=self,
        )
        return False
