"""
Dados da igreja na versao web.

Reaproveita buscar/salvar_configuracoes_igreja do desktop (mesma tabela,
mesmos campos) e grava logotipo, carimbo e assinatura em
<dados>/imagens_igreja/, guardando o caminho no banco como o desktop faz.
"""

import io
from pathlib import Path

from flask import abort, jsonify, render_template, request, send_file, session

from banco.database import buscar_configuracoes_igreja, salvar_configuracoes_igreja
from config import configuracoes
from utils.auditoria import registrar_acao
from utils.caminhos import base_dados, caminho_dados, caminho_recurso

try:
    from PIL import Image, ImageOps, UnidentifiedImageError
except ImportError:  # pragma: no cover
    Image = None

LADO_MAXIMO_IMAGEM = 1600
LOGO_PADRAO = caminho_recurso("assets", "logo", "logo.png")

OBRIGATORIOS = {
    "nome_igreja": "Nome da Igreja",
    "ministerio": "Ministério",
    "cidade": "Cidade",
    "estado": "Estado",
}

IMAGENS = {
    "logotipo": ("Logotipo da Igreja", "LOGOTIPO_ALTERADO", "Logotipo da igreja alterado."),
    "carimbo": ("Carimbo", "CARIMBO_ALTERADO", "Carimbo da igreja alterado."),
    "assinatura_pastor": (
        "Assinatura do Pastor", "ASSINATURA_PASTOR_ALTERADA", "Assinatura do pastor alterada.",
    ),
}

# Abas iguais as do desktop (sem os campos de secretarios, retirados do sistema).
ABAS = [
    ("identificacao", "Identificação", [
        ("nome_igreja", "Nome da Igreja"), ("ministerio", "Ministério"),
        ("convencao", "Convenção"), ("setor", "Setor"),
        ("congregacao_sede", "Congregação Sede"), ("cidade", "Cidade"), ("estado", "Estado"),
    ]),
    ("lideranca", "Liderança", [
        ("pastor_presidente", "Pastor Presidente"), ("pastor_setorial", "Pastor Setorial"),
    ]),
    ("contatos", "Contatos", [
        ("telefone", "Telefone"), ("whatsapp", "WhatsApp"),
        ("email", "E-mail"), ("site", "Site"),
    ]),
    ("congregacao-local", "Congregação Local", [
        ("congregacao_local_nome", "Nome da Congregação Local"),
        ("congregacao_local_dirigente", "Dirigente Local"),
        ("congregacao_local_numero", "Número da Congregação"),
        ("congregacao_local_campo_setor", "Campo/Setor"),
        ("congregacao_local_cidade", "Cidade da Congregação"),
        ("congregacao_local_estado", "Estado da Congregação"),
        ("congregacao_local_rua", "Rua"), ("congregacao_local_numero_endereco", "Número"),
        ("congregacao_local_bairro", "Bairro"), ("congregacao_local_cep", "CEP"),
        ("congregacao_local_telefone", "Telefone"),
        ("congregacao_local_whatsapp", "WhatsApp"), ("congregacao_local_email", "E-mail"),
    ]),
    ("endereco", "Endereço", [
        ("rua", "Endereço"), ("numero", "Número"), ("complemento", "Complemento"),
        ("bairro", "Bairro"), ("cep", "CEP"),
        ("cidade_endereco", "Cidade"), ("estado_endereco", "Estado"),
    ]),
    ("sistema", "Sistema", [
        ("tema", "Tema futuro"), ("versiculo_institucional", "Versículo institucional (opcional)"),
    ]),
]

CAMPOS_TEXTO = {campo: rotulo for _, _, campos in ABAS for campo, rotulo in campos}
ROTULOS = dict(CAMPOS_TEXTO)
ROTULOS.update({campo: dados[0] for campo, dados in IMAGENS.items()})

