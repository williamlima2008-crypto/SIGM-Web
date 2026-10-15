"""
==========================================================
SIGM - Sistema de Gestão de Membros

Arquivo: app.py
Descrição: Inicializa o sistema.

Desenvolvido por:
William Lima

"Servindo à Igreja com organização e excelência."
==========================================================
"""

import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from utils.caminhos import caminho_dados, garantir_pastas_runtime
from utils.formatadores import formatar_cpf, formatar_rg
from utils.seguranca import gerar_hash_senha, verificar_senha

BANCO = caminho_dados("sigm.db")
CAMPOS_FOTO_MEMBRO = (
    "foto",
    "foto_membro",
    "caminho_foto",
    "foto_path",
)
COLUNAS_DATA_FUNCAO_MEMBRO = (
    "data_funcao",
    "data_cargo",
    "data_consagracao",
)
COLUNAS_COMPLEMENTARES_MEMBRO = {
    "nome_pai": "TEXT",
    "nome_mae": "TEXT",
    "cidade_nascimento": "TEXT",
    "estado_nascimento": "TEXT",
    "nome_conjuge": "TEXT",
    "data_nascimento_conjuge": "TEXT",
    "grau_instrucao": "TEXT",
    "curso_teologico": "TEXT",
    "data_batismo_espirito_santo": "TEXT",
    "cep": "TEXT",
}

COLUNAS_DOCUMENTOS_EMITIDOS = {
    "membro_id": "INTEGER NOT NULL",
    "tipo_documento": "TEXT NOT NULL",
    "titulo_documento": "TEXT NOT NULL",
    "caminho_arquivo": "TEXT NOT NULL",
    "data_emissao": "TEXT NOT NULL",
    "usuario_emissor": "TEXT",
    "observacao": "TEXT",
}

COLUNAS_ARQUIVOS_MEMBRO = {
    "membro_id": "INTEGER NOT NULL",
    "tipo_arquivo": "TEXT NOT NULL",
    "titulo": "TEXT NOT NULL",
    "nome_original": "TEXT NOT NULL",
    "caminho_arquivo": "TEXT NOT NULL",
    "data_anexo": "TEXT NOT NULL",
    "usuario_responsavel": "TEXT",
    "observacao": "TEXT",
}

COLUNAS_LOGS_AUDITORIA = (
    "id",
    "usuario_id",
    "usuario_nome",
    "usuario_login",
    "acao",
    "descricao",
    "data_hora",
    "modulo",
    "registro_id",
    "detalhes",
)

COLUNAS_CONFIGURACOES_ONLINE_IGREJA = (
    "id",
    "identificador_publico",
    "chave_sincronizacao",
    "api_base_url",
    "formulario_url",
    "qr_code_path",
    "ativo",
    "status_ativacao",
    "ultima_sincronizacao",
    "criado_em",
    "atualizado_em",
)

CAMPOS_CADASTRAIS_PRE_CADASTRO = (
    "nome",
    "rg",
    "orgao_emissor",
    "cpf",
    "data_nascimento",
    "cidade_nascimento",
    "estado_nascimento",
    "estado_civil",
    "nome_conjuge",
    "data_nascimento_conjuge",
    "profissao",
    "nome_pai",
    "nome_mae",
    "grau_instrucao",
    "telefone",
    "celular",
    "email",
    "endereco",
    "numero",
    "bairro",
    "cidade",
    "estado",
    "cep",
    "batismo_aguas",
    "batismo_espirito_santo",
    "ministerio",
    "cargo",
    "data_funcao",
    "curso_teologico",
    "status_membro",
    "congregacao",
    "dirigente",
    "setor_campo",
    "igreja_local_batismo_aguas",
    "igreja_local_batismo_espirito_santo",
    "recados_outros",
    "nome_titular_lgpd",
    "observacoes",
    "caminho_foto",
)

CAMPOS_TECNICOS_PRE_CADASTRO = (
    "remote_id",
    "identificador_publico_igreja",
    "payload_json",
    "status",
    "membro_id_aprovado",
    "motivo_rejeicao",
    "duplicidade_membro_id",
    "recebido_em",
    "revisado_em",
    "usuario_revisor",
    "origem",
    "atualizado_em",
)

COLUNAS_PRE_CADASTROS = (
    "id",
    *CAMPOS_TECNICOS_PRE_CADASTRO[:3],
    *CAMPOS_CADASTRAIS_PRE_CADASTRO,
    *CAMPOS_TECNICOS_PRE_CADASTRO[3:],
)

COLUNAS_INSERCAO_PRE_CADASTROS = tuple(
    campo
    for campo in COLUNAS_PRE_CADASTROS
    if campo != "id"
)

DEFINICOES_COLUNAS_PRE_CADASTROS = {
    campo: "TEXT"
    for campo in CAMPOS_CADASTRAIS_PRE_CADASTRO
}
DEFINICOES_COLUNAS_PRE_CADASTROS.update({
    "remote_id": "TEXT",
    "identificador_publico_igreja": "TEXT",
    "payload_json": "TEXT",
    "status": "TEXT DEFAULT 'pendente'",
    "membro_id_aprovado": "INTEGER",
    "motivo_rejeicao": "TEXT",
    "duplicidade_membro_id": "INTEGER",
    "recebido_em": "TEXT",
    "revisado_em": "TEXT",
    "usuario_revisor": "TEXT",
    "origem": "TEXT DEFAULT 'sincronizacao'",
    "atualizado_em": "TEXT",
})

COLUNAS_SINCRONIZACOES_PRE_CADASTRO = (
    "id",
    "data_hora",
    "status",
    "quantidade_recebida",
    "quantidade_nova",
    "quantidade_ignorada",
    "erro",
    "detalhes",
)


def conectar():
    return sqlite3.connect(str(BANCO))


