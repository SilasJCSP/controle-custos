# 🔄 Guia de Restauração

## Visão geral

Este projeto foi reorganizado para manter compatibilidade com a base antiga e, ao mesmo tempo, operar com uma arquitetura mais clara.

---

## O que o fluxo faz

```text
Google Drive / dados/faturas → parser → consolidação → Google Sheets
                                             ↓
                                      CSV local + SQLite
                                             ↓
                                        dashboard.py
```

### Componentes principais
- `main.py`: ponto de entrada do pipeline
- `pipeline/processor.py`: orquestração do processamento
- `data_source/drive.py`: leitura de PDFs do Drive
- `data_source/sheets.py`: leitura da aba `2026` e escrita em `TRANSACOES_CONSOLIDADAS`
- `app/settings.py`: configuração central
- `dashboard.py`: visualização dos dados consolidados

---

## Como restaurar o ambiente

### 1. Instalar dependências
```bash
pip install -r requirements.txt
```

### 2. Configurar credenciais
Na raiz do projeto, use um destes arquivos:
- `google_oauth_client.json`
- `credenciais.json`

> Esses arquivos devem permanecer fora do Git.

### 3. Validar o setup
```bash
python validar_setup.py
```

### 4. Executar o pipeline
```bash
python main.py
```

### 5. Abrir o dashboard
```bash
python -m streamlit run dashboard.py
```

---

## Dados esperados

### Entrada
- PDFs do Google Drive
- PDFs locais em `dados/faturas/`
- Gastos manuais na aba `2026`

### Saída
- Google Sheets na aba `TRANSACOES_CONSOLIDADAS`
- CSVs em `output/`
- Banco SQLite em `database/gastos.db`

---

## Segurança

Mantenha fora do repositório:
- `credenciais.json`
- `google_oauth_client.json`
- `*.token.json`
- `.env`
- `database/gastos.db`
- `output/`
- PDFs pessoais em `dados/faturas/`

---

## Se algo der errado

1. Execute `python validar_setup.py`
2. Verifique se a aba `2026` existe
3. Confirme os IDs em `.env` ou nas variáveis do sistema
4. Confira se os arquivos de credenciais existem na raiz
5. Abra `MUDANCAS_TECNICAS.md` para detalhes da arquitetura

---

## Comandos úteis

```bash
python main.py
python validar_setup.py
python -m streamlit run dashboard.py
```
