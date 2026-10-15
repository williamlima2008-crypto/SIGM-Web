"""
SIGM Web - Aniversariantes e Relatorios.

Usa as mesmas consultas e regras da versao desktop (telas/aniversariantes.py
e telas/relatorios.py). A exportacao e enviada como download no navegador.
"""

import csv
import io
from datetime import date, datetime

from flask import abort, jsonify, render_template, request, send_file, session

from banco.database import (
    conectar,
    garantir_tabela_arquivos_membro,
    garantir_tabela_documentos_emitidos,
    interpretar_data_nascimento,
)
from config import configuracoes
from utils.auditoria import registrar_acao
from utils.formatadores import formatar_data_hora, normalizar_texto_busca
from web.documentos_web import acentuar

MESES = (
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)

TIPOS_RELATORIO = (
    ("todos", "Lista de todos os membros"),
    ("membros-ativos", "Membros ativos"),
    ("congregados", "Congregados"),
    ("visitantes", "Visitantes"),
    ("aniversariantes-mes", "Aniversariantes do mês"),
    ("documentos-emitidos", "Documentos emitidos"),
    ("arquivos-anexados", "Arquivos anexados"),
)
NOMES_RELATORIO = dict(TIPOS_RELATORIO)
LIMITE_TELA = 300


def _contato(celular, telefone):
    return celular or telefone or ""


