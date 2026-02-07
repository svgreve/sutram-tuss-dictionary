#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para construir dicionário de procedimentos TUSS (Terminologia Unificada da Saúde Suplementar)
com foco em exames e procedimentos diagnósticos/terapêuticos.

Busca a Tabela 22 do TUSS no GitHub, filtra códigos SADT e procedimentos clínicos,
categoriza por tipo de procedimento, gera aliases automáticos e permite mesclagem
com dicionários curados.

Autor: Script automatizado para HAOC/Sutram
Data: 2024
"""

import json
import urllib.request
import urllib.error
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Optional
import re


class TussDictBuilder:
    """Construtor de dicionário TUSS com categorização e geração de aliases."""

    # Categorias SADT (códigos 40xx)
    CATEGORIAS_SADT = {
        '4010': 'Métodos Diagnósticos por Grafismo',
        '4020': 'Endoscopia',
        '4030': 'Exames Laboratoriais',
        '4031': 'Microbiologia e Parasitologia',
        '4032': 'Bioquímica e Imunologia',
        '4040': 'Hemoterapia',
        '4050': 'Genética',
        '4060': 'Anatomia Patológica',
        '4070': 'Medicina Nuclear - Diagnóstico',
        '4071': 'Medicina Nuclear - Terapia',
        '4080': 'Radiologia',
        '4081': 'Radiologia Intervencionista',
        '4090': 'Ultrassonografia',
        '4091': 'Ressonância Magnética',
        '4092': 'Tomografia',
        '4099': 'Outros SADT',
    }

    # Categorias não-SADT que são exames comuns (procedimentos clínicos)
    CATEGORIAS_NAO_SADT = {
        '2010': 'Procedimentos Clínicos',
    }

    # Códigos específicos de procedimentos clínicos que são exames
    CODIGOS_EXAME_CLINICOS = {
        '20102038',  # MAPA
        '20102039',  # Holter
    }

    # Padrão para Holter (201020xx)
    PADRAO_HOLTER = re.compile(r'^20102[0-9]{3}$')

    def __init__(self, verbose: bool = False):
        """
        Inicializa o construtor.

        Args:
            verbose: Se True, exibe mensagens de progresso
        """
        self.verbose = verbose
        self.procedimentos = []
        self.procedimentos_filtrados = []
        self.dicionario_final = []
        self.stats = {
            'total_tabela22': 0,
            'total_sadt': 0,
            'total_nao_sadt': 0,
            'total_com_aliases_curados': 0,
            'aliases_gerados': 0,
            'aliases_curados': 0,
        }

    def log(self, mensagem: str) -> None:
        """Exibe mensagem se modo verbose está ativo."""
        if self.verbose:
            print(f"[INFO] {mensagem}")

    def fetch_tuss_table22(self) -> bool:
        """
        Busca a Tabela 22 do TUSS do GitHub.

        Returns:
            True se conseguiu buscar, False caso contrário
        """
        url = 'https://raw.githubusercontent.com/charlesfgarcia/tabelas-ans/master/TUSS/tabela%2022/tabela_22.json'

        self.log(f"Buscando Tabela 22 do TUSS de: {url}")

        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                dados = json.loads(response.read().decode('utf-8'))

            if 'rows' in dados:
                self.procedimentos = dados.get('rows', [])
                self.stats['total_tabela22'] = len(self.procedimentos)
                self.log(f"Tabela 22 obtida com sucesso: {self.stats['total_tabela22']} procedimentos")
                return True
            else:
                print(f"[ERRO] Formato de dados inesperado. Chaves encontradas: {list(dados.keys())}")
                return False

        except urllib.error.URLError as e:
            print(f"[ERRO] Falha na conexão com GitHub: {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"[ERRO] Falha ao decodificar JSON: {e}")
            return False
        except Exception as e:
            print(f"[ERRO] Erro inesperado ao buscar Tabela 22: {e}")
            return False

    def filtrar_procedimentos(self) -> None:
        """Filtra procedimentos SADT e procedimentos clínicos que são exames."""
        self.log("Filtrando procedimentos...")

        for proc in self.procedimentos:
            codigo = str(proc.get('codigo', ''))

            # Filtrar SADT (códigos começando com 4)
            if codigo.startswith('4'):
                self.procedimentos_filtrados.append(proc)
                self.stats['total_sadt'] += 1
            # Filtrar procedimentos clínicos específicos que são exames
            elif codigo in self.CODIGOS_EXAME_CLINICOS or self.PADRAO_HOLTER.match(codigo):
                self.procedimentos_filtrados.append(proc)
                self.stats['total_nao_sadt'] += 1

        self.log(f"Total de SADT filtrados: {self.stats['total_sadt']}")
        self.log(f"Total de procedimentos clínicos/exames filtrados: {self.stats['total_nao_sadt']}")

    def categorizar_procedimento(self, codigo: str) -> str:
        """
        Categoriza um procedimento baseado em seu código.

        Args:
            codigo: Código do procedimento

        Returns:
            Nome da categoria
        """
        # Verificar se é SADT
        for prefixo_categoria in sorted(self.CATEGORIAS_SADT.keys(), reverse=True):
            if codigo.startswith(prefixo_categoria):
                return self.CATEGORIAS_SADT[prefixo_categoria]

        # Verificar se é não-SADT
        for prefixo_categoria in self.CATEGORIAS_NAO_SADT.keys():
            if codigo.startswith(prefixo_categoria):
                return self.CATEGORIAS_NAO_SADT[prefixo_categoria]

        # Padrão para SADT não categorizado
        if codigo.startswith('4'):
            return 'SADT - Outros'

        # Padrão geral
        return 'Outros'

    def gerar_aliases(self, nome: str) -> List[str]:
        """
        Gera aliases para um procedimento baseado em padrões.

        Args:
            nome: Nome do procedimento

        Returns:
            Lista de aliases gerados
        """
        aliases = set()

        # Adicionar versão em maiúsculas como alias
        nome_upper = nome.upper()
        aliases.add(nome_upper)

        # Padrão: US - ... → USG ..., ULTRASSONOGRAFIA ...
        if nome.startswith('US - '):
            sufixo = nome[5:].strip()  # Remove "US - "
            aliases.add(f"USG {sufixo.upper()}")
            aliases.add(f"ULTRASSONOGRAFIA {sufixo.upper()}")

        # Padrão: Ecodopplercardiograma
        if 'ecodoppler' in nome.lower():
            aliases.add('ECOCARDIOGRAMA')
            aliases.add('ECO')
            aliases.add('ECO DOPPLER')

        # Padrão: ECG ...
        if nome.startswith('ECG '):
            aliases.add('ELETROCARDIOGRAMA')
            sufixo = nome[4:].strip()
            if sufixo:
                aliases.add(f"ELETROCARDIOGRAMA {sufixo.upper()}")

        # Padrão: RX - ... → RADIOGRAFIA ..., RAIO X ..., RAIO-X ...
        if nome.startswith('RX - '):
            sufixo = nome[5:].strip()  # Remove "RX - "
            aliases.add(f"RADIOGRAFIA {sufixo.upper()}")
            aliases.add(f"RAIO X {sufixo.upper()}")
            aliases.add(f"RAIO-X {sufixo.upper()}")

        # Padrão: RM - ... → RESSONÂNCIA MAGNÉTICA ..., RNM ...
        if nome.startswith('RM - '):
            sufixo = nome[5:].strip()  # Remove "RM - "
            aliases.add(f"RESSONANCIA MAGNETICA {sufixo.upper()}")
            aliases.add(f"RNM {sufixo.upper()}")

        # Padrão: TC - ... → TOMOGRAFIA COMPUTADORIZADA ...
        if nome.startswith('TC - '):
            sufixo = nome[5:].strip()  # Remove "TC - "
            aliases.add(f"TOMOGRAFIA COMPUTADORIZADA {sufixo.upper()}")

        # Remover conteúdo em parênteses para alias mais curto
        nome_sem_parenteses = re.sub(r'\s*\([^)]*\)', '', nome).strip()
        if nome_sem_parenteses and nome_sem_parenteses != nome:
            aliases.add(nome_sem_parenteses.upper())

        # Remover "pesquisa e/ou dosagem" para exames laboratoriais
        nome_sem_pesquisa = re.sub(
            r'(?:pesquisa\s+)?(?:e/ou\s+)?dosagem\s+',
            '',
            nome,
            flags=re.IGNORECASE
        ).strip()
        if nome_sem_pesquisa and nome_sem_pesquisa != nome:
            aliases.add(nome_sem_pesquisa.upper())

        # Remover "de " do início de nomes para alias mais curto
        if nome_sem_parenteses.startswith('de '):
            alias_curto = nome_sem_parenteses[3:].strip()
            if alias_curto:
                aliases.add(alias_curto.upper())

        # Remover o nome original se foi adicionado (mantém apenas variações)
        if nome_upper in aliases and len(aliases) > 1:
            # Manter original apenas se houver outras variações
            pass

        return sorted(list(aliases))

    def normalizar_aliases(self, aliases: List[str]) -> List[str]:
        """
        Remove duplicatas (case-insensitive) de aliases.

        Args:
            aliases: Lista de aliases

        Returns:
            Lista normalizada sem duplicatas
        """
        # Usar dicionário para manter primeira ocorrência, ignorando case
        visto = {}
        resultado = []

        for alias in aliases:
            chave = alias.upper()
            if chave not in visto:
                visto[chave] = True
                resultado.append(alias)

        return resultado

    def construir_dicionario(self) -> None:
        """Constrói o dicionário final com procedimentos, categorias e aliases."""
        self.log("Construindo dicionário...")

        for proc in self.procedimentos_filtrados:
            codigo = str(proc.get('codigo', ''))
            nome = proc.get('procedimento', '').strip()

            if not codigo or not nome:
                continue

            categoria = self.categorizar_procedimento(codigo)
            aliases = self.gerar_aliases(nome)
            aliases = self.normalizar_aliases(aliases)

            self.stats['aliases_gerados'] += len(aliases)

            entrada = {
                'codigo_tuss': codigo,
                'nome_padrao': nome,
                'categoria': categoria,
                'aliases': aliases,
            }

            self.dicionario_final.append(entrada)

        # Ordenar por código TUSS
        self.dicionario_final.sort(key=lambda x: x['codigo_tuss'])

        self.log(f"Dicionário construído com {len(self.dicionario_final)} procedimentos")

    def carregar_dicionario_curado(self, caminho: str) -> Dict[str, List[str]]:
        """
        Carrega dicionário curado com aliases para mesclagem.

        Args:
            caminho: Caminho para o arquivo JSON curado

        Returns:
            Dicionário mapeando código TUSS → lista de aliases
        """
        self.log(f"Carregando dicionário curado de: {caminho}")

        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                dados_curados = json.load(f)

            # Tentar extrair entradas do formato esperado
            if isinstance(dados_curados, dict) and 'exames' in dados_curados:
                dados_curados = dados_curados['exames']

            # Construir mapeamento codigo → aliases
            mapa_curado = {}

            if isinstance(dados_curados, list):
                for entrada in dados_curados:
                    if isinstance(entrada, dict):
                        codigo = entrada.get('codigo_tuss')
                        aliases = entrada.get('aliases', [])
                        if codigo and aliases:
                            mapa_curado[codigo] = aliases

            self.log(f"Carregado {len(mapa_curado)} procedimentos curados")
            return mapa_curado

        except FileNotFoundError:
            print(f"[AVISO] Arquivo curado não encontrado: {caminho}")
            return {}
        except json.JSONDecodeError as e:
            print(f"[AVISO] Erro ao decodificar arquivo curado: {e}")
            return {}
        except Exception as e:
            print(f"[AVISO] Erro ao carregar arquivo curado: {e}")
            return {}

    def mesclar_aliases_curados(self, mapa_curado: Dict[str, List[str]]) -> None:
        """
        Mescla aliases curados no dicionário final.

        Args:
            mapa_curado: Dicionário mapeando código TUSS → aliases curados
        """
        self.log("Mesclando aliases curados...")

        for entrada in self.dicionario_final:
            codigo = entrada['codigo_tuss']

            if codigo in mapa_curado:
                aliases_curados = mapa_curado[codigo]
                aliases_existentes = set(a.upper() for a in entrada['aliases'])

                # Adicionar aliases curados que não estão presentes
                for alias_curado in aliases_curados:
                    alias_curado_upper = alias_curado.upper()
                    if alias_curado_upper not in aliases_existentes:
                        entrada['aliases'].append(alias_curado)
                        aliases_existentes.add(alias_curado_upper)
                        self.stats['aliases_curados'] += 1

                # Ordenar aliases
                entrada['aliases'] = sorted(entrada['aliases'])
                self.stats['total_com_aliases_curados'] += 1

        self.log(f"Aliases curados mesclados: {self.stats['aliases_curados']}")

    def gerar_metadados(self) -> Dict:
        """
        Gera metadados para o dicionário.

        Returns:
            Dicionário com metadados
        """
        return {
            'source': 'ANS - Tabela TUSS 22 (Procedimentos e Eventos em Saúde)',
            'github_origin': 'https://github.com/charlesfgarcia/tabelas-ans',
            'ans_ftp': 'http://ftp.dadosabertos.ans.gov.br/FTP/PDA/terminologia_unificada_saude_suplementar_TUSS/TUSS.zip',
            'total_procedimentos_tabela22': self.stats['total_tabela22'],
            'total_sadt': self.stats['total_sadt'],
            'total_procedimentos_clinicos': self.stats['total_nao_sadt'],
            'total_no_dicionario': len(self.dicionario_final),
            'total_com_aliases_curados': self.stats['total_com_aliases_curados'],
            'total_aliases_gerados': self.stats['aliases_gerados'],
            'total_aliases_curados': self.stats['aliases_curados'],
            'generated_at': datetime.utcnow().isoformat() + 'Z',
        }

    def salvar_dicionario(self, caminho_saida: str) -> bool:
        """
        Salva o dicionário final em formato JSON.

        Args:
            caminho_saida: Caminho para salvar o arquivo

        Returns:
            True se conseguiu salvar, False caso contrário
        """
        self.log(f"Salvando dicionário em: {caminho_saida}")

        try:
            # Garantir que o diretório existe
            Path(caminho_saida).parent.mkdir(parents=True, exist_ok=True)

            dicionario_completo = {
                '_meta': self.gerar_metadados(),
                'exames': self.dicionario_final,
            }

            with open(caminho_saida, 'w', encoding='utf-8') as f:
                json.dump(dicionario_completo, f, ensure_ascii=False, indent=2)

            self.log(f"Dicionário salvo com sucesso")
            return True

        except Exception as e:
            print(f"[ERRO] Falha ao salvar dicionário: {e}")
            return False

    def exibir_stats(self) -> None:
        """Exibe estatísticas da construção do dicionário."""
        print("\n" + "="*60)
        print("ESTATÍSTICAS DE CONSTRUÇÃO DO DICIONÁRIO TUSS")
        print("="*60)
        print(f"Total de procedimentos na Tabela 22: {self.stats['total_tabela22']}")
        print(f"Total de SADT (códigos 40xx): {self.stats['total_sadt']}")
        print(f"Total de procedimentos clínicos/exames: {self.stats['total_nao_sadt']}")
        print(f"Total de procedimentos no dicionário: {len(self.dicionario_final)}")
        print(f"Total de aliases gerados: {self.stats['aliases_gerados']}")
        print(f"Total de aliases curados mesclados: {self.stats['aliases_curados']}")
        print(f"Total de procedimentos com aliases curados: {self.stats['total_com_aliases_curados']}")
        print("="*60 + "\n")

    def processar(self, caminho_saida: str, caminho_curado: Optional[str] = None) -> bool:
        """
        Executa todo o processo de construção do dicionário.

        Args:
            caminho_saida: Caminho para salvar o dicionário final
            caminho_curado: Caminho para dicionário curado (opcional)

        Returns:
            True se sucesso, False caso contrário
        """
        # Buscar Tabela 22
        if not self.fetch_tuss_table22():
            return False

        # Filtrar procedimentos
        self.filtrar_procedimentos()

        # Construir dicionário
        self.construir_dicionario()

        # Mesclar aliases curados se fornecido
        if caminho_curado:
            mapa_curado = self.carregar_dicionario_curado(caminho_curado)
            self.mesclar_aliases_curados(mapa_curado)

        # Salvar dicionário
        if not self.salvar_dicionario(caminho_saida):
            return False

        return True


def main():
    """Função principal do script."""
    parser = argparse.ArgumentParser(
        description='Construtor de dicionário TUSS com categorização de exames e procedimentos.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python build_tuss_dict.py
  python build_tuss_dict.py -o meu_dicionario.json
  python build_tuss_dict.py -m tuss_exames_comuns.json -v
  python build_tuss_dict.py -o resultado.json --stats
        """
    )

    parser.add_argument(
        '-o', '--output',
        default='tuss_tabela22_oficial.json',
        help='Caminho para arquivo de saída (padrão: tuss_tabela22_oficial.json no diretório atual)'
    )

    parser.add_argument(
        '-m', '--merge',
        help='Caminho para dicionário curado para mesclar aliases'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Exibir mensagens de progresso'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Exibir estatísticas após construção'
    )

    args = parser.parse_args()

    # Criar construtor
    builder = TussDictBuilder(verbose=args.verbose)

    # Processar
    sucesso = builder.processar(args.output, args.merge)

    if sucesso:
        print(f"✓ Dicionário construído com sucesso em: {args.output}")

        if args.stats:
            builder.exibir_stats()

        sys.exit(0)
    else:
        print("✗ Falha ao construir dicionário")
        sys.exit(1)


if __name__ == '__main__':
    main()