GRUPOS_AUDITORIA = {
    "DADOS_INSTITUCIONAIS_ALTERADOS": (
        "Dados institucionais da igreja alterados.",
        {"nome_igreja", "ministerio", "convencao", "setor", "congregacao_sede",
         "cidade", "estado", "versiculo_institucional"},
    ),
    "LIDERANCA_IGREJA_ALTERADA": (
        "Dados de lideranca da igreja alterados.",
        {"pastor_presidente", "pastor_setorial"},
    ),
    "CONTATOS_IGREJA_ALTERADOS": (
        "Contatos da igreja alterados.", {"telefone", "whatsapp", "email", "site"},
    ),
    "ENDERECO_IGREJA_ALTERADO": (
        "Endereco da igreja alterado.",
        {"rua", "numero", "complemento", "bairro", "cep", "cidade_endereco", "estado_endereco"},
    ),
    "DADOS_CONGREGACAO_LOCAL_ALTERADOS": (
        "Dados da congregacao local alterados.",
        {c for c in CAMPOS_TEXTO if c.startswith("congregacao_local_")},
    ),
}


def pasta_imagens():
    return caminho_dados("imagens_igreja", criar_pai=False)


def _normalizar_cep(valor):
    digitos = "".join(c for c in valor if c.isdigit())
    if not digitos:
        return ""
    if len(digitos) != 8:
        raise ValueError("CEP deve ter 8 números.")
    return f"{digitos[:5]}-{digitos[5:]}"


def validar_e_normalizar(enviado):
    """Devolve (campos_limpos, erro). So considera campos conhecidos."""
    limpos = {}
    for campo in CAMPOS_TEXTO:
        if campo in enviado:
            limpos[campo] = str(enviado.get(campo) or "").strip()
    for campo in ("estado", "estado_endereco", "congregacao_local_estado"):
        if limpos.get(campo):
            limpos[campo] = limpos[campo].upper()
    for campo in ("cep", "congregacao_local_cep"):
        if campo in limpos:
            try:
                limpos[campo] = _normalizar_cep(limpos[campo])
            except ValueError:
                return None, f"{ROTULOS[campo]} (CEP) deve ter 8 números."
    atual = buscar_configuracoes_igreja()
    final = {**atual, **limpos}
    faltando = [rotulo for campo, rotulo in OBRIGATORIOS.items() if not final.get(campo)]
    if faltando:
        return None, "Preencha os campos obrigatórios: " + ", ".join(faltando) + "."
    return limpos, None


def caminho_imagem(tipo):
    """Arquivo configurado para logotipo/carimbo/assinatura (ou None)."""
    valor = str(buscar_configuracoes_igreja().get(tipo) or "").strip()
    if valor:
        caminho = Path(valor).expanduser()
        if not caminho.is_absolute():
            caminho = base_dados() / caminho
        try:
            if caminho.is_file() and caminho.stat().st_size > 0:
                return caminho
        except OSError:
            pass
    if tipo == "logotipo":
        try:
            if LOGO_PADRAO.is_file():
                return Path(LOGO_PADRAO)
        except OSError:
            pass
    return None


def versao_imagem(tipo):
    caminho = caminho_imagem(tipo)
    try:
        return int(caminho.stat().st_mtime) if caminho else 0
    except OSError:
        return 0


def salvar_imagem(tipo, conteudo):
    if Image is None:
        raise ValueError("Não foi possível processar imagens neste computador.")
    try:
        with Image.open(io.BytesIO(conteudo)) as original:
            original.load()
            imagem = ImageOps.exif_transpose(original).convert("RGBA")
            imagem.thumbnail((LADO_MAXIMO_IMAGEM, LADO_MAXIMO_IMAGEM))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ValueError("Esse arquivo não é uma imagem válida. Use PNG, JPG ou WEBP.")
    pasta = pasta_imagens()
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{tipo}.png"
    imagem.save(destino, "PNG", optimize=True)
    return str(destino)


def _dentro_da_pasta(caminho):
    try:
        Path(caminho).resolve().relative_to(pasta_imagens().resolve())
        return True
    except (ValueError, OSError):
        return False


def _detalhes(campos):
    return "Campos alterados: " + ", ".join(ROTULOS.get(c, c) for c in campos) if campos else ""


def _registrar(dados_antes, dados_depois):
    alterados = [c for c in ROTULOS if (dados_antes.get(c) or "") != (dados_depois.get(c) or "")]
    if not alterados:
        return alterados
    registrar_acao("CONFIGURACOES_IGREJA_ALTERADAS", "Configuracoes da igreja alteradas.",
                   modulo="Configuracoes", registro_id=1, detalhes=_detalhes(alterados))
    for tipo, (_, acao, descricao) in IMAGENS.items():
        if tipo in alterados:
            registrar_acao(acao, descricao, modulo="Configuracoes", registro_id=1,
                           detalhes=_detalhes([tipo]))
    conjunto = set(alterados)
    for acao, (descricao, grupo) in GRUPOS_AUDITORIA.items():
        tocados = [c for c in alterados if c in grupo]
        if tocados and conjunto & grupo:
            registrar_acao(acao, descricao, modulo="Configuracoes", registro_id=1,
                           detalhes=_detalhes(tocados))
    return alterados


