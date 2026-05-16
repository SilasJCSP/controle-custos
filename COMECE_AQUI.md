# 🚀 Comece Aqui

## Estado atual

O projeto está organizado para:
- importar faturas do Google Drive ou da pasta local `dados/faturas/`
- processar PDFs por banco (`Santander`, `Mercado Pago`, `Nubank` e genérico)
- consolidar com a aba `2026` do Google Sheets
- gravar a saída local em CSV e SQLite
- abrir dashboard em Streamlit

---

## Execução rápida

### 1. Instalar dependências
```bash
pip install -r requirements.txt
```

### 2. Configurar credenciais
Use um destes arquivos na raiz do projeto:
- `google_oauth_client.json`
- `credenciais.json`

### 3. Validar o ambiente
```bash
python validar_setup.py
```

### 4. Rodar o pipeline
```bash
python main.py
```

### 5. Abrir o dashboard
```bash
python -m streamlit run dashboard.py
```

---

## Fluxo de dados

```text
Google Drive / dados/faturas → Parser → Consolidação → Google Sheets
                                             ↓
                                      CSV local + SQLite
                                             ↓
                                        Dashboard Streamlit
```

---

## Estrutura principal

- `main.py`: entrada principal do pipeline
- `dashboard.py`: interface visual
- `pipeline/processor.py`: orquestração do fluxo
- `data_source/`: integrações Google
- `app/`: nova camada centralizada da aplicação
- `parser/`: compatibilidade legada
- `output/`: arquivos gerados localmente

---

## Credenciais

### OAuth
1. Crie um client desktop no Google Cloud
2. Salve como `google_oauth_client.json`

### Service Account
1. Crie uma service account
2. Salve como `credenciais.json`

> Esses arquivos estão listados no `.gitignore`.

---

## O que conferir se der erro

1. `python validar_setup.py`
2. Verifique se a aba `2026` existe
3. Verifique `GOOGLE_DRIVE_FOLDER_ID` e `GOOGLE_SHEETS_SPREADSHEET_ID`
4. Veja `GUIA_RESTAURACAO.md` e `MUDANCAS_TECNICAS.md`

---

## Atalhos úteis

```bash
python main.py
python validar_setup.py
python -m streamlit run dashboard.py
```
