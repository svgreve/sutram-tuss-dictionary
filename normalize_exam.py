#!/usr/bin/env python3
"""
normalize_exam.py - Normaliza nomes de exames médicos para o padrão TUSS.

Estratégia de matching (em ordem de prioridade):
1. Match exato no dicionário de aliases (case-insensitive, sem acentos)
2. Fuzzy match nos aliases com score >= threshold
3. Fallback para LLM (opcional, via flag --use-llm)

Uso:
    # Match único
    python normalize_exam.py "HMG COMPLETO"
    
    # Batch de nomes (um por linha)
    python normalize_exam.py --batch nomes.txt
    
    # Com output JSON
    python normalize_exam.py --batch nomes.txt --output resultado.json
    
    # Modo verbose com scores
    python normalize_exam.py -v "hemograma compl"
    
    # Ajustar threshold de fuzzy matching (default: 75)
    python normalize_exam.py --threshold 80 "exame desconhecido"
"""

import json
import sys
import os
import re
import unicodedata
import argparse
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Text normalization helpers
# ---------------------------------------------------------------------------

def remove_accents(text: str) -> str:
    """Remove acentos de uma string."""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def normalize_text(text: str) -> str:
    """Normaliza texto para comparação: lowercase, sem acentos, sem pontuação extra."""
    text = remove_accents(text.strip().upper())
    # Remove caracteres especiais exceto espaços e hífens
    text = re.sub(r'[^A-Z0-9\s\-/()]', '', text)
    # Normaliza espaços múltiplos
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ---------------------------------------------------------------------------
# Fuzzy matching (sem dependências externas)
# ---------------------------------------------------------------------------

def levenshtein_ratio(s1: str, s2: str) -> float:
    """Calcula similaridade entre duas strings (0-100) usando distância de Levenshtein."""
    if not s1 or not s2:
        return 0.0
    
    len1, len2 = len(s1), len(s2)
    
    # Otimização: se uma string contém a outra, alta similaridade
    if s1 in s2 or s2 in s1:
        return (min(len1, len2) / max(len1, len2)) * 100
    
    # Matriz de distância
    matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    for i in range(len1 + 1):
        matrix[i][0] = i
    for j in range(len2 + 1):
        matrix[0][j] = j
    
    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i-1] == s2[j-1] else 1
            matrix[i][j] = min(
                matrix[i-1][j] + 1,      # deletion
                matrix[i][j-1] + 1,       # insertion
                matrix[i-1][j-1] + cost   # substitution
            )
    
    distance = matrix[len1][len2]
    max_len = max(len1, len2)
    return ((max_len - distance) / max_len) * 100


def token_sort_ratio(s1: str, s2: str) -> float:
    """Compara strings com tokens ordenados (lida com ordem diferente de palavras)."""
    tokens1 = ' '.join(sorted(s1.split()))
    tokens2 = ' '.join(sorted(s2.split()))
    return levenshtein_ratio(tokens1, tokens2)


def best_fuzzy_score(s1: str, s2: str) -> float:
    """Retorna o melhor score entre diferentes estratégias de fuzzy matching."""
    return max(
        levenshtein_ratio(s1, s2),
        token_sort_ratio(s1, s2)
    )


# ---------------------------------------------------------------------------
# TUSS Dictionary
# ---------------------------------------------------------------------------

