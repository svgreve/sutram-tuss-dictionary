---
name: medical-exam-migration
version: 3.0.0
description: |
  Skill para importar exames médicos de portais hospitalares para o Sutram.

  Suporta múltiplos portais (começando com HAOC) e estrutura de pastas configurável.
  Princípio fundamental: ZERO RASTROS - após importação, nenhum arquivo fica no computador.

triggers:
  # O skill é ativado quando detecta combinação de hospital + contexto médico

  hospitals:
    haoc:
      - HAOC
      - Oswaldo Cruz
      - Osvaldo Cruz
      - Hospital Alemão
      - Hospital Alemão Oswaldo Cruz
    # Futuros conectores:
    # einstein:
    #   - Einstein
    #   - Albert Einstein
    #   - Hospital Einstein

  medical_context:
    - exame
    - exames
    - resultado
    - resultados
    - laudo
    - laudos
    - imagem
    - imagens

  action_verbs:
    - importar
    - baixar
    - trazer
    - pegar
    - buscar
    - transferir
    - salvar
    - guardar

  example_phrases:
    - "Importar exames do HAOC"
    - "Baixar exames do Oswaldo Cruz"
    - "Meu exame ficou pronto no Osvaldo Cruz?"
    - "Quero trazer os resultados do Hospital Alemão"
    - "Tenho exames novos no Oswaldo Cruz"
    - "Salvar meus exames do Hospital Alemão no Sutram"
---

# Medical Exam Migration

Importa exames médicos de portais hospitalares para o Sutram de forma automatizada e segura.

## Princípios

1. **Zero rastros** - Após importação, arquivos existem APENAS no Sutram
2. **Sem intervenção técnica** - Usuário não precisa saber de APIs ou configurações
3. **Detecção de duplicados** - Não reimporta o que já existe
4. **Recuperação automática** - Se credenciais falham, pede novas
5. **Nomes padronizados (TUSS)** - Nomes de exames são normalizados para o padrão TUSS antes de criar pastas, eliminando duplicação por variação de nomenclatura

---

## Permissões e Automação

Este skill executa muitos comandos repetitivos no computador do usuário. **É fundamental que as permissões estejam pré-configuradas** para evitar que o usuário seja interrompido dezenas de vezes durante uma sessão de importação.

### Problema: Diálogos de Permissão Repetitivos

O Claude Code e Cowork pedem confirmação para cada comando bash e cada chamada de ferramenta. Em uma sessão típica com 5 exames, isso significaria **30-50 diálogos de confirmação**, tornando o processo inviável como automação.

### Solução: Pré-autorização via settings.local.json

O arquivo `.claude/settings.local.json` na pasta do projeto deve conter TODAS as permissões necessárias. **Este arquivo deve ser verificado e atualizado no início de cada sessão (Fase 0).**

### Comandos que DEVEM estar pré-autorizados:

| Comando | Finalidade |
|---------|------------|
| `python3` | Processar ZIPs, codificar base64, upload via MCP |
| `curl` | Chamadas HTTP diretas para o Sutram MCP |
| `unzip` | Extrair imagens do arquivo ZIP |
| `rm` | Remover arquivos temporários (limpeza) |
| `rm -rf` | Remover pasta temporária (limpeza) |
| `mkdir` | Criar pasta temporária |
| `mv`, `cp` | Mover/copiar arquivos durante processamento |
| `cat`, `ls`, `wc` | Listar, verificar e contar arquivos |
| `head`, `file` | Identificar tipo/conteúdo de arquivos |
| `base64` | Codificar arquivos para upload |
| `sleep` | Pausas obrigatórias entre exames |
| `find` | Localizar arquivos baixados |

### Configuração OBRIGATÓRIA (settings.local.json):

O skill deve verificar na Fase 0 se o arquivo `.claude/settings.local.json` na pasta do projeto contém as permissões abaixo. Se não contiver, **atualizá-lo automaticamente**:

```json
{
  "permissions": {
    "allow": [
      "Bash(python3:*)",
      "Bash(curl:*)",
      "Bash(rm:*)",
      "Bash(rm -rf:*)",
      "Bash(mkdir:*)",
      "Bash(unzip:*)",
      "Bash(mv:*)",
      "Bash(cp:*)",
      "Bash(cat:*)",
      "Bash(ls:*)",
      "Bash(wc:*)",
      "Bash(head:*)",
      "Bash(file:*)",
      "Bash(base64:*)",
      "Bash(sleep:*)",
      "Bash(find:*)",
      "Bash(test:*)",
      "Bash(echo:*)",
      "Bash(for:*)",
      "Bash(do:*)",
      "Bash(done:*)"
    ]
  }
}
```

### Estratégia para Scripts Python Compostos

Para minimizar prompts, **agrupar operações em scripts Python únicos** em vez de executar comandos individuais:

```python
# ❌ RUIM: Múltiplos comandos = múltiplos prompts
# bash: unzip file.zip -d /tmp/
# bash: ls /tmp/*.jpg
# bash: python3 encode.py
# bash: curl -X POST ...

# ✅ BOM: Script Python único = 1 prompt
# bash: python3 -c "
import zipfile, base64, json, subprocess, os
# 1. Extrair ZIP
# 2. Listar arquivos
# 3. Codificar em base64
# 4. Fazer upload via curl/requests
# 5. Limpar temporários
# Tudo em um único script!
# "
```

