# 📋 Mudanças Técnicas

## Visão geral

O projeto foi reorganizado para manter compatibilidade com a base antiga, mas com uma arquitetura mais clara e centralizada.

---

## Principais mudanças

### `app/settings.py`
- Centraliza configurações do projeto
- Usa `pydantic-settings`
- Resolve caminhos da base, cache, logs e banco SQLite

### `main.py`
- Virou apenas o ponto de entrada do pipeline
- Delegou a execução para `pipeline/processor.py`

### `dashboard.py`
- Mantém o dashboard em Streamlit
- Prioriza dados do SQLite e faz fallback para CSV local
- Usa gráficos com `altair` e `streamlit`

### `app/repositories/sqlite_repository.py`
- Responsável pela persistência local
- Alimenta o dashboard e parte dos serviços

### `data_source/sheets.py`
- Lê a aba `2026` por padrão
- Insere em `TRANSACOES_CONSOLIDADAS`
- Faz deduplicação antes da escrita

### `pipeline/processor.py`
- Orquestra listagem, parsing, consolidação e saída
- Gera CSVs locais e sincroniza com Google Sheets
- Usa logging estruturado por etapas

---

## Compatibilidade mantida

- `config.py` continua disponível como wrapper
- `parser/` continua existindo para compatibilidade
- `data_source/drive.py` continua sendo usado para Drive
- Arquivos locais em `dados/faturas/` continuam válidos

---

## Segurança e dados sensíveis

Os seguintes arquivos devem continuar fora do Git:
- `credenciais.json`
- `google_oauth_client.json`
- `*.token.json`
- `.env`

Também vale evitar versionar dados gerados localmente, como:
- `database/gastos.db`
- `output/`
- PDFs pessoais em `dados/faturas/`

---

## Fluxo atual

```text
main.py → pipeline/processor.py → parsers → sheets/CSV/SQLite → dashboard.py
```

---

## Próximos passos sugeridos

1. Rodar `python validar_setup.py`
2. Executar `python main.py`
3. Abrir `python -m streamlit run dashboard.py`
4. Revisar a base antes de publicar no GitHub