class TUSSDictionary:
    """Gerencia o dicionário TUSS e faz matching de nomes de exames.

    Aceita como fonte:
      - str/Path: caminho para arquivo JSON local (compatibilidade)
      - dict: dados já carregados (com chaves 'exames' e '_meta')
      - RemoteDictionaryFetcher: busca remota com cache
      - None: tenta RemoteDictionaryFetcher, fallback para arquivo local
    """

    def __init__(self, dict_source=None):
        data = self._load_data(dict_source)

        self.exames = data['exames']
        self.meta = data.get('_meta', {})
        
        # Constrói índice de aliases normalizados -> exame
        self._alias_index: dict[str, dict] = {}
        for exame in self.exames:
            # Indexa o nome padrão
            key = normalize_text(exame['nome_padrao'])
            self._alias_index[key] = exame
            # Indexa cada alias
            for alias in exame.get('aliases', []):
                key = normalize_text(alias)
                self._alias_index[key] = exame
    
    @staticmethod
    def _load_data(dict_source) -> dict:
        """Carrega dados do dicionário a partir de diversas fontes."""
        # dict já carregado
        if isinstance(dict_source, dict):
            if 'exames' not in dict_source:
                raise ValueError("dict_source precisa ter chave 'exames'")
            return dict_source

        # str ou Path → arquivo local
        if isinstance(dict_source, (str, Path)):
            with open(dict_source, 'r', encoding='utf-8') as f:
                return json.load(f)

        # RemoteDictionaryFetcher (duck-typed: qualquer objeto com .fetch())
        if dict_source is not None and hasattr(dict_source, 'fetch'):
            return dict_source.fetch()

        # None → tenta remoto, fallback para local
        try:
            from dict_fetcher import RemoteDictionaryFetcher
            fetcher = RemoteDictionaryFetcher()
            return fetcher.fetch()
        except Exception:
            script_dir = Path(__file__).parent
            local_path = script_dir / "tuss_exames_comuns.json"
            if local_path.exists():
                with open(local_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            raise RuntimeError(
                "Não foi possível carregar o dicionário TUSS: "
                "sem acesso remoto e arquivo local não encontrado."
            )

    def match_exact(self, nome: str) -> Optional[dict]:
        """Tenta match exato no índice de aliases."""
        key = normalize_text(nome)
        return self._alias_index.get(key)
    
    def match_fuzzy(self, nome: str, threshold: int = 75, top_n: int = 3) -> list[dict]:
        """
        Faz fuzzy match contra todos os aliases.
        Retorna lista de matches com score >= threshold, ordenados por score desc.
        """
        key = normalize_text(nome)
        results = []
        seen_codes = set()
        
        for alias_norm, exame in self._alias_index.items():
            code = exame['codigo_tuss']
            if code in seen_codes:
                # Pega apenas o melhor score por exame
                for r in results:
                    if r['codigo_tuss'] == code:
                        score = best_fuzzy_score(key, alias_norm)
                        if score > r['score']:
                            r['score'] = score
                            r['matched_alias'] = alias_norm
                        break
                continue
            
            score = best_fuzzy_score(key, alias_norm)
            if score >= threshold:
                seen_codes.add(code)
                results.append({
                    'codigo_tuss': code,
                    'nome_padrao': exame['nome_padrao'],
                    'categoria': exame['categoria'],
                    'score': score,
                    'matched_alias': alias_norm
                })
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_n]
    
    def normalize(self, nome: str, threshold: int = 75, verbose: bool = False) -> dict:
        """
        Normaliza um nome de exame.

        Retorna:
            {
                "input": str,
                "nome_padrao": str | None,
                "nome_comum": str | None,  # Nome amigável (se disponível), senão = nome_padrao
                "codigo_tuss": str | None,
                "categoria": str | None,
                "confidence": "exact" | "fuzzy" | "no_match",
                "score": float,
                "alternatives": [...] (se fuzzy)
            }
        """
        result = {
            'input': nome,
            'nome_padrao': None,
            'nome_comum': None,
            'codigo_tuss': None,
            'categoria': None,
            'confidence': 'no_match',
            'score': 0.0,
            'alternatives': []
        }

        # 1. Match exato
        exact = self.match_exact(nome)
        if exact:
            nome_comum = exact.get('nome_comum', exact['nome_padrao'])
            result.update({
                'nome_padrao': exact['nome_padrao'],
                'nome_comum': nome_comum,
                'codigo_tuss': exact['codigo_tuss'],
                'categoria': exact['categoria'],
                'confidence': 'exact',
                'score': 100.0
            })
            if verbose:
                display = nome_comum if nome_comum != exact['nome_padrao'] else exact['nome_padrao']
                print(f"  ✅ Match exato: {display} ({exact['codigo_tuss']})")
            return result

        # 2. Fuzzy match
        fuzzy_results = self.match_fuzzy(nome, threshold=threshold)
        if fuzzy_results:
            best = fuzzy_results[0]
            # Buscar nome_comum do exame original
            nome_comum = best['nome_padrao']
            for exame in self.exames:
                if exame['codigo_tuss'] == best['codigo_tuss']:
                    nome_comum = exame.get('nome_comum', exame['nome_padrao'])
                    break
            result.update({
                'nome_padrao': best['nome_padrao'],
                'nome_comum': nome_comum,
                'codigo_tuss': best['codigo_tuss'],
                'categoria': best['categoria'],
                'confidence': 'fuzzy',
                'score': best['score'],
                'alternatives': fuzzy_results[1:]
            })
            if verbose:
                display = nome_comum if nome_comum != best['nome_padrao'] else best['nome_padrao']
                print(f"  🔍 Fuzzy match (score={best['score']:.1f}): {display} ({best['codigo_tuss']})")
                for alt in fuzzy_results[1:]:
                    print(f"     Alt (score={alt['score']:.1f}): {alt['nome_padrao']}")
            return result
        
        # 3. Sem match
        if verbose:
            print(f"  ❌ Sem match para: {nome}")
        return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Normaliza nomes de exames médicos para o padrão TUSS'
    )
    parser.add_argument(
        'nome', nargs='?',
        help='Nome do exame a normalizar'
    )
    parser.add_argument(
        '--batch', '-b', type=str,
        help='Arquivo com nomes de exames (um por linha)'
    )
    parser.add_argument(
        '--output', '-o', type=str,
        help='Arquivo de saída JSON (default: stdout)'
    )
    parser.add_argument(
        '--threshold', '-t', type=int, default=75,
        help='Threshold mínimo para fuzzy matching (0-100, default: 75)'
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Modo verbose com detalhes do matching'
    )
    parser.add_argument(
        '--dict', '-d', type=str, default=None,
        help='Caminho para o dicionário TUSS JSON'
    )
    parser.add_argument(
        '--stats', action='store_true',
        help='Mostra estatísticas do batch'
    )
    
    args = parser.parse_args()
    
    if not args.nome and not args.batch:
        parser.error('Informe um nome de exame ou use --batch com um arquivo')
    
    tuss = TUSSDictionary(args.dict)
    
    if args.batch:
        # Modo batch
        with open(args.batch, 'r', encoding='utf-8') as f:
            nomes = [line.strip() for line in f if line.strip()]
        
        results = []
        for nome in nomes:
            if args.verbose:
                print(f"\n📋 {nome}")
            result = tuss.normalize(nome, threshold=args.threshold, verbose=args.verbose)
            results.append(result)
        
        if args.stats:
            exact = sum(1 for r in results if r['confidence'] == 'exact')
            fuzzy = sum(1 for r in results if r['confidence'] == 'fuzzy')
            no_match = sum(1 for r in results if r['confidence'] == 'no_match')
            total = len(results)
            print(f"\n{'='*50}")
            print(f"📊 Estatísticas:")
            print(f"   Total:    {total}")
            print(f"   Exatos:   {exact} ({exact/total*100:.1f}%)")
            print(f"   Fuzzy:    {fuzzy} ({fuzzy/total*100:.1f}%)")
            print(f"   Sem match: {no_match} ({no_match/total*100:.1f}%)")
            print(f"{'='*50}")
        
        output = json.dumps(results, ensure_ascii=False, indent=2)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"\n💾 Resultado salvo em: {args.output}")
        else:
            if not args.verbose:
                print(output)
    
    else:
        # Modo single
        if args.verbose:
            print(f"\n📋 Normalizando: {args.nome}")
        result = tuss.normalize(args.nome, threshold=args.threshold, verbose=args.verbose)
        
        if not args.verbose:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"\n📦 Resultado:")
            print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