def data_hora_atual():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def criar_tabelas():
    garantir_pastas_runtime()
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            usuario TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL,
            perfil TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS igreja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            ministerio TEXT,
            cidade TEXT,
            estado TEXT,
            endereco TEXT,
            telefone TEXT,
            email TEXT,
            logo TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes_igreja (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            nome_igreja TEXT,
            ministerio TEXT,
            convencao TEXT,
            setor TEXT,
            congregacao_sede TEXT,
            cidade TEXT,
            estado TEXT,
            pastor_presidente TEXT,
            pastor_setorial TEXT,
            primeiro_secretario TEXT,
            segundo_secretario TEXT,
            terceiro_secretario TEXT,
            telefone TEXT,
            whatsapp TEXT,
            email TEXT,
            site TEXT,
            tema TEXT,
            rua TEXT,
            numero TEXT,
            complemento TEXT,
            bairro TEXT,
            cep TEXT,
            cidade_endereco TEXT,
            estado_endereco TEXT,
            logotipo TEXT,
            carimbo TEXT,
            assinatura_pastor TEXT,
            congregacao_local_nome TEXT,
            congregacao_local_dirigente TEXT,
            congregacao_local_numero TEXT,
            congregacao_local_campo_setor TEXT,
            congregacao_local_cidade TEXT,
            congregacao_local_estado TEXT,
            congregacao_local_rua TEXT,
            congregacao_local_numero_endereco TEXT,
            congregacao_local_bairro TEXT,
            congregacao_local_cep TEXT,
            congregacao_local_telefone TEXT,
            congregacao_local_whatsapp TEXT,
            congregacao_local_email TEXT,
            versiculo_institucional TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS membros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            rg TEXT,
            orgao_emissor TEXT,
            cpf TEXT,
            data_nascimento TEXT,
            estado_civil TEXT,
            profissao TEXT,
            telefone TEXT,
            celular TEXT,
            email TEXT,
            endereco TEXT,
            numero TEXT,
            bairro TEXT,
            cidade TEXT,
            estado TEXT,
            cep TEXT,
            batismo_aguas TEXT,
            data_batismo_espirito_santo TEXT,
            ministerio TEXT,
            cargo TEXT,
            data_funcao TEXT,
            status TEXT,
            observacoes TEXT,
            caminho_foto TEXT,
            nome_pai TEXT,
            nome_mae TEXT,
            cidade_nascimento TEXT,
            estado_nascimento TEXT,
            nome_conjuge TEXT,
            data_nascimento_conjuge TEXT,
            grau_instrucao TEXT,
            curso_teologico TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documentos_emitidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            membro_id INTEGER NOT NULL,
            tipo_documento TEXT NOT NULL,
            titulo_documento TEXT NOT NULL,
            caminho_arquivo TEXT NOT NULL,
            data_emissao TEXT NOT NULL,
            usuario_emissor TEXT,
            observacao TEXT,
            FOREIGN KEY (membro_id) REFERENCES membros(id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_documentos_emitidos_membro
        ON documentos_emitidos (membro_id, data_emissao)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_documentos_emitidos_caminho
        ON documentos_emitidos (caminho_arquivo)
    """)

    conexao.commit()
    conexao.close()

    garantir_coluna_ativo_usuario()
    garantir_configuracoes_igreja()
    garantir_coluna_foto_membro()
    garantir_coluna_data_funcao_membro()
    garantir_colunas_complementares_membro()
    garantir_tabela_documentos_emitidos()
    garantir_tabela_arquivos_membro()
    garantir_tabela_logs_auditoria()
    garantir_tabelas_pre_cadastro_online()


def garantir_tabela_logs_auditoria():
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs_auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            usuario_nome TEXT,
            usuario_login TEXT,
            acao TEXT NOT NULL,
            descricao TEXT NOT NULL,
            data_hora TEXT NOT NULL,
            modulo TEXT,
            registro_id INTEGER,
            detalhes TEXT
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_logs_auditoria_data
        ON logs_auditoria (data_hora DESC, id DESC)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_logs_auditoria_acao
        ON logs_auditoria (acao)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_logs_auditoria_usuario
        ON logs_auditoria (usuario_login, usuario_nome)
    """)

    conexao.commit()
    conexao.close()


def normalizar_data_filtro(valor, fim_do_dia=False):
    texto = str(valor or "").strip()
    if not texto:
        return None

    if len(texto) == 10:
        return f"{texto} {'23:59:59' if fim_do_dia else '00:00:00'}"

    return texto


def registrar_log_auditoria(
    acao,
    descricao,
    usuario_id=None,
    usuario_nome=None,
    usuario_login=None,
    modulo=None,
    registro_id=None,
    detalhes=None,
):
    try:
        garantir_tabela_logs_auditoria()
        conexao = conectar()
        cursor = conexao.cursor()
        cursor.execute("""
            INSERT INTO logs_auditoria (
                usuario_id,
                usuario_nome,
                usuario_login,
                acao,
                descricao,
                data_hora,
                modulo,
                registro_id,
                detalhes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            usuario_id,
            usuario_nome,
            usuario_login,
            str(acao or "").strip(),
            str(descricao or "").strip(),
            data_hora_atual(),
            modulo,
            registro_id,
            detalhes,
        ))
        id_log = cursor.lastrowid
        conexao.commit()
        conexao.close()
        return id_log
    except Exception as erro:
        try:
            print(f"[AUDITORIA] Falha ao registrar log: {erro}")
        except Exception:
            pass
        return None


def converter_log_auditoria(resultado):
    if not resultado:
        return None

    return {
        campo: resultado[indice] if indice < len(resultado) else ""
        for indice, campo in enumerate(COLUNAS_LOGS_AUDITORIA)
    }


def listar_logs_auditoria(
    termo=None,
    acao=None,
    usuario=None,
    modulo=None,
    data_inicial=None,
    data_final=None,
    limite=None,
):
    garantir_tabela_logs_auditoria()

    filtros = []
    parametros = []

    termo = str(termo or "").strip()
    if termo:
        filtros.append("""
            (
                usuario_nome LIKE ?
                OR usuario_login LIKE ?
                OR acao LIKE ?
                OR modulo LIKE ?
                OR descricao LIKE ?
                OR detalhes LIKE ?
            )
        """)
        parametros.extend([f"%{termo}%"] * 6)

    acao = str(acao or "").strip()
    if acao:
        filtros.append("acao LIKE ?")
        parametros.append(f"%{acao}%")

    usuario = str(usuario or "").strip()
    if usuario:
        filtros.append("(usuario_nome LIKE ? OR usuario_login LIKE ?)")
        parametros.extend([f"%{usuario}%", f"%{usuario}%"])

    modulo = str(modulo or "").strip()
    if modulo:
        filtros.append("modulo LIKE ?")
        parametros.append(f"%{modulo}%")

    data_inicial = normalizar_data_filtro(data_inicial)
    if data_inicial:
        filtros.append("data_hora >= ?")
        parametros.append(data_inicial)

    data_final = normalizar_data_filtro(data_final, fim_do_dia=True)
    if data_final:
        filtros.append("data_hora <= ?")
        parametros.append(data_final)

    sql = f"""
        SELECT {", ".join(COLUNAS_LOGS_AUDITORIA)}
        FROM logs_auditoria
    """

    if filtros:
        sql += " WHERE " + " AND ".join(filtros)

    sql += " ORDER BY data_hora DESC, id DESC"

    if limite:
        sql += " LIMIT ?"
        parametros.append(int(limite))

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute(sql, parametros)
    logs = [
        converter_log_auditoria(resultado)
        for resultado in cursor.fetchall()
    ]
    conexao.close()
    return logs


def buscar_log_auditoria_por_id(id_log):
    garantir_tabela_logs_auditoria()

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute(f"""
        SELECT {", ".join(COLUNAS_LOGS_AUDITORIA)}
        FROM logs_auditoria
        WHERE id = ?
    """, (id_log,))

    log = converter_log_auditoria(cursor.fetchone())
    conexao.close()
    return log


def contar_logs_auditoria():
    garantir_tabela_logs_auditoria()

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute("SELECT COUNT(*) FROM logs_auditoria")
    total = cursor.fetchone()[0]
    conexao.close()
    return total


def garantir_tabelas_pre_cadastro_online():
    garantir_tabela_configuracoes_online_igreja()
    garantir_tabela_pre_cadastros()
    garantir_tabela_sincronizacoes_pre_cadastro()


def garantir_tabela_configuracoes_online_igreja():
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes_online_igreja (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            identificador_publico TEXT,
            chave_sincronizacao TEXT,
            api_base_url TEXT,
            formulario_url TEXT,
            qr_code_path TEXT,
            ativo INTEGER DEFAULT 0,
            status_ativacao TEXT DEFAULT 'pendente',
            ultima_sincronizacao TEXT,
            criado_em TEXT,
            atualizado_em TEXT
        )
    """)

    definicoes = {
        "identificador_publico": "TEXT",
        "chave_sincronizacao": "TEXT",
        "api_base_url": "TEXT",
        "formulario_url": "TEXT",
        "qr_code_path": "TEXT",
        "ativo": "INTEGER DEFAULT 0",
        "status_ativacao": "TEXT DEFAULT 'pendente'",
        "ultima_sincronizacao": "TEXT",
        "criado_em": "TEXT",
        "atualizado_em": "TEXT",
    }
    cursor.execute("PRAGMA table_info(configuracoes_online_igreja)")
    colunas_existentes = {
        str(coluna[1]).lower()
        for coluna in cursor.fetchall()
    }
    for coluna, definicao in definicoes.items():
        if coluna not in colunas_existentes:
            cursor.execute(
                f"ALTER TABLE configuracoes_online_igreja ADD COLUMN {coluna} {definicao}"
            )

    conexao.commit()
    conexao.close()


def garantir_tabela_pre_cadastros():
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pre_cadastros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            remote_id TEXT,
            identificador_publico_igreja TEXT,
            payload_json TEXT,
            nome TEXT,
            rg TEXT,
            orgao_emissor TEXT,
            cpf TEXT,
            data_nascimento TEXT,
            cidade_nascimento TEXT,
            estado_nascimento TEXT,
            estado_civil TEXT,
            nome_conjuge TEXT,
            data_nascimento_conjuge TEXT,
            profissao TEXT,
            nome_pai TEXT,
            nome_mae TEXT,
            grau_instrucao TEXT,
            telefone TEXT,
            celular TEXT,
            email TEXT,
            endereco TEXT,
            numero TEXT,
            bairro TEXT,
            cidade TEXT,
            estado TEXT,
            cep TEXT,
            batismo_aguas TEXT,
            batismo_espirito_santo TEXT,
            ministerio TEXT,
            cargo TEXT,
            data_funcao TEXT,
            curso_teologico TEXT,
            status_membro TEXT,
            congregacao TEXT,
            dirigente TEXT,
            setor_campo TEXT,
            igreja_local_batismo_aguas TEXT,
            igreja_local_batismo_espirito_santo TEXT,
            recados_outros TEXT,
            nome_titular_lgpd TEXT,
            observacoes TEXT,
            caminho_foto TEXT,
            status TEXT DEFAULT 'pendente',
            membro_id_aprovado INTEGER,
            motivo_rejeicao TEXT,
            duplicidade_membro_id INTEGER,
            recebido_em TEXT,
            revisado_em TEXT,
            usuario_revisor TEXT,
            origem TEXT DEFAULT 'sincronizacao',
            atualizado_em TEXT
        )
    """)

    cursor.execute("PRAGMA table_info(pre_cadastros)")
    colunas_existentes = {
        str(coluna[1]).lower()
        for coluna in cursor.fetchall()
    }
    for coluna, definicao in DEFINICOES_COLUNAS_PRE_CADASTROS.items():
        if coluna not in colunas_existentes:
            cursor.execute(
                f"ALTER TABLE pre_cadastros ADD COLUMN {coluna} {definicao}"
            )

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pre_cadastros_remote_id_unico
        ON pre_cadastros (remote_id)
        WHERE remote_id IS NOT NULL
        AND TRIM(remote_id) <> ''
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pre_cadastros_status
        ON pre_cadastros (status, recebido_em DESC, id DESC)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pre_cadastros_cpf
        ON pre_cadastros (cpf)
    """)

    conexao.commit()
    conexao.close()


