# Quick Start — Importação de Exames Médicos para o Sutram

## O que você precisa

1. Uma conta no [Sutram](https://sutram.io) com acesso remoto (MCP) habilitado
2. [Claude Code](https://claude.com/claude-code) instalado

## Como usar

Abra o Claude Code em uma pasta vazia e diga:

```
Clone o repositório https://github.com/svgreve/sutram-tuss-dictionary
para sua pasta de trabalho e importe meus exames do HAOC para o Sutram.
```

O Claude vai:

1. Clonar o repositório com o skill e os scripts de normalização
2. Pedir suas credenciais do Sutram (apenas na primeira vez)
3. Abrir o portal do HAOC no navegador
4. Baixar, normalizar e enviar seus exames para o Sutram

Na **primeira execução**, o Claude vai pedir que você autorize alguns comandos. Aceite com "Sempre permitir" — isso não será pedido novamente.

## Exames já normalizados?

O dicionário TUSS inclui 220+ exames com nomes padronizados pela ANS. Se o seu exame não estiver no dicionário, o Claude resolve na hora usando IA e contribui o novo mapeamento de volta para a comunidade.

## Problemas?

- **Credenciais inválidas:** Acesse sutram.io → Configurações → Integrações → MCP e gere novas chaves
- **Exame não reconhecido:** O fallback com LLM resolve automaticamente; o resultado é salvo para futuros usos
- **Documentação do MCP:** Consulte `docs_mcp/sutram_mcp_server_user_guide.md`
