"""
SIGM Web - servidor local.

Camada HTML/CSS do SIGM. Nao reimplementa regra de negocio: chama as
mesmas funcoes de banco/ e servicos/ usadas pela versao desktop.
"""

import ipaddress
import os
import secrets
import socket
import tempfile
import threading
import time
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from banco.database import (
    CAMPOS_CADASTRAIS_PRE_CADASTRO,
    atualizar_dados_pre_cadastro,
    atualizar_status_pre_cadastro,
    buscar_configuracoes_igreja,
    buscar_pre_cadastro_por_id,
    conectar,
    excluir_pre_cadastro,
    listar_campos_faltantes_pre_cadastro,
    listar_pre_cadastros,
    listar_usuarios,
    validar_login,
)
from config import configuracoes
from servicos.aprovacao_pre_cadastro import (
    aprovar_pre_cadastro,
    atualizar_membro_existente_com_pre_cadastro,
    caminho_foto_seguro,
    maior_nivel_duplicidade,
    rejeitar_pre_cadastro,
)
from servicos.duplicidade_membros import (
    detectar_duplicidades_pre_cadastro,
    normalizar_cpf,
    normalizar_rg,
)
from servicos.importador_pre_cadastro_json import (
    ImportacaoPreCadastroErro,
    importar_pre_cadastros_json,
)
from servicos.sincronizacao_pre_cadastro_online import sincronizar_pre_cadastros_online
from utils.auditoria import registrar_acao
from utils.caminhos import caminho_dados
from utils.sessao import iniciar_sessao, limpar_sessao
from web.auditoria import registrar_rotas_auditoria
from web.acesso import registrar_rotas_acesso
from web.arquivos_membro import registrar_rotas_arquivos_membro
from web.backup_web import registrar_rotas_backup
from web.central_documentos import registrar_rotas_central_documentos
from web.celular import registrar_rotas_celular
from web.configuracao_online import registrar_rotas_configuracao_online
from web import limite_tentativas
from web.igreja import registrar_rotas_igreja, versao_imagem
from web.membros import registrar_rotas_membros
from web.painel import registrar_rotas_painel
from web.relatorios import registrar_rotas_relatorios
from web.usuarios import registrar_rotas_usuarios

ROTULOS = {
    "nome": "Nome",
    "rg": "RG",
    "orgao_emissor": "Órgão emissor",
    "cpf": "CPF",
    "data_nascimento": "Data de nascimento",
    "cidade_nascimento": "Cidade de nascimento",
    "estado_nascimento": "Estado de nascimento",
    "estado_civil": "Estado civil",
    "nome_conjuge": "Nome do cônjuge",
    "data_nascimento_conjuge": "Nascimento do cônjuge",
    "profissao": "Profissão",
    "nome_pai": "Nome do pai",
    "nome_mae": "Nome da mãe",
    "grau_instrucao": "Grau de instrução",
    "telefone": "Telefone",
    "celular": "Celular",
    "email": "E-mail",
    "endereco": "Endereço",
    "numero": "Número",
    "bairro": "Bairro",
    "cidade": "Cidade",
    "estado": "Estado",
    "cep": "CEP",
    "batismo_aguas": "Batismo nas águas",
    "batismo_espirito_santo": "Batismo no Espírito Santo",
    "ministerio": "Ministério",
    "cargo": "Cargo",
    "data_funcao": "Data da função",
    "curso_teologico": "Curso teológico",
    "status_membro": "Status do membro",
    "congregacao": "Congregação",
    "dirigente": "Dirigente",
    "setor_campo": "Setor/Campo",
    "igreja_local_batismo_aguas": "Igreja do batismo nas águas",
    "igreja_local_batismo_espirito_santo": "Igreja do batismo no Espírito Santo",
    "recados_outros": "Recados/outros",
    "nome_titular_lgpd": "Nome do titular LGPD",
    "observacoes": "Observações",
    "caminho_foto": "Foto",
}

