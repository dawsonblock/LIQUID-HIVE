"""
Tool auditor for HiveMind
=========================

This module defines a ``ToolAuditor`` class that periodically analyses run
logs to assess the effectiveness of tools used by the agents.  Each
execution of a tool can be logged with a success flag and latency via the
``skill_tracker`` in ``hivemind/memory``.  The auditor aggregates these
records and computes a simple success ratio per tool.  Tools falling
below a configurable threshold are flagged for review.

In a production system the auditor would run in a background task and
trigger a self‑extension workflow when poor performance is detected.
Here we provide a synchronous implementation that can be invoked
manually.
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Dict, List, Tuple


class ToolAuditor:
    """Analyse tool execution logs and flag underperforming tools."""

    def __init__(self, runs_dir: str = "./runs", threshold: float = 0.5) -> None:
        self.runs_dir = Path(runs_dir)
        self.threshold = threshold

    def _iter_logs(self) -> List[Path]:
        """Yield all JSON run logs in the runs directory."""
        if not self.runs_dir.exists():
            return []
        return list(self.runs_dir.glob("*.json"))

    def analyse(self) -> Dict[str, Dict[str, float]]:
        """Aggregate tool execution statistics from run logs.

        Returns a mapping from tool name to a dict with keys ``success_rate``
        and ``count``.  Tools with a success rate below the threshold may
        require refactoring.
        """
        stats: Dict[str, Dict[str, float]] = {}
        logs = self._iter_logs()
        for log_file in logs:
            try:
                with log_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            # Expect each record to contain a list of tool executions under
            # ``tool_execution_log`` with fields ``tool``, ``success``.
            if not isinstance(data, list):
                continue
            for record in data:
                executions: List[Dict[str, any]] = record.get("tool_execution_log", [])
                for entry in executions:
                    tool_name = entry.get("tool")
                    success = bool(entry.get("success"))
                    if tool_name is None:
                        continue
                    tool_stats = stats.setdefault(tool_name, {"successes": 0.0, "count": 0.0})
                    tool_stats["count"] += 1
                    if success:
                        tool_stats["successes"] += 1
        # Compute success_rate for each tool
        for tool, res in stats.items():
            count = res.get("count", 0.0)
            successes = res.get("successes", 0.0)
            res["success_rate"] = successes / count if count else 0.0
        return stats

    def flag_underperforming(self) -> List[str]:
        """Return a list of tool names whose success_rate is below the threshold."""
        stats = self.analyse()
        return [tool for tool, res in stats.items() if res.get("success_rate", 1.0) < self.threshold]
