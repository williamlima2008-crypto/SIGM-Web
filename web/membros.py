"""
SIGM Web - rotas de Membros (lista, ficha, edicao, cadastro e foto).

Nao reimplementa regra de negocio: usa as mesmas funcoes de banco/ e
documentos/ da versao desktop (cadastrar_membro, atualizar_membro,
excluir_membro, buscar_caminho_foto_membro...).
"""

import io
import re
import unicodedata
from pathlib import Path

from flask import abort, jsonify, render_template, request, send_file, session

from banco.database import (
    atualizar_membro,
    listar_documentos_emitidos_por_membro,
    registrar_documento_emitido,
    buscar_data_funcao_membro,
    buscar_membro_por_id,
    cadastrar_membro,
    conectar,
    excluir_membro,
    garantir_coluna_foto_membro,
    garantir_colunas_complementares_membro,
    garantir_tabela_documentos_emitidos,
)
from config import configuracoes
from documentos.datas import CAMPOS_DATA_BR, normalizar_campo_data, separar_data_documento
from documentos.integrador_documentos import (
    EXTENSOES_FOTO_MEMBRO,
    PASTA_FOTOS_MEMBROS,
    buscar_caminho_foto_membro,
)
from utils.auditoria import registrar_acao
from utils.formatadores import (
    formatar_cpf,
    formatar_data_hora,
    formatar_rg,
    normalizar_texto_busca,
)
from web import documentos_web

try:
    from PIL import Image, ImageOps, UnidentifiedImageError
except ImportError:  # pragma: no cover - Pillow faz parte dos requisitos
    Image = None
    ImageOps = None
    UnidentifiedImageError = Exception

# Mesma ordem do SELECT de banco.database.buscar_membro_por_id.
CAMPOS_FICHA = (
    "id", "nome", "rg", "orgao_emissor", "cpf", "data_nascimento",
    "estado_civil", "profissao", "telefone", "celular", "email",
    "endereco", "numero", "bairro", "cidade", "estado",
    "batismo_aguas", "ministerio", "cargo", "status", "observacoes",
    "nome_pai", "nome_mae", "cidade_nascimento", "estado_nascimento",
    "nome_conjuge", "data_nascimento_conjuge", "grau_instrucao",
    "curso_teologico", "data_batismo_espirito_santo", "cep",
)
CAMPOS_EDITAVEIS = tuple(c for c in CAMPOS_FICHA if c != "id") + ("data_funcao",)

ROTULOS_MEMBRO = {
    "id": "Código",
    "nome": "Nome completo",
    "rg": "RG",
    "orgao_emissor": "Órgão emissor",
    "cpf": "CPF",
    "data_nascimento": "Data de nascimento",
    "cidade_nascimento": "Cidade de nascimento",
    "estado_nascimento": "Estado / UF de nascimento",
    "estado_civil": "Estado civil",
    "nome_conjuge": "Nome do cônjuge",
    "data_nascimento_conjuge": "Nascimento do cônjuge",
    "profissao": "Profissão",
    "nome_pai": "Nome do pai",
    "nome_mae": "Nome da mãe",
    "grau_instrucao": "Grau de instrução",
    "telefone": "Telefone",
    "celular": "Celular / WhatsApp",
    "email": "E-mail",
    "endereco": "Rua / Logradouro",
    "numero": "Número",
    "bairro": "Bairro",
    "cidade": "Cidade",
    "estado": "Estado / UF",
    "cep": "CEP",
    "batismo_aguas": "Batismo nas águas",
    "data_batismo_espirito_santo": "Batismo no Espírito Santo",
    "ministerio": "Ministério",
    "cargo": "Cargo / Função atual",
    "data_funcao": "Data da função atual",
    "curso_teologico": "Curso teológico",
    "status": "Status do membro",
    "observacoes": "Observações",
}

SECOES_MEMBRO = (
    ("Dados pessoais", ("nome", "rg", "orgao_emissor", "cpf", "data_nascimento",
                        "cidade_nascimento", "estado_nascimento", "estado_civil",
                        "profissao", "grau_instrucao")),
    ("Família", ("nome_pai", "nome_mae", "nome_conjuge", "data_nascimento_conjuge")),
    ("Contato", ("telefone", "celular", "email")),
    ("Endereço", ("endereco", "numero", "bairro", "cidade", "estado", "cep")),
    ("Igreja", ("status", "cargo", "data_funcao", "ministerio", "batismo_aguas",
                "data_batismo_espirito_santo", "curso_teologico")),
    ("Observações", ("observacoes",)),
)