**Regra:** Sempre que possível, combinar extração do ZIP + codificação base64 + upload em um ÚNICO script Python. Isso reduz os diálogos de permissão de ~10 por exame para ~2-3.

### Para o Usuário: Primeira Execução

Na **primeira execução**, caso ainda apareçam diálogos de permissão:
1. Marque **"Sempre permitir"** para cada tipo de comando
2. Isso persiste para a sessão atual
3. Para sessões futuras, o `settings.local.json` já estará configurado

---

## FASE 0: Inicialização e Verificação

### 0.1 Verificar Normalizador TUSS

Antes de tudo, verificar que os arquivos do normalizador existem na pasta de trabalho.
Os scripts Python e o dicionário TUSS são mantidos no repositório centralizado:
`https://github.com/svgreve/sutram-tuss-dictionary`

```python
from pathlib import Path

workspace = Path(".")  # pasta de trabalho do projeto
required_files = {
    "normalize_exam.py": "Motor de normalização TUSS",
    "exam_normalizer.py": "Wrapper com cache e fallback LLM",
    "dict_fetcher.py": "Busca dicionário remoto do GitHub (com cache ETag)",
    "contribution_submitter.py": "Submete novos mapeamentos ao dicionário comunitário",
}

# O dicionário tuss_exames_comuns.json NÃO precisa estar local.
# O dict_fetcher.py busca a versão mais recente do GitHub automaticamente,
# com cache local em ~/.cache/tuss-dict/ e TTL de 24h.
# Se o fetch falhar, usa o cache local ou o arquivo bundled como fallback.

for filename, descricao in required_files.items():
    if not (workspace / filename).exists():
        print(f"❌ Faltando: {filename} ({descricao})")
        # Interromper e orientar o usuário
    else:
        print(f"✅ {filename}")
```

Se `mapping_cache.json` não existir, será criado automaticamente na primeira normalização.

### 0.2 Verificar Configuração

Ao ser ativado, SEMPRE verificar primeiro se existe configuração:

```
CONFIG_PATH = ~/.claude/skills/medical-exam-migration/config.yaml
```

```python
import os
import yaml
from pathlib import Path

config_path = Path.home() / '.claude' / 'skills' / 'medical-exam-migration' / 'config.yaml'

if config_path.exists():
    with open(config_path) as f:
        config = yaml.safe_load(f)
    # Ir para verificação de conexão (0.2)
else:
    # Ir para init (0.3)
```

### 0.2 Testar Conexão com Sutram

Se config existe, testar se as credenciais ainda funcionam:

```bash
curl -s -X POST "https://sutram.io/mcp" \
  -H "Content-Type: application/json" \
  -H "x-project-key: ${config.sutram.project_key}" \
  -H "x-user-key: ${config.sutram.user_key}" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "sutram_project_info", "arguments": {}}, "id": 1}'
```

**Se sucesso:** Prosseguir para Fase 1
**Se erro de autenticação:** Informar usuário e pedir novas chaves

```
"Suas credenciais do Sutram parecem estar inválidas.
Pode ser que tenham sido regeneradas.

Para atualizar:
1. Acesse sutram.io → Configurações → Integrações → MCP
2. Copie a nova Project Key e User Key

Pode colar as novas chaves aqui?"
```

### 0.3 Init (Primeira Execução)

Se não existe configuração, iniciar setup guiado:

```
"Vejo que é a primeira vez que você importa exames para o Sutram.
Vamos configurar rapidinho!

Você já tem uma conta no Sutram?"

[Sim, tenho conta]  [Não, preciso criar]
```

**Se não tem conta:**
```
"Você pode criar sua conta gratuita em sutram.io
Quando estiver pronto, me avise que continuamos a configuração."
```

**Se tem conta:**
```
"Ótimo! Agora preciso das chaves de acesso:

1. Acesse sutram.io
2. Vá em Configurações → Integrações → MCP
3. Copie a Project Key (começa com sk_proj_)
4. Copie a User Key (começa com sk_user_)

Pode colar as chaves aqui?"
```

**Após receber as chaves:**

```python
# Testar conexão
response = test_sutram_connection(project_key, user_key)

if response.success:
    # Salvar configuração
    config = {
        'sutram': {
            'endpoint': 'https://sutram.io/mcp',
            'project_key': project_key,
            'user_key': user_key,
            'project_name': response.project_name,
            'verified_at': datetime.now().isoformat()
        },
        'preferences': {
            'path_template': '{medico}/{exame}/{data}',
            'date_format': 'YYYY-MM-DD',
            'default_portal': 'haoc'
        }
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w') as f:
        yaml.dump(config, f)

    print(f"✅ Conectado ao projeto '{response.project_name}'!")
else:
    print("❌ Não consegui conectar. Verifique se as chaves estão corretas.")
```

### 0.4 Estrutura de Configuração

