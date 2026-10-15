from pathlib import Path

from banco.database import (
    conectar,
    data_hora_atual,
    garantir_coluna_data_funcao_membro,
    garantir_coluna_foto_membro,
    garantir_colunas_complementares_membro,
    garantir_tabela_pre_cadastros,
    buscar_pre_cadastro_por_id,
)
from servicos.duplicidade_membros import (
    detectar_duplicidades_pre_cadastro,
    encontrar_membro_correspondente_exato,
)
from utils.auditoria import registrar_acao
from utils.formatadores import formatar_cpf, formatar_rg


STATUS_APROVADO = "aprovado"
STATUS_DUPLICADO = "duplicado"
STATUS_PENDENTE = "pendente"
STATUS_REJEITADO = "rejeitado"
STATUS_MEMBRO_PADRAO = "Membro"

CAMPOS_MEMBRO_APROVACAO = (
    "nome",
    "rg",
    "orgao_emissor",
    "cpf",
    "data_nascimento",
    "estado_civil",
    "profissao",
    "telefone",
    "celular",
    "email",
    "endereco",
    "numero",
    "bairro",
    "cidade",
    "estado",
    "batismo_aguas",
    "ministerio",
    "cargo",
    "data_funcao",
    "status",
    "observacoes",
    "caminho_foto",
    "nome_pai",
    "nome_mae",
    "grau_instrucao",
    "curso_teologico",
    "cidade_nascimento",
    "estado_nascimento",
    "nome_conjuge",
    "data_nascimento_conjuge",
)

COLUNAS_INSERCAO_MEMBRO = (
    "nome",
    "rg",
    "orgao_emissor",
    "cpf",
    "data_nascimento",
    "estado_civil",
    "profissao",
    "telefone",
    "celular",
    "email",
    "endereco",
    "numero",
    "bairro",
    "cidade",
    "estado",
    "batismo_aguas",
    "ministerio",
    "cargo",
    "status",
    "observacoes",
    "nome_pai",
    "nome_mae",
    "cidade_nascimento",
    "estado_nascimento",
    "nome_conjuge",
    "data_nascimento_conjuge",
    "grau_instrucao",
    "curso_teologico",
)


class AprovacaoPreCadastroErro(Exception):
    pass


def status_fluxo(pre_cadastro):
    return str((pre_cadastro or {}).get("status") or STATUS_PENDENTE).strip().lower()


def maior_nivel_duplicidade(duplicidades):
    if not duplicidades:
        return ""
    return str(duplicidades[0].get("nivel") or "").strip().lower()


def caminho_foto_seguro(caminho):
    texto = str(caminho or "").strip()
    if not texto or "\x00" in texto or "://" in texto:
        return ""

    try:
        caminho_resolvido = Path(texto).expanduser()
        if not caminho_resolvido.is_absolute():
            caminho_resolvido = Path.cwd() / caminho_resolvido
        caminho_resolvido = caminho_resolvido.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return ""

    if not caminho_resolvido.exists() or not caminho_resolvido.is_file():
        return ""
    return str(caminho_resolvido)


def preparar_dados_membro(pre_cadastro):
    dados = {
        campo: str((pre_cadastro or {}).get(campo) or "").strip()
        for campo in CAMPOS_MEMBRO_APROVACAO
    }
    dados["cpf"] = formatar_cpf(dados.get("cpf"))
    dados["rg"] = formatar_rg(dados.get("rg"))
    dados["status"] = str((pre_cadastro or {}).get("status_membro") or "").strip()
    if not dados["status"]:
        dados["status"] = STATUS_MEMBRO_PADRAO
    dados["caminho_foto"] = caminho_foto_seguro(
        (pre_cadastro or {}).get("caminho_foto")
    )
    return dados


def resultado(sucesso, pre_cadastro_id, mensagem, membro_id=None, duplicidades=None):
    return {
        "sucesso": bool(sucesso),
        "membro_id": membro_id,
        "pre_cadastro_id": pre_cadastro_id,
        "mensagem": mensagem,
        "duplicidades": list(duplicidades or []),
    }