# ----------------------------------------------------------- aniversariantes
def carregar_aniversariantes():
    conexao = conectar()
    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id, nome, data_nascimento, telefone, celular
            FROM membros
            WHERE data_nascimento IS NOT NULL AND TRIM(data_nascimento) <> ''
            """
        )
        linhas = cursor.fetchall()
    finally:
        conexao.close()
    membros = []
    for id_membro, nome, data_nascimento, telefone, celular in linhas:
        nascimento = interpretar_data_nascimento(data_nascimento)
        if nascimento is None:
            continue
        membros.append({
            "id": id_membro,
            "nome": nome or "",
            "nascimento": nascimento,
            "contato": _contato(celular, telefone),
            "busca": normalizar_texto_busca(f"{nome} {telefone} {celular}"),
        })
    return membros


def aniversariantes_do_mes(membros, mes, termo="", hoje=None):
    hoje = hoje or date.today()
    termo = normalizar_texto_busca(termo)
    itens = []
    for m in membros:
        nasc = m["nascimento"]
        if nasc.month != mes:
            continue
        if termo and termo not in m["busca"]:
            continue
        itens.append({
            "id": m["id"],
            "nome": m["nome"],
            "dia": nasc.day,
            "data": nasc.strftime("%d/%m/%Y"),
            "idade": max(hoje.year - nasc.year, 0),
            "contato": m["contato"],
            "hoje": nasc.month == hoje.month and nasc.day == hoje.day,
        })
    itens.sort(key=lambda i: (i["dia"], i["nome"]))
    return itens


# ---------------------------------------------------------------- relatorios
def _consulta(sql, parametros=()):
    conexao = conectar()
    try:
        cursor = conexao.cursor()
        cursor.execute(sql, parametros)
        return cursor.fetchall()
    finally:
        conexao.close()


def _relatorio_membros(status=None):
    sql = "SELECT id, nome, status, celular, telefone, cidade, cargo FROM membros"
    parametros = []
    if status:
        sql += " WHERE status = ?"
        parametros.append(status)
    sql += " ORDER BY nome COLLATE NOCASE ASC"
    dados = [
        [i, nome or "", st or "", _contato(cel, tel), cidade or "", cargo or ""]
        for i, nome, st, cel, tel, cidade, cargo in _consulta(sql, parametros)
    ]
    return ["ID", "Nome", "Status", "Contato", "Cidade", "Função"], dados


def _relatorio_aniversariantes():
    hoje = date.today()
    itens = aniversariantes_do_mes(carregar_aniversariantes(), hoje.month, hoje=hoje)
    dados = [[i["nome"], i["data"], i["contato"]] for i in itens]
    return ["Nome", "Nascimento", "Contato"], dados


def _relatorio_documentos():
    garantir_tabela_documentos_emitidos()
    linhas = _consulta(
        """
        SELECT d.titulo_documento, d.data_emissao, d.usuario_emissor, m.nome
        FROM documentos_emitidos d
        LEFT JOIN membros m ON m.id = d.membro_id
        ORDER BY d.data_emissao DESC, d.id DESC
        """
    )
    dados = [
        [acentuar(titulo), formatar_data_hora(data), usuario or "", membro or ""]
        for titulo, data, usuario, membro in linhas
    ]
    return ["Documento", "Data", "Usuário", "Membro"], dados


def _relatorio_arquivos():
    garantir_tabela_arquivos_membro()
    linhas = _consulta(
        """
        SELECT a.tipo_arquivo, a.titulo, a.data_anexo, a.usuario_responsavel, m.nome
        FROM arquivos_membro a
        LEFT JOIN membros m ON m.id = a.membro_id
        ORDER BY a.data_anexo DESC, a.id DESC
        """
    )
    dados = [
        [tipo or "", titulo or "", formatar_data_hora(data), usuario or "", membro or ""]
        for tipo, titulo, data, usuario, membro in linhas
    ]
    return ["Tipo", "Título", "Data", "Usuário", "Membro"], dados


def montar_relatorio(slug):
    """Devolve (colunas, linhas) do relatorio ou None se o tipo nao existe."""
    if slug == "todos":
        return _relatorio_membros()
    if slug == "membros-ativos":
        return _relatorio_membros("Membro")
    if slug == "congregados":
        return _relatorio_membros("Congregado")
    if slug == "visitantes":
        return _relatorio_membros("Visitante")
    if slug == "aniversariantes-mes":
        return _relatorio_aniversariantes()
    if slug == "documentos-emitidos":
        return _relatorio_documentos()
    if slug == "arquivos-anexados":
        return _relatorio_arquivos()
    return None


def _nome_arquivo(slug, extensao):
    agora = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{slug.replace('-', '_')}_{agora}.{extensao}"


def gerar_csv(colunas, dados):
    texto = io.StringIO()
    escritor = csv.writer(texto, delimiter=";")
    escritor.writerow(colunas)
    escritor.writerows(dados)
    return io.BytesIO(texto.getvalue().encode("utf-8-sig"))


def gerar_xlsx(colunas, dados):
    import openpyxl  # opcional: sem ele a rota cai para CSV

    planilha = openpyxl.Workbook()
    aba = planilha.active
    aba.title = "Relatorio"
    aba.append(list(colunas))
    for linha in dados:
        aba.append(list(linha))
    for coluna in aba.columns:
        maior = max((len(str(c.value or "")) for c in coluna), default=8)
        aba.column_dimensions[coluna[0].column_letter].width = min(max(maior + 2, 10), 50)
    saida = io.BytesIO()
    planilha.save(saida)
    saida.seek(0)
    return saida


def gerar_pdf(titulo, subtitulo, colunas, dados):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    estilos = getSampleStyleSheet()
    celula = ParagraphStyle("celula", parent=estilos["BodyText"], fontSize=8.5, leading=10.5)
    cabecalho = ParagraphStyle(
        "cab", parent=celula, fontName="Helvetica-Bold", textColor=colors.white
    )
    saida = io.BytesIO()

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        largura, _ = landscape(A4)
        canvas.drawString(15 * mm, 8 * mm, f"{titulo} - {datetime.now():%d/%m/%Y %H:%M}")
        canvas.drawRightString(largura - 15 * mm, 8 * mm, f"Página {doc.page}")
        canvas.restoreState()

    documento = SimpleDocTemplate(
        saida, pagesize=landscape(A4), leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=16 * mm, title=titulo,
    )
    elementos = [Paragraph(f"<b>{_esc(titulo)}</b>", estilos["Title"])]
    if subtitulo:
        elementos.append(Paragraph(_esc(subtitulo), estilos["Normal"]))
    elementos.append(Paragraph(f"{len(dados)} registro(s)", estilos["Normal"]))
    elementos.append(Spacer(1, 6 * mm))

    if dados:
        tabela = [[Paragraph(_esc(c), cabecalho) for c in colunas]]
        for linha in dados:
            tabela.append([Paragraph(_esc(v) or "-", celula) for v in linha])
        t = Table(tabela, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B5ED7")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F4F7")]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D9E0EA")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elementos.append(t)
    else:
        elementos.append(Paragraph("Nenhum registro encontrado.", estilos["Normal"]))
    documento.build(elementos, onFirstPage=rodape, onLaterPages=rodape)
    saida.seek(0)
    return saida


def _esc(valor):
    return (
        str(valor if valor is not None else "")
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def registrar_rotas_relatorios(app, exige_login, dados_igreja, menu_usuario):
    def contexto(ativo):
        return dict(
            igreja=dados_igreja(),
            sistema=configuracoes.NOME_SISTEMA,
            usuario=session.get("usuario"),
            menu=menu_usuario(ativo),
        )

    @app.get("/aniversariantes")
    @exige_login
    def pagina_aniversariantes():
        return render_template(
            "aniversariantes.html", meses=MESES, mes_atual=date.today().month,
            **contexto("aniversariantes"),
        )

    @app.get("/api/aniversariantes")
    @exige_login
    def api_aniversariantes():
        hoje = date.today()
        try:
            mes = int(request.args.get("mes") or hoje.month)
        except ValueError:
            mes = hoje.month
        if not 1 <= mes <= 12:
            mes = hoje.month
        membros = carregar_aniversariantes()
        itens = aniversariantes_do_mes(membros, mes, request.args.get("q") or "", hoje)
        total_hoje = sum(
            1 for m in membros
            if m["nascimento"].month == hoje.month and m["nascimento"].day == hoje.day
        )
        return jsonify(itens=itens, mes=mes, total_hoje=total_hoje, total_mes=len(itens))

    @app.get("/relatorios")
    @exige_login
    def pagina_relatorios():
        return render_template(
            "relatorios.html", tipos=TIPOS_RELATORIO, **contexto("relatorios"),
        )

    @app.get("/api/relatorios/<slug>")
    @exige_login
    def api_relatorio(slug):
        resultado = montar_relatorio(slug)
        if resultado is None:
            abort(404)
        colunas, dados = resultado
        return jsonify(
            titulo=NOMES_RELATORIO[slug], colunas=colunas,
            linhas=dados[:LIMITE_TELA], total=len(dados),
            cortado=len(dados) > LIMITE_TELA,
        )

    @app.get("/api/relatorios/<slug>/exportar")
    @exige_login
    def api_exportar_relatorio(slug):
        resultado = montar_relatorio(slug)
        if resultado is None:
            abort(404)
        colunas, dados = resultado
        titulo = NOMES_RELATORIO[slug]
        formato = (request.args.get("formato") or "pdf").lower()
        if formato == "pdf":
            igreja = dados_igreja()
            arquivo = gerar_pdf(titulo, igreja.get("nome") or "", colunas, dados)
            extensao, tipo = "pdf", "application/pdf"
        elif formato == "xlsx":
            try:
                arquivo = gerar_xlsx(colunas, dados)
                extensao = "xlsx"
                tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            except ImportError:
                arquivo = gerar_csv(colunas, dados)
                extensao, tipo, formato = "csv", "text/csv", "csv"
        elif formato == "csv":
            arquivo = gerar_csv(colunas, dados)
            extensao, tipo = "csv", "text/csv"
        else:
            abort(404)
        registrar_acao(
            "RELATORIO_EXPORTADO", f"Relatorio exportado em {formato.upper()}: {titulo}",
            modulo="Relatorios",
        )
        resposta = send_file(
            arquivo, mimetype=tipo, as_attachment=True,
            download_name=_nome_arquivo(slug, extensao),
        )
        resposta.headers["X-SIGM-Formato"] = extensao
        return resposta
