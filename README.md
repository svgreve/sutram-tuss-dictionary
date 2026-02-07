# TUSS Medical Exam Dictionary

Centralized, community-enriched dictionary for normalizing medical exam names across Brazilian hospitals and labs. Based on [ANS TUSS Table 22](https://www.gov.br/ans/pt-br/assuntos/prestadores/padrao-para-troca-de-informacao-de-saude-suplementar-2013-tiss/padrao-tiss-tabelas-relacionadas) (official standard), with curated aliases for fuzzy matching. Auto-synced weekly with the official ANS catalog.

## What is this?

Brazilian hospitals and labs use wildly different names for the same medical exam. "USG ABDOME TOTAL", "Usg Abdome Total", "ULTRASSONOGRAFIA DE ABDOME TOTAL" and "US Abdomen" are all the same procedure — TUSS code `40901122`.

This dictionary maps those variations to a single, canonical TUSS name, enabling consistent folder structures when organizing medical records in [Sutram](https://sutram.io).

## How it works

This repository is designed to be consumed by the **Medical Exam Migration Skill** — a Claude skill that automates importing medical exams from hospital portals (HAOC, Einstein, Sírio-Libanês, etc.) into Sutram via the [Sutram MCP Server](https://sutram.io/mcp).

```
Hospital Portal                    Sutram
┌──────────────┐                  ┌──────────────────────────────────────┐
│ "Usg Abdome  │   normalize()    │ Dr. Kildare/                         │
│  Total"      │ ───────────────► │   Ultrassonografia de abdome total/  │
│              │   TUSS 40901122  │     2024-12-12/                      │
│ "USG ABDOME  │ ───────────────► │       000_laudo.pdf                  │
│  TOTAL"      │   same folder!   │       001_imagem.jpg                 │
└──────────────┘                  └──────────────────────────────────────┘
```

The skill fetches this dictionary at startup, normalizes exam names during import, and — when it discovers a new mapping via LLM fallback — contributes it back to this repository for everyone to benefit.

## Dictionary structure

```
https://raw.githubusercontent.com/svgreve/sutram-tuss-dictionary/main/tuss_exames_comuns.json
```

```json
{
  "_meta": {
    "source": "ANS - Tabela TUSS 22",
    "version": "2025-05",
    "total_registros": 220
  },
  "exames": [
    {
      "codigo_tuss": "40901122",
      "nome_padrao": "US - Abdome total (abdome superior, rins, bexiga, aorta, veia cava inferior e adrenais)",
      "nome_comum": "Ultrassonografia de abdome total",
      "categoria": "Ultrassonografia",
      "aliases": ["USG ABDOME TOTAL", "US ABDOME TOTAL", "ULTRASSONOGRAFIA DE ABDOME TOTAL", "Usg Abdome Total"]
    }
  ]
}
```

| Field | Description |
|:------|:------------|
| `codigo_tuss` | Official TUSS code from ANS Table 22 |
| `nome_padrao` | Official TUSS procedure name |
| `nome_comum` | Friendly name used for folder creation in Sutram (when the official name is too verbose) |
| `categoria` | Exam category (Ultrassonografia, Cardiologia, Hematologia, etc.) |
| `aliases` | Known name variations from hospital portals — the key to fuzzy matching |

## Integration with the Skill

The skill uses three Python modules to consume this dictionary:

| Module | Purpose |
|:-------|:--------|
| `dict_fetcher.py` | Fetches the dictionary from this repo with HTTP ETag caching (24h TTL) and local fallback |
| `normalize_exam.py` | Core matching engine — exact alias lookup → fuzzy (Levenshtein + token sort) → LLM fallback |
| `exam_normalizer.py` | Wrapper with persistent cache, batch processing, and contribution submission |

The skill's `config.yaml` points to this repository:

```yaml
tuss_dictionary:
  remote_url: "https://raw.githubusercontent.com/svgreve/sutram-tuss-dictionary/main/tuss_exames_comuns.json"
  cache_ttl_hours: 24
  fallback_local: true
```

## Contributing

### Automatic (via Skill)

When the skill encounters an exam name it can't match, Claude normalizes it via LLM fallback. The result is automatically submitted as a Pull Request to `contrib/pending.json`. A maintainer reviews and merges.

### Manual

1. Fork this repository
2. Add or correct entries in `tuss_exames_comuns.json`
3. Run validation: `python scripts/validate_dictionary.py tuss_exames_comuns.json`
4. Submit a Pull Request with a clear description

All PRs are automatically validated by GitHub Actions before merge.

## ANS auto-sync

A GitHub Actions workflow runs weekly (Sundays at 02:00 UTC) to sync with the [official ANS TUSS Table 22](https://github.com/charlesfgarcia/tabelas-ans). It fetches the latest data, merges new procedures while preserving community-contributed aliases, and opens a PR for review.

## Rebuilding from scratch

To regenerate the full dictionary from the official ANS table (2,822 SADT procedures):

```bash
python build_tuss_dict.py -o tuss_exames_comuns.json -m existing_dict.json -v --stats
```

This fetches all 5,851 procedures from TUSS Table 22, filters to diagnostic exams (SADT codes), auto-generates aliases, and merges with any existing curated aliases.

## Sources

- [ANS TUSS Table 22](https://www.gov.br/ans/pt-br/assuntos/prestadores/padrao-para-troca-de-informacao-de-saude-suplementar-2013-tiss/padrao-tiss-tabelas-relacionadas) — Official Brazilian standard for health procedure naming
- [charlesfgarcia/tabelas-ans](https://github.com/charlesfgarcia/tabelas-ans) — Parsed TUSS tables in JSON/CSV format
- [Sutram](https://sutram.io) — Document management platform
- [Sutram MCP Server](https://sutram.io/mcp) — API for programmatic access to Sutram projects

## License

The data in this repository is derived from public information published by ANS (Agência Nacional de Saúde Suplementar). It is made available for both commercial and non-commercial use.

