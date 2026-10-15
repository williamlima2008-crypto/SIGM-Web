"""Painel inicial da versao web (mesmos indicadores do dashboard desktop)."""

from datetime import datetime
from pathlib import Path

from flask import jsonify, render_template, session

from banco.database import (
    listar_arquivos_anexados_recentes,
    listar_documentos_emitidos_recentes,
    listar_pre_cadastros,
    proximos_aniversariantes,
    total_arquivos_anexados,
    total_documentos_emitidos,
    total_documentos_emitidos_hoje,
    total_membros,
    total_por_status,
    ultimos_membros_cadastrados,
)
from config import configuracoes
from utils.caminhos import caminho_dados
from web.documentos_web import acentuar


def saudacao(agora=None):
    hora = (agora or datetime.now()).hour
    if hora < 12:
        return "Bom dia"
    if hora < 18:
        return "Boa tarde"
    return "Boa noite"


def _tamanho(bytes_):
    valor = float(bytes_)
    for unidade in ("B", "KB", "MB", "GB"):
        if valor < 1024 or unidade == "GB":
            return f"{valor:.0f} {unidade}" if unidade == "B" else f"{valor:.1f} {unidade}"
        valor /= 1024


def ultimo_backup():
    pasta = caminho_dados("backup", criar_pai=False)
    try:
        arquivos = [p for p in Path(pasta).rglob("*") if p.is_file()]
    except OSError:
        arquivos = []
    if not arquivos:
        return {"existe": False, "texto": "Nenhum backup encontrado."}
    ultimo = max(arquivos, key=lambda p: p.stat().st_mtime)
    dados = ultimo.stat()
    return {
        "existe": True,
        "arquivo": ultimo.name,
        "data": datetime.fromtimestamp(dados.st_mtime).strftime("%d/%m/%Y %H:%M"),
        "tamanho": _tamanho(dados.st_size),
    }


def _data(valor):
    texto = str(valor or "").strip()
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(texto[:19], formato)
        except ValueError:
            continue
    return None


def atividades_recentes(limite=8):
    itens = []
    for doc in listar_documentos_emitidos_recentes(limite):
        itens.append((_data(doc["data"]), f"PDF: {acentuar(doc['titulo']) or '-'} — {doc['membro'] or 'Membro'}"))
    for arq in listar_arquivos_anexados_recentes(limite):
        itens.append((_data(arq["data"]),
                      f"Arquivo: {arq['titulo'] or arq['tipo'] or '-'} — {arq['membro'] or 'Membro'}"))
    itens.sort(key=lambda i: i[0] or datetime.min, reverse=True)
    return [{"data": d.strftime("%d/%m/%Y %H:%M") if d else "", "texto": t} for d, t in itens[:limite]]


def montar_painel():
    pendentes = 0
    try:
        pendentes = len(listar_pre_cadastros("pendente"))
    except Exception:
        pass
    return {
        "indicadores": {
            "total": total_membros(),
            "membros": total_por_status("Membro"),
            "visitantes": total_por_status("Visitante"),
            "congregados": total_por_status("Congregado"),
            "pdfs": total_documentos_emitidos(),
            "pdfs_hoje": total_documentos_emitidos_hoje(),
            "arquivos": total_arquivos_anexados(),
            "pre_cadastros_pendentes": pendentes,
        },
        "ultimos_membros": ultimos_membros_cadastrados(5),
        "aniversariantes": [
            {"id": a["id"], "nome": a["nome"], "data": a["proximo"].strftime("%d/%m"), "dias": int(a["dias"])}
            for a in proximos_aniversariantes(5)
        ],
        "atividades": atividades_recentes(),
        "backup": ultimo_backup(),
    }


def registrar_rotas_painel(app, exige_login, dados_igreja, menu_usuario):
    @app.get("/inicio")
    @exige_login
    def pagina_inicio():
        usuario = session.get("usuario") or {}
        return render_template(
            "inicio.html",
            igreja=dados_igreja(),
            sistema=configuracoes.NOME_SISTEMA,
            usuario=usuario,
            menu=menu_usuario("inicio"),
            saudacao=saudacao(),
            hoje=datetime.now().strftime("%d/%m/%Y"),
        )

    @app.get("/api/painel")
    @exige_login
    def api_painel():
        return jsonify(montar_painel())