```yaml
# ~/.claude/skills/medical-exam-migration/config.yaml

sutram:
  endpoint: https://sutram.io/mcp
  project_key: sk_proj_xxxxx
  user_key: sk_user_xxxxx
  project_name: "Minha Saúde"
  verified_at: "2026-02-04T20:30:00Z"

preferences:
  # Template para estrutura de pastas no Sutram
  # Variáveis disponíveis: {medico}, {exame}, {data}, {ano}, {mes}
  path_template: "{medico}/{exame}/{data}"

  # Formato da data nas pastas
  date_format: "YYYY-MM-DD"

  # Portal padrão
  default_portal: haoc
```

---

## FASE 1: Verificar Acesso ao Portal

### 1.1 Confirmar Login

```
"Você está logado no portal do Hospital Alemão Oswaldo Cruz?"

[Sim, estou logado]  [Não, preciso logar]
```

**Se não está logado:**
```
"Sem problemas! Acesse portalexames.hospitaloswaldocruz.org.br
e faça login com seu CPF e senha.

Me avise quando estiver na página de exames."
```

### 1.2 Navegar até Lista de Exames

Usar browser automation para verificar se está na página correta:
- URL deve conter `portalexames.hospitaloswaldocruz.org.br`
- Deve haver lista de exames visível

---

## FASE 2: Seleção de Exames

### 2.1 Perguntar o que Importar

```
"O que você quer importar?"

○ Um exame específico
  → "Qual exame? Pode me dizer o nome ou a data"

○ Exames a partir de uma data
  → "A partir de qual data?"

○ Exames de um médico específico
  → "Qual médico?"

○ Exames de um ano específico
  → "Qual ano?"

○ Todos os exames disponíveis
  → "Isso pode demorar um pouco. Confirma?"
```

### 2.2 Extrair Lista de Exames e Normalizar Nomes

Usar browser automation para ler a tabela de exames e **normalizar os nomes imediatamente**:

```python
from exam_normalizer import ExamNormalizer

# Inicializar normalizador (carrega dicionário TUSS + cache)
normalizer = ExamNormalizer()

exames_portal = []

# Para cada linha na tabela de exames
for row in exam_table_rows:
    exame = {
        'nome': extract_text(row, '.exam-name'),      # ex: "USG ABDOME TOTAL"
        'medico': extract_text(row, '.doctor-name'),  # ex: "Dr. Decio Mion Junior"
        'data': parse_date(row, '.exam-date'),        # ex: "2024-12-12"
        'data_display': extract_text(row, '.exam-date'),  # ex: "12/12/2024"
        'has_images': exists(row, '.view-icon'),
        'has_pdf': exists(row, '.download-icon')
    }
    exames_portal.append(exame)

# Normalizar todos os nomes de uma vez (usa cache, retorna nome_padrao)
exames_portal = normalizer.normalize_batch(exames_portal)

# Para cada exame com _needs_llm=True (score < 80), usar o Claude como fallback:
for exame in exames_portal:
    if exame.get('_needs_llm'):
        prompt = normalizer.get_llm_prompt(exame['nome_original'], exame['score'])
        nome_normalizado = ask_claude(prompt)  # Claude responde com nome TUSS
        exame['nome_padrao'] = nome_normalizado
        exame['confidence'] = 'llm'
        exame['score'] = 90.0
        normalizer.apply_llm_result(exame['nome_original'], nome_normalizado)
```

**Após a normalização, cada exame tem:**
- `nome_original` — Nome como aparece no portal HAOC (ex: "USG ABDOME TOTAL")
- `nome_padrao` — Nome normalizado TUSS (ex: "Ultrassonografia de abdome total")
- `confidence` — "exact", "fuzzy" ou "llm"
- `score` — 0-100 (100 = match exato)
- `codigo_tuss` — Código TUSS oficial (ex: "40901200")
- `categoria` — Categoria do exame (ex: "Ultrassonografia")

### 2.3 Filtrar Conforme Seleção do Usuário

```python
def filtrar_exames(exames, filtro):
    if filtro.tipo == 'especifico':
        return [e for e in exames if filtro.valor in e['nome'] or filtro.valor in e['data']]

    elif filtro.tipo == 'a_partir_de':
        return [e for e in exames if e['data'] >= filtro.data]

    elif filtro.tipo == 'medico':
        return [e for e in exames if filtro.valor.lower() in e['medico'].lower()]

    elif filtro.tipo == 'ano':
        return [e for e in exames if e['data'].startswith(filtro.ano)]

    elif filtro.tipo == 'todos':
        return exames
```

### 2.4 Verificar Duplicados no Sutram (com nomes normalizados)

Antes de mostrar a lista, verificar quais já existem no Sutram.
**IMPORTANTE:** Usar `nome_padrao` (normalizado) para o path, não `nome_original`.

```python
for exame in exames_filtrados:
    # Path usa o nome normalizado TUSS
    path = config['preferences']['path_template'].format(
        medico=exame['medico'],
        exame=exame['nome_padrao'],   # ← NORMALIZADO
        data=exame['data'],
        ano=exame['data'][:4],
        mes=exame['data'][5:7]
    )

    # Verificar se pasta existe no Sutram (com nome normalizado)
    response = sutram_get_folder_by_path(path)

    if response.exists and response.has_files:
        exame['status'] = 'ja_existe'
        exame['selecionado'] = False
    else:
        # Verificar também se existe pasta com nome ANTIGO (não normalizado)
        if exame['nome_original'] != exame['nome_padrao']:
            path_antigo = config['preferences']['path_template'].format(
                medico=exame['medico'],
                exame=exame['nome_original'],   # ← NOME ORIGINAL
                data=exame['data'],
                ano=exame['data'][:4],
                mes=exame['data'][5:7]
            )
            response_antigo = sutram_get_folder_by_path(path_antigo)
            if response_antigo.exists:
                exame['status'] = 'nome_antigo'  # Existe com nome despadronizado
                exame['selecionado'] = False
                exame['path_antigo'] = path_antigo
            else:
                exame['status'] = 'novo'
                exame['selecionado'] = True
        else:
            exame['status'] = 'novo'
            exame['selecionado'] = True
```