def garantir_tabela_sincronizacoes_pre_cadastro():
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sincronizacoes_pre_cadastro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
            status TEXT,
            quantidade_recebida INTEGER DEFAULT 0,
            quantidade_nova INTEGER DEFAULT 0,
            quantidade_ignorada INTEGER DEFAULT 0,
            erro TEXT,
            detalhes TEXT
        )
    """)

    definicoes = {
        "data_hora": "TEXT",
        "status": "TEXT",
        "quantidade_recebida": "INTEGER DEFAULT 0",
        "quantidade_nova": "INTEGER DEFAULT 0",
        "quantidade_ignorada": "INTEGER DEFAULT 0",
        "erro": "TEXT",
        "detalhes": "TEXT",
    }
    cursor.execute("PRAGMA table_info(sincronizacoes_pre_cadastro)")
    colunas_existentes = {
        str(coluna[1]).lower()
        for coluna in cursor.fetchall()
    }
    for coluna, definicao in definicoes.items():
        if coluna not in colunas_existentes:
            cursor.execute(
                f"ALTER TABLE sincronizacoes_pre_cadastro ADD COLUMN {coluna} {definicao}"
            )

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sincronizacoes_pre_cadastro_data
        ON sincronizacoes_pre_cadastro (data_hora DESC, id DESC)
    """)

    conexao.commit()
    conexao.close()


def configuracao_online_igreja_vazia():
    return {
        "id": 1,
        "identificador_publico": "",
        "chave_sincronizacao": "",
        "api_base_url": "",
        "formulario_url": "",
        "qr_code_path": "",
        "ativo": 0,
        "status_ativacao": "pendente",
        "ultima_sincronizacao": "",
        "criado_em": "",
        "atualizado_em": "",
    }


def converter_configuracao_online_igreja(resultado):
    dados = configuracao_online_igreja_vazia()
    if not resultado:
        return dados

    for indice, campo in enumerate(COLUNAS_CONFIGURACOES_ONLINE_IGREJA):
        if indice < len(resultado):
            dados[campo] = resultado[indice] or ""

    dados["id"] = int(dados.get("id") or 1)
    dados["ativo"] = int(dados.get("ativo") or 0)
    return dados


def buscar_configuracao_online_igreja():
    garantir_tabela_configuracoes_online_igreja()

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute(f"""
        SELECT {", ".join(COLUNAS_CONFIGURACOES_ONLINE_IGREJA)}
        FROM configuracoes_online_igreja
        WHERE id = 1
    """)
    configuracao = converter_configuracao_online_igreja(cursor.fetchone())
    conexao.close()
    return configuracao


def salvar_configuracao_online_igreja(dados):
    garantir_tabela_configuracoes_online_igreja()

    agora = data_hora_atual()
    dados_atuais = buscar_configuracao_online_igreja()

    def valor_configuracao(campo):
        if campo in dados:
            return dados.get(campo)
        return dados_atuais.get(campo)

    criado_em = valor_configuracao("criado_em") or dados_atuais.get("criado_em") or agora
    valores = {
        "id": 1,
        "identificador_publico": str(valor_configuracao("identificador_publico") or "").strip(),
        "chave_sincronizacao": str(valor_configuracao("chave_sincronizacao") or ""),
        "api_base_url": str(valor_configuracao("api_base_url") or "").strip(),
        "formulario_url": str(valor_configuracao("formulario_url") or "").strip(),
        "qr_code_path": str(valor_configuracao("qr_code_path") or "").strip(),
        "ativo": int(valor_configuracao("ativo") or 0),
        "status_ativacao": str(valor_configuracao("status_ativacao") or "pendente").strip(),
        "ultima_sincronizacao": str(valor_configuracao("ultima_sincronizacao") or ""),
        "criado_em": criado_em,
        "atualizado_em": agora,
    }

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute("""
        INSERT INTO configuracoes_online_igreja (
            id,
            identificador_publico,
            chave_sincronizacao,
            api_base_url,
            formulario_url,
            qr_code_path,
            ativo,
            status_ativacao,
            ultima_sincronizacao,
            criado_em,
            atualizado_em
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            identificador_publico = excluded.identificador_publico,
            chave_sincronizacao = excluded.chave_sincronizacao,
            api_base_url = excluded.api_base_url,
            formulario_url = excluded.formulario_url,
            qr_code_path = excluded.qr_code_path,
            ativo = excluded.ativo,
            status_ativacao = excluded.status_ativacao,
            ultima_sincronizacao = excluded.ultima_sincronizacao,
            criado_em = configuracoes_online_igreja.criado_em,
            atualizado_em = excluded.atualizado_em
    """, (
        valores["id"],
        valores["identificador_publico"],
        valores["chave_sincronizacao"],
        valores["api_base_url"],
        valores["formulario_url"],
        valores["qr_code_path"],
        valores["ativo"],
        valores["status_ativacao"],
        valores["ultima_sincronizacao"],
        valores["criado_em"],
        valores["atualizado_em"],
    ))
    conexao.commit()
    conexao.close()
    return buscar_configuracao_online_igreja()


def atualizar_ultima_sincronizacao(data_hora):
    garantir_tabela_configuracoes_online_igreja()

    configuracao = buscar_configuracao_online_igreja()
    if not configuracao.get("criado_em"):
        configuracao["criado_em"] = data_hora_atual()

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute("""
        INSERT INTO configuracoes_online_igreja (
            id,
            ultima_sincronizacao,
            criado_em,
            atualizado_em
        )
        VALUES (1, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            ultima_sincronizacao = excluded.ultima_sincronizacao,
            atualizado_em = excluded.atualizado_em
    """, (
        data_hora,
        configuracao.get("criado_em") or data_hora_atual(),
        data_hora_atual(),
    ))
    conexao.commit()
    conexao.close()
    return buscar_configuracao_online_igreja()


CAMPOS_DATA_PRE_CADASTRO = (
    "data_nascimento",
    "data_nascimento_conjuge",
    "batismo_aguas",
    "batismo_espirito_santo",
    "data_funcao",
)

_DATA_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ].*)?$")


def data_iso_para_br(valor):
    """Converte AAAA-MM-DD (formato do formulario online) para DD/MM/AAAA.

    Qualquer outro texto (inclusive "Sim"/"Nao" ou datas ja em DD/MM/AAAA)
    e devolvido sem alteracao.
    """
    texto = str(valor or "").strip()
    encontrado = _DATA_ISO.match(texto)
    if not encontrado:
        return texto
    ano, mes, dia = encontrado.groups()
    return f"{dia}/{mes}/{ano}"


def converter_pre_cadastro(resultado):
    if not resultado:
        return None

    campos_inteiros = {
        "id",
        "membro_id_aprovado",
        "duplicidade_membro_id",
    }
    dados = {}
    for indice, campo in enumerate(COLUNAS_PRE_CADASTROS):
        valor = resultado[indice] if indice < len(resultado) else ""
        if valor is None and campo not in campos_inteiros:
            valor = ""
        if campo in CAMPOS_DATA_PRE_CADASTRO:
            valor = data_iso_para_br(valor)
        elif campo == "cpf":
            valor = formatar_cpf(valor)
        elif campo == "rg":
            valor = formatar_rg(valor)
        dados[campo] = valor

    return dados


def buscar_pre_cadastro_por_id(pre_cadastro_id):
    garantir_tabela_pre_cadastros()

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute(f"""
        SELECT {", ".join(COLUNAS_PRE_CADASTROS)}
        FROM pre_cadastros
        WHERE id = ?
    """, (pre_cadastro_id,))
    pre_cadastro = converter_pre_cadastro(cursor.fetchone())
    conexao.close()
    return pre_cadastro


def buscar_pre_cadastro_por_remote_id(remote_id):
    remote_id = str(remote_id or "").strip()
    if not remote_id:
        return None

    garantir_tabela_pre_cadastros()

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute(f"""
        SELECT {", ".join(COLUNAS_PRE_CADASTROS)}
        FROM pre_cadastros
        WHERE remote_id = ?
        LIMIT 1
    """, (remote_id,))
    pre_cadastro = converter_pre_cadastro(cursor.fetchone())
    conexao.close()
    return pre_cadastro


