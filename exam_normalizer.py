#!/usr/bin/env python3
"""
exam_normalizer.py - Wrapper de normalização com cache e suporte a LLM fallback.

Encapsula o TUSSDictionary de normalize_exam.py adicionando:
- Cache persistente (mapping_cache.json) para evitar re-processamento
- Suporte a fallback LLM para nomes com score < threshold
- Processamento em batch para listas de exames
- Estatísticas de normalização para relatórios

Uso:
    from exam_normalizer import ExamNormalizer

    normalizer = ExamNormalizer()
    exames = normalizer.normalize_batch([
        {'nome': 'USG ABDOME TOTAL', 'medico': 'Dr. X', 'data': '2024-12-12'},
        {'nome': 'HMG COMPLETO', 'medico': 'Dra. Y', 'data': '2024-12-10'},
    ])
    # Cada exame agora tem: nome_original, nome_padrao, confidence, score, codigo_tuss, categoria
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Adiciona o diretório do script ao path para importar normalize_exam
_script_dir = Path(__file__).parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from normalize_exam import TUSSDictionary


# ---------------------------------------------------------------------------
# Cache de mapeamentos
# ---------------------------------------------------------------------------

class MappingCache:
    """Gerencia cache persistente de normalizações anteriores."""

    def __init__(self, cache_path: str):
        self.path = Path(cache_path)
        self.data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return self._empty_cache()
        return self._empty_cache()

    def _empty_cache(self) -> dict:
        return {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "total_entries": 0,
                "version": "1.0"
            },
            "mappings": {}
        }

    def get(self, nome_original: str) -> Optional[dict]:
        """Busca no cache. Retorna o mapeamento ou None."""
        key = nome_original.strip().upper()
        entry = self.data["mappings"].get(key)
        if entry:
            entry["last_used"] = datetime.now().isoformat()
            entry["use_count"] = entry.get("use_count", 0) + 1
            return entry
        return None

    def put(self, nome_original: str, result: dict):
        """Adiciona ou atualiza uma entrada no cache."""
        key = nome_original.strip().upper()
        now = datetime.now().isoformat()

        existing = self.data["mappings"].get(key)
        self.data["mappings"][key] = {
            "nome_padrao": result.get("nome_padrao"),
            "codigo_tuss": result.get("codigo_tuss"),
            "categoria": result.get("categoria"),
            "confidence": result.get("confidence"),
            "score": result.get("score", 0.0),
            "fallback_used": result.get("confidence") == "llm",
            "first_seen": existing["first_seen"] if existing else now,
            "last_used": now,
            "use_count": (existing.get("use_count", 0) + 1) if existing else 1
        }

        self.data["metadata"]["updated_at"] = now
        self.data["metadata"]["total_entries"] = len(self.data["mappings"])

    def save(self):
        """Persiste o cache em disco."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    @property
    def stats(self) -> dict:
        """Retorna estatísticas do cache."""
        mappings = self.data["mappings"]
        return {
            "total_entries": len(mappings),
            "exact_matches": sum(1 for m in mappings.values() if m["confidence"] == "exact"),
            "fuzzy_matches": sum(1 for m in mappings.values() if m["confidence"] == "fuzzy"),
            "llm_fallbacks": sum(1 for m in mappings.values() if m.get("fallback_used")),
            "no_matches": sum(1 for m in mappings.values() if m["confidence"] == "no_match"),
        }


# ---------------------------------------------------------------------------
# Normalizador principal
# ---------------------------------------------------------------------------

