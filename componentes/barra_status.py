import customtkinter as ctk

from config import cores
from config.versao import VERSAO


class BarraStatus(ctk.CTkFrame):

    def __init__(
        self,
        master,
        usuario="",
        perfil="",
        versao=VERSAO
    ):

        super().__init__(
            master,
            height=34,
            corner_radius=0,
            fg_color="#F2F4F7"
        )

        self.pack_propagate(False)

        texto = (
            f"Usuário: {usuario}     "
            f"Perfil: {perfil}     "
            f"Banco: Conectado     "
            f"Versão {versao}"
        )

        label = ctk.CTkLabel(
            self,
            text=texto,
            font=("Segoe UI", 11),
            text_color=cores.CINZA
        )

        label.pack(side="right", padx=20)