def montar_valores_pre_cadastro(dados):
    dados = dict(dados)
    for campo_data in CAMPOS_DATA_PRE_CADASTRO:
        if campo_data in dados:
            dados[campo_data] = data_iso_para_br(dados.get(campo_data))
    agora = data_hora_atual()
    nome = dados.get("nome")
    if nome is None:
        nome = dados.get("nome_membro")
    caminho_foto = dados.get("caminho_foto")
    if caminho_foto is None:
        caminho_foto = (
            dados.get("foto_membro")
            or dados.get("foto")
            or dados.get("foto_path")
        )

    return {
        "remote_id": str(dados.get("remote_id") or "").strip(),
        "identificador_publico_igreja": str(
            dados.get("identificador_publico_igreja") or ""
        ).strip(),
        "payload_json": str(dados.get("payload_json") or ""),
        "nome": str(nome or "").strip(),
        "rg": formatar_rg(dados.get("rg")),
        "orgao_emissor": str(dados.get("orgao_emissor") or "").strip(),
        "cpf": formatar_cpf(dados.get("cpf")),
        "data_nascimento": str(dados.get("data_nascimento") or "").strip(),
        "cidade_nascimento": str(dados.get("cidade_nascimento") or "").strip(),
        "estado_nascimento": str(dados.get("estado_nascimento") or "").strip(),
        "estado_civil": str(dados.get("estado_civil") or "").strip(),
        "nome_conjuge": str(dados.get("nome_conjuge") or "").strip(),
        "data_nascimento_conjuge": str(
            dados.get("data_nascimento_conjuge") or ""
        ).strip(),
        "profissao": str(dados.get("profissao") or "").strip(),
        "nome_pai": str(dados.get("nome_pai") or "").strip(),
        "nome_mae": str(dados.get("nome_mae") or "").strip(),
        "grau_instrucao": str(dados.get("grau_instrucao") or "").strip(),
        "telefone": str(dados.get("telefone") or "").strip(),
        "celular": str(dados.get("celular") or "").strip(),
        "email": str(dados.get("email") or "").strip(),
        "endereco": str(dados.get("endereco") or "").strip(),
        "numero": str(dados.get("numero") or "").strip(),
        "bairro": str(dados.get("bairro") or "").strip(),
        "cidade": str(dados.get("cidade") or "").strip(),
        "estado": str(dados.get("estado") or "").strip(),
        "cep": str(dados.get("cep") or "").strip(),
        "batismo_aguas": str(dados.get("batismo_aguas") or "").strip(),
        "batismo_espirito_santo": str(
            dados.get("batismo_espirito_santo") or ""
        ).strip(),
        "ministerio": str(dados.get("ministerio") or "").strip(),
        "cargo": str(dados.get("cargo") or "").strip(),
        "data_funcao": str(dados.get("data_funcao") or "").strip(),
        "curso_teologico": str(dados.get("curso_teologico") or "").strip(),
        "status_membro": str(dados.get("status_membro") or "").strip(),
        "congregacao": str(dados.get("congregacao") or "").strip(),
        "dirigente": str(dados.get("dirigente") or "").strip(),
        "setor_campo": str(dados.get("setor_campo") or "").strip(),
        "igreja_local_batismo_aguas": str(
            dados.get("igreja_local_batismo_aguas") or ""
        ).strip(),
        "igreja_local_batismo_espirito_santo": str(
            dados.get("igreja_local_batismo_espirito_santo") or ""
        ).strip(),
        "recados_outros": str(dados.get("recados_outros") or "").strip(),
        "nome_titular_lgpd": str(dados.get("nome_titular_lgpd") or "").strip(),
        "observacoes": str(dados.get("observacoes") or "").strip(),
        "caminho_foto": str(caminho_foto or "").strip(),
        "status": str(dados.get("status") or "pendente").strip() or "pendente",
        "membro_id_aprovado": dados.get("membro_id_aprovado"),
        "motivo_rejeicao": str(dados.get("motivo_rejeicao") or ""),
        "duplicidade_membro_id": dados.get("duplicidade_membro_id"),
        "recebido_em": str(dados.get("recebido_em") or agora),
        "revisado_em": str(dados.get("revisado_em") or ""),
        "usuario_revisor": str(dados.get("usuario_revisor") or "").strip(),
        "origem": str(dados.get("origem") or "sincronizacao").strip() or "sincronizacao",
        "atualizado_em": str(dados.get("atualizado_em") or agora),
    }


def salvar_pre_cadastro(dados):
    garantir_tabela_pre_cadastros()
    valores = montar_valores_pre_cadastro(dados)

    conexao = conectar()
    cursor = conexao.cursor()
    try:
        if valores["remote_id"]:
            cursor.execute(f"""
                SELECT {", ".join(COLUNAS_PRE_CADASTROS)}
                FROM pre_cadastros
                WHERE remote_id = ?
                LIMIT 1
            """, (valores["remote_id"],))
            existente = converter_pre_cadastro(cursor.fetchone())
            if existente:
                return {
                    "inserido": False,
                    "existente": True,
                    "id": existente.get("id"),
                    "registro": existente,
                }

        colunas = ", ".join(COLUNAS_INSERCAO_PRE_CADASTROS)
        parametros = ", ".join("?" for _campo in COLUNAS_INSERCAO_PRE_CADASTROS)
        cursor.execute(
            f"""
            INSERT INTO pre_cadastros ({colunas})
            VALUES ({parametros})
            """,
            tuple(valores[campo] for campo in COLUNAS_INSERCAO_PRE_CADASTROS),
        )
        id_pre_cadastro = cursor.lastrowid
        conexao.commit()
        registro = buscar_pre_cadastro_por_id(id_pre_cadastro)
        return {
            "inserido": True,
            "existente": False,
            "id": id_pre_cadastro,
            "registro": registro,
        }
    except sqlite3.IntegrityError:
        conexao.rollback()
        existente = buscar_pre_cadastro_por_remote_id(valores["remote_id"])
        return {
            "inserido": False,
            "existente": bool(existente),
            "id": existente.get("id") if existente else None,
            "registro": existente,
        }
    finally:
        conexao.close()


def listar_pre_cadastros(status=None):
    garantir_tabela_pre_cadastros()

    parametros = []
    sql = f"""
        SELECT {", ".join(COLUNAS_PRE_CADASTROS)}
        FROM pre_cadastros
    """
    status = str(status or "").strip()
    if status:
        sql += " WHERE status = ?"
        parametros.append(status)

    sql += " ORDER BY recebido_em DESC, id DESC"

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute(sql, parametros)
    registros = [
        converter_pre_cadastro(resultado)
        for resultado in cursor.fetchall()
    ]
    conexao.close()
    return registros


def excluir_pre_cadastro(pre_cadastro_id):
    """Apaga definitivamente um pre-cadastro local. Nao mexe em membros.

    Retorna o registro apagado (dict) ou None se nao existir. A foto em
    disco nao e removida (pode estar em uso pelo membro aprovado).
    """
    garantir_tabela_pre_cadastros()
    registro = buscar_pre_cadastro_por_id(pre_cadastro_id)
    if not registro:
        return None

    conexao = conectar()
    try:
        cursor = conexao.cursor()
        cursor.execute("DELETE FROM pre_cadastros WHERE id = ?", (pre_cadastro_id,))
        apagados = cursor.rowcount
        conexao.commit()
    finally:
        conexao.close()
    return registro if apagados else None


def atualizar_dados_pre_cadastro(pre_cadastro_id, dados):
    garantir_tabela_pre_cadastros()

    campos_permitidos = [
        campo
        for campo in CAMPOS_CADASTRAIS_PRE_CADASTRO
        if campo in dados
    ]
    if "nome" not in campos_permitidos and "nome_membro" in dados:
        campos_permitidos.append("nome")
    if "caminho_foto" not in campos_permitidos and any(
        campo in dados
        for campo in ("foto", "foto_membro", "foto_path")
    ):
        campos_permitidos.append("caminho_foto")

    if not campos_permitidos:
        return buscar_pre_cadastro_por_id(pre_cadastro_id)

    valores_atualizados = montar_valores_pre_cadastro(dados)
    atribuicoes = ", ".join(
        f"{campo} = ?"
        for campo in campos_permitidos
    )
    parametros = [
        valores_atualizados[campo]
        for campo in campos_permitidos
    ]
    if "atualizado_em" not in campos_permitidos:
        atribuicoes += ", atualizado_em = ?"
        parametros.append(data_hora_atual())
    parametros.append(pre_cadastro_id)

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute(
        f"""
        UPDATE pre_cadastros
        SET {atribuicoes}
        WHERE id = ?
        """,
        parametros,
    )
    alterados = cursor.rowcount
    conexao.commit()
    conexao.close()
    if not alterados:
        return None
    return buscar_pre_cadastro_por_id(pre_cadastro_id)


