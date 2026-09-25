"""Chunk 4 — P2 HTML report: single self-contained file per run.

Covers plan §3 / spec §6:
- snapshot of HTML from a sample record (examples/known_overfit.csv via engine)
- no ``http`` anywhere in the output (offline, no CDN)
- verdict + deflated side-by-side, trials line, checks table, history strip,
  footer with engine_version / hashes / repeat command
- escaping of user-controlled values, slug filenames, CLI + MCP wiring
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from falsify_agent import html, ledger
from falsify_agent.mcp_server import tool_check, tool_report

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("FALSIFY_HOME", str(tmp_path / ".falsify"))
    return tmp_path / ".falsify"


def make_record(strategy="ema-cross", sha="canon-1", trials=1,
                verdict="fail", params=3,
                created_at="2026-09-23T00:00:00+00:00"):
    return {
        "schema_version": 1,
        "engine_version": "0.1.0",
        "input": {"path": "x.csv", "sha256": f"raw-{sha}",
                  "canonical_sha256": sha, "n_trades": 42},
        "declared": {"params": params, "trials": trials,
                     "trials_was_default": trials == 1},
        "dataset": {"symbol": None, "timeframe": None, "strategy": strategy,
                    "date_range": {"first_entry": "2026-01-01", "last_exit": "2026-02-01"}},
        "verdict": verdict,
        "checks": [
            {"name": "sample_size", "verdict": "warn", "value": 42,
             "threshold": 30, "explanation": "n=42, p=0.64",
             "inputs": {"n_trades": 42}},
            {"name": "deflated_sharpe", "verdict": "fail", "value": 0.12,
             "threshold": 0.95, "explanation": "SR=0.18 deflated",
             "inputs": {"sharpe": 0.18}},
        ],
        "created_at": created_at,
    }


def engine_record(csv_name="known_overfit.csv", strategy="ema-cross"):
    proc = subprocess.run(
        [sys.executable, "-m", "falsify.cli", "check",
         f"examples/{csv_name}", "--params", "3",
         "--strategy", strategy, "--json"],
        capture_output=True, text=True, cwd=REPO)
    assert proc.returncode in (0, 1), proc.stderr
    return json.loads(proc.stdout)


def test_snapshot_from_example_record(home):
    rec = engine_record()
    for sha in ("canon-a", "canon-b"):
        r = dict(rec)
        r["input"] = {**rec["input"], "canonical_sha256": sha,
                       "sha256": f"raw-{sha}"}
        ledger.append_record(r)
    summary = ledger.status("ema-cross")
    runs = ledger.strategy_runs("ema-cross")
    page = html.render(runs[-1], "ema-cross", 2, summary["observed_trials"],
                       deflated_verdict="fail",
                       history_verdicts=[r["verdict"] for r in runs])
    assert "<!DOCTYPE html>" in page
    assert "ema-cross — run #2" in page
    assert "ledger นับได้ 2" in page
    assert "กรอก 1" in page
    assert "verdict แบบ deflate" in page
    for check in runs[-1]["checks"]:
        assert check["name"] in page
    assert "canonical_sha256" in page
    assert "ตรวจซ้ำ:" in page
    assert "prefers-color-scheme" in page
    assert "<script" not in page


def test_deflated_checks_table_rendered(home):
    rec = engine_record()
    deflated = [{"name": "deflated_sharpe", "verdict": "fail", "value": 0.49,
                 "threshold": 0.95, "explanation": "SR deflated"}]
    page = html.render(rec, "ema-cross", 1, 2, deflated_verdict="fail",
                       history_verdicts=[rec["verdict"]],
                       deflated_checks=deflated)
    assert "checks (กรอก trials 1)" in page
    assert "checks (deflate, ledger นับได้ 2)" in page
    # the deflated failing check is present, not only the declared-trial table
    assert page.count("deflated_sharpe") == 2
    assert 'class="badge fail">fail' in page


def test_no_http_in_output(home):
    rec = engine_record()
    ledger.append_record(rec)
    page = html.render(rec, "ema-cross", 1, 1,
                       history_verdicts=[rec["verdict"]])
    assert "http" not in page


def test_escapes_user_controlled_values():
    rec = make_record(strategy="<script>alert(1)</script>")
    rec["input"]["path"] = "<img src=x>"
    page = html.render(rec, "<script>alert(1)</script>", 1, 1,
                       history_verdicts=["fail"])
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
    assert "<img src=x>" not in page


def test_slug_and_report_path(home):
    assert html.slug("a/b c+d") == "a-b-c-d"
    assert html.slug("ema-cross_2.0") == "ema-cross_2.0"
    assert html.report_path("a/b", 3).name == "a-b-3.html"
    assert html.report_path("ema", 1).parent.name == "reports"


def test_write_report_latest_and_numbered(home):
    ledger.append_record(make_record(sha="a", verdict="fail"))
    ledger.append_record(make_record(sha="b", verdict="pass"))
    latest = html.write_report("ema-cross")
    assert latest.name == "ema-cross-2.html"
    assert latest.exists()
    first = html.write_report("ema-cross", run=1)
    assert first.name == "ema-cross-1.html"
    assert "run #1" in first.read_text(encoding="utf-8")
    assert "run #2" in latest.read_text(encoding="utf-8")


def test_write_report_unknown_strategy(home):
    with pytest.raises(ValueError, match="ยังไม่มี run"):
        html.write_report("nope")


def test_write_report_bad_run_number(home):
    ledger.append_record(make_record())
    with pytest.raises(ValueError, match="1–1"):
        html.write_report("ema-cross", run=2)


def test_no_prescriptive_text(home):
    ledger.append_record(make_record())
    page = html.write_report("ema-cross").read_text(encoding="utf-8")
    for forbidden in ("ลองลด", "ควรปรับ", "แนะนำ"):
        assert forbidden not in page


def test_cli_report_prints_path(home):
    ledger.append_record(make_record())
    import os
    env = dict(os.environ, FALSIFY_HOME=str(home))
    r = subprocess.run([sys.executable, "-m", "falsify_agent.cli",
                        "report", "ema-cross"],
                       capture_output=True, text=True, cwd=REPO, env=env)
    assert r.returncode == 0, r.stderr
    path = Path(r.stdout.strip())
    assert path.exists()
    assert path.name == "ema-cross-1.html"
    r = subprocess.run([sys.executable, "-m", "falsify_agent.cli",
                        "report", "nope"],
                       capture_output=True, text=True, cwd=REPO, env=env)
    assert r.returncode == 1


def test_mcp_report_builds_file(home, tmp_path):
    a = tmp_path / "a.csv"
    a.write_text((REPO / "examples" / "known_good.csv").read_text())
    checked = tool_check(str(a), "ema", params=2, trials=1)
    assert checked["report_path"] is not None
    assert Path(checked["report_path"]).exists()
    out = tool_report("ema")
    assert Path(out["path"]).exists()
    assert out["path"].endswith("ema-1.html")
    with pytest.raises(ValueError, match="ยังไม่มี run"):
        tool_report("nope")