**Detecção de pastas com nomes antigos:** Se uma pasta existir com o nome original (não normalizado), o skill marca como `nome_antigo` e oferece renomear via `sutram_rename` — perguntando uma única vez para todos os casos.

### 2.5 Apresentar Lista para Confirmação

Mostrar nome original → nome normalizado, com indicador de confiança:

```
"Encontrei 5 exames. Nomes normalizados para o padrão TUSS:"

☑️ USG ABDOME TOTAL → Ultrassonografia de abdome total [✅ exact]
   Dr. Decio Mion Junior - 12/12/2024

☑️ HMG COMPLETO → Hemograma completo [✅ exact]
   Dra. Maria Silva - 10/12/2024

☑️ RX TORAX PA → Radiografia de tórax (PA e perfil) [🤖 llm]
   Dr. Decio Mion Junior - 05/11/2024

☐ ECG REPOUSO → Eletrocardiograma (ECG) [✅ exact]
   Dr. João Santos - 01/10/2024 (já existe no Sutram)

☑️ USG TIREOIDE → Ultrassonografia de tireoide [🔍 fuzzy 92%]
   Dra. Maria Silva - 15/09/2024

"Desmarquei 1 exame que já está no Sutram."
"Importar os 4 selecionados?"

[Sim, importar]  [Ajustar seleção]  [Cancelar]
```

**Se houver pastas com nomes antigos:**

```
⚠️ Encontrei 2 pastas no Sutram com nomes despadronizados:

1. Dr. Decio/USG ABDOME TOTAL/2024-11-20
   → Renomear para: Dr. Decio/Ultrassonografia de abdome total/2024-11-20

2. Dra. Maria/HMG COMPLETO/2024-10-15
   → Renomear para: Dra. Maria/Hemograma completo/2024-10-15

"Quer que eu renomeie essas pastas para o nome padronizado?"

[Sim, renomear todas]  [Não, manter como estão]
```

**Indicadores de confiança:**
- ✅ exact — Match exato no dicionário TUSS (100%)
- 🔍 fuzzy — Match aproximado com score (75-99%)
- 🤖 llm — Normalizado pelo Claude como fallback
```

---

## FASE 3: Download do Portal (para cada exame)

### 3.1 Identificar Pasta de Downloads

```python
from pathlib import Path
import os

# Pasta de downloads padrão do sistema
if os.name == 'nt':  # Windows
    downloads = Path.home() / 'Downloads'
else:  # macOS / Linux
    downloads = Path.home() / 'Downloads'
```

### 3.2 Baixar PDF do Laudo

Na lista de exames do portal:
1. Localizar o exame na lista
2. Clicar no ícone de download (⬇️) à direita

```python
# Aguardar download e identificar arquivo
pdf_pattern = "*.pdf"
pdf_file = wait_for_new_file(downloads, pdf_pattern, timeout=30)
```

### 3.3 Baixar ZIP com Imagens

**⚠️ REGRA: NUNCA mais de uma aba Vue Motion aberta ao mesmo tempo.**
O HAOC disponibiliza imagens via um software (Vue Motion) que roda em um frame do portal. Múltiplas janelas de visualização causam conflitos e downloads incorretos.

**Antes de abrir um novo visualizador:**
1. Fechar TODAS as abas Vue Motion existentes (verificar por título ou URL contendo "vuemotion")
2. Aguardar 2 segundos após fechar

**Procedimento de download:**
1. Clicar no ícone do olho (👁️) → abre Vue Motion em nova aba
2. **CRÍTICO:** Confirmar que existe apenas UMA aba Vue Motion aberta
3. Clicar no ícone do disquete (💾) no canto superior esquerdo
4. Selecionar **"Salvar o grupo ativo"** (ÚLTIMA opção)
   - Baixa ZIP menor (~12MB) só com JPGs
   - NÃO usar "Salvar o exame DICOM" (~100MB)
5. **Após o download completar:** Fechar a aba Vue Motion antes de prosseguir

**⚠️ ATENÇÃO: O download do ZIP pode demorar 30-60 segundos ou mais**, dependendo do tamanho do exame e da conexão. Aguardar pacientemente sem clicar novamente.

```python
# Aguardar download do ZIP - TIMEOUT LONGO (até 120 segundos)
zip_pattern = "s_vuemotion_exte_*.zip"
zip_file = wait_for_new_file(downloads, zip_pattern, timeout=120)
```

### 3.4 Extrair Imagens do ZIP

```python
import zipfile

# Criar pasta temporária na pasta de Downloads
temp_dir = downloads / f'_temp_exame_{exame["data"]}'
temp_dir.mkdir(exist_ok=True)