def atualizar_pre_cadastro(pre_cadastro_id, dados):
    return atualizar_dados_pre_cadastro(pre_cadastro_id, dados)


def listar_campos_faltantes_pre_cadastro(pre_cadastro_id):
    pre_cadastro = buscar_pre_cadastro_por_id(pre_cadastro_id)
    if not pre_cadastro:
        return []

    return [
        campo
        for campo in CAMPOS_CADASTRAIS_PRE_CADASTRO
        if not str(pre_cadastro.get(campo) or "").strip()
    ]


def atualizar_status_pre_cadastro(
    pre_cadastro_id,
    status,
    membro_id_aprovado=None,
    motivo_rejeicao=None,
    duplicidade_membro_id=None,
    usuario_revisor=None,
    revisado_em=None,
):
    garantir_tabela_pre_cadastros()
    agora = data_hora_atual()
    revisado_em = revisado_em or agora

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute("""
        UPDATE pre_cadastros
        SET status = ?,
            membro_id_aprovado = ?,
            motivo_rejeicao = ?,
            duplicidade_membro_id = ?,
            usuario_revisor = ?,
            revisado_em = ?,
            atualizado_em = ?
        WHERE id = ?
    """, (
        str(status or "").strip(),
        membro_id_aprovado,
        motivo_rejeicao,
        duplicidade_membro_id,
        usuario_revisor,
        revisado_em,
        agora,
        pre_cadastro_id,
    ))
    alterados = cursor.rowcount
    conexao.commit()
    conexao.close()
    if not alterados:
        return None
    return buscar_pre_cadastro_por_id(pre_cadastro_id)


def converter_sincronizacao_pre_cadastro(resultado):
    if not resultado:
        return None

    return {
        campo: resultado[indice] if indice < len(resultado) else ""
        for indice, campo in enumerate(COLUNAS_SINCRONIZACOES_PRE_CADASTRO)
    }


def registrar_sincronizacao_pre_cadastro(
    status,
    quantidade_recebida=0,
    quantidade_nova=0,
    quantidade_ignorada=0,
    erro=None,
    detalhes=None,
    data_hora=None,
):
    garantir_tabela_sincronizacoes_pre_cadastro()
    data_hora = data_hora or data_hora_atual()

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute("""
        INSERT INTO sincronizacoes_pre_cadastro (
            data_hora,
            status,
            quantidade_recebida,
            quantidade_nova,
            quantidade_ignorada,
            erro,
            detalhes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data_hora,
        status,
        int(quantidade_recebida or 0),
        int(quantidade_nova or 0),
        int(quantidade_ignorada or 0),
        erro,
        detalhes,
    ))
    id_sincronizacao = cursor.lastrowid
    conexao.commit()
    conexao.close()
    return id_sincronizacao


def listar_sincronizacoes_pre_cadastro(limite=50):
    garantir_tabela_sincronizacoes_pre_cadastro()

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute(f"""
        SELECT {", ".join(COLUNAS_SINCRONIZACOES_PRE_CADASTRO)}
        FROM sincronizacoes_pre_cadastro
        ORDER BY data_hora DESC, id DESC
        LIMIT ?
    """, (int(limite or 50),))
    sincronizacoes = [
        converter_sincronizacao_pre_cadastro(resultado)
        for resultado in cursor.fetchall()
    ]
    conexao.close()
    return sincronizacoes


def obter_colunas_tabela(nome_tabela):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute(f"PRAGMA table_info({nome_tabela})")
    colunas = {
        str(coluna[1]).lower(): str(coluna[1])
        for coluna in cursor.fetchall()
    }

    conexao.close()
    return colunas


def garantir_coluna_ativo_usuario():
    colunas = obter_colunas_tabela("usuarios")
    if "ativo" in colunas:
        return

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute("ALTER TABLE usuarios ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1")
    conexao.commit()
    conexao.close()


def obter_coluna_foto_membro():
    colunas = obter_colunas_tabela("membros")

    for campo in CAMPOS_FOTO_MEMBRO:
        coluna = colunas.get(campo)
        if coluna:
            return coluna

    return ""


def garantir_coluna_foto_membro():
    coluna = obter_coluna_foto_membro()
    if coluna:
        return coluna

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute("ALTER TABLE membros ADD COLUMN caminho_foto TEXT")
    conexao.commit()
    conexao.close()

    return "caminho_foto"


def obter_coluna_data_funcao_membro():
    colunas = obter_colunas_tabela("membros")

    for campo in COLUNAS_DATA_FUNCAO_MEMBRO:
        coluna = colunas.get(campo)
        if coluna:
            return coluna

    return ""


def garantir_coluna_data_funcao_membro():
    coluna = obter_coluna_data_funcao_membro()
    if coluna:
        return coluna

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute("ALTER TABLE membros ADD COLUMN data_funcao TEXT")
    conexao.commit()
    conexao.close()

    return "data_funcao"


def garantir_colunas_complementares_membro():
    colunas = obter_colunas_tabela("membros")
    faltantes = [
        (campo, definicao)
        for campo, definicao in COLUNAS_COMPLEMENTARES_MEMBRO.items()
        if campo not in colunas
    ]
    if not faltantes:
        return

    conexao = conectar()
    cursor = conexao.cursor()
    for campo, definicao in faltantes:
        cursor.execute(f"ALTER TABLE membros ADD COLUMN {campo} {definicao}")
    conexao.commit()
    conexao.close()


def buscar_data_funcao_membro(id_membro):
    coluna = garantir_coluna_data_funcao_membro()
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute(
        f"""
        SELECT {coluna}
        FROM membros
        WHERE id = ?
        """,
        (id_membro,),
    )
    resultado = cursor.fetchone()
    conexao.close()

    if not resultado:
        return ""

    return resultado[0] or ""


def existe_administrador():
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM usuarios
        WHERE perfil = 'Administrador'
    """)

    quantidade = cursor.fetchone()[0]
    conexao.close()

    return quantidade > 0


def cadastrar_igreja(nome, ministerio, cidade, estado):
    dados = buscar_configuracoes_igreja()
    dados.update({
        "nome_igreja": nome,
        "ministerio": ministerio,
        "cidade": cidade,
        "estado": estado,
    })
    salvar_configuracoes_igreja(dados)