def _inserir_membro_transacao(cursor, dados_membro, coluna_data_funcao, coluna_foto):
    colunas = list(COLUNAS_INSERCAO_MEMBRO)
    valores = [dados_membro.get(coluna, "") for coluna in colunas]

    if coluna_data_funcao and coluna_data_funcao not in colunas:
        colunas.append(coluna_data_funcao)
        valores.append(dados_membro.get("data_funcao", ""))

    if coluna_foto and coluna_foto not in colunas:
        colunas.append(coluna_foto)
        valores.append(dados_membro.get("caminho_foto", ""))

    parametros = ", ".join("?" for _coluna in colunas)
    cursor.execute(
        f"""
        INSERT INTO membros ({", ".join(colunas)})
        VALUES ({parametros})
        """,
        valores,
    )
    return cursor.lastrowid


def _valor_membro_para_coluna(dados_membro, coluna, coluna_data_funcao, coluna_foto):
    if coluna_data_funcao and coluna == coluna_data_funcao:
        return dados_membro.get("data_funcao", "")
    if coluna_foto and coluna == coluna_foto:
        return dados_membro.get("caminho_foto", "")
    return dados_membro.get(coluna, "")


def _atualizar_membro_transacao(cursor, membro_id, dados_membro, coluna_data_funcao, coluna_foto):
    """
    Atualiza um membro ja existente com os dados do pre-cadastro.

    Regra de mesclagem (definida com o usuario): quando o pre-cadastro
    traz um valor preenchido para um campo, esse valor PREVALECE sobre
    o que ja estava salvo (mesmo que seja diferente). Quando o
    pre-cadastro nao traz nada para aquele campo, o valor atual do
    membro e mantido - nunca e apagado.
    """
    colunas = list(COLUNAS_INSERCAO_MEMBRO)
    if coluna_data_funcao and coluna_data_funcao not in colunas:
        colunas.append(coluna_data_funcao)
    if coluna_foto and coluna_foto not in colunas:
        colunas.append(coluna_foto)

    atribuicoes = ", ".join(
        f"{coluna} = CASE WHEN ? <> '' THEN ? ELSE {coluna} END"
        for coluna in colunas
    )
    parametros = []
    for coluna in colunas:
        valor = _valor_membro_para_coluna(dados_membro, coluna, coluna_data_funcao, coluna_foto)
        parametros.extend([valor, valor])
    parametros.append(membro_id)

    cursor.execute(
        f"UPDATE membros SET {atribuicoes} WHERE id = ?",
        parametros,
    )


def _marcar_pre_cadastro_aprovado_transacao(
    cursor,
    pre_cadastro_id,
    membro_id,
    usuario_revisor,
    agora,
):
    cursor.execute(
        """
        UPDATE pre_cadastros
        SET status = ?,
            membro_id_aprovado = ?,
            motivo_rejeicao = NULL,
            duplicidade_membro_id = NULL,
            usuario_revisor = ?,
            revisado_em = ?,
            atualizado_em = ?
        WHERE id = ?
          AND COALESCE(status, 'pendente') NOT IN (?, ?, ?)
          AND membro_id_aprovado IS NULL
        """,
        (
            STATUS_APROVADO,
            membro_id,
            usuario_revisor,
            agora,
            agora,
            pre_cadastro_id,
            STATUS_APROVADO,
            STATUS_REJEITADO,
            STATUS_DUPLICADO,
        ),
    )
    if cursor.rowcount != 1:
        raise AprovacaoPreCadastroErro(
            "O pre-cadastro mudou de status antes da conclusao da aprovacao."
        )


