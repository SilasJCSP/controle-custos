<!--
Descrição oficial sugerida para uso no campo de descrição do repositório:

Um sistema para controle e gerenciamento de custos, desenvolvido em Python, com objetivo de facilitar o registro, acompanhamento e análise de despesas. Ideal para usuários que desejam organizar seu orçamento pessoal ou empresarial, permitindo o monitoramento eficiente dos gastos e a criação de relatórios financeiros.
-->
# 📊 Controle de Gastos Pessoais

> **Status**: ✅ Em uso local | **Versão**: 2.0 | **Última atualização**: 2026-05-16

## 🎯 Visão geral

Sistema para centralizar gastos pessoais com:
- ✅ Importação de faturas via **Google Drive** e leitura local de PDFs
- ✅ Parsers para **Santander**, **Mercado Pago**, **Nubank** e fluxo genérico
- ✅ Consolidação com dados manuais da aba **"2026"** do Google Sheets
- ✅ Persistência local em **SQLite** e exportações em **CSV/XLSX/PDF**
- ✅ Dashboard em **Streamlit** com filtros, KPIs e gráficos
- ✅ Configuração centralizada em `app/settings.py`
- ✅ Credenciais protegidas por `.gitignore`

---

## 🚀 Quick Start

### 1) Instalar dependências
```bash
pip install -r requirements.txt
```

### 2) Configurar credenciais
- `google_oauth_client.json` para OAuth (recomendado)
- `credenciais.json` para service account

### 3) Configurar o `.env`
```bash
cp .env.example .env
# Edite .env e preencha DRIVE_FOLDER_ID e SHEETS_SPREADSHEET_ID
```

### 4) Validar o ambiente
```bash
python validar_setup.py
```

### 5) Executar o pipeline
```bash
python main.py
```

### 6) Abrir o dashboard
```bash
python -m streamlit run dashboard.py
```

---

## 📚 Documentação

| Arquivo | Descrição |
|---------|-----------|
| **COMECE_AQUI.md** | Visão geral e primeiros passos |
| **validar_setup.py** | Validação do setup |
| **GUIA_RESTAURACAO.md** | Uso e troubleshooting |
| **CHECKLIST.md** | Checklist de validação |
| **ARQUITETURA.md** | Diagramas e fluxos |
| **MUDANCAS_TECNICAS.md** | Resumo técnico das mudanças |

---

## 🔄 Fluxo atual

```text
Google Drive / dados/faturas → Detectar banco → Parse → Normalizar
                                              ↓
                                     Consolidar + Aba "2026"
                                              ↓
                                          Deduplicar
                                              ↓
                    Google Sheets + CSV local + SQLite + Dashboard
```

---

## 📁 Estrutura principal

```text
├── main.py                 ← Pipeline principal
├── dashboard.py            ← Dashboard em Streamlit
├── app/
│   ├── settings.py         ← Configuração central
│   ├── core/               ← Regras de negócio
│   ├── repositories/       ← Persistência SQLite
│   ├── parsers/            ← Parsers novos/compatíveis
│   └── services/           ← Exportação, importação e insights
├── pipeline/processor.py   ← Orquestração
├── data_source/            ← Integrações Google
├── parser/                 ← Compatibilidade legada
├── output/                 ← CSV, cache e tokens locais
└── COMECE_AQUI.md          ← Comece por aqui
```

---

## ✨ Destaques

- **Deduplicação por hash**: evita inserir a mesma transação duas vezes
- **Logging estruturado**: facilita depuração e auditoria
- **Google Sheets automático**: centraliza dados na nuvem
- **Fallback local**: funciona sem Drive/Sheets quando necessário
- **Cache de Drive**: não re-baixa PDFs já processados
- **Dashboard com SQLite**: consulta dados consolidados com boa resposta

---

## 📊 Dados

**Entrada**:
- PDFs do Google Drive ou da pasta `dados/faturas/`
- Aba **"2026"** do Google Sheets com gastos manuais

**Saída**:
- Aba **"TRANSACOES_CONSOLIDADAS"** no Google Sheets
- CSVs locais em `output/`
- Banco SQLite local em `database/gastos.db`

---

## 🔧 Configuração

### Credenciais Google

**OAuth (recomendado)**
1. Google Cloud → OAuth 2.0 Client ID (Desktop app)
2. Baixe o JSON e salve como `google_oauth_client.json`

**Service Account**
1. Google Cloud → Service Account
2. Baixe o JSON e salve como `credenciais.json`

> Esses arquivos já estão listados no `.gitignore` e não devem ser commitados.

### Variáveis de ambiente obrigatórias

| Variável | Descrição |
|---|---|
| `DRIVE_FOLDER_ID` | ID da pasta Google Drive com as faturas |
| `SHEETS_SPREADSHEET_ID` | ID da planilha Google Sheets |
| `LIMITE_MENSAL_REAIS` | Limite mensal em R$ para alertas (0 = desativado) |

---

## 🛠️ Troubleshooting

| Problema | Solução |
|----------|---------|
| Aba não encontrada | Verifique o nome exato |
| Credenciais não funcionam | Execute `python validar_setup.py` |
| Nenhum PDF no Drive | Verifique `GOOGLE_DRIVE_FOLDER_ID` |
| Parser não extrai | O PDF pode ser imagem (sem texto) |

Mais detalhes em **GUIA_RESTAURACAO.md**.

---

## 📈 Performance

| Operação | Tempo |
|----------|-------|
| Validar setup | 1-5 seg |
| Listar Drive | 2-3 seg (1ª), 0.5 seg (cache) |
| Parse PDF | 0.5-2 seg |
| Inserir Sheets | ~10ms/linha |
| Abrir dashboard | 1-3 seg |
| **Total** | 5-30 seg |

---

## 🎓 Exemplos

```python
# Executar pipeline completo
python main.py

# Abrir dashboard
python -m streamlit run dashboard.py

# Validar setup
python validar_setup.py

# Listar PDFs do Drive
from data_source.drive import listar_faturas
for fatura in listar_faturas():
    print(f"{fatura.nome_arquivo} [{fatura.banco}]")

# Ler dados Sheets
from data_source.sheets import ler_gastos
df = ler_gastos()  # Aba "2026"
print(df)

# Inserir dados
from data_source.sheets import inserir_transacoes_sheets
inseridas, puladas = inserir_transacoes_sheets(df)
print(f"Inseridas: {inseridas}, Já existentes: {puladas}")
```

---

## 📝 Mudanças recentes

**Adicionado**:
- ✅ Configuração central em `app/settings.py`
- ✅ Dashboard em Streamlit com leitura de CSV/SQLite
- ✅ Exportações em CSV/XLSX/PDF
- ✅ Logging estruturado e fluxos mais claros

**Removido**:
- ❌ Lógica de configuração espalhada
- ❌ Trechos legados duplicados no entrypoint

**Melhorado**:
- 🔧 Deduplicação por hash
- 🔧 Arquitetura modular em `app/`
- 🔧 Segurança de credenciais e organização do projeto

---

## 📞 Suporte

Se algo falhar, siga esta ordem:
1. `python validar_setup.py`
2. **GUIA_RESTAURACAO.md**
3. **MUDANCAS_TECNICAS.md**

---

<p align="center">
  <b>🎉 Pronto para usar! 🎉</b><br>
  Execute: <code>python main.py</code><br>
  Dashboard: <code>python -m streamlit run dashboard.py</code><br>
  Docs: <a href="COMECE_AQUI.md">COMECE_AQUI.md</a>
</p>
