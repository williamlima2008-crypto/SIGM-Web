"""
SIGM Web - inicia o servidor local e abre a janela do sistema.

Uso:
    python iniciar_web.py            # so neste computador
    python iniciar_web.py --rede     # tambem acessivel pelo celular (mesmo Wi-Fi)
    python iniciar_web.py --porta 8765
"""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

# Empacotado sem console (PyInstaller), stdout/stderr nao existem.
for _nome in ("stdout", "stderr"):
    if getattr(sys, _nome) is None:
        setattr(sys, _nome, open(os.devnull, "w", encoding="utf-8"))

from werkzeug.serving import make_server

from banco.database import criar_tabelas
from utils.caminhos import garantir_pastas_runtime
from web.servidor import criar_app

PORTA_PADRAO = 8765
TEMPO_SEM_JANELA = 90  # segundos sem sinal da janela para encerrar (modo local)


def sigm_ja_esta_rodando(porta):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/ping", timeout=1.5) as r:
            return b"sigm" in r.read()
    except Exception:
        return False


def ip_da_rede():
    try:
        teste = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        teste.connect(("10.255.255.255", 1))
        ip = teste.getsockname()[0]
        teste.close()
        return ip
    except Exception:
        return "127.0.0.1"


def abrir_janela(url):
    candidatos = [
        shutil.which("msedge"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        shutil.which("chrome"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
    ]
    for caminho in candidatos:
        if caminho and os.path.exists(caminho):
            subprocess.Popen([caminho, f"--app={url}", "--window-size=1280,820"])
            return
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rede", action="store_true", help="aceita conexoes do celular na mesma rede Wi-Fi")
    parser.add_argument("--porta", type=int, default=PORTA_PADRAO)
    parser.add_argument("--sem-janela", action="store_true", help="nao abre a janela do navegador")
    args = parser.parse_args()

    url_local = f"http://127.0.0.1:{args.porta}/"
    if sigm_ja_esta_rodando(args.porta):
        if not args.sem_janela:
            abrir_janela(url_local)
        return

    garantir_pastas_runtime()
    criar_tabelas()

    app = criar_app()
    app.config["ULTIMO_PING"] = time.time()
    host = "0.0.0.0" if args.rede else "127.0.0.1"
    servidor = make_server(host, args.porta, app, threaded=True)

    if args.rede:
        print(f"SIGM Web no celular: http://{ip_da_rede()}:{args.porta}/")
        print("O celular precisa estar no mesmo Wi-Fi. Feche esta janela para encerrar.")
        print("ATENCAO: neste modo a conexao NAO e criptografada (HTTP). Use somente em")
        print("rede de confianca (Wi-Fi da igreja protegido por senha), nunca em rede publica.")
    else:
        print(f"SIGM Web em {url_local}")

        def vigiar():
            while True:
                time.sleep(10)
                if time.time() - app.config["ULTIMO_PING"] > TEMPO_SEM_JANELA:
                    servidor.shutdown()
                    return

        threading.Thread(target=vigiar, daemon=True).start()

    if not args.sem_janela:
        threading.Timer(0.8, abrir_janela, args=(url_local,)).start()

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


def _registrar_erro_fatal():
    """Sem console, uma falha na partida seria invisivel: grava em logs/."""
    import traceback
    try:
        from datetime import datetime
        from utils.caminhos import caminho_dados
        arquivo = caminho_dados("logs", "erro_inicializacao_web.txt")
        with open(arquivo, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now():%d/%m/%Y %H:%M:%S}]\n{traceback.format_exc()}")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        _registrar_erro_fatal()
        raise