def _aprovar_pre_cadastro_transacional(pre_cadastro_id, dados_membro, usuario_revisor):
    garantir_tabela_pre_cadastros()
    garantir_colunas_complementares_membro()
    coluna_data_funcao = garantir_coluna_data_funcao_membro()
    coluna_foto = garantir_coluna_foto_membro()

    conexao = conectar()
    try:
        cursor = conexao.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            """
            SELECT status, membro_id_aprovado
            FROM pre_cadastros
            WHERE id = ?
            """,
            (pre_cadastro_id,),
        )
        linha = cursor.fetchone()
        if not linha:
            raise AprovacaoPreCadastroErro("Pre-cadastro nao encontrado.")

        status_atual = str(linha[0] or STATUS_PENDENTE).strip().lower()
        membro_aprovado = linha[1]
        if status_atual == STATUS_APROVADO or membro_aprovado:
            raise AprovacaoPreCadastroErro("Este pre-cadastro ja foi aprovado.")
        if status_atual == STATUS_REJEITADO:
            raise AprovacaoPreCadastroErro("Pre-cadastro rejeitado nao pode ser aprovado.")
        if status_atual == STATUS_DUPLICADO:
            raise AprovacaoPreCadastroErro("Pre-cadastro duplicado nao pode ser aprovado.")

        membro_id = _inserir_membro_transacao(
            cursor,
            dados_membro,
            coluna_data_funcao,
            coluna_foto,
        )
        _marcar_pre_cadastro_aprovado_transacao(
            cursor,
            pre_cadastro_id,
            membro_id,
            usuario_revisor,
            data_hora_atual(),
        )
        conexao.commit()
        return membro_id
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def _atualizar_pre_cadastro_aprovado_transacional(pre_cadastro_id, membro_id, dados_membro, usuario_revisor):
    """
    Mesma logica de _aprovar_pre_cadastro_transacional, mas ATUALIZA
    um membro ja existente (correspondencia exata de CPF+RG+Nome) em
    vez de inserir um novo.
    """
    garantir_tabela_pre_cadastros()
    garantir_colunas_complementares_membro()
    coluna_data_funcao = garantir_coluna_data_funcao_membro()
    coluna_foto = garantir_coluna_foto_membro()

    conexao = conectar()
    try:
        cursor = conexao.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            """
            SELECT status, membro_id_aprovado
            FROM pre_cadastros
            WHERE id = ?
            """,
            (pre_cadastro_id,),
        )
        linha = cursor.fetchone()
        if not linha:
            raise AprovacaoPreCadastroErro("Pre-cadastro nao encontrado.")

        status_atual = str(linha[0] or STATUS_PENDENTE).strip().lower()
        membro_aprovado = linha[1]
        if status_atual == STATUS_APROVADO or membro_aprovado:
            raise AprovacaoPreCadastroErro("Este pre-cadastro ja foi aprovado.")
        if status_atual == STATUS_REJEITADO:
            raise AprovacaoPreCadastroErro("Pre-cadastro rejeitado nao pode ser aprovado.")
        if status_atual == STATUS_DUPLICADO:
            raise AprovacaoPreCadastroErro("Pre-cadastro duplicado nao pode ser aprovado.")

        cursor.execute("SELECT id FROM membros WHERE id = ?", (membro_id,))
        if not cursor.fetchone():
            raise AprovacaoPreCadastroErro("Membro correspondente nao foi encontrado.")

        _atualizar_membro_transacao(
            cursor,
            membro_id,
            dados_membro,
            coluna_data_funcao,
            coluna_foto,
        )
        _marcar_pre_cadastro_aprovado_transacao(
            cursor,
            pre_cadastro_id,
            membro_id,
            usuario_revisor,
            data_hora_atual(),
        )
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def aprovar_pre_cadastro(
    pre_cadastro_id,
    usuario_revisor=None,
    permitir_duplicidade=False,
):
    pre_cadastro = buscar_pre_cadastro_por_id(pre_cadastro_id)
    if not pre_cadastro:
        return resultado(False, pre_cadastro_id, "Pre-cadastro nao encontrado.")

    status_atual = status_fluxo(pre_cadastro)
    membro_aprovado = pre_cadastro.get("membro_id_aprovado")
    if status_atual == STATUS_APROVADO or membro_aprovado:
        return resultado(False, pre_cadastro_id, "Este pre-cadastro ja foi aprovado.")
    if status_atual == STATUS_REJEITADO:
        return resultado(False, pre_cadastro_id, "Pre-cadastro rejeitado nao pode ser aprovado.")
    if status_atual == STATUS_DUPLICADO:
        return resultado(False, pre_cadastro_id, "Pre-cadastro duplicado nao pode ser aprovado.")

    if not str(pre_cadastro.get("nome") or "").strip():
        return resultado(False, pre_cadastro_id, "Informe o nome antes de aprovar.")

    dados_membro = preparar_dados_membro(pre_cadastro)

    # Correspondencia exata (CPF + RG + Nome): atualiza o cadastro ja
    # existente em vez de criar um novo, sem passar pela revisao manual
    # de duplicidade - com os tres dados batendo, e a mesma pessoa sem
    # duvida razoavel. Campos vazios no pre-cadastro mantem o valor que
    # o membro ja tinha; campos preenchidos substituem o valor antigo.
    membro_correspondente = encontrar_membro_correspondente_exato(pre_cadastro)
    if membro_correspondente:
        try:
            _atualizar_pre_cadastro_aprovado_transacional(
                pre_cadastro_id,
                membro_correspondente,
                dados_membro,
                str(usuario_revisor or "").strip(),
            )
        except AprovacaoPreCadastroErro as erro:
            return resultado(False, pre_cadastro_id, str(erro))
        except Exception as erro:
            return resultado(
                False,
                pre_cadastro_id,
                f"Nao foi possivel atualizar o membro existente: {erro}",
            )

        registrar_acao(
            "PRE_CADASTRO_ATUALIZOU_MEMBRO",
            "Pre-cadastro aprovado atualizando um membro ja existente (CPF, RG e nome identicos).",
            modulo="Pre-cadastros",
            registro_id=pre_cadastro_id,
            detalhes=f"Membro atualizado: {membro_correspondente}",
            usuario_nome=str(usuario_revisor or "").strip() or None,
        )
        registrar_acao(
            "EDICAO_MEMBRO",
            "Membro atualizado automaticamente a partir de pre-cadastro (mesmo CPF, RG e nome).",
            modulo="Membros",
            registro_id=membro_correspondente,
            detalhes=f"Origem: pre-cadastro {pre_cadastro_id}",
            usuario_nome=str(usuario_revisor or "").strip() or None,
        )
        return resultado(
            True,
            pre_cadastro_id,
            "Pre-cadastro aprovado: os dados foram atualizados no cadastro ja existente.",
            membro_id=membro_correspondente,
        )

    duplicidades = detectar_duplicidades_pre_cadastro(pre_cadastro)
    nivel = maior_nivel_duplicidade(duplicidades)
    if nivel == "alto":
        return resultado(
            False,
            pre_cadastro_id,
            "Risco alto de duplicidade. Analise o pre-cadastro antes de aprovar.",
            duplicidades=duplicidades,
        )
    if nivel == "medio" and not permitir_duplicidade:
        return resultado(
            False,
            pre_cadastro_id,
            "Existem possiveis duplicidades que exigem confirmacao.",
            duplicidades=duplicidades,
        )

    try:
        membro_id = _aprovar_pre_cadastro_transacional(
            pre_cadastro_id,
            dados_membro,
            str(usuario_revisor or "").strip(),
        )
    except AprovacaoPreCadastroErro as erro:
        return resultado(False, pre_cadastro_id, str(erro), duplicidades=duplicidades)
    except Exception as erro:
        return resultado(
            False,
            pre_cadastro_id,
            f"Nao foi possivel aprovar o pre-cadastro: {erro}",
            duplicidades=duplicidades,
        )

    registrar_acao(
        "PRE_CADASTRO_APROVADO",
        "Pre-cadastro aprovado e membro oficial criado.",
        modulo="Pre-cadastros",
        registro_id=pre_cadastro_id,
        detalhes=f"Membro criado: {membro_id}; duplicidades avaliadas: {len(duplicidades)}",
        usuario_nome=str(usuario_revisor or "").strip() or None,
    )
    registrar_acao(
        "CADASTRO_MEMBRO",
        "Membro cadastrado a partir de pre-cadastro aprovado.",
        modulo="Membros",
        registro_id=membro_id,
        detalhes=f"Origem: pre-cadastro {pre_cadastro_id}",
        usuario_nome=str(usuario_revisor or "").strip() or None,
    )
    return resultado(
        True,
        pre_cadastro_id,
        "Pre-cadastro aprovado com sucesso.",
        membro_id=membro_id,
        duplicidades=duplicidades,
    )


