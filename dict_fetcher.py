# -*- coding: utf-8 -*-
"""
Remote TUSS Medical Exam Dictionary Fetcher

This module provides smart HTTP caching with ETag support, local fallback,
and TTL-based refresh for fetching a TUSS medical exam dictionary from GitHub.

No external dependencies required (stdlib only).
"""

import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Optional, Any


class RemoteDictionaryFetcher:
    """
    Fetches and caches a TUSS medical exam dictionary from a remote GitHub URL.

    Features:
    - Smart HTTP caching using ETags
    - Local fallback for offline scenarios
    - TTL-based cache refresh
    - Verbose logging support
    """

    DEFAULT_REMOTE_URL = "https://raw.githubusercontent.com/svgreve/sutram-tuss-dictionary/main/tuss_exames_comuns.json"
    DEFAULT_CACHE_DIR = None  # Will be set to ~/.cache/tuss-dict/
    DEFAULT_TTL_SECONDS = 86400  # 24 hours
    CACHE_FILENAME = "tuss_dict_cache.json"
    ETAG_FILENAME = "tuss_dict_etag.txt"
    USER_AGENT = "tuss-dict-fetcher/1.0"
    TIMEOUT_SECONDS = 15

    def __init__(
        self,
        remote_url: str = DEFAULT_REMOTE_URL,
        cache_dir: Optional[str] = None,
        fallback_path: Optional[str] = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        verbose: bool = False,
    ):
        """
        Initialize the RemoteDictionaryFetcher.

        Args:
            remote_url: GitHub URL to fetch the dictionary from
            cache_dir: Directory for caching (defaults to ~/.cache/tuss-dict/)
            fallback_path: Path to bundled fallback JSON (defaults to same dir as this script)
            ttl_seconds: Cache TTL in seconds (default: 86400 = 24 hours)
            verbose: Enable verbose logging
        """
        self.remote_url = remote_url
        self.ttl_seconds = ttl_seconds
        self.verbose = verbose
        self._cached_data = None
        self._source = None

        # Set cache directory
        if cache_dir is None:
            self.cache_dir = Path.home() / ".cache" / "tuss-dict"
        else:
            self.cache_dir = Path(cache_dir)

        # Set fallback path
        if fallback_path is None:
            self.fallback_path = Path(__file__).parent / "tuss_exames_comuns.json"
        else:
            self.fallback_path = Path(fallback_path)

        self.cache_file = self.cache_dir / self.CACHE_FILENAME
        self.etag_file = self.cache_dir / self.ETAG_FILENAME

    def _log(self, msg: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[dict_fetcher] {msg}")

    def _ensure_cache_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _is_cache_valid(self) -> bool:
        """Check if cache exists and is not stale."""
        if not self.cache_file.exists():
            self._log("Cache file does not exist")
            return False

        cache_age = time.time() - self.cache_file.stat().st_mtime
        cache_age_hours = cache_age / 3600

        if cache_age > self.ttl_seconds:
            self._log(f"Cache is stale (age: {cache_age_hours:.2f}h, TTL: {self.ttl_seconds / 3600:.2f}h)")
            return False

        self._log(f"Cache is valid (age: {cache_age_hours:.2f}h)")
        return True

    def _read_cache(self) -> Optional[Dict[str, Any]]:
        """Read cached dictionary from file."""
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._log("Cache loaded successfully")
            return data
        except Exception as e:
            self._log(f"Failed to read cache: {e}")
            return None

    def _write_cache(self, data: Dict[str, Any]) -> None:
        """Write dictionary to cache file."""
        try:
            self._ensure_cache_dir()
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._log("Cache written successfully")
        except Exception as e:
            self._log(f"Failed to write cache: {e}")

    def _read_etag(self) -> Optional[str]:
        """Read stored ETag from file."""
        try:
            if self.etag_file.exists():
                with open(self.etag_file, 'r', encoding='utf-8') as f:
                    etag = f.read().strip()
                return etag if etag else None
        except Exception as e:
            self._log(f"Failed to read ETag: {e}")
        return None

    def _write_etag(self, etag: str) -> None:
        """Write ETag to file."""
        try:
            self._ensure_cache_dir()
            with open(self.etag_file, 'w', encoding='utf-8') as f:
                f.write(etag)
            self._log(f"ETag stored: {etag}")
        except Exception as e:
            self._log(f"Failed to write ETag: {e}")

    def _fetch_remote(self) -> Optional[Dict[str, Any]]:
        """Fetch dictionary from remote URL with ETag support."""
        try:
            self._log(f"Fetching from remote: {self.remote_url}")

            # Create request with User-Agent
            req = urllib.request.Request(
                self.remote_url,
                headers={'User-Agent': self.USER_AGENT}
            )

            # Add If-None-Match header if we have a cached ETag
            etag = self._read_etag()
            if etag:
                req.add_header('If-None-Match', etag)
                self._log(f"Using If-None-Match header with ETag: {etag}")

            try:
                with urllib.request.urlopen(req, timeout=self.TIMEOUT_SECONDS) as response:
                    if response.status == 304:
                        self._log("Remote returned 304 Not Modified")
                        # Update cache timestamp by touching the file
                        self.cache_file.touch()
                        return None  # Signal to use cache

                    # 200 OK - read response
                    response_data = response.read().decode('utf-8')
                    data = json.loads(response_data)

                    # Store new ETag if present
                    new_etag = response.headers.get('ETag')
                    if new_etag:
                        self._write_etag(new_etag)

                    self._log("Successfully fetched and parsed remote data")
                    return data

            except urllib.error.HTTPError as e:
                if e.code == 304:
                    self._log("Remote returned 304 Not Modified")
                    self.cache_file.touch()
                    return None  # Signal to use cache
                else:
                    self._log(f"HTTP error {e.code}: {e.reason}")
                    return None

        except (urllib.error.URLError, urllib.error.HTTPError, Exception) as e:
            self._log(f"Network error during remote fetch: {e}")
            return None

    def _read_fallback(self) -> Optional[Dict[str, Any]]:
        """Read dictionary from fallback bundled file."""
        try:
            if self.fallback_path.exists():
                self._log(f"Loading fallback from: {self.fallback_path}")
                with open(self.fallback_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._log("Fallback loaded successfully")
                return data
        except Exception as e:
            self._log(f"Failed to read fallback: {e}")
        return None

    def fetch(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Fetch the TUSS dictionary with intelligent caching.

        Strategy:
        1. Return cached data if valid and not forced to refresh
        2. Attempt HTTP fetch with ETag
        3. Fall back to local bundled file if network fails
        4. Raise RuntimeError if all sources fail

        Args:
            force_refresh: Force refresh from remote, ignoring cache TTL

        Returns:
            Dictionary with '_meta' and 'exames' keys

        Raises:
            RuntimeError: If all data sources fail
        """
        self._log(f"Fetch called (force_refresh={force_refresh})")

        # Check cache first
        if not force_refresh and self._is_cache_valid():
            data = self._read_cache()
            if data is not None:
                self._cached_data = data
                self._source = "cache"
                return data

        # Try remote fetch
        remote_data = self._fetch_remote()
        if remote_data is not None:
            self._write_cache(remote_data)
            self._cached_data = remote_data
            self._source = "remote"
            return remote_data

        # If remote returned 304, use cached data
        if self._is_cache_valid():
            data = self._read_cache()
            if data is not None:
                self._cached_data = data
                self._source = "cache"
                return data

        # Try fallback
        fallback_data = self._read_fallback()
        if fallback_data is not None:
            self._cached_data = fallback_data
            self._source = "fallback"
            return fallback_data

        # All sources failed
        raise RuntimeError(
            "Failed to fetch TUSS dictionary: no remote access, "
            "no valid cache, and no fallback file available"
        )

    def get_status(self) -> Dict[str, Any]:
        """
        Get status information about the current dictionary state.

        Returns:
            Dictionary with source, version, cache age, exam count, and URL
        """
        if self._cached_data is None:
            raise RuntimeError("No dictionary loaded. Call fetch() first.")

        cache_age_hours = 0.0
        if self.cache_file.exists():
            cache_age_seconds = time.time() - self.cache_file.stat().st_mtime
            cache_age_hours = cache_age_seconds / 3600

        meta = self._cached_data.get('_meta', {})
        version = meta.get('version', 'unknown')
        exames = self._cached_data.get('exames', {})
        total_exames = len(exames)

        return {
            'source': self._source or 'unknown',
            'version': version,
            'cache_age_hours': round(cache_age_hours, 2),
            'total_exames': total_exames,
            'remote_url': self.remote_url,
        }

    def invalidate_cache(self) -> None:
        """Delete the cached file and ETag."""
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
                self._log("Cache file deleted")
            if self.etag_file.exists():
                self.etag_file.unlink()
                self._log("ETag file deleted")
            self._cached_data = None
            self._source = None
        except Exception as e:
            self._log(f"Failed to invalidate cache: {e}")


if __name__ == '__main__':
    # Example usage
    fetcher = RemoteDictionaryFetcher(verbose=True)

    print("\n=== Fetching Dictionary ===")
    try:
        data = fetcher.fetch()
        print("✓ Dictionary loaded successfully\n")
    except RuntimeError as e:
        print(f"✗ Failed to load dictionary: {e}\n")
        exit(1)

    print("=== Status ===")
    status = fetcher.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")

    print("\n=== First 5 Exam Names ===")
    exames = data.get('exames', {})
    exam_names = list(exames.keys())[:5]
    for i, exam_name in enumerate(exam_names, 1):
        print(f"  {i}. {exam_name}")

    print("\n✓ Done")
