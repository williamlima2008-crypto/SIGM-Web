def centralizar_janela(janela, largura=None, altura=None, master=None):
    janela.update_idletasks()

    if largura is None or altura is None:
        geometria = janela.geometry().split("+")[0]
        if "x" in geometria:
            largura_atual, altura_atual = geometria.split("x", 1)
            largura = largura or int(largura_atual)
            altura = altura or int(altura_atual)

    largura = largura or janela.winfo_width()
    altura = altura or janela.winfo_height()

    if master is not None and master.winfo_exists() and master.winfo_viewable():
        master.update_idletasks()
        x_base = master.winfo_rootx()
        y_base = master.winfo_rooty()
        largura_base = master.winfo_width()
        altura_base = master.winfo_height()
    else:
        x_base = 0
        y_base = 0
        largura_base = janela.winfo_screenwidth()
        altura_base = janela.winfo_screenheight()

    x = x_base + max((largura_base - largura) // 2, 0)
    y = y_base + max((altura_base - altura) // 2, 0)

    janela.geometry(f"{largura}x{altura}+{x}+{y}")


def ajustar_dimensoes_monitor(janela, largura, altura, margem=60):
    largura_tela = janela.winfo_screenwidth()
    altura_tela = janela.winfo_screenheight()

    largura = min(int(largura), max(largura_tela - margem, 320))
    altura = min(int(altura), max(altura_tela - margem, 240))

    return largura, altura


def trazer_para_frente(janela):
    def focar():
        try:
            if janela.winfo_exists():
                janela.lift()
                janela.focus_force()
        except Exception:
            pass

    focar()

    def remover_topmost():
        try:
            if janela.winfo_exists():
                janela.attributes("-topmost", False)
                focar()
        except Exception:
            pass

    try:
        janela.attributes("-topmost", True)
        janela.after(50, focar)
        janela.after(250, remover_topmost)
        janela.after(600, focar)
        janela.after(1200, focar)
    except Exception:
        pass


def configurar_janela_principal(
    janela,
    largura,
    altura,
    largura_minima=None,
    altura_minima=None,
    master=None,
):
    largura, altura = ajustar_dimensoes_monitor(janela, largura, altura)
    largura_minima = largura_minima or min(largura, 800)
    altura_minima = altura_minima or min(altura, 600)

    janela.geometry(f"{largura}x{altura}")
    janela.minsize(largura_minima, altura_minima)
    janela.resizable(True, True)
    centralizar_janela(janela, largura, altura, master=master)
    trazer_para_frente(janela)


def configurar_modal(janela, master):
    janela.transient(master)
    centralizar_janela(janela, master=master)
    trazer_para_frente(janela)
    