def atualizar_membro_existente_com_pre_cadastro(
    pre_cadastro_id,
    membro_id,
    usuario_revisor=None,
):
    """
    Acao manual (botao "Atualizar cadastro existente"): o revisor escolhe
    qual membro ja cadastrado deve receber os dados do pre-cadastro.

    Mesma regra de mesclagem da aprovacao automatica: campos preenchidos
    no pre-cadastro substituem os atuais; campos vazios mantem o que o
    membro ja tinha. O pre-cadastro fica como aprovado, ligado a esse
    membro. Nenhum membro novo e criado.
    """
    pre_cadastro = buscar_pre_cadastro_por_id(pre_cadastro_id)
    if not pre_cadastro:
        return resultado(False, pre_cadastro_id, "Pre-cadastro nao encontrado.")
    if not membro_id:
        return resultado(False, pre_cadastro_id, "Selecione o membro a ser atualizado.")

    status_atual = status_fluxo(pre_cadastro)
    if status_atual == STATUS_APROVADO or pre_cadastro.get("membro_id_aprovado"):
        return resultado(False, pre_cadastro_id, "Este pre-cadastro ja foi aprovado.")
    if status_atual == STATUS_REJEITADO:
        return resultado(False, pre_cadastro_id, "Pre-cadastro rejeitado nao pode ser aprovado.")
    if status_atual == STATUS_DUPLICADO:
        return resultado(False, pre_cadastro_id, "Pre-cadastro duplicado nao pode ser aprovado.")

    dados_membro = preparar_dados_membro(pre_cadastro)
    usuario = str(usuario_revisor or "").strip()
    try:
        _atualizar_pre_cadastro_aprovado_transacional(
            pre_cadastro_id,
            membro_id,
            dados_membro,
            usuario,
        )
    except AprovacaoPreCadastroErro as erro:
        return resultado(False, pre_cadastro_id, str(erro))
    except Exception as erro:
        return resultado(
            False,
            pre_cadastro_id,
            f"Nao foi possivel atualizar o membro existente: {erro}",
        )

    registrar_acao(
        "PRE_CADASTRO_ATUALIZOU_MEMBRO",
        "Pre-cadastro usado para atualizar um membro ja existente (escolha manual).",
        modulo="Pre-cadastros",
        registro_id=pre_cadastro_id,
        detalhes=f"Membro atualizado: {membro_id}",
        usuario_nome=usuario or None,
    )
    registrar_acao(
        "EDICAO_MEMBRO",
        "Membro atualizado a partir de pre-cadastro (atualizacao de cadastro existente).",
        modulo="Membros",
        registro_id=membro_id,
        detalhes=f"Origem: pre-cadastro {pre_cadastro_id}",
        usuario_nome=usuario or None,
    )
    return resultado(
        True,
        pre_cadastro_id,
        "Cadastro existente atualizado com os dados do pre-cadastro.",
        membro_id=membro_id,
    )


