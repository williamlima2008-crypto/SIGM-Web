import customtkinter as ctk
from config import cores


class Card(ctk.CTkFrame):

    def __init__(self, master, titulo, valor="", icone="", comando=None):
        super().__init__(
            master,
            corner_radius=8,
            fg_color=cores.BRANCO,
            border_width=1,
            border_color="#D8E3F2",
            cursor="hand2"
        )

        self.comando = comando

        self.icone = ctk.CTkLabel(
            self,
            text=icone,
            font=("Segoe UI Emoji", 34)
        )
        self.icone.pack(pady=(18, 5))

        self.titulo = ctk.CTkLabel(
            self,
            text=titulo,
            font=("Segoe UI", 16, "bold"),
            text_color=cores.PRETO
        )
        self.titulo.pack()

        self.valor = ctk.CTkLabel(
            self,
            text=str(valor),
            font=("Segoe UI", 26, "bold"),
            text_color=cores.AZUL_PRINCIPAL
        )
        self.valor.pack(pady=(8, 10))

        self.bind("<Button-1>", self.clicar)
        self.icone.bind("<Button-1>", self.clicar)
        self.titulo.bind("<Button-1>", self.clicar)
        self.valor.bind("<Button-1>", self.clicar)

        self.bind("<Enter>", self.mouse_entrou)
        self.bind("<Leave>", self.mouse_saiu)

    def clicar(self, event=None):
        if self.comando:
            self.comando()

    def mouse_entrou(self, event=None):
        self.configure(border_width=2, border_color=cores.AZUL_PRINCIPAL)

    def mouse_saiu(self, event=None):
        self.configure(border_width=1, border_color="#D8E3F2")
