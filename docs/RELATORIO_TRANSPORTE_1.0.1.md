# Relatorio de Transporte 1.0.1

Branch criada: `1.0.0-com-melhorias-1.0.1`

Commit-base estavel 1.0.0: `e8e663a Create SIGM_Setup.iss`

Origem das melhorias: `backup-1.0.1-antes-restaurar-janelas`

## Regra aplicada

Nao foram transportadas alteracoes de gerenciamento de janelas dos arquivos:

- `app.py`
- `utils/janelas.py`
- `telas/tela_inicial.py`
- `telas/tela_carregamento.py`
- `telas/tela_login.py`
- `telas/tela_primeiro_acesso.py`
- `telas/dashboard.py`

## Comparacao de transporte

| Funcionalidade da 1.0.1 | Arquivo/trecho transportado | Confirmacao sobre janelas |
| --- | --- | --- |
| Migracoes seguras do banco e novas colunas complementares de membros | `banco/database.py` | Nao altera fluxo de janelas |
| Coluna `ativo` em usuarios e garantia de coluna de foto | `banco/database.py` | Nao altera fluxo de janelas |
| Cadastro, edicao e carregamento de naturalidade, conjuge e nascimento do conjuge | `telas/cadastro_membro.py` | Tela de cadastro mantem abertura herdada da base 1.0.0 |
| Exibicao dos novos campos na ficha do membro | `telas/ficha_membro.py` | Aplicado manualmente; `lift()` e `focus_force()` da 1.0.0 foram preservados |
| Exibicao dos novos campos no dossie digital | `telas/dossie_membro.py` | Aplicado manualmente; `lift()` e `focus_force()` da 1.0.0 foram preservados |
| Integracao dos novos campos com dados de documentos | `documentos/integrador_documentos.py` | Nao altera fluxo de janelas |
| Integracao dos novos campos com geracao final de PDF | `documentos/gerar_documentos.py` | Nao altera fluxo de janelas |
| Editor da ficha cadastral com naturalidade, pai, mae, conjuge e data do conjuge | `telas/documentos/editor_ficha_cadastral.py` | Nao altera fluxo principal de janelas |
| Versao centralizada 1.0.1 | `config/versao.py`, `componentes/barra_status.py` | Nao altera fluxo de janelas |
| README, changelog e mapeamento da ficha | `README.md`, `docs/CHANGELOG.md`, `docs/FICHA_CADASTRAL_MAPEAMENTO.md` | Documentacao apenas |
| Instalador apontando para versao 1.0.1 | `instalador/SIGM_Setup.iss` | Nao altera fluxo de janelas |

## Arquivos avaliados e nao transportados

As mudancas de `telas/arquivos_membro.py`, `telas/central_documentos.py`, `telas/consulta_membros.py`, `telas/log_auditoria.py`, `telas/usuarios.py` e `telas/dashboard.py` eram relacionadas a foco, `grab_set`, reuso de janela ou `trazer_para_frente`; por isso nao foram transportadas.

## Testes

| Grupo | Resultado |
| --- | --- |
| Base 1.0.0 antes do transporte | Validada visualmente ate `Primeiro Acesso` |
| Grupo 1 - banco e migracoes | Aplicado; `py_compile` aprovado |
| Grupo 2 - cadastro, ficha e dossie | Aplicado; teste visual de abertura aprovado |
| Grupo 3 - documentos e PDFs | Integracao aplicada; `py_compile` aprovado |
| Grupo 4 - auditoria, relatorios, backup e telas complementares | Sem transporte adicional; diffs eram de janela/foco |
| Grupo 5 - versao, barra de status, Sobre e ajustes visuais | Versao e barra de status aplicadas; ajustes de janela/Sobre nao transportados |
| Teste de abertura apos transporte | Usuario confirmou: "tudo certo" |
| `python -m compileall banco componentes config documentos telas utils app.py` | Aprovado |

## Pendencias

- Testar cadastro real salvando todos os novos campos.
- Testar ficha, dossie e PDF oficial com dados reais.
- Gerar e validar `dist\SIGM\SIGM.exe`.
- Gerar e validar `SIGM_Setup_1.0.1.exe`.
