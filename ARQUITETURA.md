# 🏗️ Arquitetura do Sistema

## Diagrama de Fluxo de Dados

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PIPELINE DE CONTROLE DE GASTOS                      │
└─────────────────────────────────────────────────────────────────────────────┘

                            ┌──────────────┐
                            │  main.py     │
                            │  (entrypoint)│
                            └──────┬───────┘
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │  pipeline/processor.py   │
                    │    run_pipeline()        │
                    └──────────────────────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            ▼                      ▼                      ▼
    ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
    │  data_source/    │  │  data_source/    │  │  Consolidar &    │
    │  drive.py        │  │  sheets.py       │  │  Exportar        │
    │                  │  │                  │  │                  │
    │ listar_faturas() │  │ ler_gastos()     │  │ • Deduplicar     │
    │ ler_texto_       │  │ inserir_transacoes│ │ • Categorizar    │
    │ fatura()         │  │ _sheets()        │  │ • CSV + Sheets   │
    │                  │  │                  │  │                  │
    └────────┬─────────┘  └────────┬─────────┘  └──────────────────┘
             │                     │
             ▼                     ▼
    ┌──────────────────┐  ┌──────────────────┐
    │ Google Drive API │  │ Google Sheets    │
    │                  │  │ API              │
    │ • Lista PDFs     │  │                  │
    │ • Download       │  │ • Aba "2026"     │
    │ • Cache          │  │ • TRANSACOES_    │
    │                  │  │   CONSOLIDADAS   │
    └────────┬─────────┘  └──────────────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │          parser/ (seleção)           │
    │                                      │
    │  ┌──────────┐  ┌──────────┐  ┌────┐ │
    │  │santander │  │mercado   │  │gen│ │
    │  │.parse()  │  │_pago.    │  │eric│
    │  │          │  │parse()   │  │    │
    │  └──────────┘  └──────────┘  └────┘
    │       ↑              ↑           ↑
    │       └──────┬───────┴───────────┘
    │              │
    │     _selecionar_parser(fonte, texto)
    │              │
    │     Detecta banco por nome do arquivo
    └──────────────┬──────────────────────┘
                   │
                   ▼
         ┌──────────────────────┐
         │  parser/base.py      │
         │                      │
         │ • Extrair texto PDF  │
         │ • Parse transações   │
         │ • Normalizar dados   │
         └──────────────────────┘
                   │
                   ▼
         ┌──────────────────────┐
         │  utils/text.py       │
         │                      │
         │ • Normalizar desc.   │
         │ • Gerar ID (SHA1)    │
         │ • Classificar tipo   │
         └──────────────────────┘
                   │
                   ▼
    ┌──────────────────────────────────────┐
    │ DataFrame Normalizado                │
    │ ┌──────────────────────────────────┐ │
    │ │ id | data | desc | valor | cat   │ │
    │ │ ...                              │ │
    │ └──────────────────────────────────┘ │
    └──────────────┬───────────────────────┘
                   │
                   ▼
         ┌──────────────────────┐
         │  Consolidação        │
         │                      │
         │ 1. Union DataFrames  │
         │ 2. Dedup (by ID)     │
         │ 3. Calc. Resumo      │
         │ 4. Escrever output   │
         │    • CSV local       │
         │    • Google Sheets   │
         └──────────────────────┘
```

---

## Estrutura de Arquivos

```
controle_gastos/
├── main.py                    ← ENTRYPOINT (apenas 1 função)
├── config.py                  ← Configurações centrais
├── requirements.txt           ← Dependências
├── categorias.py              ← Lógica de categorização
│
├── pipeline/
│   ├── processor.py           ← ORQUESTRAÇÃO (run_pipeline)
│   └── __init__.py
│
├── data_source/
│   ├── drive.py               ← Google Drive (listar, baixar)
│   ├── sheets.py              ← Google Sheets (ler, inserir)
│   ├── google_utils.py        ← Autenticação Google
│   ├── models.py              ← Dataclasses (FaturaFonte)
│   └── __init__.py
│
├── parser/
│   ├── base.py                ← Classe base + utilitários
│   ├── santander.py           ← Parser Santander
│   ├── mercado_pago.py        ← Parser Mercado Pago
│   ├── generico.py            ← Parser genérico
│   └── __init__.py
│
├── utils/
│   ├── text.py                ← Normalização, ID, classificação
│   └── __init__.py
│
├── output/                    ← GERADO (CSV, cache)
│   ├── transacoes_categorizadas.csv
│   ├── gastos_consolidados.csv
│   ├── drive_cache/
│   ├── processed_files.json
│   └── google_oauth_token.json
│
├── dados/
│   └── faturas/               ← PDFs locais (fallback)
│
├── COMECE_AQUI.md            ← 📍 LEIA PRIMEIRO
├── GUIA_RESTAURACAO.md       ← Instruções completas
├── MUDANCAS_TECNICAS.md      ← Detalhes técnicos
└── validar_setup.py          ← Script de validação
```

---

## Fluxo de Execução Detalhado

```
┌─ main.py ─────────────────────────────────────────────────────┐
│                                                                │
│  if __name__ == "__main__":                                  │
│      run_pipeline()                                           │
│                                                                │
└─────────────────────────┬──────────────────────────────────────┘
                          │
        ┌─────────────────▼──────────────────┐
        │  run_pipeline() em processor.py    │
        │                                    │
        │  FASE 1: Listar Arquivos           │
        │  ├─ listar_faturas()               │
        │  │  ├─ _listar_faturas_drive()     │
        │  │  └─ fallback: _listar_faturas   │
        │  │           _locais()             │
        │  └─ Log: encontrados N arquivo(s)  │
        │                                    │
        │  FASE 2: Processar Cada Arquivo    │
        │  ├─ for fonte in fontes:           │
        │  │  ├─ ler_texto_fatura()          │
        │  │  ├─ _selecionar_parser()        │
        │  │  │  └─ detecta banco            │
        │  │  ├─ parser.parse()              │
        │  │  ├─ _normalizar_transacoes()    │
        │  │  └─ registrar_processado()      │
        │  └─ Log: N transações extraídas    │
        │                                    │
        │  FASE 3: Ler Gastos Manuais        │
        │  ├─ ler_gastos()                   │
        │  │  └─ aba "2026"                  │
        │  ├─ _normalizar_transacoes()       │
        │  └─ Log: M gastos manuais          │
        │                                    │
        │  FASE 4: Consolidar                │
        │  ├─ Carregar CSV existente         │
        │  ├─ Concat(existing + novos)       │
        │  ├─ Drop duplicates(by ID)         │
        │  ├─ _calcular_resumo()             │
        │  └─ Log: K duplicatas removidas    │
        │                                    │
        │  FASE 5: Escrever Saída            │
        │  ├─ CSV local                      │
        │  ├─ inserir_transacoes_sheets()    │
        │  │  ├─ Carregar IDs existentes     │
        │  │  ├─ Filtrar novos               │
        │  │  └─ Append rows                 │
        │  └─ Log: L inseridas, P puladas    │
        │                                    │
        └──────────────────┬──────────────────┘
                           │
                    ┌──────▼──────┐
                    │ RELATÓRIO    │
                    │ FINAL        │
                    │              │
                    │ Resumo:      │
                    │ • Arquivos   │
                    │ • Trans.     │
                    │ • Duplicatas │
                    │ • Tempo      │
                    └──────────────┘