SECOES = (
    ("Dados pessoais", ("nome", "rg", "orgao_emissor", "cpf", "data_nascimento",
                        "cidade_nascimento", "estado_nascimento", "estado_civil",
                        "profissao", "grau_instrucao")),
    ("Família", ("nome_pai", "nome_mae", "nome_conjuge", "data_nascimento_conjuge")),
    ("Contato", ("telefone", "celular", "recados_outros", "email")),
    ("Endereço", ("endereco", "numero", "bairro", "cidade", "estado", "cep")),
    ("Igreja", ("batismo_aguas", "batismo_espirito_santo", "ministerio",
                        "cargo", "data_funcao", "curso_teologico", "status_membro",
                        "congregacao", "dirigente", "setor_campo",
                        "igreja_local_batismo_aguas",
                        "igreja_local_batismo_espirito_santo")),
    ("Informações adicionais", ("observacoes",)),
)

CAMPOS_COMPARACAO = (
    "nome", "cpf", "rg", "data_nascimento", "celular", "telefone",
    "email", "endereco", "cidade", "nome_mae",
)

EXTENSOES_FOTO = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

# O backend legado guarda a sessao em uma variavel global (utils.sessao).
# Para que cada requisicao use o usuario correto, as requisicoes sao
# atendidas uma de cada vez.
_trava_requisicao = threading.RLock()


def _chave_secreta():
    arquivo = Path(caminho_dados("web_chave_secreta.txt"))
    if arquivo.exists():
        texto = arquivo.read_text(encoding="utf-8").strip()
        if texto:
            return texto
    chave = secrets.token_hex(32)
    arquivo.write_text(chave, encoding="utf-8")
    return chave


def host_permitido(host):
    """So aceita IP, localhost e o nome deste computador (barra DNS rebinding)."""
    host = str(host or "").strip().lower()
    if host.startswith("["):
        nome = host[1:].split("]")[0]
    else:
        nome = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    try:
        ipaddress.ip_address(nome)
        return True
    except ValueError:
        pass
    try:
        meu_nome = socket.gethostname().lower()
    except OSError:
        meu_nome = ""
    permitidos = {"localhost"}
    if meu_nome:
        permitidos |= {meu_nome, meu_nome + ".local"}
    return nome in permitidos