def registrar_rotas_igreja(app, exige_login, dados_igreja, menu_usuario):
    @app.get("/igreja")
    @exige_login
    def pagina_igreja():
        return render_template(
            "igreja.html",
            igreja=dados_igreja(),
            sistema=configuracoes.NOME_SISTEMA,
            usuario=session.get("usuario"),
            menu=menu_usuario("igreja"),
            abas=ABAS,
            obrigatorios=list(OBRIGATORIOS),
            imagens=[(t, d[0]) for t, d in IMAGENS.items()],
        )

    @app.get("/api/igreja")
    @exige_login
    def api_igreja():
        dados = buscar_configuracoes_igreja()
        return jsonify(
            campos={c: dados.get(c, "") for c in CAMPOS_TEXTO},
            imagens={t: {"tem": bool(str(dados.get(t) or "").strip()) and caminho_imagem(t) is not None,
                         "versao": versao_imagem(t)} for t in IMAGENS},
        )

    @app.put("/api/igreja")
    @exige_login
    def api_igreja_salvar():
        enviado = request.get_json(silent=True) or {}
        limpos, erro = validar_e_normalizar(enviado)
        if erro:
            return jsonify(ok=False, mensagem=erro), 400
        antes = buscar_configuracoes_igreja()
        salvar_configuracoes_igreja({**antes, **limpos})
        depois = buscar_configuracoes_igreja()
        alterados = _registrar(antes, depois)
        return jsonify(ok=True, alterados=len(alterados),
                       mensagem="Configurações da igreja salvas." if alterados
                       else "Nada mudou: os dados já estavam salvos.",
                       campos={c: depois.get(c, "") for c in CAMPOS_TEXTO})

    @app.post("/api/igreja/imagem/<tipo>")
    @exige_login
    def api_igreja_imagem_enviar(tipo):
        if tipo not in IMAGENS:
            abort(404)
        arquivo = request.files.get("arquivo")
        conteudo = arquivo.read() if arquivo else b""
        if not conteudo:
            return jsonify(ok=False, mensagem="Escolha uma imagem."), 400
        try:
            destino = salvar_imagem(tipo, conteudo)
        except ValueError as erro:
            return jsonify(ok=False, mensagem=str(erro)), 400
        antes = buscar_configuracoes_igreja()
        salvar_configuracoes_igreja({**antes, tipo: destino})
        _registrar(antes, buscar_configuracoes_igreja())
        return jsonify(ok=True, versao=versao_imagem(tipo),
                       mensagem=f"{IMAGENS[tipo][0]} atualizado.")

    @app.delete("/api/igreja/imagem/<tipo>")
    @exige_login
    def api_igreja_imagem_remover(tipo):
        if tipo not in IMAGENS:
            abort(404)
        antes = buscar_configuracoes_igreja()
        anterior = str(antes.get(tipo) or "").strip()
        salvar_configuracoes_igreja({**antes, tipo: ""})
        if anterior and _dentro_da_pasta(anterior):
            try:
                Path(anterior).unlink()
            except OSError:
                pass
        _registrar(antes, buscar_configuracoes_igreja())
        return jsonify(ok=True, mensagem=f"{IMAGENS[tipo][0]} removido.")

    @app.get("/igreja/imagem/<tipo>")
    @exige_login
    def igreja_imagem(tipo):
        if tipo not in IMAGENS:
            abort(404)
        caminho = caminho_imagem(tipo)
        if not caminho:
            abort(404)
        return send_file(caminho, max_age=0)

    @app.get("/igreja/logo")
    def igreja_logo():
        """Logo publica (tela de login e topo). Nao expõe carimbo nem assinatura."""
        caminho = caminho_imagem("logotipo")
        if not caminho:
            abort(404)
        resposta = send_file(caminho, max_age=0)
        resposta.headers["Cache-Control"] = "no-cache"
        return resposta