class ExamNormalizer:
    """
    Normalizador de nomes de exames com cache e fallback LLM.

    Fluxo para cada nome:
    1. Consulta cache → se encontrar, retorna imediatamente
    2. Match exato no dicionário TUSS → score 100
    3. Fuzzy match → score >= threshold
    4. Se score < llm_threshold → marca para fallback LLM
    5. Armazena resultado no cache
    """

    def __init__(
        self,
        dict_source=None,
        cache_path: Optional[str] = None,
        threshold: int = 75,
        llm_threshold: int = 80,
        enable_contributions: bool = False,
        github_token: Optional[str] = None,
    ):
        """
        Args:
            dict_source: Fonte do dicionário TUSS. Pode ser:
                         - str/Path: caminho para JSON local (compatibilidade)
                         - dict: dados já carregados
                         - RemoteDictionaryFetcher: busca remota
                         - None: tenta remoto → fallback local
            cache_path: Caminho para mapping_cache.json (default: mesmo diretório do script)
            threshold: Score mínimo para fuzzy match (default: 75)
            llm_threshold: Score abaixo do qual solicitar fallback LLM (default: 80)
            enable_contributions: Habilita submissão de novas descobertas ao repo central
            github_token: Token GitHub para contribuições (ou env TUSS_GITHUB_TOKEN)
        """
        base_dir = Path(__file__).parent

        if cache_path is None:
            cache_path = str(base_dir / "mapping_cache.json")

        self.tuss = TUSSDictionary(dict_source)
        self.cache = MappingCache(cache_path)
        self.threshold = threshold
        self.llm_threshold = llm_threshold

        # Contribuições
        self._contrib = None
        if enable_contributions:
            try:
                from contribution_submitter import ContributionSubmitter
                self._contrib = ContributionSubmitter(github_token=github_token)
            except ImportError:
                pass

        # Contadores da sessão atual
        self._session_stats = {
            "total": 0,
            "cache_hits": 0,
            "exact": 0,
            "fuzzy": 0,
            "llm_needed": 0,
            "no_match": 0,
        }

    def normalize_one(self, nome: str, verbose: bool = False) -> dict:
        """
        Normaliza um único nome de exame.

        Retorna dict com campos:
            nome_original, nome_padrao, codigo_tuss, categoria,
            confidence, score, alternatives, _cache_hit
        """
        self._session_stats["total"] += 1

        # 1. Consultar cache
        cached = self.cache.get(nome)
        if cached and cached.get("nome_padrao"):
            self._session_stats["cache_hits"] += 1
            if verbose:
                print(f"  💾 Cache hit: {nome} → {cached['nome_padrao']}")
            return {
                "nome_original": nome,
                "nome_padrao": cached["nome_padrao"],
                "codigo_tuss": cached.get("codigo_tuss"),
                "categoria": cached.get("categoria"),
                "confidence": cached["confidence"],
                "score": cached["score"],
                "alternatives": [],
                "_cache_hit": True,
            }

        # 2. Normalizar via TUSSDictionary
        result = self.tuss.normalize(nome, threshold=self.threshold, verbose=verbose)

        output = {
            "nome_original": nome,
            "nome_padrao": result["nome_padrao"],
            "codigo_tuss": result.get("codigo_tuss"),
            "categoria": result.get("categoria"),
            "confidence": result["confidence"],
            "score": result["score"],
            "alternatives": result.get("alternatives", []),
            "_cache_hit": False,
        }

        # Atualizar contadores
        if result["confidence"] == "exact":
            self._session_stats["exact"] += 1
        elif result["confidence"] == "fuzzy":
            self._session_stats["fuzzy"] += 1
            # Verificar se precisa de fallback LLM
            if result["score"] < self.llm_threshold:
                self._session_stats["llm_needed"] += 1
                output["_needs_llm"] = True
        else:
            self._session_stats["no_match"] += 1
            output["_needs_llm"] = True
            self._session_stats["llm_needed"] += 1

        # 3. Armazenar no cache (mesmo sem match, para evitar re-processamento)
        self.cache.put(nome, output)

        return output

    def normalize_batch(self, exames: list, verbose: bool = False) -> list:
        """
        Normaliza uma lista de exames em batch.

        Input:  [{'nome': str, 'medico': str, 'data': str, ...}, ...]
        Output: Mesma lista com campos adicionados:
                nome_original, nome_padrao, confidence, score, codigo_tuss, categoria

        O campo 'nome' original é preservado como 'nome_original'.
        """
        for exame in exames:
            nome = exame.get("nome", exame.get("nome_original", ""))
            result = self.normalize_one(nome, verbose=verbose)

            exame["nome_original"] = nome
            exame["nome_padrao"] = result["nome_padrao"] or nome  # fallback ao original
            exame["confidence"] = result["confidence"]
            exame["score"] = result["score"]
            exame["codigo_tuss"] = result.get("codigo_tuss")
            exame["categoria"] = result.get("categoria")
            exame["_cache_hit"] = result.get("_cache_hit", False)
            exame["_needs_llm"] = result.get("_needs_llm", False)

        # Persistir cache após batch
        self.cache.save()

        return exames

    def apply_llm_result(self, nome_original: str, nome_normalizado: str,
                         codigo_tuss: str = None, portal: str = "unknown"):
        """
        Registra o resultado de um fallback LLM no cache e enfileira contribuição.

        Chamado pelo skill após o Claude normalizar um nome que o script não conseguiu.
        """
        result = {
            "nome_padrao": nome_normalizado,
            "codigo_tuss": codigo_tuss,
            "categoria": None,
            "confidence": "llm",
            "score": 90.0,  # Score convencional para LLM
        }
        self.cache.put(nome_original, result)
        self.cache.save()

        # Enfileirar contribuição para o repo central
        if self._contrib:
            self._contrib.queue(
                original_name=nome_original,
                mapped_name=nome_normalizado,
                codigo_tuss=codigo_tuss or "",
                confidence="llm",
                score=90.0,
                portal=portal,
            )

    def flush_contributions(self) -> dict:
        """
        Submete contribuições enfileiradas ao repositório central via GitHub API.

        Chamado no fim da sessão de importação (Fase 6 do skill).

        Returns:
            dict com {status, submitted, message, pr_url}
        """
        if not self._contrib:
            return {"status": "disabled", "submitted": 0, "message": "Contribuições desabilitadas"}

        result = self._contrib.flush()

        # Salvar localmente como backup se falhou
        if result.get("status") == "error":
            backup = self._contrib.save_local()
            result["local_backup"] = backup

        return result

    def get_llm_prompt(self, nome_original: str, score: float = 0.0) -> str:
        """
        Retorna o prompt formatado para fallback LLM.

        O skill deve usar este prompt com o Claude para normalizar nomes
        que não atingiram o threshold de confiança.
        """
        return f"""Normalize o seguinte nome de exame médico para o padrão TUSS \
(Terminologia Unificada da Saúde Suplementar da ANS).
Retorne APENAS o nome padronizado, sem explicações.

Nome original: "{nome_original}"
Confiança do match automático: {score:.1f}% (abaixo do threshold de {self.llm_threshold}%)

Contexto: Este é um exame de um portal hospitalar brasileiro (HAOC).

Exemplos de normalização:
- "HMG COMPLETO" → "Hemograma completo"
- "RX TORAX PA" → "Radiografia de tórax (PA e perfil)"
- "USG ABD TOTAL" → "Ultrassonografia de abdome total"
- "ECG REPOUSO" → "Eletrocardiograma em repouso"
- "T4 LIVRE" → "Tiroxina livre (T4 livre)"
- "GAMA GT" → "Gama-glutamiltransferase (GGT)"

Nome padronizado:"""

    @property
    def session_stats(self) -> dict:
        """Retorna estatísticas da sessão atual (para o relatório)."""
        return {
            **self._session_stats,
            "cache_stats": self.cache.stats,
        }

    def format_stats_for_report(self) -> str:
        """Formata estatísticas como seção markdown para o relatório de importação."""
        s = self._session_stats
        cs = self.cache.stats

        lines = []
        lines.append("## Normalização de Exames (TUSS)\n")
        lines.append("| Métrica | Valor |")
        lines.append("|---------|-------|")
        lines.append(f"| Exames normalizados | {s['total']} |")
        lines.append(f"| Cache hits (reuso) | {s['cache_hits']} |")
        lines.append(f"| Match exato | {s['exact']} |")
        lines.append(f"| Match fuzzy | {s['fuzzy']} |")
        lines.append(f"| Fallback LLM | {s['llm_needed']} |")
        lines.append(f"| Sem match | {s['no_match']} |")
        lines.append(f"| Total no cache (acumulado) | {cs['total_entries']} |")
        lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI (para testes rápidos)
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Normaliza nomes de exames com cache e estatísticas'
    )
    parser.add_argument('nome', nargs='?', help='Nome do exame a normalizar')
    parser.add_argument('--batch', '-b', type=str, help='Arquivo com nomes (um por linha)')
    parser.add_argument('--threshold', '-t', type=int, default=75)
    parser.add_argument('--llm-threshold', type=int, default=80)
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--cache-stats', action='store_true', help='Mostra estatísticas do cache')

    args = parser.parse_args()

    normalizer = ExamNormalizer(
        threshold=args.threshold,
        llm_threshold=args.llm_threshold,
    )

    if args.cache_stats:
        print(json.dumps(normalizer.cache.stats, indent=2))
        return

    if args.batch:
        with open(args.batch, 'r', encoding='utf-8') as f:
            nomes = [line.strip() for line in f if line.strip()]
        exames = [{'nome': n} for n in nomes]
        results = normalizer.normalize_batch(exames, verbose=args.verbose)
        for r in results:
            conf = r['confidence']
            icon = {'exact': '✅', 'fuzzy': '🔍', 'no_match': '❌'}.get(conf, '❓')
            print(f"  {icon} {r['nome_original']} → {r['nome_padrao']} [{conf} {r['score']:.0f}%]")
        print(f"\n{normalizer.format_stats_for_report()}")

    elif args.nome:
        result = normalizer.normalize_one(args.nome, verbose=args.verbose)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("_needs_llm"):
            print("\n--- Prompt para fallback LLM ---")
            print(normalizer.get_llm_prompt(args.nome, result["score"]))

    else:
        parser.error('Informe um nome de exame ou use --batch')


if __name__ == '__main__':
    main()
