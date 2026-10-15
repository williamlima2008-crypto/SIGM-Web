"""
==========================================================
SIGM - Sistema de Gestão de Membros

Arquivo: recuperacao_senha.py
Descrição: Recuperação de senha por CHAVE DE RECUPERAÇÃO.

Como funciona:
- O Administrador possui uma chave de recuperação (ex.: K7M2-9QXA-4TPD-HW6R),
  gerada no primeiro acesso ao sistema ou, depois, na tela de Usuários.
- A chave aparece uma única vez; o sistema guarda apenas uma "impressão
  digital" dela (PBKDF2 com sal), nunca a chave em si.
- Na tela de login, depois de 3 tentativas erradas, o usuário pode informar
  usuário + chave de recuperação + nova senha para redefinir a senha.
- Depois de usada, a chave é substituída por uma nova (uso único), que deve
  ser guardada novamente.

Este módulo é independente: só cria uma tabela nova (seguranca) e usa a
função já existente redefinir_senha_usuario(). Não altera nenhuma tabela
ou regra de login existente.

Desenvolvido por:
William Lima

"Servindo à Igreja com organização e excelência."
==========================================================
"""
import hashlib
import hmac
import secrets
from datetime import datetime

from banco.database import conectar, redefinir_senha_usuario

# Alfabeto sem caracteres que se confundem (I, O, 0, 1).
ALFABETO_CHAVE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TAMANHO_CHAVE = 16
ITERACOES_PBKDF2 = 200_000

_CAMPO_HASH = "recuperacao_chave_hash"
_CAMPO_SALT = "recuperacao_chave_salt"
_CAMPO_CRIADA_EM = "recuperacao_chave_criada_em"

MENSAGEM_DADOS_INVALIDOS = "Usuário ou chave de recuperação inválidos."


def garantir_tabela_seguranca():
    conexao = conectar()
    try:
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS seguranca (
                chave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            )
            """
        )
        conexao.commit()
    finally:
        conexao.close()


def _ler(campo):
    garantir_tabela_seguranca()
    conexao = conectar()
    try:
        linha = conexao.execute(
            "SELECT valor FROM seguranca WHERE chave = ?",
            (campo,),
        ).fetchone()
    finally:
        conexao.close()

    return linha[0] if linha else None


def _gravar(valores):
    garantir_tabela_seguranca()
    conexao = conectar()
    try:
        for campo, valor in valores.items():
            conexao.execute(
                "INSERT OR REPLACE INTO seguranca (chave, valor) VALUES (?, ?)",
                (campo, valor),
            )
        conexao.commit()
    finally:
        conexao.close()


def normalizar_chave(texto):
    """Deixa só letras/números em maiúsculas (aceita espaços e hífens na digitação)."""
    return "".join(c for c in str(texto or "").upper() if c.isalnum())


def _derivar(chave_normalizada, salt_hex):
    return hashlib.pbkdf2_hmac(
        "sha256",
        chave_normalizada.encode("utf-8"),
        bytes.fromhex(salt_hex),
        ITERACOES_PBKDF2,
    ).hex()


def gerar_chave_recuperacao():
    """
    Gera uma NOVA chave de recuperação (a anterior deixa de valer) e a
    devolve no formato XXXX-XXXX-XXXX-XXXX. Só a impressão digital é gravada.
    """
    bruta = "".join(secrets.choice(ALFABETO_CHAVE) for _ in range(TAMANHO_CHAVE))
    salt = secrets.token_hex(16)

    _gravar(
        {
            _CAMPO_HASH: _derivar(bruta, salt),
            _CAMPO_SALT: salt,
            _CAMPO_CRIADA_EM: datetime.now().strftime("%d/%m/%Y %H:%M"),
        }
    )

    return "-".join(bruta[i:i + 4] for i in range(0, TAMANHO_CHAVE, 4))


def existe_chave_recuperacao():
    return bool(_ler(_CAMPO_HASH) and _ler(_CAMPO_SALT))


def data_chave_recuperacao():
    return _ler(_CAMPO_CRIADA_EM) or ""


def validar_chave_recuperacao(chave_digitada):
    hash_salvo = _ler(_CAMPO_HASH)
    salt = _ler(_CAMPO_SALT)
    if not hash_salvo or not salt:
        return False

    normalizada = normalizar_chave(chave_digitada)
    if len(normalizada) != TAMANHO_CHAVE:
        return False

    return hmac.compare_digest(_derivar(normalizada, salt), hash_salvo)


def redefinir_senha_com_chave(usuario, chave, nova_senha):
    """
    Redefine a senha de 'usuario' se a chave de recuperação estiver correta.

    Retorna (sucesso, mensagem, dados_usuario). A mensagem de erro é a mesma
    para "usuário inexistente" e "chave errada", para não revelar quais
    usuários existem.
    """
    usuario = str(usuario or "").strip()
    chave = str(chave or "").strip()
    # O login também remove espaços das pontas da senha; fazemos igual aqui
    # para que a nova senha sempre consiga ser digitada depois.
    nova_senha = str(nova_senha or "").strip()

    if not usuario or not chave or not nova_senha:
        return False, "Preencha usuário, chave de recuperação e nova senha.", None

    if not existe_chave_recuperacao():
        return (
            False,
            "Ainda não existe chave de recuperação neste computador. "
            "Peça a um Administrador para redefinir sua senha em Usuários.",
            None,
        )

    if not validar_chave_recuperacao(chave):
        return False, MENSAGEM_DADOS_INVALIDOS, None

    conexao = conectar()
    try:
        linha = conexao.execute(
            "SELECT id, nome, usuario, ativo FROM usuarios WHERE usuario = ?",
            (usuario,),
        ).fetchone()
    finally:
        conexao.close()

    if not linha:
        return False, MENSAGEM_DADOS_INVALIDOS, None

    if not linha[3]:
        return False, "Usuário bloqueado. Procure o Administrador.", None

    if not redefinir_senha_usuario(linha[0], nova_senha):
        return False, "Não foi possível redefinir a senha.", None

    return True, "Senha redefinida com sucesso.", {
        "id": linha[0],
        "nome": linha[1],
        "usuario": linha[2],
    }
