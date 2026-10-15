"""Arquivos anexados ao membro (RG, CPF, certidoes...) na versao web.

Usa as mesmas funcoes de banco e a mesma pasta do desktop
(<dados>/arquivos_membros/membro_000001/documentos|imagens).
"""

import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path

from flask import abort, jsonify, request, send_file, session

from banco.database import (
    atualizar_titulo_arquivo_membro,
    buscar_arquivo_membro_por_id,
    buscar_membro_por_id,
    excluir_registro_arquivo,
    listar_arquivos_membro,
    registrar_arquivo_membro,
)
from utils.auditoria import registrar_acao
from utils.caminhos import caminho_dados
from utils.formatadores import formatar_data_hora

EXTENSOES_PERMITIDAS = {".pdf", ".png", ".jpg", ".jpeg"}
# Mesmos valores gravados pelo desktop (sem acento); o rotulo e so para exibir.
TIPOS_ARQUIVO = [
    ("RG", "RG"), ("CPF", "CPF"),
    ("Certidao de Batismo", "Certidão de Batismo"),
    ("Carta de Mudanca", "Carta de Mudança"),
    ("Certificado", "Certificado"),
    ("Comprovante de Endereco", "Comprovante de Endereço"),
    ("Foto", "Foto"), ("Outro", "Outro"),
]
ROTULO_TIPO = dict(TIPOS_ARQUIVO)
ASSINATURAS = {
    ".pdf": (b"%PDF",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
}
TIPOS_MIME = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def pasta_arquivos():
    return caminho_dados("arquivos_membros", criar_pai=False)


def limpar_nome(valor):
    texto = unicodedata.normalize("NFD", str(valor or "").strip().lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", texto).strip("_") or "arquivo"


def dentro_da_pasta(caminho):
    try:
        Path(caminho).resolve().relative_to(pasta_arquivos().resolve())
        return True
    except (ValueError, OSError):
        return False


def caminho_servivel(arquivo):
    """Arquivo existente e dentro da pasta de anexos (ou None)."""
    texto = str((arquivo or {}).get("caminho_arquivo") or "").strip()
    if not texto or "\x00" in texto:
        return None
    caminho = Path(texto)
    if caminho.suffix.lower() not in EXTENSOES_PERMITIDAS or not dentro_da_pasta(caminho):
        return None
    return caminho if caminho.is_file() else None


def _validar_envio(nome_original, conteudo):
    extensao = Path(nome_original or "").suffix.lower()
    if extensao not in EXTENSOES_PERMITIDAS:
        raise ValueError("Formato não permitido. Use apenas PDF, PNG, JPG ou JPEG.")
    if not conteudo:
        raise ValueError("O arquivo está vazio.")
    if not any(conteudo.startswith(a) for a in ASSINATURAS[extensao]):
        raise ValueError("O conteúdo não corresponde ao formato do arquivo.")
    return extensao


def _copiar_para_membro(id_membro, tipo, extensao, conteudo):
    subpasta = "documentos" if extensao == ".pdf" else "imagens"
    destino_pasta = pasta_arquivos() / f"membro_{int(id_membro):06d}" / subpasta
    destino_pasta.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = limpar_nome(tipo)
    destino = destino_pasta / f"{base}_{carimbo}{extensao}"
    contador = 1
    while destino.exists():
        destino = destino_pasta / f"{base}_{carimbo}_{contador}{extensao}"
        contador += 1
    destino.write_bytes(conteudo)
    return destino


def _descrever(arquivo):
    return {
        "id": arquivo["id"],
        "tipo": arquivo.get("tipo_arquivo") or "",
        "tipo_rotulo": ROTULO_TIPO.get(arquivo.get("tipo_arquivo"), arquivo.get("tipo_arquivo") or ""),
        "titulo": arquivo.get("titulo") or "",
        "nome_original": arquivo.get("nome_original") or "",
        "data": formatar_data_hora(arquivo.get("data_anexo")),
        "usuario": arquivo.get("usuario_responsavel") or "",
        "observacao": arquivo.get("observacao") or "",
        "eh_imagem": Path(arquivo.get("caminho_arquivo") or "").suffix.lower() in {".png", ".jpg", ".jpeg"},
        "disponivel": caminho_servivel(arquivo) is not None,
    }


def registrar_rotas_arquivos_membro(app, exige_login):
    def _usuario():
        usuario = session.get("usuario") or {}
        return usuario.get("nome") or usuario.get("login") or ""

    @app.get("/api/membros/<int:id_membro>/arquivos")
    @exige_login
    def api_arquivos_listar(id_membro):
        if not buscar_membro_por_id(id_membro):
            abort(404)
        return jsonify(
            tipos=[{"valor": v, "rotulo": r} for v, r in TIPOS_ARQUIVO],
            itens=[_descrever(a) for a in listar_arquivos_membro(id_membro)],
        )

    @app.post("/api/membros/<int:id_membro>/arquivos")
    @exige_login
    def api_arquivos_anexar(id_membro):
        membro = buscar_membro_por_id(id_membro)
        if not membro:
            abort(404)
        arquivo = request.files.get("arquivo")
        tipo = (request.form.get("tipo") or "").strip()
        titulo = (request.form.get("titulo") or "").strip()
        observacao = (request.form.get("observacao") or "").strip()
        if not arquivo or not arquivo.filename:
            return jsonify(ok=False, mensagem="Escolha um arquivo."), 400
        if tipo not in ROTULO_TIPO:
            return jsonify(ok=False, mensagem="Informe o tipo do arquivo."), 400
        if not titulo:
            return jsonify(ok=False, mensagem="Informe o título do arquivo."), 400
        conteudo = arquivo.read()
        try:
            extensao = _validar_envio(arquivo.filename, conteudo)
        except ValueError as erro:
            return jsonify(ok=False, mensagem=str(erro)), 400
        destino = _copiar_para_membro(id_membro, tipo, extensao, conteudo)
        try:
            id_arquivo = registrar_arquivo_membro(
                membro_id=id_membro, tipo_arquivo=tipo, titulo=titulo,
                nome_original=Path(arquivo.filename).name, caminho_arquivo=str(destino),
                usuario_responsavel=_usuario(), observacao=observacao,
            )
        except Exception:
            destino.unlink(missing_ok=True)
            return jsonify(ok=False, mensagem="Não foi possível registrar o arquivo."), 500
        nome = membro[1] if not isinstance(membro, dict) else membro.get("nome")
        registrar_acao("ARQUIVO_ANEXADO", f"Arquivo {titulo} anexado ao membro {nome}.",
                       modulo="Arquivos do Membro", registro_id=id_arquivo,
                       detalhes=f"Arquivo: {destino}")
        return jsonify(ok=True, id=id_arquivo, mensagem="Arquivo anexado.")

    def _buscar(id_arquivo):
        arquivo = buscar_arquivo_membro_por_id(id_arquivo)
        if not arquivo:
            abort(404)
        return arquivo

    @app.put("/api/arquivos-membro/<int:id_arquivo>")
    @exige_login
    def api_arquivo_renomear(id_arquivo):
        arquivo = _buscar(id_arquivo)
        titulo = str((request.get_json(silent=True) or {}).get("titulo") or "").strip()
        if not titulo:
            return jsonify(ok=False, mensagem="Informe o título."), 400
        atualizar_titulo_arquivo_membro(id_arquivo, titulo)
        registrar_acao("TITULO_ARQUIVO_ALTERADO", f"Titulo de arquivo alterado para {titulo}.",
                       modulo="Arquivos do Membro", registro_id=id_arquivo,
                       detalhes=f"Titulo anterior: {arquivo.get('titulo') or ''}")
        return jsonify(ok=True, mensagem="Título atualizado.")

    @app.post("/api/arquivos-membro/<int:id_arquivo>/excluir")
    @exige_login
    def api_arquivo_excluir(id_arquivo):
        arquivo = _buscar(id_arquivo)
        fisico = bool((request.get_json(silent=True) or {}).get("fisico"))
        caminho = Path(arquivo.get("caminho_arquivo") or "")
        apagou_arquivo = False
        if fisico and dentro_da_pasta(caminho) and caminho.is_file():
            caminho.unlink()
            apagou_arquivo = True
        excluir_registro_arquivo(id_arquivo)
        rotulo = arquivo.get("titulo") or arquivo.get("tipo_arquivo") or "arquivo"
        if fisico:
            registrar_acao("ARQUIVO_REGISTRO_E_FISICO_EXCLUIDOS",
                           f"Registro e arquivo fisico excluidos: {rotulo}.",
                           modulo="Arquivos do Membro", registro_id=id_arquivo,
                           detalhes=f"Arquivo: {caminho}")
        else:
            registrar_acao("REGISTRO_ARQUIVO_EXCLUIDO", f"Registro de arquivo excluido: {rotulo}.",
                           modulo="Arquivos do Membro", registro_id=id_arquivo,
                           detalhes=f"Arquivo: {caminho}")
        return jsonify(ok=True, arquivo_apagado=apagou_arquivo,
                       mensagem="Arquivo excluído." if fisico else "Registro excluído; o arquivo foi mantido no disco.")

    @app.get("/api/arquivos-membro/<int:id_arquivo>/arquivo")
    @exige_login
    def api_arquivo_baixar(id_arquivo):
        arquivo = _buscar(id_arquivo)
        caminho = caminho_servivel(arquivo)
        if not caminho:
            abort(404)
        baixar = request.args.get("baixar") == "1"
        nome = Path(arquivo.get("nome_original") or caminho.name).name
        resposta = send_file(caminho, mimetype=TIPOS_MIME[caminho.suffix.lower()],
                             as_attachment=baixar, download_name=nome)
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        return resposta