def rejeitar_pre_cadastro(pre_cadastro_id, motivo=None, usuario_revisor=None):
    garantir_tabela_pre_cadastros()
    pre_cadastro = buscar_pre_cadastro_por_id(pre_cadastro_id)
    if not pre_cadastro:
        return resultado(False, pre_cadastro_id, "Pre-cadastro nao encontrado.")

    status_atual = status_fluxo(pre_cadastro)
    if status_atual == STATUS_APROVADO or pre_cadastro.get("membro_id_aprovado"):
        return resultado(False, pre_cadastro_id, "Pre-cadastro aprovado nao pode ser rejeitado.")
    if status_atual == STATUS_REJEITADO:
        return resultado(False, pre_cadastro_id, "Este pre-cadastro ja foi rejeitado.")
    if status_atual == STATUS_DUPLICADO:
        return resultado(False, pre_cadastro_id, "Pre-cadastro duplicado nao pode ser rejeitado.")

    agora = data_hora_atual()
    motivo = str(motivo or "").strip()[:180]
    usuario_revisor = str(usuario_revisor or "").strip()

    conexao = conectar()
    try:
        cursor = conexao.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            """
            UPDATE pre_cadastros
            SET status = ?,
                motivo_rejeicao = ?,
                usuario_revisor = ?,
                revisado_em = ?,
                atualizado_em = ?
            WHERE id = ?
              AND COALESCE(status, 'pendente') NOT IN (?, ?, ?)
              AND membro_id_aprovado IS NULL
            """,
            (
                STATUS_REJEITADO,
                motivo,
                usuario_revisor,
                agora,
                agora,
                pre_cadastro_id,
                STATUS_APROVADO,
                STATUS_REJEITADO,
                STATUS_DUPLICADO,
            ),
        )
        if cursor.rowcount != 1:
            raise AprovacaoPreCadastroErro(
                "O pre-cadastro mudou de status antes da rejeicao."
            )
        conexao.commit()
    except AprovacaoPreCadastroErro as erro:
        conexao.rollback()
        return resultado(False, pre_cadastro_id, str(erro))
    except Exception as erro:
        conexao.rollback()
        return resultado(
            False,
            pre_cadastro_id,
            f"Nao foi possivel rejeitar o pre-cadastro: {erro}",
        )
    finally:
        conexao.close()

    registrar_acao(
        "PRE_CADASTRO_REJEITADO",
        "Pre-cadastro rejeitado.",
        modulo="Pre-cadastros",
        registro_id=pre_cadastro_id,
        detalhes="Motivo informado: sim" if motivo else "Motivo informado: nao",
        usuario_nome=usuario_revisor or None,
    )
    return resultado(True, pre_cadastro_id, "Pre-cadastro rejeitado com sucesso.")
