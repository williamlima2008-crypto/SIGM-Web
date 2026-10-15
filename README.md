# SIGM - Sistema de Gestao de Membros

Versao: 1.0.1  
Desenvolvedor: William Lima

O SIGM e um sistema desktop para gestao de membros, configuracoes institucionais da igreja, documentos oficiais, arquivos anexados, historico de documentos, usuarios e auditoria.

## Principais Funcionalidades

- Cadastro, consulta, edicao e ficha completa de membros.
- Dossie digital do membro.
- Configuracoes centralizadas da igreja e congregacao local.
- Geracao de documentos oficiais em PDF.
- Historico de documentos emitidos.
- Arquivos anexados por membro.
- Controle de usuarios e primeiro acesso.
- Log de auditoria.
- Relatorios de auditoria.

## Requisitos

- Python 3.12 ou superior recomendado.
- Windows para uso final com instalador.
- Dependencias listadas em `requirements.txt`.

## Executar em Desenvolvimento

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Instalacao Limpa

Em uma instalacao sem banco de dados, o SIGM cria automaticamente:

- `sigm.db`
- tabelas e colunas necessarias
- pastas de dados gerados
- fluxo de primeiro acesso

No primeiro acesso, cadastre os dados da igreja e o primeiro usuario Administrador. Depois disso o sistema segue para a tela de login.

## Estrutura Basica

- `app.py`: entrada do sistema.
- `banco/`: persistencia SQLite e migracoes simples.
- `componentes/`: componentes visuais reutilizaveis.
- `config/`: cores, fontes e identificacao da versao.
- `documentos/`: modelos, mapeamentos e renderizacao de PDFs.
- `telas/`: telas do aplicativo.
- `utils/`: caminhos, janelas, auditoria, sessao e utilitarios.

## Pre-cadastro Online

O SIGM Desktop pode sincronizar pre-cadastros pendentes do SIGM Online sem
alterar o fluxo local de analise, edicao, aprovacao ou rejeicao.

Fluxo de configuracao:

1. Na instalacao inicial, cadastre os dados basicos da igreja.
2. Abra as configuracoes da igreja e acesse `Pre-cadastro Online`.
3. Clique em `ATIVAR INTEGRACAO`.
4. O Desktop cria a identidade local da igreja, com identificador publico e
   chave secreta, e tenta ativar automaticamente a igreja no SIGM Online.
5. A API Base URL e a URL publica do formulario sao preenchidas
   automaticamente em modo somente leitura.
6. Com a integracao conectada, gere o QR Code e use o link publico para o
   pre-cadastro online.

A URL base oficial usada pelo Desktop e `https://sigm-online-l0ad.onrender.com`, e
a URL publica do formulario segue o formato
`https://sigm-online-l0ad.onrender.com/cadastro/<identificador_publico>`.

Se a internet estiver indisponivel durante a ativacao, o identificador publico
e a chave secreta permanecem salvos localmente com ativacao pendente. Nesse
caso, abra a mesma tela e clique em `ATIVAR INTEGRACAO` novamente quando houver
conexao. A nova tentativa reutiliza a mesma identidade e aceita normalmente a
resposta `ja_ativada` do SIGM Online.

Na tela de pre-cadastros, use o botao `SINCRONIZAR` para validar a igreja,
baixar os registros pendentes e confirmar ao SIGM Online somente os
`remote_id` que ja foram gravados com sucesso no SQLite local. Registros
incompletos continuam entrando como pendentes; o secretario segue responsavel
por revisar, completar, aprovar ou rejeitar.

Ao aprovar um pre-cadastro cujo CPF, RG e Nome batem exatamente (apos
normalizacao) com um membro ja cadastrado, o SIGM atualiza automaticamente
esse cadastro existente em vez de criar um duplicado, sem passar pela tela de
analise de duplicidades. Nessa atualizacao, campos que o pre-cadastro trouxer
preenchidos substituem o valor anterior; campos que o pre-cadastro deixar em
branco mantem o valor que o membro ja tinha. Qualquer outra combinacao (por
exemplo, apenas o CPF ou apenas o RG batendo, com o nome diferente) continua
seguindo o fluxo normal de deteccao de duplicidade, exigindo revisao manual.

Sem internet, com a integracao desativada ou com configuracao incompleta, o
SIGM continua abrindo e funcionando offline. A sincronizacao apenas informa a
falha de forma segura. Se os registros forem salvos localmente, mas a
confirmacao online falhar, uma nova sincronizacao podera tentar confirmar de
novo sem duplicar os pre-cadastros ja recebidos.

Nunca envie a chave de sincronizacao por mensagem, publique em documentacao,
grave em logs, coloque no QR Code ou inclua em URL/query string. A chave deve
ser usada somente no cabecalho `X-SIGM-Key`.

## Pastas Geradas em Execucao

Estas pastas podem conter dados locais e nao devem ser versionadas:

- `backup/`
- `documentos_gerados/`
- `arquivos_membros/`
- `fotos_membros/`
- `relatorios/`
- `logs/`

Faca backup regular do banco `sigm.db` e das pastas de arquivos/fotos/documentos antes de atualizar ou reinstalar o sistema.

## Atualizacao 1.0.1

A versao 1.0.1 pode ser instalada por cima da versao 1.0.0 usando o instalador `SIGM_Setup_1.0.1.exe`.

A atualizacao substitui somente os arquivos do programa e preserva os dados do usuario em `%LOCALAPPDATA%\SIGM`, incluindo banco `sigm.db`, fotos, anexos, documentos gerados, relatorios, logs, backups e configuracoes.

## Recursos Necessarios no Executavel

Para empacotamento futuro, incluir:

- `documentos/modelos/`
- `documentos/modelos_editaveis/`
- `assets/`
- arquivos Python do projeto

Nao incluir `venv/`, `__pycache__/`, `.git/`, bancos reais, backups antigos, documentos pessoais gerados ou arquivos de teste.

## Status

Projeto preparado para a atualizacao oficial 1.0.1 com executavel `SIGM.exe` e instalador `SIGM_Setup_1.0.1.exe`.
