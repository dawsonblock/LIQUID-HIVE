import json
import os
import tempfile
from training.pipeline.provenance import pii_redact, build_platinum


def test_pii_redaction():
    text = "Contact me at john.doe@example.com or (555) 123-4567. My SSN is 123-45-6789 and I live at 221B Baker Street."
    red, has, types_ = pii_redact(text)
    assert has
    assert "EMAIL" in types_ and "PHONE" in types_ and "SSN" in types_
    assert "<REDACTED:EMAIL>" in red


def test_build_platinum_schema_and_filters(tmp_path):
    # Prepare inputs
    src = tmp_path / "logs.jsonl"
    with open(src, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "source_uri": "s3://bucket/log1",
            "license": "CC-BY-4.0",
            "prompt": "What is 2+2?",
            "response": "4",
            "oracle_trace": {"engine": "DeepSeek", "deltas": []}
        }) + "\n")
        # Missing license should be skipped
        f.write(json.dumps({
            "source_uri": "s3://bucket/log2",
            "license": "",
            "prompt": "Hello",
            "response": "Hi"
        }) + "\n")

    out_path = tmp_path / "platinum.jsonl"
    report = build_platinum([str(src)], str(out_path))

    # Validate output file exists and has one record
    assert out_path.exists()
    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    for key in ["id", "timestamp", "sha256_source", "source_uri", "license", "pii_redacted", "pii_types", "prompt", "response", "oracle_trace", "policy_tags"]:
        assert key in rec

    # Validate report fields
    assert "count" in report and report["count"] == 1
    assert "redaction_rate" in report
    assert "license_top" in report