def buscar_igreja():
    dados = buscar_configuracoes_igreja()
    if any(dados.get(campo) for campo in ("nome_igreja", "ministerio", "cidade", "estado")):
        return (
            1,
            dados.get("nome_igreja", ""),
            dados.get("ministerio", ""),
            dados.get("cidade", ""),
            dados.get("estado", ""),
            dados.get("rua", ""),
            dados.get("telefone", ""),
            dados.get("email", ""),
            dados.get("logotipo", ""),
        )

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, ministerio, cidade, estado, endereco, telefone, email, logo
        FROM igreja
        ORDER BY id ASC
        LIMIT 1
    """)

    igreja = cursor.fetchone()
    conexao.close()

    return igreja


CAMPOS_CONFIGURACOES_IGREJA = [
    "nome_igreja",
    "ministerio",
    "convencao",
    "setor",
    "congregacao_sede",
    "cidade",
    "estado",
    "pastor_presidente",
    "pastor_setorial",
    "telefone",
    "whatsapp",
    "email",
    "site",
    "tema",
    "rua",
    "numero",
    "complemento",
    "bairro",
    "cep",
    "cidade_endereco",
    "estado_endereco",
    "logotipo",
    "carimbo",
    "assinatura_pastor",
    "congregacao_local_nome",
    "congregacao_local_dirigente",
    "congregacao_local_numero",
    "congregacao_local_campo_setor",
    "congregacao_local_cidade",
    "congregacao_local_estado",
    "congregacao_local_rua",
    "congregacao_local_numero_endereco",
    "congregacao_local_bairro",
    "congregacao_local_cep",
    "congregacao_local_telefone",
    "congregacao_local_whatsapp",
    "congregacao_local_email",
    "versiculo_institucional",
]


def configuracao_igreja_vazia():
    return {campo: "" for campo in CAMPOS_CONFIGURACOES_IGREJA}


def garantir_configuracoes_igreja():
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes_igreja (
            id INTEGER PRIMARY KEY CHECK (id = 1)
        )
    """)

    cursor.execute("PRAGMA table_info(configuracoes_igreja)")
    colunas_existentes = {
        coluna[1]
        for coluna in cursor.fetchall()
    }

    for campo in CAMPOS_CONFIGURACOES_IGREJA:
        if campo not in colunas_existentes:
            cursor.execute(
                f"ALTER TABLE configuracoes_igreja ADD COLUMN {campo} TEXT"
            )

    cursor.execute("""
        INSERT OR IGNORE INTO configuracoes_igreja (id)
        VALUES (1)
    """)

    cursor.execute("""
        SELECT nome_igreja, ministerio, cidade, estado, telefone, email, logotipo
        FROM configuracoes_igreja
        WHERE id = 1
    """)
    configuracao_atual = cursor.fetchone() or ()

    if not any(configuracao_atual):
        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name = 'igreja'
        """)
        if not cursor.fetchone():
            conexao.commit()
            conexao.close()
            return

        cursor.execute("""
            SELECT nome, ministerio, cidade, estado, telefone, email, logo
            FROM igreja
            ORDER BY id ASC
            LIMIT 1
        """)
        igreja_legada = cursor.fetchone()
        if igreja_legada:
            cursor.execute("""
                UPDATE configuracoes_igreja
                SET nome_igreja = ?,
                    ministerio = ?,
                    cidade = ?,
                    estado = ?,
                    telefone = ?,
                    email = ?,
                    logotipo = ?
                WHERE id = 1
            """, igreja_legada)

    conexao.commit()
    conexao.close()


def buscar_configuracoes_igreja():
    garantir_configuracoes_igreja()

    conexao = conectar()
    cursor = conexao.cursor()

    colunas = ", ".join(CAMPOS_CONFIGURACOES_IGREJA)
    cursor.execute(f"""
        SELECT {colunas}
        FROM configuracoes_igreja
        WHERE id = 1
    """)

    resultado = cursor.fetchone()
    conexao.close()

    if not resultado:
        return configuracao_igreja_vazia()

    return {
        campo: resultado[indice] or ""
        for indice, campo in enumerate(CAMPOS_CONFIGURACOES_IGREJA)
    }


def salvar_configuracoes_igreja(dados):
    garantir_configuracoes_igreja()

    conexao = conectar()
    cursor = conexao.cursor()

    atribuicoes = ", ".join(
        f"{campo} = ?"
        for campo in CAMPOS_CONFIGURACOES_IGREJA
    )
    valores = [
        dados.get(campo, "")
        for campo in CAMPOS_CONFIGURACOES_IGREJA
    ]

    cursor.execute(
        f"""
        UPDATE configuracoes_igreja
        SET {atribuicoes}
        WHERE id = 1
        """,
        valores
    )

    conexao.commit()
    conexao.close()


def cadastrar_usuario(nome, usuario, senha, perfil):
    conexao = conectar()
    cursor = conexao.cursor()

    senha_hash = gerar_hash_senha(senha)

    cursor.execute("""
        INSERT INTO usuarios (nome, usuario, senha, perfil)
        VALUES (?, ?, ?, ?)
    """, (nome, usuario, senha_hash, perfil))

    id_usuario = cursor.lastrowid
    conexao.commit()
    conexao.close()
    return id_usuario


def validar_login(usuario, senha):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, usuario, senha, perfil, ativo
        FROM usuarios
        WHERE usuario = ?
    """, (usuario,))

    resultado = cursor.fetchone()
    conexao.close()

    if resultado:
        id_usuario = resultado[0]
        nome_banco = resultado[1]
        usuario_banco = resultado[2]
        senha_hash_banco = resultado[3]
        perfil_banco = resultado[4]
        ativo = resultado[5]

        if not ativo:
            return {
                "bloqueado": True,
                "nome": nome_banco,
                "usuario": usuario_banco,
            }

        if verificar_senha(senha, senha_hash_banco):
            return {
                "id_usuario": id_usuario,
                "nome": nome_banco,
                "usuario": usuario_banco,
                "login": usuario_banco,
                "perfil": perfil_banco,
                "status": "Ativo",
            }

    return None


def listar_usuarios():
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, usuario, perfil, ativo
        FROM usuarios
        ORDER BY nome ASC
    """)

    usuarios = [
        {
            "id": resultado[0],
            "nome": resultado[1] or "",
            "usuario": resultado[2] or "",
            "perfil": resultado[3] or "",
            "ativo": int(resultado[4] or 0),
            "status": "Ativo" if int(resultado[4] or 0) else "Bloqueado",
        }
        for resultado in cursor.fetchall()
    ]
    conexao.close()
    return usuarios


def buscar_usuario_por_id(id_usuario):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, usuario, perfil, ativo
        FROM usuarios
        WHERE id = ?
    """, (id_usuario,))

    resultado = cursor.fetchone()
    conexao.close()

    if not resultado:
        return None

    return {
        "id": resultado[0],
        "nome": resultado[1] or "",
        "usuario": resultado[2] or "",
        "perfil": resultado[3] or "",
        "ativo": int(resultado[4] or 0),
        "status": "Ativo" if int(resultado[4] or 0) else "Bloqueado",
    }


def total_administradores_ativos():
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM usuarios
        WHERE perfil = 'Administrador'
        AND ativo = 1
    """)

    total = cursor.fetchone()[0]
    conexao.close()
    return total


def usuario_eh_ultimo_admin_ativo(id_usuario):
    usuario = buscar_usuario_por_id(id_usuario)
    if not usuario:
        return False

    return (
        usuario["perfil"] == "Administrador"
        and usuario["ativo"] == 1
        and total_administradores_ativos() <= 1
    )


def atualizar_usuario(id_usuario, nome, usuario, perfil, ativo):
    if usuario_eh_ultimo_admin_ativo(id_usuario) and (
        perfil != "Administrador" or int(ativo) != 1
    ):
        raise ValueError("Nao e permitido alterar ou bloquear o ultimo Administrador ativo.")

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE usuarios
        SET nome = ?,
            usuario = ?,
            perfil = ?,
            ativo = ?
        WHERE id = ?
    """, (nome, usuario, perfil, int(ativo), id_usuario))

    alterados = cursor.rowcount
    conexao.commit()
    conexao.close()
    return alterados > 0


def redefinir_senha_usuario(id_usuario, nova_senha):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE usuarios
        SET senha = ?
        WHERE id = ?
    """, (gerar_hash_senha(nova_senha), id_usuario))

    alterados = cursor.rowcount
    conexao.commit()
    conexao.close()
    return alterados > 0


def alterar_status_usuario(id_usuario, ativo):
    if int(ativo) != 1 and usuario_eh_ultimo_admin_ativo(id_usuario):
        raise ValueError("Nao e permitido bloquear o ultimo Administrador ativo.")

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE usuarios
        SET ativo = ?
        WHERE id = ?
    """, (int(ativo), id_usuario))

    alterados = cursor.rowcount
    conexao.commit()
    conexao.close()
    return alterados > 0


def excluir_usuario(id_usuario):
    if usuario_eh_ultimo_admin_ativo(id_usuario):
        raise ValueError("Nao e permitido excluir o ultimo Administrador ativo.")

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        DELETE FROM usuarios
        WHERE id = ?
    """, (id_usuario,))

    removidos = cursor.rowcount
    conexao.commit()
    conexao.close()
    return removidos > 0


def cadastrar_membro(dados):
    coluna_data_funcao = garantir_coluna_data_funcao_membro()
    garantir_colunas_complementares_membro()
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO membros (
            nome, rg, orgao_emissor, cpf, data_nascimento,
            estado_civil, profissao, telefone, celular, email,
            endereco, numero, bairro, cidade, estado,
            cep, batismo_aguas, ministerio, cargo, status, observacoes,
            nome_pai, nome_mae, cidade_nascimento, estado_nascimento,
            nome_conjuge, data_nascimento_conjuge,
            grau_instrucao, curso_teologico,
            data_batismo_espirito_santo
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        dados["nome"],
        dados["rg"],
        dados["orgao_emissor"],
        dados["cpf"],
        dados["data_nascimento"],
        dados["estado_civil"],
        dados["profissao"],
        dados["telefone"],
        dados["celular"],
        dados["email"],
        dados["endereco"],
        dados["numero"],
        dados["bairro"],
        dados["cidade"],
        dados["estado"],
        dados.get("cep", ""),
        dados["batismo_aguas"],
        dados["ministerio"],
        dados["cargo"],
        dados["status"],
        dados["observacoes"],
        dados.get("nome_pai", ""),
        dados.get("nome_mae", ""),
        dados.get("cidade_nascimento", ""),
        dados.get("estado_nascimento", ""),
        dados.get("nome_conjuge", ""),
        dados.get("data_nascimento_conjuge", ""),
        dados.get("grau_instrucao", ""),
        dados.get("curso_teologico", ""),
        dados.get("data_batismo_espirito_santo", "")
    ))

    id_membro = cursor.lastrowid
    cursor.execute(
        f"""
        UPDATE membros
        SET {coluna_data_funcao} = ?
        WHERE id = ?
        """,
        (dados.get("data_funcao", ""), id_membro),
    )
    conexao.commit()
    conexao.close()
    return id_membro


def listar_membros():
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, celular, cidade, status
        FROM membros
        ORDER BY nome ASC
    """)

    membros = cursor.fetchall()
    conexao.close()

    return membros


