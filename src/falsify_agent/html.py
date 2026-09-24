"""P2 HTML report — one self-contained file per run.

Built from an engine JSON record plus the ledger history of its strategy.
Never produces or alters verdicts: every verdict shown comes from an engine
record verbatim. No network, no JS, no external assets — CSS is inline and
the file contains no ``http`` so it opens fully offline. No prescriptive
text: numbers and thresholds only, never parameter advice.
"""

from __future__ import annotations

import html as _html
import re
from pathlib import Path

from falsify_agent import ledger

VERDICT_MARKS = {"pass": "✓", "fail": "✗", "warn": "!"}


def slug(strategy: str) -> str:
    """Filesystem-safe strategy name: ``[^A-Za-z0-9._-]`` → ``-``."""
    return re.sub(r"[^A-Za-z0-9._-]", "-", strategy)


def report_path(strategy: str, run: int) -> Path:
    """``$FALSIFY_HOME/reports/<strategy-slug>-<run>.html``."""
    return ledger.home() / "reports" / f"{slug(strategy)}-{run}.html"


def _esc(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return str(value)
    return _html.escape(str(value), quote=True)


def _verdict_badge(verdict) -> str:
    v = _esc(verdict)
    cls = verdict if verdict in ("pass", "fail", "warn") else "unknown"
    return f'<span class="badge {cls}">{v}</span>'


def render(record: dict, strategy: str, run: int, observed: int,
           deflated_verdict: str | None = None,
           history_verdicts: list | None = None) -> str:
    """Render the full HTML page. Pure function (no I/O) for snapshot tests."""
    declared = record.get("declared", {}) if isinstance(record.get("declared"), dict) else {}
    verdict = record.get("verdict")
    checks = record.get("checks") if isinstance(record.get("checks"), list) else []
    engine_version = record.get("engine_version")
    inputs = record.get("input", {}) if isinstance(record.get("input"), dict) else {}

    declared_trials = declared.get("trials")

    if deflated_verdict is not None:
        verdict_block = (
            "<div class=\"verdicts\">"
            f"<div><div class=\"label\">verdict (กรอก trials {_esc(declared_trials)})</div>"
            f"<div class=\"big\">{_verdict_badge(verdict)}</div></div>"
            "<div><div class=\"label\">verdict แบบ deflate "
            f"(ledger นับได้ {_esc(observed)})</div>"
            f"<div class=\"big\">{_verdict_badge(deflated_verdict)}</div></div>"
            "</div>"
        )
    else:
        verdict_block = (
            "<div class=\"verdicts\">"
            "<div><div class=\"label\">verdict</div>"
            f"<div class=\"big\">{_verdict_badge(verdict)}</div></div>"
            "</div>"
        )

    rows = []
    for check in checks if isinstance(checks, list) else []:
        if not isinstance(check, dict):
            continue
        rows.append(
            "<tr><td>" + _esc(check.get("name")) + "</td>"
            "<td>" + _verdict_badge(check.get("verdict")) + "</td>"
            "<td>" + _esc(check.get("value")) + "</td>"
            "<td>" + _esc(check.get("threshold")) + "</td>"
            "<td>" + _esc(check.get("explanation")) + "</td></tr>"
        )
    checks_table = (
        "<table><thead><tr><th>name</th><th>verdict</th>"
        "<th>ค่า</th><th>เกณฑ์</th><th>คำอธิบาย (จาก engine)</th></tr></thead>"
        f"<tbody>{''.join(rows) if rows else '<tr><td colspan=\"5\">-</td></tr>'}</tbody></table>"
    )

    history = history_verdicts if history_verdicts is not None else []
    strip = []
    for i, v in enumerate(history, start=1):
        mark = VERDICT_MARKS.get(v, "?") if isinstance(v, str) else "?"
        cls = v if v in ("pass", "fail", "warn") else "unknown"
        strip.append(
            f'<span class="tick {cls}" title="run #{i}: {_esc(v)}">{mark}</span>'
        )
    history_block = (
        f"<p>ประวัติ {len(history)} runs: {''.join(strip) if strip else '-'}</p>"
        if history is not None else ""
    )

    repeat = (
        f"falsify check {_esc(inputs.get('path'))} "
        f"--params {_esc(declared.get('params'))} "
        f"--trials {_esc(declared_trials)} --json"
    )

    return (
        "<!DOCTYPE html>\n<html lang=\"th\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{_esc(strategy)} run #{run} — {_esc(verdict)}</title>\n"
        "<style>\n"
        ":root{color-scheme:light dark}\n"
        "body{font-family:system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem}\n"
        ".verdicts{display:flex;gap:2rem;margin:1rem 0}\n"
        ".label{font-size:.85rem;opacity:.75}\n"
        ".big{font-size:2.5rem;font-weight:700}\n"
        ".badge{padding:.1em .5em;border-radius:.4em;font-weight:700}\n"
        ".badge.pass{background:#d3f9d8;color:#0b3d1b}\n"
        ".badge.fail{background:#ffe3e3;color:#7a0c0c}\n"
        ".badge.warn{background:#fff3bf;color:#5c3d00}\n"
        "table{border-collapse:collapse;width:100%}\n"
        "th,td{border:1px solid #999;padding:.3em .6em;text-align:left}\n"
        ".tick{display:inline-block;width:1.6em;text-align:center;margin:.1em;"
        "border:1px solid #999;border-radius:.3em}\n"
        ".tick.pass{background:#d3f9d8}.tick.fail{background:#ffe3e3}.tick.warn{background:#fff3bf}\n"
        "@media (prefers-color-scheme:dark){"
        "body{background:#121212;color:#eee}"
        "th,td{border-color:#555}.tick{border-color:#555}"
        ".badge.pass{background:#0b3d1b;color:#d3f9d8}"
        ".badge.fail{background:#7a0c0c;color:#ffe3e3}"
        ".badge.warn{background:#5c3d00;color:#fff3bf}"
        ".tick.pass{background:#0b3d1b}.tick.fail{background:#7a0c0c}.tick.warn{background:#5c3d00}"
        "}\n</style>\n</head>\n<body>\n"
        f"<h1>{_esc(strategy)} — run #{run}</h1>\n"
        f"{verdict_block}\n"
        f"<p>trials: กรอก {_esc(declared_trials)} · ledger นับได้ {_esc(observed)}</p>\n"
        f"{checks_table}\n"
        f"{history_block}\n"
        "<footer>\n"
        f"<p>engine_version: {_esc(engine_version)}</p>\n"
        f"<p>input.sha256: {_esc(inputs.get('sha256'))}</p>\n"
        f"<p>canonical_sha256: {_esc(inputs.get('canonical_sha256'))}</p>\n"
        f"<p>ตรวจซ้ำ: <code>{repeat}</code></p>\n"
        "</footer>\n</body>\n</html>\n"
    )


def write_report(strategy: str, run: int | None = None,
                 deflated_verdict: str | None = None) -> Path:
    """Render one strategy run to its HTML file. Returns the path.

    ``run`` is the 1-based index within the strategy (``None`` = latest).
    Raises ``ValueError`` when the strategy has no runs.
    """
    runs = ledger.strategy_runs(strategy)
    if not runs:
        raise ValueError(f'ยังไม่มี run ของ "{strategy}"')
    number = len(runs) if run is None else run
    if not isinstance(number, int) or not 1 <= number <= len(runs):
        raise ValueError(f"run ต้องอยู่ระหว่าง 1–{len(runs)}")
    record = runs[number - 1]
    summary = ledger.status(strategy)
    assert summary is not None  # runs non-empty
    history_verdicts = [r.get("verdict") for r in runs]
    page = render(record, strategy, number, summary["observed_trials"],
                  deflated_verdict, history_verdicts)
    path = report_path(strategy, number)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path
