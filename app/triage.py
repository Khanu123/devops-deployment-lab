from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SEVERITY_WEIGHT = {"critical": 100, "high": 75, "medium": 45, "low": 20}
DEFAULT_CONFIG = {
    "severity_weight": SEVERITY_WEIGHT,
    "volume_points_per_alert": 8,
    "max_volume_score": 40,
    "tactic_diversity_points": 5,
    "sla": {
        "critical": "Immediate escalation",
        "high": "Investigate within 4 hours",
        "medium": "Investigate within 1 business day",
        "low": "Monitor during normal queue review",
    },
}
TACTIC_TO_MITRE = {
    "Credential Access": "T1110 - Brute Force",
    "Initial Access": "T1078 - Valid Accounts",
    "Execution": "T1059 - Command and Scripting Interpreter",
    "Reconnaissance": "T1595 - Active Scanning",
    "Defense Evasion": "T1027 - Obfuscated Files or Information",
    "Discovery": "T1087 - Account Discovery",
    "Command and Control": "T1071 - Application Layer Protocol",
    "Exfiltration": "T1041 - Exfiltration Over C2 Channel",
}


@dataclass(frozen=True)
class Alert:
    timestamp: datetime
    title: str
    severity: str
    source_ip: str
    host: str
    user: str
    tactic: str
    status: str = "open"
    source: str = "siem"
    confidence: str = "medium"
    false_positive_hint: str = ""
    analyst_note: str = ""
    iocs: tuple[str, ...] = ()


@dataclass(frozen=True)
class TriageConfig:
    severity_weight: dict[str, int]
    volume_points_per_alert: int
    max_volume_score: int
    tactic_diversity_points: int
    sla: dict[str, str]


def load_config(path: str | Path | None = None) -> TriageConfig:
    raw = DEFAULT_CONFIG | {}
    if path:
        override = json.loads(Path(path).read_text(encoding="utf-8"))
        raw.update(override)
    return TriageConfig(
        severity_weight={key.lower(): int(value) for key, value in raw["severity_weight"].items()},
        volume_points_per_alert=int(raw["volume_points_per_alert"]),
        max_volume_score=int(raw["max_volume_score"]),
        tactic_diversity_points=int(raw["tactic_diversity_points"]),
        sla={key.lower(): value for key, value in raw["sla"].items()},
    )


def load_alerts(path: str | Path) -> list[Alert]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("Alert input must be a non-empty JSON array.")
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or str(row.get("severity", "")).lower() not in SEVERITY_WEIGHT:
            raise ValueError(f"Alert {index} has an unsupported severity.")
        if not all(isinstance(row.get(key), str) for key in ("timestamp", "title", "severity")):
            raise ValueError(f"Alert {index} is missing required text fields.")
    return [
        Alert(
            timestamp=datetime.fromisoformat(row["timestamp"]),
            title=row["title"],
            severity=row["severity"].lower(),
            source_ip=row.get("source_ip", ""),
            host=row.get("host", ""),
            user=row.get("user", ""),
            tactic=row.get("tactic", "unknown"),
            status=row.get("status", "open"),
            source=row.get("source", "siem"),
            confidence=row.get("confidence", "medium"),
            false_positive_hint=row.get("false_positive_hint", ""),
            analyst_note=row.get("analyst_note", ""),
            iocs=tuple(row.get("iocs", [])),
        )
        for row in rows
    ]


def triage(alerts: list[Alert], config: TriageConfig | None = None) -> list[dict[str, object]]:
    config = config or load_config()
    grouped: dict[tuple[str, str], list[Alert]] = defaultdict(list)
    for alert in alerts:
        grouped[(alert.source_ip, alert.host)].append(alert)

    cases = []
    for (source_ip, host), items in grouped.items():
        severity_score = max(config.severity_weight.get(item.severity, 0) for item in items)
        volume_score = min(len(items) * config.volume_points_per_alert, config.max_volume_score)
        tactics = sorted({item.tactic for item in items})
        priority = min(severity_score + volume_score + len(tactics) * config.tactic_diversity_points, 100)
        top_alert = max(items, key=lambda item: config.severity_weight.get(item.severity, 0))
        open_items = [item for item in items if item.status == "open"]
        closed_items = [item for item in items if item.status != "open"]
        iocs = sorted({ioc for item in items for ioc in item.iocs})
        cases.append(
            {
                "source_ip": source_ip,
                "host": host,
                "alert_count": len(items),
                "open_alert_count": len(open_items),
                "closed_alert_count": len(closed_items),
                "top_severity": top_alert.severity,
                "tactics": ", ".join(tactics),
                "mitre": ", ".join(TACTIC_TO_MITRE.get(tactic, "Unmapped") for tactic in tactics),
                "priority": priority,
                "sla": config.sla.get(top_alert.severity, "Review using team SLA"),
                "evidence": [item.title for item in items],
                "iocs": iocs,
                "analyst_notes": analyst_notes(items),
                "false_positive_handling": false_positive_handling(items),
                "recommended_action": recommendation(priority),
            }
        )
    return sorted(cases, key=lambda item: item["priority"], reverse=True)


def recommendation(priority: int) -> str:
    if priority >= 90:
        return "Escalate immediately, isolate host, preserve evidence, and review account activity."
    if priority >= 70:
        return "Investigate within SLA, enrich source IP, and validate endpoint telemetry."
    if priority >= 45:
        return "Queue for analyst review and correlate with recent authentication events."
    return "Monitor and close if no additional suspicious activity appears."


def analyst_notes(alerts: list[Alert]) -> str:
    notes = [item.analyst_note for item in alerts if item.analyst_note]
    if notes:
        return " ".join(notes)
    users = sorted({item.user for item in alerts if item.user and item.user != "-"})
    if users:
        return f"Review authentication and endpoint activity for: {', '.join(users)}."
    return "Validate the alert context against endpoint, identity, and network telemetry."


def false_positive_handling(alerts: list[Alert]) -> str:
    hints = sorted({item.false_positive_hint for item in alerts if item.false_positive_hint})
    if hints:
        return "Check before escalation: " + " ".join(hints)
    if all(item.status != "open" for item in alerts):
        return "All related alerts are closed; verify closure reason before reopening."
    return "Compare with known maintenance windows, approved scanners, and expected admin activity."


def case_summary(case: dict[str, Any]) -> str:
    return (
        f"Priority {case['priority']} case on {case['host']} from {case['source_ip']} "
        f"with {case['alert_count']} alert(s), mapped to {case['mitre']}."
    )
