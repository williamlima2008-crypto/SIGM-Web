"""Central de documentos: historico geral de documentos emitidos."""

from flask import jsonify, render_template, request, session

from banco.database import (
    buscar_documento_emitido_por_id,
    conectar,
    excluir_registro_documento,
    listar_documentos_emitidos,
    total_documentos_emitidos,
)
from config import configuracoes
from utils.auditoria import registrar_acao
from utils.formatadores import formatar_data_hora, normalizar_texto_busca
from web import documentos_web

LIMITE_PADRAO = 20
LIMITE_BUSCA = 50


def _nomes_membros(ids):
    ids = [i for i in set(ids) if i]
    if not ids:
        return {}
    conexao = conectar()
    try:
        marcas = ",".join("?" * len(ids))
        linhas = conexao.execute(f"SELECT id, nome FROM membros WHERE id IN ({marcas})", ids).fetchall()
    finally:
        conexao.close()
    return {linha[0]: linha[1] or "" for linha in linhas}


def listar_central(termo=""):
    documentos = [dict(d) for d in listar_documentos_emitidos()]
    nomes = _nomes_membros([d.get("membro_id") for d in documentos])
    itens = []
    for doc in documentos:
        titulo = documentos_web.acentuar(doc.get("titulo_documento") or doc.get("tipo_documento") or "Documento")
        membro = nomes.get(doc.get("membro_id"), "")
        itens.append({
            "id": doc["id"],
            "titulo": titulo,
            "tipo": doc.get("tipo_documento") or "",
            "membro_id": doc.get("membro_id"),
            "membro": membro,
            "data": formatar_data_hora(doc.get("data_emissao")),
            "usuario": doc.get("usuario_emissor") or "",
            "disponivel": bool(documentos_web.caminho_pdf_seguro(doc.get("caminho_arquivo"))),
            "_busca": normalizar_texto_busca(" ".join([
                titulo, doc.get("tipo_documento") or "", membro, doc.get("usuario_emissor") or "",
            ])),
        })
    termo = normalizar_texto_busca(termo)
    if termo:
        itens = [i for i in itens if termo in i["_busca"]][:LIMITE_BUSCA]
    else:
        itens = itens[:LIMITE_PADRAO]
    for i in itens:
        i.pop("_busca")
    return itens


def registrar_rotas_central_documentos(app, exige_login, dados_igreja, menu_usuario):
    @app.get("/documentos")
    @exige_login
    def pagina_central_documentos():
        return render_template(
            "central_documentos.html",
            igreja=dados_igreja(),
            sistema=configuracoes.NOME_SISTEMA,
            usuario=session.get("usuario"),
            menu=menu_usuario("documentos"),
        )

    @app.get("/api/documentos-emitidos")
    @exige_login
    def api_central_documentos():
        termo = (request.args.get("q") or "").strip()
        return jsonify(total=total_documentos_emitidos(), itens=listar_central(termo),
                       filtrado=bool(termo))

    @app.post("/api/documentos-emitidos/<int:id_documento>/excluir")
    @exige_login
    def api_excluir_documento_emitido(id_documento):
        """Remove o registro do historico (como no desktop); o PDF so e apagado se pedido."""
        dados = request.get_json(silent=True) or {}
        apagar_pdf = bool(dados.get("fisico"))
        doc = buscar_documento_emitido_por_id(id_documento)
        if not doc:
            return jsonify(ok=False, mensagem="Documento não encontrado."), 404
        arquivo_apagado = False
        if apagar_pdf:
            arquivo = documentos_web.caminho_pdf_seguro(doc.get("caminho_arquivo"))
            pasta = documentos_web.pasta_saida().resolve()
            if arquivo and arquivo.resolve().parent == pasta:
                try:
                    arquivo.unlink()
                    arquivo_apagado = True
                except OSError:
                    return jsonify(ok=False, mensagem="Não foi possível apagar o arquivo PDF."), 500
        excluir_registro_documento(id_documento)
        titulo = doc.get("titulo_documento") or doc.get("tipo_documento") or "Documento"
        registrar_acao(
            "HISTORICO_DOCUMENTO_EXCLUIDO",
            f"Registro do historico excluido: {titulo}.",
            modulo="Documentos", registro_id=id_documento,
            detalhes=f"Arquivo: {doc.get('caminho_arquivo') or ''}; PDF apagado: {'sim' if arquivo_apagado else 'não'} (versão web)",
        )
        return jsonify(ok=True, arquivo_apagado=arquivo_apagado)