# Extrair apenas os JPGs
with zipfile.ZipFile(zip_file, 'r') as zf:
    for member in zf.namelist():
        # Estrutura: exam/jpeg/*.jpg
        if 'exam/jpeg/' in member and member.lower().endswith('.jpg'):
            filename = os.path.basename(member)
            if filename:  # Ignorar diretórios
                with zf.open(member) as src:
                    with open(temp_dir / filename, 'wb') as dst:
                        dst.write(src.read())

# Contar arquivos extraídos
image_count = len(list(temp_dir.glob('*.jpg')))
print(f"✓ {image_count} imagens extraídas")
```

---

## FASE 4: Upload para Sutram (MCP)

### 4.1 Criar Estrutura de Pastas (com nome normalizado TUSS)

Usar o path_template da configuração com o **nome normalizado**:

```python
# Montar path conforme template — USANDO NOME NORMALIZADO
path = config['preferences']['path_template'].format(
    medico=exame['medico'],
    exame=exame['nome_padrao'],   # ← NORMALIZADO (TUSS)
    data=exame['data'],
    ano=exame['data'][:4],
    mes=exame['data'][5:7]
)

# Criar hierarquia completa em uma chamada
response = sutram_create_folder(path=path)
folder_id = response['folder']['id']
```

Chamada MCP (exemplo com nome normalizado):
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "sutram_create_folder",
    "arguments": {
      "path": "Dr. Decio Mion Junior/Ultrassonografia de abdome total/2024-12-12"
    }
  },
  "id": 1
}
```

**Resultado:** Pastas no Sutram agora usam nomes padronizados TUSS. Diferentes variações do portal ("USG ABDOME TOTAL", "USG ABD TOTAL") convergem para a mesma pasta "Ultrassonografia de abdome total".

### 4.2 Preparar Arquivos para Upload

**IMPORTANTE: Ordenação dos arquivos no Sutram**

O Sutram lista arquivos em ordem alfabética do nome. Para garantir:
- Laudo sempre aparece **primeiro**
- Imagens em **ordem numérica correta**

Usar **prefixos numéricos** nos nomes:

```
000_laudo.pdf          ← sempre primeiro
001_i0001.jpg          ← imagens em ordem
002_i0002.jpg
003_i0003.jpg
...
```

```python
import base64
import re

files_to_upload = []

# 1. LAUDO PRIMEIRO (prefixo 000)
with open(pdf_file, 'rb') as f:
    content = base64.b64encode(f.read()).decode('utf-8')
files_to_upload.append({
    'filename': f'000_{pdf_file.name}',
    'content_base64': content
})

# 2. IMAGENS EM ORDEM NUMÉRICA (prefixo 001, 002, ...)
# Ordenar pelo número no final do nome (ex: i0001.jpg, i0002.jpg)
def extract_number(filename):
    """Extrai número do nome do arquivo para ordenação"""
    match = re.search(r'(\d+)\.jpg$', filename.name, re.IGNORECASE)
    return int(match.group(1)) if match else 0

jpg_files = sorted(temp_dir.glob('*.jpg'), key=extract_number)

for idx, jpg_file in enumerate(jpg_files, start=1):
    with open(jpg_file, 'rb') as f:
        content = base64.b64encode(f.read()).decode('utf-8')
    files_to_upload.append({
        'filename': f'{idx:03d}_{jpg_file.name}',
        'content_base64': content
    })

print(f"✓ {len(files_to_upload)} arquivos preparados (1 laudo + {len(jpg_files)} imagens)")
```

### 4.3 Upload em Lote

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "sutram_upload_batch",
    "arguments": {
      "folder_id": "uuid-da-pasta-data",
      "files": [
        {"filename": "000_laudo.pdf", "content_base64": "..."},
        {"filename": "001_i0001.jpg", "content_base64": "..."},
        {"filename": "002_i0002.jpg", "content_base64": "..."},
        {"filename": "003_i0003.jpg", "content_base64": "..."}
      ]
    }
  },
  "id": 2
}
```

**Resultado no Sutram (ordenação correta):**
```
📄 000_laudo.pdf         ← Laudo sempre primeiro!
📷 001_i0001.jpg
📷 002_i0002.jpg
📷 003_i0003.jpg
...
```

### 4.4 Verificar Resultado

```python
result = response['result']

if result['failed'] == 0:
    print(f"✅ {result['uploaded']} arquivos enviados com sucesso")
    return True
else:
    print(f"⚠️ {result['failed']} arquivos falharam")
    for file in result['files']:
        if file['status'] != 'success':
            print(f"   - {file['name']}: {file.get('error', 'erro desconhecido')}")
    return False
```

---

## Estabilidade do Browser (entre exames)

### Pausa entre Exames

**OBRIGATÓRIO:** Aguardar no mínimo **30 segundos** entre o término de um exame e o início do download do próximo. Isso evita sobrecarga no portal HAOC e na extensão Claude in Chrome.

```python
import time

