"""Backup e restauracao na versao web.

Mesmos itens e mesmo formato do desktop (SIGM_backup_AAAAMMDD_HHMMSS.zip na
pasta backup). A restauracao so aceita backups que ja estao nessa pasta e
sempre cria antes um backup de seguranca do estado atual.
"""

import re
import zipfile
from datetime import datetime
from pathlib import Path

from flask import abort, jsonify, render_template, request, send_file, session

from banco.database import buscar_configuracoes_igreja
from config import configuracoes
from utils.auditoria import registrar_acao
from utils.caminhos import base_dados, caminho_dados

ITENS_BACKUP = ("sigm.db", "fotos_membros", "arquivos_membros", "documentos_gerados", "relatorios")
PADRAO_NOME = re.compile(r"^SIGM_backup_[0-9A-Za-z_]+\.zip$")
CABECALHO_SQLITE = b"SQLite format 3\x00"


def pasta_backup():
    return caminho_dados("backup", criar_pai=False)


def _ignorar(caminho):
    return caminho.name.lower().endswith((".tmp", ".temp", ".log")) or "__pycache__" in caminho.parts


def _adicionar(zip_, caminho, base):
    if not caminho.exists():
        return
    arquivos = [caminho] if caminho.is_file() else [a for a in caminho.rglob("*") if a.is_file()]
    for arquivo in arquivos:
        if _ignorar(arquivo):
            continue
        try:
            zip_.write(arquivo, arquivo.relative_to(base))
        except ValueError:
            continue  # fora da pasta de dados: nao da para restaurar no mesmo lugar


def _imagens_da_igreja():
    config = buscar_configuracoes_igreja()
    base = base_dados()
    achados = []
    for campo in ("logotipo", "assinatura_pastor", "carimbo"):
        valor = str(config.get(campo) or "").strip()
        if not valor:
            continue
        caminho = Path(valor)
        if not caminho.is_absolute():
            caminho = base / caminho
        if caminho.is_file():
            achados.append(caminho)
    return achados


def criar_backup(sufixo=""):
    pasta = pasta_backup()
    pasta.mkdir(parents=True, exist_ok=True)
    base = base_dados()
    nome = f"SIGM_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{sufixo}.zip"
    destino = pasta / nome
    contador = 1
    while destino.exists():
        destino = pasta / f"SIGM_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{sufixo}_{contador}.zip"
        contador += 1
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zip_:
        for item in ITENS_BACKUP:
            _adicionar(zip_, base / item, base)
        for imagem in _imagens_da_igreja():
            _adicionar(zip_, imagem, base)
    return destino


def listar_backups():
    pasta = pasta_backup()
    if not pasta.exists():
        return []
    itens = []
    for arq in pasta.glob("SIGM_backup_*.zip"):
        if arq.is_file() and PADRAO_NOME.match(arq.name):
            info = arq.stat()
            itens.append((info.st_mtime, arq.name, info.st_size))
    itens.sort(reverse=True)
    return [{"nome": n, "data": datetime.fromtimestamp(m).strftime("%d/%m/%Y %H:%M"),
             "tamanho": formatar_tamanho(t)} for m, n, t in itens]


def formatar_tamanho(tamanho):
    if tamanho < 1024:
        return f"{tamanho} B"
    if tamanho < 1024 * 1024:
        return f"{tamanho / 1024:.1f} KB"
    return f"{tamanho / (1024 * 1024):.1f} MB"


def caminho_backup(nome):
    """Backup existente na pasta de backups (ou None). Nome sem barras."""
    if not PADRAO_NOME.match(str(nome or "")):
        return None
    caminho = pasta_backup() / nome
    return caminho if caminho.is_file() else None


def validar_zip(caminho):
    """Levanta ValueError se o zip nao for um backup restauravel."""
    if not zipfile.is_zipfile(caminho):
        raise ValueError("O arquivo não é um backup válido.")
    destino = base_dados().resolve()
    with zipfile.ZipFile(caminho) as zip_:
        nomes = [i.filename for i in zip_.infolist()]
        if "sigm.db" not in nomes:
            raise ValueError("O backup não contém o banco de dados (sigm.db).")
        for nome in nomes:
            alvo = (destino / nome).resolve()
            if Path(nome).is_absolute() or destino not in alvo.parents and alvo != destino:
                raise ValueError("Backup contém caminho inválido.")
        with zip_.open("sigm.db") as banco:
            if banco.read(16) != CABECALHO_SQLITE:
                raise ValueError("O banco de dados dentro do backup está corrompido.")
        if zip_.testzip() is not None:
            raise ValueError("O backup está corrompido.")


def restaurar(caminho):
    validar_zip(caminho)
    seguranca = criar_backup("_antes_de_restaurar")
    with zipfile.ZipFile(caminho) as zip_:
        zip_.extractall(base_dados().resolve())
    return seguranca


def registrar_rotas_backup(app, exige_login, exige_admin, dados_igreja, menu_usuario):
    @app.get("/backup")
    @exige_login
    def pagina_backup():
        return render_template(
            "backup.html", igreja=dados_igreja(), sistema=configuracoes.NOME_SISTEMA,
            usuario=session.get("usuario"), menu=menu_usuario("backup"),
            itens=[*ITENS_BACKUP, "logotipo, carimbo e assinatura configurados"],
        )

    @app.get("/api/backup")
    @exige_login
    def api_backup():
        eh_admin = (session.get("usuario") or {}).get("perfil") == "Administrador"
        return jsonify(itens=listar_backups(), admin=eh_admin)

    @app.post("/api/backup")
    @exige_login
    def api_backup_criar():
        try:
            destino = criar_backup()
        except Exception as erro:
            return jsonify(ok=False, mensagem=f"Não foi possível criar o backup: {erro}"), 500
        registrar_acao("BACKUP_CRIADO", "Backup ZIP criado.", modulo="Backup",
                       detalhes=f"{destino.name} (versão web)")
        return jsonify(ok=True, nome=destino.name, mensagem="Backup criado: " + destino.name)

    @app.get("/api/backup/<nome>/arquivo")
    @exige_login
    @exige_admin
    def api_backup_baixar(nome):
        caminho = caminho_backup(nome)
        if not caminho:
            abort(404)
        registrar_acao("BACKUP_BAIXADO", "Backup ZIP baixado pela versão web.", modulo="Backup",
                       detalhes=nome)
        return send_file(caminho, mimetype="application/zip", as_attachment=True, download_name=nome)

    @app.post("/api/backup/<nome>/restaurar")
    @exige_login
    @exige_admin
    def api_backup_restaurar(nome):
        caminho = caminho_backup(nome)
        if not caminho:
            return jsonify(ok=False, mensagem="Backup não encontrado."), 404
        if not (request.get_json(silent=True) or {}).get("confirmar"):
            return jsonify(ok=False, mensagem="Confirmação necessária."), 400
        try:
            seguranca = restaurar(caminho)
        except ValueError as erro:
            return jsonify(ok=False, mensagem=str(erro)), 400
        except Exception as erro:
            return jsonify(ok=False, mensagem=f"Não foi possível restaurar: {erro}"), 500
        registrar_acao("BACKUP_RESTAURADO", "Backup ZIP restaurado.", modulo="Backup",
                       detalhes=f"{nome} (versão web); segurança: {seguranca.name}")
        return jsonify(ok=True, seguranca=seguranca.name,
                       mensagem="Backup restaurado. Um backup do estado anterior foi guardado como "
                                f"{seguranca.name}. Reinicie o SIGM para recarregar tudo.")
