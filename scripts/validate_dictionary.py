#!/usr/bin/env python3
"""
Validates the TUSS dictionary JSON structure and content.
Ensures data integrity and reports statistics.
"""

import json
import sys
from collections import defaultdict


def validate_dictionary(file_path):
    """
    Validates a TUSS dictionary JSON file.

    Returns:
        tuple: (is_valid: bool, errors: list, stats: dict)
    """
    errors = []
    stats = {
        'total_entries': 0,
        'entries_without_aliases': 0,
        'duplicate_codes': [],
        'duplicate_aliases': defaultdict(list)
    }

    # Load JSON file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        errors.append(f"Arquivo não encontrado: {file_path}")
        return False, errors, stats
    except json.JSONDecodeError as e:
        errors.append(f"Erro ao decodificar JSON: {e}")
        return False, errors, stats

    # Validate _meta exists
    if '_meta' not in data:
        errors.append("Campo '_meta' não encontrado no dicionário")
        return False, errors, stats

    # Validate exames is array
    if 'exames' not in data:
        errors.append("Campo 'exames' não encontrado no dicionário")
        return False, errors, stats

    if not isinstance(data['exames'], list):
        errors.append("Campo 'exames' deve ser um array")
        return False, errors, stats

    stats['total_entries'] = len(data['exames'])

    # Track codes and aliases for duplicate detection
    seen_codes = {}
    all_aliases = defaultdict(list)

    # Validate each entry
    for idx, entry in enumerate(data['exames']):
        if not isinstance(entry, dict):
            errors.append(f"Entrada {idx} não é um objeto JSON válido")
            continue

        # Check required fields
        required_fields = ['codigo_tuss', 'nome_padrao', 'categoria', 'aliases']
        for field in required_fields:
            if field not in entry:
                errors.append(f"Entrada {idx} falta campo obrigatório: {field}")
                continue

        # Validate codigo_tuss
        codigo = entry.get('codigo_tuss', '')
        if not isinstance(codigo, str) or not codigo.strip():
            errors.append(f"Entrada {idx}: codigo_tuss deve ser uma string não-vazia")
            continue

        if codigo in seen_codes:
            stats['duplicate_codes'].append({
                'codigo': codigo,
                'primeira_linha': seen_codes[codigo],
                'duplicada_linha': idx
            })
        else:
            seen_codes[codigo] = idx

        # Validate nome_padrao
        nome_padrao = entry.get('nome_padrao', '')
        if not isinstance(nome_padrao, str) or not nome_padrao.strip():
            errors.append(f"Entrada {idx}: nome_padrao deve ser uma string não-vazia")

        # Validate categoria
        categoria = entry.get('categoria', '')
        if not isinstance(categoria, str) or not categoria.strip():
            errors.append(f"Entrada {idx}: categoria deve ser uma string não-vazia")

        # Validate aliases
        aliases = entry.get('aliases', [])
        if not isinstance(aliases, list):
            errors.append(f"Entrada {idx}: aliases deve ser um array")
            continue

        if not aliases or len(aliases) == 0:
            stats['entries_without_aliases'] += 1

        # Track aliases for duplicate detection
        for alias in aliases:
            if not isinstance(alias, str):
                errors.append(f"Entrada {idx}: alias deve ser string, encontrado {type(alias)}")
                continue
            all_aliases[alias].append(idx)

    # Report duplicate aliases
    for alias, entries in all_aliases.items():
        if len(entries) > 1:
            stats['duplicate_aliases'][alias] = entries

    is_valid = len(errors) == 0

    return is_valid, errors, stats


def print_report(file_path, is_valid, errors, stats):
    """Prints validation report to stdout."""

    print(f"\n{'='*60}")
    print(f"Validação do Dicionário TUSS")
    print(f"{'='*60}\n")

    print(f"Arquivo: {file_path}")
    print(f"Status: {'VÁLIDO ✓' if is_valid else 'INVÁLIDO ✗'}\n")

    # Statistics
    print(f"Estatísticas:")
    print(f"  - Total de entradas: {stats['total_entries']}")
    print(f"  - Entradas sem aliases: {stats['entries_without_aliases']}")
    print(f"  - Códigos duplicados: {len(stats['duplicate_codes'])}")
    print(f"  - Aliases duplicados: {len(stats['duplicate_aliases'])}\n")

    # Errors
    if errors:
        print(f"Erros encontrados ({len(errors)}):")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")
        print()

    # Duplicate codes
    if stats['duplicate_codes']:
        print(f"Códigos TUSS duplicados:")
        for dup in stats['duplicate_codes']:
            print(f"  - {dup['codigo']}: linhas {dup['primeira_linha']} e {dup['duplicada_linha']}")
        print()

    # Duplicate aliases
    if stats['duplicate_aliases']:
        print(f"Aliases duplicados:")
        for alias, entries in list(stats['duplicate_aliases'].items())[:10]:
            print(f"  - '{alias}': encontrado em {len(entries)} entradas (linhas: {', '.join(map(str, entries))})")
        if len(stats['duplicate_aliases']) > 10:
            print(f"  ... e mais {len(stats['duplicate_aliases']) - 10}")
        print()

    print(f"{'='*60}\n")


def main():
    if len(sys.argv) < 2:
        print("Uso: python validate_dictionary.py <caminho_do_arquivo.json>")
        sys.exit(1)

    file_path = sys.argv[1]

    is_valid, errors, stats = validate_dictionary(file_path)
    print_report(file_path, is_valid, errors, stats)

    # Exit with appropriate code
    sys.exit(0 if is_valid else 1)


if __name__ == '__main__':
    main()