# Após completar limpeza de um exame, antes de iniciar o próximo:
print("⏳ Aguardando 30 segundos antes do próximo exame...")
time.sleep(30)
```

### Reiniciar Chrome a cada 2 Exames

**OBRIGATÓRIO para sessões com mais de 2 exames:**

A extensão Claude in Chrome pode apresentar instabilidade após uso prolongado com muitas interações. Para evitar travamentos e comportamentos inesperados:

**A cada 2 exames completados:**
1. Fechar TODAS as abas do grupo MCP (usar `tabs_context_mcp` para listar e fechar)
2. Criar uma nova aba limpa (greenfield) com `tabs_create_mcp`
3. Navegar novamente até o portal HAOC
4. Continuar com o próximo exame

```
Exame 1 → Download, Upload, Limpeza
Exame 2 → Download, Upload, Limpeza
🔄 REINICIAR CHROME (fechar tudo, nova aba)
Exame 3 → Download, Upload, Limpeza
Exame 4 → Download, Upload, Limpeza
🔄 REINICIAR CHROME (fechar tudo, nova aba)
...
```

**Implementação:**
```python
exame_counter = 0

for exame in exames_selecionados:
    exame_counter += 1

    # Processar exame (fases 3-5)
    processar_exame(exame)

    # Reiniciar browser a cada 2 exames
    if exame_counter % 2 == 0 and exame != exames_selecionados[-1]:
        print("🔄 Reiniciando Chrome para estabilidade...")
        # 1. Fechar todas as abas
        # 2. Criar nova aba limpa
        # 3. Navegar ao portal HAOC
        print("✓ Chrome reiniciado")

    # Pausa obrigatória entre exames
    if exame != exames_selecionados[-1]:
        print("⏳ Aguardando 30 segundos...")
        time.sleep(30)
```

---

## FASE 5: Limpeza (OBRIGATÓRIA)

**Executar SOMENTE se upload foi 100% bem-sucedido (failed == 0)**

```python
import shutil

def limpar_arquivos(temp_dir, zip_file, pdf_file):
    """Remove todos os arquivos temporários - ZERO RASTROS"""

    # 1. Remover pasta temporária com imagens extraídas
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
        print(f"🗑️ Pasta temporária removida")

    # 2. Remover ZIP original
    if zip_file.exists():
        zip_file.unlink()
        print(f"🗑️ ZIP removido")

    # 3. Remover PDF original
    if pdf_file.exists():
        pdf_file.unlink()
        print(f"🗑️ PDF removido")

    print("✅ Limpeza concluída - zero rastros!")
```

**IMPORTANTE:** Não pedir confirmação para limpeza. É parte integral do processo.

---

## FASE 6: Relatório Final

### 6.1 Para um Exame

```
"✅ Exame importado com sucesso!

📁 Dr. Decio Mion Junior/Ultrassonografia de abdome total/2024-12-12
   Nome original: USG ABDOME TOTAL → Normalizado [✅ exact]
   • 000_laudo.pdf (aparece primeiro)
   • 001-019: 19 imagens em ordem

🗑️ Arquivos temporários removidos

[Ver no Sutram]"
```

### 6.2 Para Múltiplos Exames

```
"✅ Importação concluída!

4 exames importados:
• Dr. Decio Mion Junior/USG ABDOME TOTAL/2024-12-12 (20 arquivos)
• Dra. Maria Silva/HEMOGRAMA COMPLETO/2024-12-10 (1 arquivo)
• Dr. Decio Mion Junior/RX TORAX PA/2024-11-05 (3 arquivos)
• Dra. Maria Silva/USG TIREOIDE/2024-09-15 (15 arquivos)

Total: 39 arquivos enviados
🗑️ Todos os arquivos temporários foram removidos

[Ver no Sutram]  [Importar mais exames]"
```

### 6.3 Relatório Markdown (OBRIGATÓRIO)

**Ao final de TODA sessão de importação**, gerar um arquivo markdown com o relatório completo e salvá-lo na pasta **Imports** do Sutram.

**Caminho de destino:** Pasta `Imports` na raiz do projeto Sutram (criar via MCP se não existir).

**Formato do arquivo:** `import-YYYY-MM-DD-HHmm.md`

**Conteúdo do relatório:**

```markdown
# Relatório de Importação - HAOC → Sutram

**Data da execução:** 2026-02-06 14:30
**Portal de origem:** Hospital Alemão Oswaldo Cruz (HAOC)
**Projeto Sutram:** [nome do projeto]

## Resumo

| Métrica | Valor |
|---------|-------|
| Exames processados | 4 |
| Exames com sucesso | 3 |
| Exames com falha | 1 |
| Total de arquivos enviados | 39 |
| Reinícios do Chrome | 1 |

## Normalização de Exames (TUSS)

| Métrica | Valor |
|---------|-------|
| Match exato | 3 |
| Match fuzzy | 0 |
| Fallback LLM | 1 |
| Cache hits | 0 |

### Mapeamentos Aplicados

| Nome Original (HAOC) | Nome Padronizado (TUSS) | Tipo | Score | Código |
|---|---|---|---|---|
| USG ABDOME TOTAL | Ultrassonografia de abdome total | exact | 100% | 40901200 |
| HEMOGRAMA COMPLETO | Hemograma completo | exact | 100% | 40301052 |
| RX TORAX PA | Radiografia de tórax (PA e perfil) | llm | 90% | — |
| ECG REPOUSO | Eletrocardiograma (ECG) | exact | 100% | 40501020 |