def buscar_membro_por_id(id_membro):
    garantir_colunas_complementares_membro()
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT
            id,
            nome,
            rg,
            orgao_emissor,
            cpf,
            data_nascimento,
            estado_civil,
            profissao,
            telefone,
            celular,
            email,
            endereco,
            numero,
            bairro,
            cidade,
            estado,
            batismo_aguas,
            ministerio,
            cargo,
            status,
            observacoes,
            nome_pai,
            nome_mae,
            cidade_nascimento,
            estado_nascimento,
            nome_conjuge,
            data_nascimento_conjuge,
            grau_instrucao,
            curso_teologico,
            data_batismo_espirito_santo,
            cep
        FROM membros
        WHERE id = ?
    """, (id_membro,))

    membro = cursor.fetchone()
    conexao.close()

    return membro

def total_membros():
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("SELECT COUNT(*) FROM membros")
    total = cursor.fetchone()[0]

    conexao.close()
    return total


def total_por_status(status):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM membros
        WHERE status = ?
    """, (status,))

    total = cursor.fetchone()[0]

    conexao.close()
    return total


def ultimos_membros_cadastrados(limite=5):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, status
        FROM membros
        ORDER BY id DESC
        LIMIT ?
    """, (limite,))

    membros = [
        {
            "id": resultado[0],
            "nome": resultado[1] or "",
            "status": resultado[2] or "",
        }
        for resultado in cursor.fetchall()
    ]
    conexao.close()
    return membros


def total_documentos_emitidos():
    garantir_tabela_documentos_emitidos()

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("SELECT COUNT(*) FROM documentos_emitidos")
    total = cursor.fetchone()[0]

    conexao.close()
    return total


def total_documentos_emitidos_hoje():
    garantir_tabela_documentos_emitidos()
    hoje = datetime.now().strftime("%Y-%m-%d")

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM documentos_emitidos
        WHERE data_emissao LIKE ?
    """, (f"{hoje}%",))

    total = cursor.fetchone()[0]
    conexao.close()
    return total


def total_arquivos_anexados():
    garantir_tabela_arquivos_membro()

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("SELECT COUNT(*) FROM arquivos_membro")
    total = cursor.fetchone()[0]

    conexao.close()
    return total


def listar_documentos_emitidos_recentes(limite=5):
    garantir_tabela_documentos_emitidos()

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT
            documentos_emitidos.id,
            documentos_emitidos.titulo_documento,
            documentos_emitidos.data_emissao,
            documentos_emitidos.usuario_emissor,
            membros.nome
        FROM documentos_emitidos
        LEFT JOIN membros ON membros.id = documentos_emitidos.membro_id
        ORDER BY documentos_emitidos.data_emissao DESC, documentos_emitidos.id DESC
        LIMIT ?
    """, (limite,))

    documentos = [
        {
            "id": resultado[0],
            "titulo": resultado[1] or "",
            "data": resultado[2] or "",
            "usuario": resultado[3] or "",
            "membro": resultado[4] or "",
        }
        for resultado in cursor.fetchall()
    ]
    conexao.close()
    return documentos


def listar_arquivos_anexados_recentes(limite=5):
    garantir_tabela_arquivos_membro()

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT
            arquivos_membro.id,
            arquivos_membro.tipo_arquivo,
            arquivos_membro.titulo,
            arquivos_membro.data_anexo,
            arquivos_membro.usuario_responsavel,
            membros.nome
        FROM arquivos_membro
        LEFT JOIN membros ON membros.id = arquivos_membro.membro_id
        ORDER BY arquivos_membro.data_anexo DESC, arquivos_membro.id DESC
        LIMIT ?
    """, (limite,))

    arquivos = [
        {
            "id": resultado[0],
            "tipo": resultado[1] or "",
            "titulo": resultado[2] or "",
            "data": resultado[3] or "",
            "usuario": resultado[4] or "",
            "membro": resultado[5] or "",
        }
        for resultado in cursor.fetchall()
    ]
    conexao.close()
    return arquivos


def proximos_aniversariantes(limite=5):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, data_nascimento
        FROM membros
        WHERE data_nascimento IS NOT NULL
        AND TRIM(data_nascimento) <> ''
    """)

    hoje = datetime.now().date()
    aniversariantes = []

    for id_membro, nome, data_nascimento in cursor.fetchall():
        nascimento = interpretar_data_nascimento(data_nascimento)
        if nascimento is None:
            continue

        try:
            proximo = nascimento.replace(year=hoje.year)
        except ValueError:
            proximo = nascimento.replace(year=hoje.year, day=28)

        if proximo < hoje:
            try:
                proximo = nascimento.replace(year=hoje.year + 1)
            except ValueError:
                proximo = nascimento.replace(year=hoje.year + 1, day=28)

        aniversariantes.append({
            "id": id_membro,
            "nome": nome or "",
            "data_nascimento": data_nascimento or "",
            "proximo": proximo,
            "dias": (proximo - hoje).days,
        })

    conexao.close()

    aniversariantes.sort(key=lambda item: (item["dias"], item["nome"]))
    return aniversariantes[:limite]


def interpretar_data_nascimento(valor):
    texto = str(valor or "").strip()
    if not texto:
        return None

    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            pass

    return None


def atualizar_membro(id_membro, dados):
    coluna_data_funcao = garantir_coluna_data_funcao_membro()
    garantir_colunas_complementares_membro()
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE membros SET
            nome = ?,
            rg = ?,
            orgao_emissor = ?,
            cpf = ?,
            data_nascimento = ?,
            estado_civil = ?,
            profissao = ?,
            telefone = ?,
            celular = ?,
            email = ?,
            endereco = ?,
            numero = ?,
            bairro = ?,
            cidade = ?,
            estado = ?,
            cep = ?,
            batismo_aguas = ?,
            ministerio = ?,
            cargo = ?,
            status = ?,
            observacoes = ?,
            nome_pai = ?,
            nome_mae = ?,
            cidade_nascimento = ?,
            estado_nascimento = ?,
            nome_conjuge = ?,
            data_nascimento_conjuge = ?,
            grau_instrucao = ?,
            curso_teologico = ?,
            data_batismo_espirito_santo = ?
        WHERE id = ?
    """, (
        dados["nome"],
        dados["rg"],
        dados["orgao_emissor"],
        dados["cpf"],
        dados["data_nascimento"],
        dados["estado_civil"],
        dados["profissao"],
        dados["telefone"],
        dados["celular"],
        dados["email"],
        dados["endereco"],
        dados["numero"],
        dados["bairro"],
        dados["cidade"],
        dados["estado"],
        dados.get("cep", ""),
        dados["batismo_aguas"],
        dados["ministerio"],
        dados["cargo"],
        dados["status"],
        dados["observacoes"],
        dados.get("nome_pai", ""),
        dados.get("nome_mae", ""),
        dados.get("cidade_nascimento", ""),
        dados.get("estado_nascimento", ""),
        dados.get("nome_conjuge", ""),
        dados.get("data_nascimento_conjuge", ""),
        dados.get("grau_instrucao", ""),
        dados.get("curso_teologico", ""),
        dados.get("data_batismo_espirito_santo", ""),
        id_membro
    ))

    cursor.execute(
        f"""
        UPDATE membros
        SET {coluna_data_funcao} = ?
        WHERE id = ?
        """,
        (dados.get("data_funcao", ""), id_membro),
    )

    conexao.commit()
    conexao.close()


