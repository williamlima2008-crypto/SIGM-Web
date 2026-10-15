import customtkinter as ctk

from config import cores


class BotaoModerno(ctk.CTkButton):

    def __init__(
        self,
        master,
        text,
        command=None,
        width=220,
        height=45,
        icone=None
    ):

        texto = text

        if icone:
            texto = f"{icone}   {text}"

        super().__init__(
            master,
            text=texto,
            command=command,
            width=width,
            height=height,
            corner_radius=8,
            fg_color=cores.AZUL_PRINCIPAL,
            hover_color=cores.AZUL_ESCURO,
            border_width=1,
            border_color="#D6E4FF",
            font=("Segoe UI", 15, "bold"),
            cursor="hand2"
        )