## Exames Importados

### ✅ Ultrassonografia de abdome total
- **Original:** USG ABDOME TOTAL → [✅ exact]
- **Médico:** Dr. Decio Mion Junior
- **Data:** 2024-12-12
- **Caminho no Sutram:** Dr. Decio Mion Junior/Ultrassonografia de abdome total/2024-12-12
- **Arquivos:** 1 laudo PDF + 19 imagens JPG

### ✅ Hemograma completo
- **Original:** HEMOGRAMA COMPLETO → [✅ exact]
- **Médico:** Dra. Maria Silva
- **Data:** 2024-12-10
- **Caminho no Sutram:** Dra. Maria Silva/Hemograma completo/2024-12-10
- **Arquivos:** 1 laudo PDF

### ❌ Radiografia de tórax (PA e perfil)
- **Original:** RX TORAX PA → [🤖 llm]
- **Médico:** Dr. Decio Mion Junior
- **Data:** 2024-11-05
- **Problema:** Timeout no download do ZIP após 120 segundos
- **Ação recomendada:** Tentar novamente manualmente

## Problemas Encontrados

1. **RX TORAX PA (2024-11-05):** Download do ZIP expirou. Conexão pode ter sido instável.
2. **Reinício do Chrome** foi necessário após exame 2 (comportamento esperado).

## Observações

- Tempo total de execução: ~8 minutos
- Todos os arquivos temporários foram removidos (zero rastros)
- Cache de normalização atualizado com 4 mapeamentos
```

**Implementação:**

```python
from datetime import datetime
from exam_normalizer import ExamNormalizer

def gerar_relatorio(exames_processados, projeto_nome, normalizer: ExamNormalizer):
    """Gera relatório markdown com seção de normalização e faz upload para Sutram."""

    agora = datetime.now()
    filename = f"import-{agora.strftime('%Y-%m-%d-%H%M')}.md"

    sucesso = [e for e in exames_processados if e['status'] == 'sucesso']
    falha = [e for e in exames_processados if e['status'] != 'sucesso']

    conteudo = f"# Relatório de Importação - HAOC → Sutram\n\n"
    conteudo += f"**Data da execução:** {agora.strftime('%Y-%m-%d %H:%M')}\n"
    conteudo += f"**Portal de origem:** Hospital Alemão Oswaldo Cruz (HAOC)\n"
    conteudo += f"**Projeto Sutram:** {projeto_nome}\n\n"
    conteudo += f"## Resumo\n\n"
    conteudo += f"| Métrica | Valor |\n|---------|-------|\n"
    conteudo += f"| Exames processados | {len(exames_processados)} |\n"
    conteudo += f"| Exames com sucesso | {len(sucesso)} |\n"
    conteudo += f"| Exames com falha | {len(falha)} |\n\n"

    # Seção de normalização (gerada pelo ExamNormalizer)
    conteudo += normalizer.format_stats_for_report()
    conteudo += "\n### Mapeamentos Aplicados\n\n"
    conteudo += "| Original (HAOC) | Padronizado (TUSS) | Tipo | Score |\n"
    conteudo += "|---|---|---|---|\n"
    for exame in exames_processados:
        conf = exame.get('confidence', '—')
        score = exame.get('score', 0)
        conteudo += f"| {exame.get('nome_original', '—')} | {exame.get('nome_padrao', '—')} | {conf} | {score:.0f}% |\n"
    conteudo += "\n"

    # Detalhes de cada exame
    conteudo += "## Exames Importados\n\n"
    for exame in exames_processados:
        status_icon = "✅" if exame['status'] == 'sucesso' else "❌"
        conf_icon = {'exact': '✅', 'fuzzy': '🔍', 'llm': '🤖'}.get(exame.get('confidence'), '❓')
        nome_titulo = exame.get('nome_padrao', exame.get('nome_original', ''))

        conteudo += f"### {status_icon} {nome_titulo}\n"
        conteudo += f"- **Original:** {exame.get('nome_original', '—')} → [{conf_icon} {exame.get('confidence', '—')}]\n"
        conteudo += f"- **Médico:** {exame['medico']}\n"
        conteudo += f"- **Data:** {exame['data']}\n"
        if exame['status'] != 'sucesso':
            conteudo += f"- **Problema:** {exame.get('erro', 'Erro desconhecido')}\n"
        conteudo += "\n"

    # Upload para pasta Imports no Sutram
    sutram_create_folder(path="Imports")
    import base64
    content_b64 = base64.b64encode(conteudo.encode('utf-8')).decode('utf-8')
    sutram_upload_file(folder_id=imports_folder_id, filename=filename, content_base64=content_b64)

    return filename
```

**O relatório deve ser gerado SEMPRE, mesmo que todos os exames tenham falhado.** Ele serve como log de auditoria do que foi tentado.

---

## Conectores de Portal

### Conector: HAOC (Hospital Alemão Oswaldo Cruz)

```yaml
# connectors/haoc.yaml

id: haoc
name: "Hospital Alemão Oswaldo Cruz"
portal_url: "portalexames.hospitaloswaldocruz.org.br"

aliases:
  - HAOC
  - Oswaldo Cruz
  - Osvaldo Cruz
  - Hospital Alemão