def excluir_membro(id_membro):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        DELETE FROM membros
        WHERE id = ?
    """, (id_membro,))

    conexao.commit()
    conexao.close()


def garantir_tabela_documentos_emitidos():
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documentos_emitidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            membro_id INTEGER NOT NULL,
            tipo_documento TEXT NOT NULL,
            titulo_documento TEXT NOT NULL,
            caminho_arquivo TEXT NOT NULL,
            data_emissao TEXT NOT NULL,
            usuario_emissor TEXT,
            observacao TEXT,
            FOREIGN KEY (membro_id) REFERENCES membros(id)
        )
    """)

    cursor.execute("PRAGMA table_info(documentos_emitidos)")
    colunas_existentes = {
        str(coluna[1]).lower()
        for coluna in cursor.fetchall()
    }

    for coluna, definicao in COLUNAS_DOCUMENTOS_EMITIDOS.items():
        if coluna not in colunas_existentes:
            definicao_migracao = definicao.replace(" NOT NULL", "")
            cursor.execute(
                f"ALTER TABLE documentos_emitidos ADD COLUMN {coluna} {definicao_migracao}"
            )

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_documentos_emitidos_membro
        ON documentos_emitidos (membro_id, data_emissao)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_documentos_emitidos_caminho
        ON documentos_emitidos (caminho_arquivo)
    """)

    conexao.commit()
    conexao.close()


def normalizar_caminho_documento(caminho_arquivo):
    caminho = Path(str(caminho_arquivo or "")).expanduser()
    try:
        caminho = caminho.resolve(strict=False)
    except Exception:
        caminho = Path(os.path.abspath(os.path.normpath(str(caminho))))

    return os.path.normcase(os.path.normpath(str(caminho)))


def converter_documento_emitido(resultado):
    if not resultado:
        return None

    campos = (
        "id",
        "membro_id",
        "tipo_documento",
        "titulo_documento",
        "caminho_arquivo",
        "data_emissao",
        "usuario_emissor",
        "observacao",
    )
    return {
        campo: resultado[indice] if indice < len(resultado) else ""
        for indice, campo in enumerate(campos)
    }


def registrar_documento_emitido(
    membro_id,
    tipo_documento,
    titulo_documento,
    caminho_arquivo,
    data_emissao=None,
    usuario_emissor=None,
    observacao=None,
):
    garantir_tabela_documentos_emitidos()
    if data_emissao is None:
        data_emissao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    caminho_normalizado = normalizar_caminho_documento(caminho_arquivo)

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id
        FROM documentos_emitidos
        WHERE caminho_arquivo = ?
        OR lower(caminho_arquivo) = lower(?)
        LIMIT 1
    """, (caminho_normalizado, caminho_normalizado))

    registro_existente = cursor.fetchone()
    if registro_existente:
        conexao.close()
        return registro_existente[0]

    cursor.execute("""
        SELECT id, caminho_arquivo
        FROM documentos_emitidos
    """)

    for id_existente, caminho_existente in cursor.fetchall():
        if normalizar_caminho_documento(caminho_existente) == caminho_normalizado:
            conexao.close()
            return id_existente

    cursor.execute("""
        INSERT INTO documentos_emitidos (
            membro_id,
            tipo_documento,
            titulo_documento,
            caminho_arquivo,
            data_emissao,
            usuario_emissor,
            observacao
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        membro_id,
        tipo_documento,
        titulo_documento,
        caminho_normalizado,
        data_emissao,
        usuario_emissor,
        observacao,
    ))

    id_documento = cursor.lastrowid
    conexao.commit()
    conexao.close()
    return id_documento


def listar_documentos_emitidos_por_membro(membro_id):
    garantir_tabela_documentos_emitidos()

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT
            id,
            membro_id,
            tipo_documento,
            titulo_documento,
            caminho_arquivo,
            data_emissao,
            usuario_emissor,
            observacao
        FROM documentos_emitidos
        WHERE membro_id = ?
        ORDER BY data_emissao DESC, id DESC
    """, (membro_id,))

    documentos = [
        converter_documento_emitido(resultado)
        for resultado in cursor.fetchall()
    ]
    conexao.close()
    return documentos


def listar_documentos_emitidos(limite=None):
    garantir_tabela_documentos_emitidos()

    parametros = []
    sql = """
        SELECT
            id,
            membro_id,
            tipo_documento,
            titulo_documento,
            caminho_arquivo,
            data_emissao,
            usuario_emissor,
            observacao
        FROM documentos_emitidos
        ORDER BY data_emissao DESC, id DESC
    """
    if limite:
        sql += " LIMIT ?"
        parametros.append(int(limite))

    conexao = conectar()
    cursor = conexao.cursor()
    cursor.execute(sql, parametros)
    documentos = [
        converter_documento_emitido(resultado)
        for resultado in cursor.fetchall()
    ]
    conexao.close()
    return documentos


def buscar_documento_emitido_por_id(id_documento):
    garantir_tabela_documentos_emitidos()

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT
            id,
            membro_id,
            tipo_documento,
            titulo_documento,
            caminho_arquivo,
            data_emissao,
            usuario_emissor,
            observacao
        FROM documentos_emitidos
        WHERE id = ?
    """, (id_documento,))

    documento = converter_documento_emitido(cursor.fetchone())
    conexao.close()
    return documento


def excluir_registro_documento(id_documento):
    garantir_tabela_documentos_emitidos()

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        DELETE FROM documentos_emitidos
        WHERE id = ?
    """, (id_documento,))

    removidos = cursor.rowcount
    conexao.commit()
    conexao.close()
    return removidos > 0


def garantir_tabela_arquivos_membro():
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS arquivos_membro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            membro_id INTEGER NOT NULL,
            tipo_arquivo TEXT NOT NULL,
            titulo TEXT NOT NULL,
            nome_original TEXT NOT NULL,
            caminho_arquivo TEXT NOT NULL,
            data_anexo TEXT NOT NULL,
            usuario_responsavel TEXT,
            observacao TEXT,
            FOREIGN KEY (membro_id) REFERENCES membros(id)
        )
    """)

    cursor.execute("PRAGMA table_info(arquivos_membro)")
    colunas_existentes = {
        str(coluna[1]).lower()
        for coluna in cursor.fetchall()
    }

    for coluna, definicao in COLUNAS_ARQUIVOS_MEMBRO.items():
        if coluna not in colunas_existentes:
            definicao_migracao = definicao.replace(" NOT NULL", "")
            cursor.execute(
                f"ALTER TABLE arquivos_membro ADD COLUMN {coluna} {definicao_migracao}"
            )

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_arquivos_membro_membro
        ON arquivos_membro (membro_id, data_anexo)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_arquivos_membro_caminho
        ON arquivos_membro (caminho_arquivo)
    """)

    conexao.commit()
    conexao.close()


def converter_arquivo_membro(resultado):
    if not resultado:
        return None

    campos = (
        "id",
        "membro_id",
        "tipo_arquivo",
        "titulo",
        "nome_original",
        "caminho_arquivo",
        "data_anexo",
        "usuario_responsavel",
        "observacao",
    )
    return {
        campo: resultado[indice] if indice < len(resultado) else ""
        for indice, campo in enumerate(campos)
    }


def registrar_arquivo_membro(
    membro_id,
    tipo_arquivo,
    titulo,
    nome_original,
    caminho_arquivo,
    data_anexo=None,
    usuario_responsavel=None,
    observacao=None,
):
    garantir_tabela_arquivos_membro()
    if data_anexo is None:
        data_anexo = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    caminho_normalizado = normalizar_caminho_documento(caminho_arquivo)

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO arquivos_membro (
            membro_id,
            tipo_arquivo,
            titulo,
            nome_original,
            caminho_arquivo,
            data_anexo,
            usuario_responsavel,
            observacao
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        membro_id,
        tipo_arquivo,
        titulo,
        nome_original,
        caminho_normalizado,
        data_anexo,
        usuario_responsavel,
        observacao,
    ))

    id_arquivo = cursor.lastrowid
    conexao.commit()
    conexao.close()
    return id_arquivo


def listar_arquivos_membro(membro_id):
    garantir_tabela_arquivos_membro()

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT
            id,
            membro_id,
            tipo_arquivo,
            titulo,
            nome_original,
            caminho_arquivo,
            data_anexo,
            usuario_responsavel,
            observacao
        FROM arquivos_membro
        WHERE membro_id = ?
        ORDER BY data_anexo DESC, id DESC
    """, (membro_id,))

    arquivos = [
        converter_arquivo_membro(resultado)
        for resultado in cursor.fetchall()
    ]
    conexao.close()
    return arquivos


def buscar_arquivo_membro_por_id(id_arquivo):
    garantir_tabela_arquivos_membro()

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT
            id,
            membro_id,
            tipo_arquivo,
            titulo,
            nome_original,
            caminho_arquivo,
            data_anexo,
            usuario_responsavel,
            observacao
        FROM arquivos_membro
        WHERE id = ?
    """, (id_arquivo,))

    arquivo = converter_arquivo_membro(cursor.fetchone())
    conexao.close()
    return arquivo


def atualizar_titulo_arquivo_membro(id_arquivo, titulo):
    garantir_tabela_arquivos_membro()

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE arquivos_membro
        SET titulo = ?
        WHERE id = ?
    """, (titulo, id_arquivo))

    alterados = cursor.rowcount
    conexao.commit()
    conexao.close()
    return alterados > 0


def excluir_registro_arquivo(id_arquivo):
    garantir_tabela_arquivos_membro()

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        DELETE FROM arquivos_membro
        WHERE id = ?
    """, (id_arquivo,))

    removidos = cursor.rowcount
    conexao.commit()
    conexao.close()
    return removidos > 0