def criar_app():
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )
    app.secret_key = _chave_secreta()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        MAX_CONTENT_LENGTH=15 * 1024 * 1024,
    )

    # ------------------------------------------------------------ infra
    @app.before_request
    def _antes():
        if not host_permitido(request.host):
            abort(400)
        _trava_requisicao.acquire()
        usuario = session.get("usuario")
        if usuario:
            iniciar_sessao(usuario)
        else:
            limpar_sessao()
        if request.method in ("POST", "PUT", "DELETE"):
            if request.headers.get("X-SIGM") != "1":
                _trava_requisicao.release()
                abort(403)

    @app.teardown_request
    def _depois(_erro):
        limpar_sessao()
        try:
            _trava_requisicao.release()
        except RuntimeError:
            pass

    @app.after_request
    def _cabecalhos(resposta):
        resposta.headers["Cache-Control"] = "no-store"
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["X-Frame-Options"] = "DENY"
        return resposta

    def exige_login(funcao):
        @wraps(funcao)
        def interno(*args, **kwargs):
            if not session.get("usuario"):
                if request.path.startswith("/api/"):
                    return jsonify(erro="Sessão expirada. Entre novamente."), 401
                return redirect(url_for("tela_login"))
            return funcao(*args, **kwargs)
        return interno

    def exige_admin(funcao):
        @wraps(funcao)
        def interno(*args, **kwargs):
            if (session.get("usuario") or {}).get("perfil") != "Administrador":
                if request.path.startswith("/api/"):
                    return jsonify(erro="Apenas o Administrador pode fazer isso.",
                                   mensagem="Apenas o Administrador pode fazer isso."), 403
                return redirect(url_for("pagina_inicio"))
            return funcao(*args, **kwargs)
        return interno

    def nome_revisor():
        usuario = session.get("usuario") or {}
        return usuario.get("nome") or usuario.get("login") or ""

    def dados_igreja():
        try:
            dados = buscar_configuracoes_igreja()
        except Exception:
            dados = {}
        try:
            versao = versao_imagem("logotipo")
        except Exception:
            versao = 0
        return {
            "logo": f"/igreja/logo?v={versao}" if versao else "",
            "nome": dados.get("nome_igreja") or configuracoes.DESCRICAO_SISTEMA,
            "detalhe": " · ".join(
                p for p in (
                    dados.get("ministerio"),
                    f"Setor {dados['setor']}" if dados.get("setor") else "",
                ) if p
            ),
        }

    def menu_usuario(ativo):
        eh_admin = (session.get("usuario") or {}).get("perfil") == "Administrador"
        itens = [
            {"nome": "Início", "url": "/inicio", "ativo": ativo == "inicio"},
            {"nome": "Membros", "url": "/membros", "ativo": ativo == "membros"},
            {"nome": "Pré-cadastros", "url": "/pre-cadastros", "ativo": ativo == "pre-cadastros"},
            {"nome": "Aniversariantes", "url": "/aniversariantes", "ativo": ativo == "aniversariantes"},
            {"nome": "Documentos", "url": "/documentos", "ativo": ativo == "documentos"},
            {"nome": "Relatórios", "url": "/relatorios", "ativo": ativo == "relatorios"},
            {"nome": "Dados da igreja", "url": "/igreja", "ativo": ativo == "igreja"},
            {"nome": "Pré-cadastro online", "url": "/online", "ativo": ativo == "online"},
            {"nome": "Celular", "url": "/celular", "ativo": ativo == "celular"},
            {"nome": "Backup", "url": "/backup", "ativo": ativo == "backup"},
            {"nome": "Sobre", "url": "/sobre", "ativo": ativo == "sobre"},
        ]
        if eh_admin:
            itens += [
                {"nome": "Usuários", "url": "/usuarios", "ativo": ativo == "usuarios"},
                {"nome": "Auditoria", "url": "/auditoria", "ativo": ativo == "auditoria"},
            ]
        return itens

    # ---------------------------------------------------------- paginas
    @app.get("/api/ping")
    def api_ping():
        app.config["ULTIMO_PING"] = time.time()
        return jsonify(sigm=True)

    @app.get("/")
    @exige_login
    def inicio():
        return redirect(url_for("pagina_inicio"))

    @app.get("/login")
    def tela_login():
        if session.get("usuario"):
            return redirect(url_for("inicio"))
        return render_template(
            "login.html",
            igreja=dados_igreja(),
            sistema=configuracoes.NOME_SISTEMA,
            sem_usuarios=not listar_usuarios(),
        )

    @app.post("/api/login")
    def api_login():
        dados = request.get_json(silent=True) or {}
        usuario = str(dados.get("usuario") or "").strip()
        senha = str(dados.get("senha") or "").strip()
        chave = f"{request.remote_addr}|{usuario.lower()}"
        if limite_tentativas.bloqueado("login", chave, 5, 60):
            return jsonify(erro="Muitas tentativas. Aguarde 1 minuto."), 429
        if not usuario or not senha:
            return jsonify(erro="Informe usuário e senha."), 400

        resultado = validar_login(usuario, senha)
        if resultado and resultado.get("bloqueado"):
            return jsonify(erro="Este usuário está bloqueado."), 403
        if not resultado:
            limite_tentativas.falhou("login", chave, 60)
            return jsonify(erro="Usuário ou senha incorretos."), 401

        limite_tentativas.limpar("login", chave)
        session.clear()
        session["usuario"] = {
            "id_usuario": resultado.get("id_usuario"),
            "nome": resultado.get("nome"),
            "login": resultado.get("login"),
            "perfil": resultado.get("perfil"),
            "status": "Ativo",
        }
        iniciar_sessao(session["usuario"])
        registrar_acao("LOGIN", "Login realizado pela versão web.", modulo="Acesso")
        return jsonify(ok=True)

    @app.post("/api/logout")
    def api_logout():
        session.clear()
        return jsonify(ok=True)

    @app.get("/pre-cadastros")
    @exige_login
    def pagina_pre_cadastros():
        return render_template(
            "pre_cadastros.html",
            igreja=dados_igreja(),
            sistema=configuracoes.NOME_SISTEMA,
            usuario=session.get("usuario"),
            menu=menu_usuario("pre-cadastros"),
            rotulos=ROTULOS,
            secoes=SECOES,
        )

    # -------------------------------------------------------------- API
    def resumo_lista(registro):
        faltantes = [
            c for c in CAMPOS_CADASTRAIS_PRE_CADASTRO
            if not str(registro.get(c) or "").strip()
        ]
        return {
            "id": registro.get("id"),
            "nome": registro.get("nome") or "",
            "cpf": registro.get("cpf") or "",
            "celular": registro.get("celular") or registro.get("telefone") or "",
            "data_nascimento": registro.get("data_nascimento") or "",
            "status": (registro.get("status") or "pendente").lower(),
            "recebido_em": registro.get("recebido_em") or "",
            "origem": registro.get("origem") or "",
            "faltantes": len(faltantes),
            "membro_id_aprovado": registro.get("membro_id_aprovado"),
        }

    @app.get("/api/pre-cadastros")
    @exige_login
    def api_listar():
        status = (request.args.get("status") or "").strip().lower() or None
        termo = (request.args.get("q") or "").strip().lower()
        registros = listar_pre_cadastros(status)
        itens = []
        for registro in registros:
            if termo:
                texto = " ".join(
                    str(registro.get(c) or "")
                    for c in ("nome", "cpf", "rg", "celular", "telefone", "email", "cidade")
                ).lower()
                if termo not in texto:
                    continue
            itens.append(resumo_lista(registro))
        todos = listar_pre_cadastros()
        contagem = {"todos": len(todos)}
        for registro in todos:
            chave = (registro.get("status") or "pendente").lower()
            contagem[chave] = contagem.get(chave, 0) + 1
        return jsonify(itens=itens, contagem=contagem)

    def buscar_ou_404(pre_id):
        registro = buscar_pre_cadastro_por_id(pre_id)
        if not registro:
            abort(404)
        return registro

    def dados_membro_comparacao(membro_id):
        conexao = conectar()
        try:
            cursor = conexao.cursor()
            cursor.execute(
                f"SELECT {', '.join(CAMPOS_COMPARACAO)} FROM membros WHERE id = ?",
                (membro_id,),
            )
            linha = cursor.fetchone()
        finally:
            conexao.close()
        if not linha:
            return {}
        return {c: (linha[i] or "") for i, c in enumerate(CAMPOS_COMPARACAO)}

    @app.get("/api/pre-cadastros/<int:pre_id>")
    @exige_login
    def api_detalhe(pre_id):
        registro = buscar_ou_404(pre_id)
        faltantes = listar_campos_faltantes_pre_cadastro(pre_id)
        # So interessa quem tem o MESMO CPF e o MESMO RG: nesse caso a tela
        # oferece "Atualizar cadastro existente". Demais semelhancas nao
        # sao mostradas.
        cpf_pre = normalizar_cpf(registro.get("cpf"))
        rg_pre = normalizar_rg(registro.get("rg"))
        candidatos = [
            c for c in detectar_duplicidades_pre_cadastro(registro)
            if cpf_pre and rg_pre
            and normalizar_cpf(c.get("cpf")) == cpf_pre
            and normalizar_rg(c.get("rg")) == rg_pre
        ]
        for candidato in candidatos[:5]:
            candidato["membro"] = dados_membro_comparacao(candidato["membro_id"])
        campos = {c: registro.get(c) or "" for c in CAMPOS_CADASTRAIS_PRE_CADASTRO}
        foto = bool(caminho_foto_seguro(registro.get("caminho_foto")))
        return jsonify(
            id=registro.get("id"),
            status=(registro.get("status") or "pendente").lower(),
            campos=campos,
            faltantes=faltantes,
            candidatos=candidatos[:5],
            total_candidatos=len(candidatos),
            nivel=maior_nivel_duplicidade(candidatos),
            tem_foto=foto,
            tecnico={
                "recebido_em": registro.get("recebido_em") or "",
                "origem": registro.get("origem") or "",
                "revisado_em": registro.get("revisado_em") or "",
                "usuario_revisor": registro.get("usuario_revisor") or "",
                "motivo_rejeicao": registro.get("motivo_rejeicao") or "",
                "membro_id_aprovado": registro.get("membro_id_aprovado"),
                "duplicidade_membro_id": registro.get("duplicidade_membro_id"),
            },
        )

    @app.get("/api/pre-cadastros/<int:pre_id>/foto")
    @exige_login
    def api_foto(pre_id):
        registro = buscar_ou_404(pre_id)
        caminho = caminho_foto_seguro(registro.get("caminho_foto"))
        if not caminho or Path(caminho).suffix.lower() not in EXTENSOES_FOTO:
            abort(404)
        return send_file(caminho)

    @app.put("/api/pre-cadastros/<int:pre_id>")
    @exige_login
    def api_editar(pre_id):
        buscar_ou_404(pre_id)
        dados = request.get_json(silent=True) or {}
        permitidos = {
            c: str(dados.get(c) or "").strip()
            for c in CAMPOS_CADASTRAIS_PRE_CADASTRO
            if c in dados and c != "caminho_foto"
        }
        try:
            atualizado = atualizar_dados_pre_cadastro(pre_id, permitidos)
        except Exception as erro:
            return jsonify(erro=f"Não foi possível salvar: {erro}"), 500
        if not atualizado:
            abort(404)
        registrar_acao(
            "PRE_CADASTRO_EDITADO", "Pré-cadastro editado.",
            modulo="Pre-cadastros", registro_id=pre_id,
        )
        return jsonify(ok=True)

    def resposta_servico(resultado):
        codigo = 200 if resultado.get("sucesso") else 409
        return jsonify(
            ok=bool(resultado.get("sucesso")),
            mensagem=resultado.get("mensagem") or "",
            membro_id=resultado.get("membro_id"),
            duplicidades=len(resultado.get("duplicidades") or []),
            nivel=maior_nivel_duplicidade(resultado.get("duplicidades")),
        ), codigo

    @app.post("/api/pre-cadastros/<int:pre_id>/aprovar")
    @exige_login
    def api_aprovar(pre_id):
        buscar_ou_404(pre_id)
        dados = request.get_json(silent=True) or {}
        resultado = aprovar_pre_cadastro(
            pre_id,
            usuario_revisor=nome_revisor(),
            permitir_duplicidade=bool(dados.get("permitir_duplicidade")),
        )
        return resposta_servico(resultado)

    @app.post("/api/pre-cadastros/<int:pre_id>/atualizar-existente")
    @exige_login
    def api_atualizar_existente(pre_id):
        buscar_ou_404(pre_id)
        dados = request.get_json(silent=True) or {}
        try:
            membro_id = int(dados.get("membro_id"))
        except (TypeError, ValueError):
            return jsonify(ok=False, mensagem="Escolha o membro a ser atualizado."), 400
        resultado = atualizar_membro_existente_com_pre_cadastro(
            pre_id, membro_id, usuario_revisor=nome_revisor(),
        )
        return resposta_servico(resultado)

    @app.post("/api/pre-cadastros/<int:pre_id>/rejeitar")
    @exige_login
    def api_rejeitar(pre_id):
        buscar_ou_404(pre_id)
        dados = request.get_json(silent=True) or {}
        resultado = rejeitar_pre_cadastro(
            pre_id, motivo=dados.get("motivo"), usuario_revisor=nome_revisor(),
        )
        return resposta_servico(resultado)

    @app.post("/api/pre-cadastros/<int:pre_id>/duplicado")
    @exige_login
    def api_duplicado(pre_id):
        registro = buscar_ou_404(pre_id)
        if (registro.get("status") or "pendente").lower() != "pendente":
            return jsonify(ok=False, mensagem="Só pré-cadastros pendentes podem ser marcados como duplicados."), 409
        dados = request.get_json(silent=True) or {}
        try:
            membro_id = int(dados.get("membro_id"))
        except (TypeError, ValueError):
            return jsonify(ok=False, mensagem="Escolha o membro duplicado."), 400
        atualizado = atualizar_status_pre_cadastro(
            pre_id, "duplicado",
            duplicidade_membro_id=membro_id, usuario_revisor=nome_revisor(),
        )
        if not atualizado:
            abort(404)
        registrar_acao(
            "PRE_CADASTRO_MARCADO_DUPLICADO", "Pré-cadastro marcado como duplicado.",
            modulo="Pre-cadastros", registro_id=pre_id,
            detalhes=f"Membro relacionado: {membro_id}",
        )
        return jsonify(ok=True, mensagem="Pré-cadastro marcado como duplicado.")

    @app.post("/api/pre-cadastros/<int:pre_id>/excluir")
    @exige_login
    def api_excluir(pre_id):
        buscar_ou_404(pre_id)
        apagado = excluir_pre_cadastro(pre_id)
        if not apagado:
            abort(404)
        registrar_acao(
            "PRE_CADASTRO_EXCLUIDO", "Pré-cadastro excluído manualmente.",
            modulo="Pre-cadastros", registro_id=pre_id,
            detalhes=f"Nome: {apagado.get('nome') or ''}; status: {apagado.get('status')}",
        )
        return jsonify(ok=True, mensagem="Pré-cadastro excluído.")

    @app.post("/api/pre-cadastros/excluir-lote")
    @exige_login
    def api_excluir_lote():
        """Exclui de uma vez os pre-cadastros ja resolvidos (nunca os pendentes)."""
        dados = request.get_json(silent=True) or {}
        status = str(dados.get("status") or "").strip().lower()
        if status not in ("aprovado", "rejeitado", "duplicado"):
            return jsonify(ok=False, mensagem="Só é possível excluir em lote os aprovados, rejeitados ou duplicados."), 400
        total = 0
        for registro in listar_pre_cadastros(status):
            if excluir_pre_cadastro(registro["id"]):
                total += 1
        if total:
            registrar_acao(
                "PRE_CADASTRO_EXCLUIDO_LOTE", f"{total} pré-cadastro(s) {status}(s) excluído(s) em lote.",
                modulo="Pre-cadastros", detalhes=f"Status: {status} (versão web)",
            )
        return jsonify(ok=True, total=total, mensagem=f"{total} pré-cadastro(s) excluído(s).")

    @app.post("/api/pre-cadastros/sincronizar")
    @exige_login
    def api_sincronizar():
        try:
            relatorio = sincronizar_pre_cadastros_online() or {}
        except Exception:
            return jsonify(ok=False, mensagem="Não foi possível sincronizar. Tente novamente."), 502
        ok = bool(relatorio.get("sucesso"))
        return jsonify(
            ok=ok,
            mensagem=relatorio.get("mensagem_usuario")
            or "Não foi possível sincronizar. Tente novamente.",
        ), (200 if ok else 502)

    @app.post("/api/pre-cadastros/importar")
    @exige_login
    def api_importar():
        arquivo = request.files.get("arquivo")
        if not arquivo or not arquivo.filename.lower().endswith(".json"):
            return jsonify(ok=False, mensagem="Escolha um arquivo .json."), 400
        with tempfile.TemporaryDirectory() as pasta:
            destino = os.path.join(pasta, "importacao.json")
            arquivo.save(destino)
            try:
                relatorio = importar_pre_cadastros_json(destino)
            except ImportacaoPreCadastroErro as erro:
                return jsonify(ok=False, mensagem=f"Arquivo inválido: {erro}"), 400
            except Exception as erro:
                return jsonify(ok=False, mensagem=f"Não foi possível importar: {erro}"), 500
        return jsonify(
            ok=True,
            mensagem=(
                f"Importação concluída. Lidos: {relatorio.get('total_lido', 0)}, "
                f"novos: {relatorio.get('inseridos', 0)}, "
                f"já existentes: {relatorio.get('ignorados', 0)}, "
                f"inválidos: {relatorio.get('invalidos', 0)}."
            ),
        )

    registrar_rotas_membros(app, exige_login, dados_igreja, menu_usuario)
    registrar_rotas_relatorios(app, exige_login, dados_igreja, menu_usuario)
    registrar_rotas_arquivos_membro(app, exige_login)
    registrar_rotas_acesso(app, exige_login, dados_igreja, menu_usuario)
    registrar_rotas_usuarios(app, exige_login, exige_admin, dados_igreja, menu_usuario)
    registrar_rotas_auditoria(app, exige_login, exige_admin, dados_igreja, menu_usuario)
    registrar_rotas_backup(app, exige_login, exige_admin, dados_igreja, menu_usuario)
    registrar_rotas_configuracao_online(app, exige_login, exige_admin, dados_igreja, menu_usuario)
    registrar_rotas_celular(app, exige_login, dados_igreja, menu_usuario)
    registrar_rotas_central_documentos(app, exige_login, dados_igreja, menu_usuario)
    registrar_rotas_painel(app, exige_login, dados_igreja, menu_usuario)
    registrar_rotas_igreja(app, exige_login, dados_igreja, menu_usuario)

    @app.errorhandler(413)
    def _grande_demais(_erro):
        return jsonify(erro="Arquivo grande demais (máximo 15 MB)."), 413

    @app.errorhandler(404)
    def _nao_encontrado(_erro):
        if request.path.startswith("/api/"):
            return jsonify(erro="Registro não encontrado."), 404
        return "Página não encontrada.", 404

    @app.errorhandler(403)
    def _proibido(_erro):
        return jsonify(erro="Requisição não autorizada."), 403

    return app
