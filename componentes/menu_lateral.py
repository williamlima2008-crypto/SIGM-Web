import customtkinter as ctk

from config import cores


class MenuLateral(ctk.CTkFrame):

    def __init__(self, master, comandos=None, itens_ocultos=None):
        super().__init__(
            master,
            width=230,
            fg_color="#F7F9FC",
            corner_radius=0,
            border_width=1,
            border_color="#DCE3EB"
        )

        self.pack_propagate(False)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        comandos = comandos or {}
        itens_ocultos = set(itens_ocultos or [])

        titulo = ctk.CTkLabel(
            self,
            text="MENU",
            font=("Segoe UI", 22, "bold"),
            text_color=cores.AZUL_PRINCIPAL
        )
        titulo.grid(row=0, column=0, padx=12, pady=(25, 14), sticky="ew")

        corpo_menu = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
            width=218,
        )
        corpo_menu.grid(row=1, column=0, padx=0, pady=(0, 12), sticky="nsew")
        corpo_menu.bind(
            "<Configure>",
            lambda _evento: self.atualizar_barra_rolagem(corpo_menu),
            add="+",
        )
        if hasattr(corpo_menu, "_parent_canvas"):
            corpo_menu._parent_canvas.bind(
                "<Configure>",
                lambda _evento: self.atualizar_barra_rolagem(corpo_menu),
                add="+",
            )

        botoes = [
            ("dashboard", "🏠 Dashboard"),
            ("membros", "👥 Membros"),
            ("pre_cadastros", "Pre-cadastros"),
            ("documentos", "📄 Documentos"),
            ("usuarios", "👤 Usuários"),
            ("aniversariantes", "🎂 Aniversariantes"),
            ("relatorios", "📊 Relatórios"),
            ("auditoria", "Auditoria"),
            ("configuracoes", "⚙ Configurações"),
            ("backup", "💾 Backup"),
            ("sobre", "ℹ Sobre"),
        ]

        for chave, texto in botoes:
            if chave in itens_ocultos:
                continue

            botao = ctk.CTkButton(
                corpo_menu,
                text=texto,
                command=comandos.get(chave),
                width=190,
                height=42,
                corner_radius=8,
                fg_color="transparent",
                hover_color="#E6F0FF",
                text_color=cores.PRETO,
                anchor="w",
                font=("Segoe UI", 14, "bold")
            )

            botao.pack(pady=4)

        corpo_menu.after_idle(lambda: self.atualizar_barra_rolagem(corpo_menu))

    def atualizar_barra_rolagem(self, frame_rolavel):
        try:
            canvas = frame_rolavel._parent_canvas
            barra = frame_rolavel._scrollbar
            area = canvas.bbox("all")
            altura_conteudo = (area[3] - area[1]) if area else 0
            precisa_rolagem = altura_conteudo > canvas.winfo_height() + 2

            if precisa_rolagem and not barra.winfo_ismapped():
                barra.grid()
            elif not precisa_rolagem and barra.winfo_ismapped():
                barra.grid_remove()
        except Exception:
            pass