CAMPOS_DATA = {
    "data_funcao": "Data da função atual",
    "data_nascimento_conjuge": "Data de nascimento do cônjuge",
    "data_batismo_espirito_santo": "Data do batismo no Espírito Santo",
}
CAMPOS_MASCARA_DATA = (
    "data_nascimento", "batismo_aguas", "data_funcao",
    "data_nascimento_conjuge", "data_batismo_espirito_santo",
)

FUNCOES_ATUAIS = ["Nenhuma", "Cooperador", "Diácono", "Presbítero", "Evangelista", "Pastor"]
STATUS_MEMBRO = ["Membro", "Congregado", "Visitante", "Em discipulado", "Inativo"]

LADO_MAXIMO_FOTO = 1600


def _sem_acento(valor):
    texto = unicodedata.normalize("NFD", str(valor or "").strip().lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def normalizar_funcao(valor):
    chave = _sem_acento(valor)
    for funcao in FUNCOES_ATUAIS:
        if _sem_acento(funcao) == chave:
            return funcao
    return "Nenhuma"


def _digitos(valor):
    return re.sub(r"\D", "", str(valor or ""))


def formatar_cep(valor):
    digitos = _digitos(valor)[:8]
    return digitos if len(digitos) <= 5 else f"{digitos[:5]}-{digitos[5:]}"


def membro_para_dict(id_membro):
    """Dados completos do membro (mesmos campos da ficha desktop) ou None."""
    linha = buscar_membro_por_id(id_membro)
    if not linha:
        return None
    dados = {
        campo: ("" if valor is None else str(valor))
        for campo, valor in zip(CAMPOS_FICHA, tuple(linha))
    }
    dados["id"] = int(linha[0])
    dados["data_funcao"] = str(buscar_data_funcao_membro(id_membro) or "")
    dados["cargo"] = normalizar_funcao(dados.get("cargo"))
    for campo in CAMPOS_DATA_BR:
        if campo in dados:
            dados[campo] = normalizar_campo_data(campo, dados[campo])
    return dados


def validar_e_normalizar(dados):
    """Mesmas regras do cadastro desktop. Devolve (dados, erro)."""
    dados = {c: str(dados.get(c) or "").strip() for c in CAMPOS_EDITAVEIS}
    if not dados["nome"]:
        return None, "O campo Nome completo é obrigatório."
    for campo, rotulo in CAMPOS_DATA.items():
        valor = dados[campo]
        if valor and separar_data_documento(valor) == ("", "", ""):
            return None, f"{rotulo} inválida. Use DD/MM/AAAA."
    if dados["cep"] and len(_digitos(dados["cep"])) != 8:
        return None, "CEP inválido. Use 00000-000."
    for campo in CAMPOS_DATA_BR:
        if campo in dados:
            dados[campo] = normalizar_campo_data(campo, dados[campo])
    dados["cpf"] = formatar_cpf(dados["cpf"])
    dados["rg"] = formatar_rg(dados["rg"])
    dados["cep"] = formatar_cep(dados["cep"])
    dados["cargo"] = normalizar_funcao(dados["cargo"])
    dados["status"] = dados["status"] or "Membro"
    return dados, ""


def _lista_resumo():
    conexao = conectar()
    try:
        cursor = conexao.cursor()
        cursor.execute(
            """
            SELECT id, nome, celular, telefone, cidade, status, cargo, cpf, email
            FROM membros
            ORDER BY nome COLLATE NOCASE ASC
            """
        )
        linhas = cursor.fetchall()
    finally:
        conexao.close()
    itens = []
    for linha in linhas:
        id_, nome, celular, telefone, cidade, status, cargo, cpf, email = tuple(linha)
        cargo = normalizar_funcao(cargo) if str(cargo or "").strip() else "Nenhuma"
        itens.append({
            "id": id_,
            "nome": nome or "",
            "celular": celular or telefone or "",
            "cidade": cidade or "",
            "status": status or "",
            "cargo": "" if cargo == "Nenhuma" else cargo,
            "_busca": normalizar_texto_busca(
                " ".join(str(v or "") for v in (nome, cpf, celular, telefone, email, cidade))
            ),
            "_digitos": _digitos(f"{cpf} {celular} {telefone}"),
        })
    return itens


def _arquivos_foto(id_membro):
    if not PASTA_FOTOS_MEMBROS.exists():
        return []
    return [
        a for a in PASTA_FOTOS_MEMBROS.glob(f"foto_{id_membro}.*")
        if a.is_file()
    ]


def _caminho_foto_valido(id_membro):
    caminho = buscar_caminho_foto_membro(id_membro)
    if not caminho:
        return None
    arquivo = Path(caminho)
    if arquivo.suffix.lower() not in EXTENSOES_FOTO_MEMBRO or not arquivo.is_file():
        return None
    return arquivo


def _gravar_coluna_foto(id_membro, caminho):
    coluna = garantir_coluna_foto_membro()
    conexao = conectar()
    try:
        conexao.execute(
            f'UPDATE membros SET "{coluna}" = ? WHERE id = ?', (caminho, id_membro)
        )
        conexao.commit()
    finally:
        conexao.close()


def salvar_foto_membro(id_membro, conteudo):
    """Valida a imagem, corrige a rotacao do celular e grava foto_<id>.jpg.

    Devolve o caminho salvo. Levanta ValueError com mensagem para o usuario.
    """
    if Image is None:
        raise ValueError("Não foi possível processar imagens neste computador.")
    try:
        with Image.open(io.BytesIO(conteudo)) as original:
            original.load()
            imagem = ImageOps.exif_transpose(original)
            if imagem.mode in ("RGBA", "LA", "P"):
                imagem = imagem.convert("RGBA")
                fundo = Image.new("RGB", imagem.size, (255, 255, 255))
                fundo.paste(imagem, mask=imagem.split()[-1])
                imagem = fundo
            else:
                imagem = imagem.convert("RGB")
            imagem.thumbnail((LADO_MAXIMO_FOTO, LADO_MAXIMO_FOTO))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ValueError("Esse arquivo não é uma imagem válida. Use JPG, PNG ou WEBP.")

    PASTA_FOTOS_MEMBROS.mkdir(parents=True, exist_ok=True)
    for antigo in _arquivos_foto(id_membro):
        try:
            antigo.unlink()
        except OSError:
            pass
    destino = PASTA_FOTOS_MEMBROS / f"foto_{id_membro}.jpg"
    imagem.save(destino, "JPEG", quality=90, optimize=True)
    _gravar_coluna_foto(id_membro, str(destino))
    return str(destino)


def remover_foto_membro(id_membro):
    for arquivo in _arquivos_foto(id_membro):
        try:
            arquivo.unlink()
        except OSError:
            pass
    _gravar_coluna_foto(id_membro, "")


def registrar_rotas_membros(app, exige_login, dados_igreja, menu_usuario):
    @app.get("/membros")
    @exige_login
    def pagina_membros():
        return render_template(
            "membros.html",
            igreja=dados_igreja(),
            sistema=configuracoes.NOME_SISTEMA,
            usuario=session.get("usuario"),
            menu=menu_usuario("membros"),
            rotulos=ROTULOS_MEMBRO,
            secoes=SECOES_MEMBRO,
            campos_data=list(CAMPOS_MASCARA_DATA),
            funcoes=FUNCOES_ATUAIS,
            status_padrao=STATUS_MEMBRO,
        )

    @app.get("/api/membros")
    @exige_login
    def api_membros():
        termo = normalizar_texto_busca(request.args.get("q"))
        digitos = _digitos(request.args.get("q"))
        status = (request.args.get("status") or "").strip()
        todos = _lista_resumo()

        contagem = {"todos": len(todos)}
        for item in todos:
            chave = item["status"] or "Sem status"
            contagem[chave] = contagem.get(chave, 0) + 1

        itens = []
        for item in todos:
            if status and (item["status"] or "Sem status") != status:
                continue
            if termo and termo not in item["_busca"] and not (
                len(digitos) >= 3 and digitos in item["_digitos"]
            ):
                continue
            itens.append({k: v for k, v in item.items() if not k.startswith("_")})
        return jsonify(itens=itens, contagem=contagem)

    def membro_ou_404(id_membro):
        dados = membro_para_dict(id_membro)
        if not dados:
            abort(404)
        return dados

    @app.get("/api/membros/<int:id_membro>")
    @exige_login
    def api_membro(id_membro):
        dados = membro_ou_404(id_membro)
        foto = _caminho_foto_valido(id_membro)
        versao = int(foto.stat().st_mtime) if foto else 0
        return jsonify(
            id=id_membro,
            campos=dados,
            tem_foto=bool(foto),
            versao_foto=versao,
        )

    @app.post("/api/membros")
    @exige_login
    def api_cadastrar():
        dados, erro = validar_e_normalizar(request.get_json(silent=True) or {})
        if erro:
            return jsonify(ok=False, mensagem=erro), 400
        try:
            id_membro = cadastrar_membro(dados)
        except Exception as e:
            return jsonify(ok=False, mensagem=f"Não foi possível salvar o membro: {e}"), 500
        registrar_acao(
            "CADASTRO_MEMBRO", f"Membro {dados['nome']} cadastrado.",
            modulo="Membros", registro_id=id_membro,
        )
        return jsonify(ok=True, id=id_membro, mensagem="Membro cadastrado.")

    @app.put("/api/membros/<int:id_membro>")
    @exige_login
    def api_atualizar(id_membro):
        atual = membro_ou_404(id_membro)
        recebido = request.get_json(silent=True) or {}
        mesclado = {c: atual.get(c, "") for c in CAMPOS_EDITAVEIS}
        mesclado.update({c: recebido[c] for c in CAMPOS_EDITAVEIS if c in recebido})
        dados, erro = validar_e_normalizar(mesclado)
        if erro:
            return jsonify(ok=False, mensagem=erro), 400
        try:
            atualizar_membro(id_membro, dados)
        except Exception as e:
            return jsonify(ok=False, mensagem=f"Não foi possível salvar o membro: {e}"), 500
        registrar_acao(
            "EDICAO_MEMBRO", f"Membro {dados['nome']} atualizado.",
            modulo="Membros", registro_id=id_membro,
            detalhes=(
                f"Funcao atual: {dados.get('cargo') or 'Nenhuma'}; "
                f"Data da funcao: {dados.get('data_funcao') or ''}"
            ),
        )
        if str(atual.get("observacoes") or "") != str(dados.get("observacoes") or ""):
            registrar_acao(
                "ALTERACAO_OBSERVACOES_MEMBRO",
                f"Observacoes do membro {dados['nome']} foram alteradas.",
                modulo="Membros", registro_id=id_membro,
            )
        return jsonify(ok=True, mensagem="Dados salvos.")

    @app.post("/api/membros/<int:id_membro>/excluir")
    @exige_login
    def api_excluir_membro(id_membro):
        atual = membro_ou_404(id_membro)
        try:
            excluir_membro(id_membro)
        except Exception as e:
            return jsonify(ok=False, mensagem=f"Não foi possível excluir o membro: {e}"), 500
        for arquivo in _arquivos_foto(id_membro):
            try:
                arquivo.unlink()
            except OSError:
                pass
        registrar_acao(
            "EXCLUSAO_MEMBRO", f"Membro {atual.get('nome') or id_membro} excluido.",
            modulo="Membros", registro_id=id_membro,
        )
        return jsonify(ok=True, mensagem="Membro excluído.")

    # ------------------------------------------------------------- foto
    @app.get("/api/membros/<int:id_membro>/foto")
    @exige_login
    def api_foto_membro(id_membro):
        membro_ou_404(id_membro)
        arquivo = _caminho_foto_valido(id_membro)
        if not arquivo:
            abort(404)
        return send_file(arquivo)

    @app.post("/api/membros/<int:id_membro>/foto")
    @exige_login
    def api_enviar_foto(id_membro):
        atual = membro_ou_404(id_membro)
        arquivo = request.files.get("foto")
        if not arquivo or not arquivo.filename:
            return jsonify(ok=False, mensagem="Escolha uma foto."), 400
        try:
            salvar_foto_membro(id_membro, arquivo.read())
        except ValueError as erro:
            return jsonify(ok=False, mensagem=str(erro)), 400
        except Exception as erro:
            return jsonify(ok=False, mensagem=f"Não foi possível salvar a foto: {erro}"), 500
        registrar_acao(
            "FOTO_MEMBRO_ALTERADA", f"Foto do membro {atual.get('nome')} alterada.",
            modulo="Membros", registro_id=id_membro,
        )
        return jsonify(ok=True, mensagem="Foto salva.")

    @app.delete("/api/membros/<int:id_membro>/foto")
    @exige_login
    def api_remover_foto(id_membro):
        atual = membro_ou_404(id_membro)
        try:
            remover_foto_membro(id_membro)
        except Exception as erro:
            return jsonify(ok=False, mensagem=f"Não foi possível remover a foto: {erro}"), 500
        registrar_acao(
            "FOTO_MEMBRO_REMOVIDA", f"Foto do membro {atual.get('nome')} removida.",
            modulo="Membros", registro_id=id_membro,
        )
        return jsonify(ok=True, mensagem="Foto removida.")

    # -------------------------------------------------------- documentos
    def _historico(id_membro):
        itens = []
        for doc in listar_documentos_emitidos_por_membro(id_membro):
            doc = dict(doc)
            itens.append({
                "id": doc.get("id"),
                "titulo": documentos_web.acentuar(
                    doc.get("titulo_documento") or doc.get("tipo_documento") or ""
                ),
                "data": formatar_data_hora(doc.get("data_emissao")),
                "usuario": doc.get("usuario_emissor") or "",
                "disponivel": bool(documentos_web.caminho_pdf_seguro(doc.get("caminho_arquivo"))),
            })
        return itens

    @app.get("/api/membros/<int:id_membro>/documentos")
    @exige_login
    def api_documentos_membro(id_membro):
        membro_ou_404(id_membro)
        return jsonify(catalogo=list(documentos_web.CATALOGO), historico=_historico(id_membro))

    @app.get("/api/membros/<int:id_membro>/documentos/<slug>/formulario")
    @exige_login
    def api_formulario_documento(id_membro, slug):
        membro_ou_404(id_membro)
        try:
            return jsonify(documentos_web.descrever_formulario(slug, id_membro))
        except documentos_web.DocumentoErro as erro:
            return jsonify(ok=False, mensagem=str(erro)), 404
        except Exception as erro:
            return jsonify(ok=False, mensagem=f"Não foi possível preparar o documento: {erro}"), 500

    @app.post("/api/membros/<int:id_membro>/documentos/<slug>")
    @exige_login
    def api_gerar_documento(id_membro, slug):
        atual = membro_ou_404(id_membro)
        if slug not in documentos_web.TITULOS:
            return jsonify(ok=False, mensagem="Documento desconhecido."), 404
        valores = request.get_json(silent=True) or {}
        try:
            caminho, tipo, titulo, observacao = documentos_web.gerar_documento(
                slug, id_membro, valores
            )
        except documentos_web.DocumentoErro as erro:
            return jsonify(ok=False, mensagem=str(erro)), 400
        except Exception as erro:
            registrar_acao(
                "FALHA_GERAR_DOCUMENTO", f"Falha ao gerar {documentos_web.TITULOS[slug]}.",
                modulo="Documentos", registro_id=id_membro, detalhes=str(erro),
            )
            return jsonify(ok=False, mensagem=f"Não foi possível gerar o documento: {erro}"), 500

        usuario = session.get("usuario") or {}
        id_documento = None
        try:
            id_documento = registrar_documento_emitido(
                membro_id=id_membro, tipo_documento=tipo, titulo_documento=titulo,
                caminho_arquivo=str(Path(caminho).resolve()),
                usuario_emissor=usuario.get("nome") or usuario.get("login") or "",
                observacao=observacao,
            )
            registrar_acao(
                "DOCUMENTO_HISTORICO_REGISTRADO", f"{titulo} registrado no historico.",
                modulo="Documentos", registro_id=id_documento, detalhes=f"Arquivo: {caminho}",
            )
        except Exception as erro:
            registrar_acao(
                "FALHA_REGISTRO_HISTORICO_DOCUMENTO",
                f"Falha ao registrar historico de {titulo}.",
                modulo="Documentos", registro_id=id_membro, detalhes=str(erro),
            )
        registrar_acao(
            "PDF_GERADO", f"{titulo} gerado para {atual.get('nome')}.",
            modulo="Documentos", registro_id=id_documento or id_membro,
            detalhes=f"Arquivo: {caminho}",
        )
        if id_documento is None:
            return jsonify(ok=False, mensagem="O PDF foi gerado, mas não foi possível registrá-lo no histórico."), 500
        return jsonify(
            ok=True, id_documento=id_documento, mensagem=f"PDF gerado: {titulo}.",
            url=f"/api/documentos-emitidos/{id_documento}/arquivo",
        )

    @app.get("/api/documentos-emitidos/<int:id_documento>/arquivo")
    @exige_login
    def api_arquivo_documento(id_documento):
        garantir_tabela_documentos_emitidos()
        conexao = conectar()
        try:
            linha = conexao.execute(
                "SELECT caminho_arquivo, titulo_documento FROM documentos_emitidos WHERE id = ?",
                (id_documento,),
            ).fetchone()
        finally:
            conexao.close()
        if not linha:
            abort(404)
        arquivo = documentos_web.caminho_pdf_seguro(linha[0])
        if not arquivo:
            abort(404)
        baixar = request.args.get("baixar") == "1"
        return send_file(arquivo, mimetype="application/pdf", as_attachment=baixar,
                         download_name=arquivo.name)