```

---

## Camadas de Dados

### CAMADA 1: Extração
```
PDF (Google Drive ou Local)
    ↓ (listar_faturas, ler_texto_fatura)
Texto bruto do PDF
```

### CAMADA 2: Parsing
```
Texto bruto
    ↓ (parser específico por banco)
DataFrame bruto (data, descricao, valor)
    ↓ (normalizar_dataframe_parsado)
DataFrame normalizado com banco/arquivo
```

### CAMADA 3: Enriquecimento
```
DataFrame normalizado
    ↓ (_normalizar_transacoes)
• Gerar ID (SHA1)
• Categorizar
• Classificar tipo
• Adicionar origem
```

### CAMADA 4: Consolidação
```
Existentes (CSV local)
    ↓ concat
Novos DataFrames (PDFs + Manual)
    ↓ dedup (by ID)
DataFrame final com histórico completo
```

### CAMADA 5: Saída
```
DataFrame final
    ├─ CSV local
    │  ├─ transacoes_categorizadas.csv
    │  └─ gastos_consolidados.csv
    │
    └─ Google Sheets
       ├─ inserir_transacoes_sheets()
       └─ TRANSACOES_CONSOLIDADAS
```

---

## Componentes Críticos

### 1. Parser Seleção
```python
def _selecionar_parser(fonte, texto):
    if banco == "santander": return santander.parse
    if banco == "mercado_pago": return mercado_pago.parse
    return generico.parse
```

### 2. Geração de ID (Deduplicação)
```python
id = SHA1(data + valor + descricao_normalizada)
```

### 3. Deduplicação
```python
df = df.drop_duplicates(subset=["id_transacao"], keep="last")
```

### 4. Inserção Sheets
```python
ids_existentes = _carregar_ids_transacoes_sheets()
df_novos = df[~df["id_transacao"].isin(ids_existentes)]
inserir_transacoes_sheets(df_novos)  # Append only new
```

---

## Estados Possíveis

```
┌─────────────────────────────────┐
│    Início da Execução           │
└────────────┬────────────────────┘
             │
             ▼
    ┌────────────────────┐
    │ Faturas encontradas?│
    └────┬──────────────┬─┘
         │ Sim          │ Não
         ▼              ▼
    ┌────────────┐  ┌──────────────┐
    │ Processar  │  │ Ler apenas   │
    │ PDFs +     │  │ gastos manuais
    │ Manuais    │  │ do Sheets    │
    └────┬───────┘  └──────┬───────┘
         │                 │
         └────────┬────────┘
                  │
                  ▼
         ┌────────────────┐
         │ Consolidar     │
         │ Dados          │
         └────────┬───────┘
                  │
                  ▼
         ┌────────────────┐
         │ Deduplicar     │
         └────────┬───────┘
                  │
                  ▼
         ┌────────────────┐
         │ Exportar       │
         │ • CSV          │
         │ • Sheets       │
         └────────┬───────┘
                  │
                  ▼
    ┌─────────────────────────────┐
    │  Fim da Execução - Sucesso  │
    └─────────────────────────────┘
```

---

## Performance Esperada

```
Operação              │ Tempo Típico  │ Fator
─────────────────────┼───────────────┼──────────
Listar Drive        │ 2-3s (1ª)     │ 0.5s (cache)
Download PDF        │ 1-3s          │ por arquivo
Parse PDF           │ 0.5-2s        │ por arquivo
Normalizar          │ <100ms        │ por lote
Consolidar          │ 1-5s          │ volume
Inserir Sheets      │ ~10ms/linha   │ 1s/100 linhas
CSV local           │ <100ms        │ I/O
─────────────────────┼───────────────┼──────────
TOTAL (2 PDFs)      │ ~15-30s       │ típico
```

---

**Última atualização**: 2026-05-04