downloads:
  laudo_pdf:
    method: click
    selector: ".download-icon, [title*='download'], [title*='Download']"
    output_pattern: "*.pdf"
    wait_timeout: 30

  imagens_zip:
    method: sequence
    steps:
      - action: click
        selector: ".view-icon, [title*='visualizar'], [title*='Visualizar']"
        wait_for: new_tab
        note: "Abre Vue Motion em nova aba"

      - action: switch_to_newest_tab
        note: "CRÍTICO: sempre usar aba mais recente"

      - action: click
        selector: ".save-icon, [title*='salvar'], button:has(svg[data-icon='save'])"
        wait_for: dropdown

      - action: click
        selector: "dropdown-item:last-child, [data-action='save-group']"
        note: "Salvar o grupo ativo - última opção"

    output_pattern: "s_vuemotion_exte_*.zip"
    wait_timeout: 60

    extraction:
      type: zip
      path_inside: "exam/jpeg/*.jpg"

metadata_selectors:
  exam_name: ".exam-name, td:nth-child(2)"
  doctor_name: ".doctor-name, td:nth-child(3)"
  exam_date: ".exam-date, td:nth-child(1)"
  date_format_input: "DD/MM/YYYY"
```

### Adicionar Novo Conector

Para suportar um novo portal (ex: Einstein), criar arquivo `connectors/einstein.yaml` seguindo o mesmo padrão.

---

## Ferramentas MCP Utilizadas

| Ferramenta | Uso no Skill |
|------------|--------------|
| `sutram_project_info` | Verificar conexão e credenciais |
| `sutram_get_folder` | Verificar se exame já existe |
| `sutram_create_folder` | Criar hierarquia de pastas (com `path`) |
| `sutram_upload_batch` | Upload de todos os arquivos de uma vez |

---

## Troubleshooting

### "Não consegui conectar ao Sutram"
- Verificar se as chaves estão corretas
- Verificar conexão com internet
- Tentar regenerar as chaves no Sutram

### "Download do ZIP está demorando muito"
- **Isso é normal!** O download pode levar 30-60 segundos ou mais
- Não clicar novamente no botão de download
- Aguardar pacientemente até o arquivo aparecer na pasta Downloads
- Para exames com muitas imagens (>30), pode demorar até 2 minutos

### "Imagens erradas baixadas"
- Causa: Vue Motion tinha abas antigas abertas
- Solução: Skill deve sempre usar a aba mais recente

### "ZIP muito grande (~100MB)"
- Causa: Usou "Salvar o exame DICOM" em vez de "Salvar o grupo ativo"
- Solução: Sempre usar última opção do dropdown

### "Imagens fora de ordem no Sutram"
- Causa: Upload sem prefixos numéricos
- Solução: Skill agora usa prefixos (000_, 001_, 002_...) para garantir ordenação

### "Exame não aparece no Sutram"
- Verificar se upload reportou `failed: 0`
- Verificar o path correto no Sutram
- Tentar reimportar o exame

### "Credenciais inválidas após funcionar antes"
- Chaves podem ter sido regeneradas no Sutram
- Ir em Sutram → Configurações → MCP e copiar novas chaves
- Skill vai pedir automaticamente quando detectar erro

---

## Exemplo de Sessão Completa

```
👤 Usuário: "Tenho exames novos no Oswaldo Cruz"

🤖 Claude: "Vou ajudar você a importar os exames do Hospital Alemão
           Oswaldo Cruz para o Sutram.

           Você está logado no portal do HAOC?"

👤 Usuário: "Sim"

🤖 Claude: "Ótimo! O que você quer importar?

           ○ Um exame específico
           ○ Exames a partir de uma data
           ○ Exames de um médico específico
           ○ Todos os exames disponíveis"

👤 Usuário: "Os de dezembro"

🤖 Claude: "Encontrei 3 exames de dezembro de 2024:

           ☑️ USG ABDOME TOTAL - Dr. Decio - 12/12/2024
           ☑️ HEMOGRAMA - Dra. Maria - 10/12/2024
           ☑️ RX TORAX - Dr. Decio - 05/12/2024

           Importar os 3 selecionados?"

👤 Usuário: "Sim"

🤖 Claude: "Importando 1/3: USG ABDOME TOTAL...
           ✓ PDF baixado
           ⏳ Baixando imagens (pode demorar 30-60s)...
           ✓ ZIP baixado (12.3 MB)
           ✓ 19 imagens extraídas
           ✓ Enviado para Sutram (000_laudo + 001-019 imagens)
           ✓ Arquivos locais removidos

           Importando 2/3: HEMOGRAMA...
           ✓ PDF baixado
           ✓ Enviado para Sutram (000_laudo)
           ✓ Arquivos locais removidos

           Importando 3/3: RX TORAX...
           ✓ PDF baixado
           ⏳ Baixando imagens...
           ✓ ZIP baixado (2.1 MB)
           ✓ 3 imagens extraídas
           ✓ Enviado para Sutram (000_laudo + 001-003 imagens)
           ✓ Arquivos locais removidos

           ✅ Importação concluída!

           3 exames importados com sucesso
           23 arquivos no total (ordenados: laudo primeiro, imagens em sequência)
           🗑️ Zero rastros no seu computador

           [Ver no Sutram]"
```
