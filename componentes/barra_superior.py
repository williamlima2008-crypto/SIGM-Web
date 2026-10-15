import customtkinter as ctk

from config import cores


class BarraSuperior(ctk.CTkFrame):

    def __init__(
        self,
        master,
        titulo="SIGM",
        usuario="",
        comando_trocar_usuario=None,
        comando_sair=None,
    ):
        super().__init__(
            master,
            height=70,
            corner_radius=0,
            fg_color=cores.AZUL_PRINCIPAL
        )

        self.pack_propagate(False)

        frame_esquerdo = ctk.CTkFrame(self, fg_color="transparent")
        frame_esquerdo.pack(side="left", padx=20)

        logo = ctk.CTkLabel(
            frame_esquerdo,
            text="SIGM",
            font=("Segoe UI", 18, "bold"),
            text_color="white",
        )
        logo.pack(side="left", padx=(0, 10))

        nome = ctk.CTkLabel(
            frame_esquerdo,
            text=titulo,
            font=("Segoe UI", 24, "bold"),
            text_color="white"
        )
        nome.pack(side="left")

        frame_direito = ctk.CTkFrame(self, fg_color="transparent")
        frame_direito.pack(side="right", padx=20)

        usuario_label = ctk.CTkLabel(
            frame_direito,
            text=f"Usuario: {usuario}",
            font=("Segoe UI", 14, "bold"),
            text_color="white"
        )
        usuario_label.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            frame_direito,
            text="TROCAR USUARIO",
            width=132,
            height=30,
            corner_radius=8,
            fg_color="white",
            hover_color="#E6F0FF",
            text_color=cores.AZUL_PRINCIPAL,
            font=("Segoe UI", 11, "bold"),
            command=comando_trocar_usuario,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            frame_direito,
            text="SAIR",
            width=70,
            height=30,
            corner_radius=8,
            fg_color=cores.VERMELHO,
            hover_color="#A71D2A",
            text_color="white",
            font=("Segoe UI", 11, "bold"),
            command=comando_sair,
        ).pack(side="left", padx=4)
