#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module for submitting new TUSS exam name mappings to a central GitHub repository.
Provides ContributionSubmitter class for queuing and submitting contributions via GitHub API.
"""

import urllib.request
import urllib.error
import json
import base64
import datetime
import os
from typing import Optional, Dict, List, Any


class ContributionSubmitter:
    """
    Submitter for TUSS exam name mappings discovered via LLM fallback.
    Manages queuing and submission of contributions to a GitHub repository.
    """

    def __init__(
        self,
        github_token: Optional[str] = None,
        repo: str = "svgreve/sutram-tuss-dictionary",
        contrib_file: str = "contrib/pending.json",
        branch_prefix: str = "contrib/auto",
        verbose: bool = False,
    ):
        """
        Initialize the ContributionSubmitter.

        Args:
            github_token: GitHub API token. If None, reads from TUSS_GITHUB_TOKEN env var.
            repo: Target GitHub repository (owner/repo format).
            contrib_file: Path to contributions file in the repository.
            branch_prefix: Prefix for auto-generated branch names.
            verbose: Enable verbose logging.
        """
        self.github_token = github_token or os.environ.get("TUSS_GITHUB_TOKEN")
        self.repo = repo
        self.contrib_file = contrib_file
        self.branch_prefix = branch_prefix
        self.verbose = verbose
        self._queue: List[Dict[str, Any]] = []

    def _log(self, msg: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[contrib] {msg}")

    def queue(
        self,
        original_name: str,
        mapped_name: str,
        codigo_tuss: str = "",
        confidence: str = "llm",
        score: float = 0.0,
        portal: str = "unknown",
    ) -> None:
        """
        Queue a new TUSS exam name mapping.

        Args:
            original_name: Original exam name from source.
            mapped_name: Standardized exam name.
            codigo_tuss: TUSS code (optional).
            confidence: Confidence level/method (default: "llm").
            score: Confidence score (0.0-1.0).
            portal: Source portal name.
        """
        entry = {
            "original_name": original_name,
            "mapped_name": mapped_name,
            "codigo_tuss": codigo_tuss,
            "confidence": confidence,
            "score": score,
            "portal": portal,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        }
        self._queue.append(entry)
        self._log(f"Queued: {original_name} → {mapped_name}")

    def get_queue(self) -> List[Dict[str, Any]]:
        """Return a copy of the current queue."""
        return list(self._queue)

    def save_local(self, path: Optional[str] = None) -> str:
        """
        Save queued contributions to a local JSON file as backup.

        Args:
            path: File path to save to. Defaults to ./contrib_pending_local.json

        Returns:
            The path where the file was saved.
        """
        if path is None:
            path = "./contrib_pending_local.json"

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._queue, f, indent=2, ensure_ascii=False)

        self._log(f"Saved {len(self._queue)} entries to {path}")
        return path

    def flush(self) -> Dict[str, Any]:
        """
        Submit all queued contributions to GitHub.

        Returns:
            Dictionary with keys: status, submitted, message, pr_url (optional).
            Status values: "success", "skipped", or "error".
        """
        # Check if queue is empty
        if not self._queue:
            result = {
                "status": "skipped",
                "submitted": 0,
                "message": "Nenhuma contribuição na fila",
                "pr_url": None,
            }
            self._log(result["message"])
            return result

        # Check if token is configured
        if not self.github_token:
            result = {
                "status": "skipped",
                "submitted": 0,
                "message": "Token GitHub não configurado. Contribuições salvas localmente.",
                "pr_url": None,
            }
            self._log(result["message"])
            return result

        try:
            self._log(f"Starting flush of {len(self._queue)} contributions")

            # Step 1: Get main branch SHA
            main_sha = self._get_main_sha()
            self._log(f"Main branch SHA: {main_sha[:7]}")

            # Step 2: Create new branch
            timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
            branch_name = f"{self.branch_prefix}-{timestamp}"
            self._create_branch(branch_name, main_sha)
            self._log(f"Created branch: {branch_name}")

            # Step 3: Get current contributions file (if exists)
            existing_content = self._get_file_content()
            if existing_content:
                all_contributions = json.loads(existing_content)
                self._log(f"Found {len(all_contributions)} existing contributions")
            else:
                all_contributions = []
                self._log("No existing contributions file found")

            # Step 4: Append new contributions
            all_contributions.extend(self._queue)

            # Step 5: Commit updated file to new branch
            self._commit_file(branch_name, all_contributions)
            self._log(f"Committed {len(self._queue)} new contributions")

            # Step 6: Create PR
            pr_url = self._create_pr(branch_name, len(self._queue), all_contributions)
            self._log(f"Created PR: {pr_url}")

            # Step 7: Clear the queue
            submitted_count = len(self._queue)
            self._queue.clear()

            result = {
                "status": "success",
                "submitted": submitted_count,
                "message": f"Enviadas {submitted_count} contribuições com sucesso",
                "pr_url": pr_url,
            }
            return result

        except Exception as e:
            error_msg = str(e)
            result = {
                "status": "error",
                "submitted": 0,
                "message": error_msg,
                "pr_url": None,
            }
            self._log(f"Error during flush: {error_msg}")
            return result

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to the GitHub API.

        Args:
            method: HTTP method (GET, POST, PUT, etc.).
            endpoint: API endpoint (without base URL).
            data: Request body data (will be JSON-encoded).

        Returns:
            Parsed JSON response.

        Raises:
            Exception: On HTTP or parsing errors.
        """
        url = f"https://api.github.com{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "tuss-contrib/1.0",
        }

        body = None
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(request) as response:
                response_body = response.read().decode("utf-8")
                return json.loads(response_body) if response_body else {}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            try:
                error_data = json.loads(error_body)
                raise Exception(
                    f"GitHub API error ({e.code}): {error_data.get('message', error_body)}"
                )
            except json.JSONDecodeError:
                raise Exception(f"GitHub API error ({e.code}): {error_body}")
        except urllib.error.URLError as e:
            raise Exception(f"Network error: {e.reason}")

    def _get_main_sha(self) -> str:
        """Get the SHA of the main branch."""
        endpoint = f"/repos/{self.repo}/git/ref/heads/main"
        response = self._make_request("GET", endpoint)
        return response["object"]["sha"]

    def _create_branch(self, branch_name: str, sha: str) -> None:
        """Create a new branch from the given SHA."""
        endpoint = f"/repos/{self.repo}/git/refs"
        data = {"ref": f"refs/heads/{branch_name}", "sha": sha}
        self._make_request("POST", endpoint, data)

    def _get_file_content(self) -> Optional[str]:
        """
        Get the current content of the contributions file.

        Returns:
            Decoded file content, or None if file doesn't exist.
        """
        endpoint = f"/repos/{self.repo}/contents/{self.contrib_file}?ref=main"
        try:
            response = self._make_request("GET", endpoint)
            # GitHub API returns base64-encoded content
            encoded_content = response.get("content", "")
            if encoded_content:
                return base64.b64decode(encoded_content).decode("utf-8")
            return None
        except Exception as e:
            if "404" in str(e):
                return None
            raise

    def _commit_file(
        self, branch_name: str, content: List[Dict[str, Any]]
    ) -> None:
        """
        Commit the updated contributions file to the given branch.

        Args:
            branch_name: Target branch name.
            content: Updated contributions list.
        """
        file_content = json.dumps(content, indent=2, ensure_ascii=False)
        encoded_content = base64.b64encode(file_content.encode("utf-8")).decode(
            "ascii"
        )

        endpoint = f"/repos/{self.repo}/contents/{self.contrib_file}"
        data = {
            "message": f"Add {len(self._queue)} new TUSS contributions",
            "content": encoded_content,
            "branch": branch_name,
        }
        self._make_request("PUT", endpoint, data)

    def _create_pr(
        self, branch_name: str, count: int, all_contributions: List[Dict[str, Any]]
    ) -> str:
        """
        Create a pull request for the new contributions.

        Args:
            branch_name: Source branch name.
            count: Number of new contributions.
            all_contributions: All contributions (for building the table).

        Returns:
            URL of the created PR.
        """
        # Build the contributions table
        rows = []
        for contrib in self._queue:
            rows.append(
                f"| {contrib['original_name']} | {contrib['mapped_name']} | "
                f"{contrib['codigo_tuss']} | {contrib['confidence']} | {contrib['portal']} |"
            )

        body = f"""## Novas contribuições TUSS

{count} novos mapeamentos descobertos automaticamente pelo skill de migração de exames.

### Mapeamentos

| Nome Original | Nome Padronizado | Código TUSS | Confiança | Portal |
|:---|:---|:---:|:---:|:---:|
{chr(10).join(rows)}

---
Submetido automaticamente por `medical-exam-migration-skill`
"""

        endpoint = f"/repos/{self.repo}/pulls"
        data = {
            "title": f"Novas contribuições TUSS ({count} mapeamentos)",
            "body": body,
            "head": branch_name,
            "base": "main",
        }
        response = self._make_request("POST", endpoint, data)
        return response["html_url"]


if __name__ == "__main__":
    # Create a submitter with verbose output
    submitter = ContributionSubmitter(verbose=True)

    # Queue 2 sample contributions
    submitter.queue(
        original_name="Ressonância Magnética de Crânio",
        mapped_name="Ressonância magnética de crânio",
        codigo_tuss="40301018",
        confidence="llm",
        score=0.95,
        portal="HAOC",
    )

    submitter.queue(
        original_name="Ultrassom Abdominal Total",
        mapped_name="Ultrassom de abdômen total",
        codigo_tuss="40201019",
        confidence="llm",
        score=0.92,
        portal="HAOC",
    )

    # Print the queue
    print("\n--- Current Queue ---")
    queue = submitter.get_queue()
    print(json.dumps(queue, indent=2, ensure_ascii=False))

    # Save locally (does not flush to GitHub)
    print("\n--- Saving Locally ---")
    saved_path = submitter.save_local()
    print(f"Saved to: {saved_path}")
