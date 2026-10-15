"""Log de auditoria na versao web (somente Administrador)."""

import io
from datetime import datetime, timedelta

from flask import abort, jsonify, render_template, request, send_file, session

from banco.database import (
    conectar,
    garantir_tabela_logs_auditoria,
    buscar_configuracoes_igreja,
    buscar_log_auditoria_por_id,
    listar_logs_auditoria,
)
from config import configuracoes
from utils.auditoria import registrar_acao
from utils.formatadores import formatar_data_hora

LIMITE_TELA = 500
LIMITE_PDF = 1000
MINIMO_DIAS = 90


def _filtros():
    return {
        "termo": request.args.get("q", ""), "acao": request.args.get("acao", ""),
        "usuario": request.args.get("usuario", ""), "modulo": request.args.get("modulo", ""),
        "data_inicial": request.args.get("de", ""), "data_final": request.args.get("ate", ""),
    }


def _linha(log):
    return {
        "id": log["id"], "data": formatar_data_hora(log.get("data_hora")),
        "usuario": log.get("usuario_nome") or log.get("usuario_login") or "-",
        "login": log.get("usuario_login") or "", "acao": log.get("acao") or "",
        "modulo": log.get("modulo") or "", "descricao": log.get("descricao") or "",
        "registro_id": log.get("registro_id") or "", "detalhes": log.get("detalhes") or "",
    }


def gerar_pdf(logs, filtros):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    igreja = buscar_configuracoes_igreja()
    estilos = getSampleStyleSheet()
    pequeno = estilos["BodyText"].clone("pequeno", fontSize=8, leading=10)
    saida = io.BytesIO()
    doc = SimpleDocTemplate(saida, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=14 * mm, title="Log de Auditoria")
    periodo = " a ".join(p for p in (filtros["data_inicial"], filtros["data_final"]) if p) or "Todos"
    topo = [
        Paragraph(f"<b>Log de Auditoria</b> - {igreja.get('nome_igreja') or 'SIGM'}", estilos["Title"]),
        Paragraph(f"Período: {periodo} · {len(logs)} registro(s) · gerado em "
                  f"{datetime.now().strftime('%d/%m/%Y %H:%M')}", pequeno),
        Spacer(1, 6),
    ]
    dados = [["Data e hora", "Usuário", "Ação", "Módulo", "Descrição"]]
    for log in logs:
        l = _linha(log)
        dados.append([Paragraph(str(v).replace("&", "&amp;").replace("<", "&lt;"), pequeno)
                      for v in (l["data"], l["usuario"], l["acao"], l["modulo"], l["descricao"])])
    tabela = Table(dados, colWidths=[30 * mm, 38 * mm, 48 * mm, 32 * mm, 105 * mm], repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B5ED7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8d0db")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f4f7")]),
    ]))

    def rodape(canvas, d):
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(landscape(A4)[0] - 12 * mm, 8 * mm, f"Página {d.page}")

    doc.build(topo + [tabela], onFirstPage=rodape, onLaterPages=rodape)
    saida.seek(0)
    return saida


def registrar_rotas_auditoria(app, exige_login, exige_admin, dados_igreja, menu_usuario):
    @app.get("/auditoria")
    @exige_login
    @exige_admin
    def pagina_auditoria():
        return render_template(
            "auditoria.html", igreja=dados_igreja(), sistema=configuracoes.NOME_SISTEMA,
            usuario=session.get("usuario"), menu=menu_usuario("auditoria"),
        )

    @app.get("/api/auditoria")
    @exige_login
    @exige_admin
    def api_auditoria():
        logs = listar_logs_auditoria(**_filtros(), limite=LIMITE_TELA + 1)
        return jsonify(itens=[_linha(l) for l in logs[:LIMITE_TELA]], truncado=len(logs) > LIMITE_TELA,
                       limite=LIMITE_TELA)

    @app.get("/api/auditoria/<int:id_log>")
    @exige_login
    @exige_admin
    def api_auditoria_detalhe(id_log):
        log = buscar_log_auditoria_por_id(id_log)
        if not log:
            abort(404)
        return jsonify(_linha(log))

    @app.get("/api/auditoria/exportar")
    @exige_login
    @exige_admin
    def api_auditoria_exportar():
        filtros = _filtros()
        logs = listar_logs_auditoria(**filtros, limite=LIMITE_PDF)
        if not logs:
            return jsonify(ok=False, mensagem="Não há registros para exportar."), 404
        pdf = gerar_pdf(logs, filtros)
        registrar_acao("LOG_AUDITORIA_EXPORTADO", "Log de auditoria exportado em PDF.",
                       modulo="Auditoria", detalhes=f"{len(logs)} registro(s) pela versão web")
        nome = f"log_auditoria_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=nome)

    @app.post("/api/auditoria/limpar")
    @exige_login
    @exige_admin
    def api_auditoria_limpar():
        """Apaga registros mais antigos que N dias (minimo 90). A propria limpeza fica registrada."""
        dados = request.get_json(silent=True) or {}
        try:
            dias = int(dados.get("dias"))
        except (TypeError, ValueError):
            return jsonify(ok=False, mensagem="Informe a quantidade de dias."), 400
        if dias < MINIMO_DIAS:
            return jsonify(ok=False, mensagem=f"Por segurança, mantenha pelo menos {MINIMO_DIAS} dias de registros."), 400
        limite = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
        garantir_tabela_logs_auditoria()
        conexao = conectar()
        try:
            removidos = conexao.execute("DELETE FROM logs_auditoria WHERE data_hora < ?", (limite,)).rowcount
            conexao.commit()
        finally:
            conexao.close()
        registrar_acao("LOG_AUDITORIA_LIMPO", f"{removidos} registro(s) de auditoria com mais de {dias} dias removidos.",
                       modulo="Auditoria", detalhes=f"Corte: {limite} (versão web)")
        return jsonify(ok=True, removidos=removidos)
