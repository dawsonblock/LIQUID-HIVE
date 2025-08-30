from __future__ import annotations

import argparse
import os
import re
import json
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Iterable

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(?:\+?\d[\s\-]?)?(?:\(\d{3}\)|\d{3})[\s\-]?\d{3}[\s\-]?\d{4}")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
ADDRESS_RE = re.compile(r"\d+\s+[\w\s]+\b(?:Street|St\.|Avenue|Ave\.|Road|Rd\.|Boulevard|Blvd\.|Lane|Ln\.|Drive|Dr\.)\b", re.IGNORECASE)
PHI_KEYWORDS = [
    "diagnosis", "patient", "prescription", "medical record", "MRN", "HIPAA"
]

PII_TYPES = [
    ("EMAIL", EMAIL_RE),
    ("PHONE", PHONE_RE),
    ("SSN", SSN_RE),
    ("ADDRESS", ADDRESS_RE),
]


@dataclass
class PlatinumRecord:
    id: str
    timestamp: str
    sha256_source: str
    source_uri: str
    license: str
    pii_redacted: bool
    pii_types: List[str]
    prompt: str
    response: str
    oracle_trace: Dict[str, Any]
    policy_tags: List[str]


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _mask_value(kind: str) -> str:
    return f"<REDACTED:{kind}>"


def pii_redact(text: str) -> (str, bool, List[str]):
    found: List[str] = []
    redacted = text
    for name, rx in PII_TYPES:
        if rx.search(redacted):
            found.append(name)
            redacted = rx.sub(_mask_value(name), redacted)
    # PHI keyword heuristic
    phi_hits = [kw for kw in PHI_KEYWORDS if re.search(rf"\b{re.escape(kw)}\b", redacted, re.IGNORECASE)]
    found.extend([f"PHI:{kw}" for kw in phi_hits])
    return redacted, len(found) > 0, found


def _load_jsonl(paths: List[str]) -> Iterable[Dict[str, Any]]:
    for p in paths:
        try:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except Exception:
                        continue
        except FileNotFoundError:
            continue


def build_platinum(inputs: List[str], out_path: str) -> Dict[str, Any]:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    written = 0
    licenses: Dict[str, int] = {}
    redaction_hits = 0

    with open(out_path, "w", encoding="utf-8") as out:
        for rec in _load_jsonl(inputs):
            # Required fields and license check
            source_uri = rec.get("source_uri") or rec.get("uri") or rec.get("source") or "unknown"
            license_str = rec.get("license") or rec.get("license_type") or ""
            prompt = (rec.get("prompt") or rec.get("question") or rec.get("input") or "").strip()
            response = (rec.get("response") or rec.get("answer") or rec.get("output") or "").strip()
            oracle = rec.get("oracle_trace") or {}
            if not license_str or not prompt or not response:
                # refuse missing license or content
                continue

            # Hashing and provenance
            src_hash = _sha256_bytes((source_uri + "|" + prompt).encode("utf-8"))

            # PII redaction
            pr_red, has_pii, pii_types = pii_redact(prompt)
            rr_red, has_pii_r, pii_types_r = pii_redact(response)
            pii_any = has_pii or has_pii_r
            pii_all_types = list(sorted(set(pii_types + pii_types_r)))

            # Policy tags
            tags = ["safety.ok", "license.ok"]
            if pii_any:
                redaction_hits += 1

            record = PlatinumRecord(
                id=_sha256_bytes((pr_red + "|" + rr_red).encode("utf-8"))[:16],
                timestamp=datetime.now(timezone.utc).isoformat(),
                sha256_source=src_hash,
                source_uri=source_uri,
                license=license_str,
                pii_redacted=pii_any,
                pii_types=pii_all_types,
                prompt=pr_red,
                response=rr_red,
                oracle_trace=oracle,
                policy_tags=tags,
            )
            out.write(json.dumps(asdict(record)) + "\n")
            written += 1
            licenses[license_str] = licenses.get(license_str, 0) + 1

    # provenance report
    report = {
        "count": written,
        "redaction_rate": (redaction_hits / written) if written else 0.0,
        "license_top": sorted(licenses.items(), key=lambda x: x[1], reverse=True)[:10],
    }
    rep_path = os.path.join(os.path.dirname(out_path), "provenance_report.md")
    with open(rep_path, "w", encoding="utf-8") as f:
        f.write("# Provenance Report\n\n")
        f.write(f"Total: {written}\n\n")
        f.write(f"Redaction rate: {report['redaction_rate']:.2%}\n\n")
        f.write("Top licenses:\n\n")
        for k, v in report["license_top"]:
            f.write(f"- {k}: {v}\n")
    return report


def main_cli():
    parser = argparse.ArgumentParser(description="Build platinum dataset from logs and ingests")
    parser.add_argument("--inputs", nargs="+", required=True, help="Paths (globs resolved by shell) to input .jsonl files")
    parser.add_argument("--out", required=True, help="Output platinum.jsonl path")
    args = parser.parse_args()

    report = build_platinum(args.inputs, args.out)
    print(json.dumps(report))


if __name__ == "__main__":
    main_cli()