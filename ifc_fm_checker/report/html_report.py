"""
HTML Report Generator
Produces a professional, self-contained HTML report from check results.
"""

import base64
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from ifc_fm_checker.config import RATING_THRESHOLDS, RATING_COLORS, RATING_LABELS

_MAX_CLASHES_SHOWN = 20
_MAX_CLASHES_STORED = 50


def get_rating(score: int) -> str:
    if score >= RATING_THRESHOLDS["excellent"]:
        return "excellent"
    elif score >= RATING_THRESHOLDS["good"]:
        return "good"
    elif score >= RATING_THRESHOLDS["fair"]:
        return "fair"
    return "poor"


def render(
    results: List[Dict[str, Any]],
    overall_score: int,
    model_info: Dict[str, Any],
    output_path: str,
):
    rating = get_rating(overall_score)
    color = RATING_COLORS[rating]
    label = RATING_LABELS[rating]
    now = datetime.now().strftime("%d %B %Y, %H:%M")

    # Build JSON download payload (embedded as base64 data URI)
    stem = model_info.get("filename", "report").rsplit(".", 1)[0]
    json_payload = {
        "overall_score": overall_score,
        "rating": label,
        "model_info": model_info,
        "checks": results,
    }
    json_bytes = json.dumps(json_payload, indent=2, default=str).encode("utf-8")
    json_b64 = base64.b64encode(json_bytes).decode("ascii")
    download_btn = (
        f'<a href="data:application/json;base64,{json_b64}" '
        f'download="{stem}_fm_report.json" class="download-btn">'
        f'&#x2B07; Download JSON</a>'
    )

    # Build per-check card sections
    sections_html = ""
    for check in results:
        check_score = check["score"]
        check_rating = get_rating(check_score)
        check_color = RATING_COLORS[check_rating]
        issue_rows = _render_issues(check.get("issues", []))
        stats_html = _render_stats(check.get("stats", {}))

        sections_html += f"""
        <div class="check-card">
            <div class="check-header">
                <div>
                    <h3>{check['name']}</h3>
                    <p class="check-desc">{check.get('description', '')}</p>
                </div>
                <div class="score-badge" style="background:{check_color}">
                    {check_score}<span style="font-size:14px">/100</span>
                </div>
            </div>
            <div class="score-bar-bg">
                <div class="score-bar-fill" style="width:{check_score}%; background:{check_color}"></div>
            </div>
            {stats_html}
            {issue_rows}
        </div>
        """

    # Build clash report section
    clash_section_html = _render_clash_section(results)

    # Build model info table
    model_rows = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>"
        for k, v in model_info.items()
        if v not in (None, "", "Unknown")
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IFC FM Readiness Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f4f6fa; color: #222; font-size: 14px; }}
  .header {{ background: #1a3a5c; color: #fff; padding: 28px 40px; display: flex;
    justify-content: space-between; align-items: flex-start; }}
  .header h1 {{ font-size: 26px; font-weight: 700; letter-spacing: 0.5px; }}
  .header p {{ color: #a8c4e0; margin-top: 4px; font-size: 13px; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 28px 24px; }}

  /* Download button */
  .download-btn {{ display: inline-block; background: rgba(255,255,255,0.15);
    color: #fff; border: 1px solid rgba(255,255,255,0.4); border-radius: 6px;
    padding: 8px 16px; font-size: 13px; font-weight: 600; text-decoration: none;
    white-space: nowrap; transition: background 0.2s; margin-top: 4px; }}
  .download-btn:hover {{ background: rgba(255,255,255,0.25); }}

  /* Overall score card */
  .overall-card {{ background: #fff; border-radius: 10px; padding: 28px 36px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.09); display: flex; align-items: center;
    gap: 36px; margin-bottom: 28px; }}
  .overall-score {{ font-size: 72px; font-weight: 800; line-height: 1;
    color: {color}; min-width: 120px; text-align: center; }}
  .overall-score span {{ display: block; font-size: 16px; color: #888; font-weight: 400; }}
  .overall-badge {{ display: inline-block; background: {color}; color: #fff;
    border-radius: 6px; padding: 6px 18px; font-size: 15px; font-weight: 700;
    letter-spacing: 1px; margin-bottom: 8px; }}
  .overall-info h2 {{ font-size: 20px; margin-bottom: 6px; }}
  .overall-info p {{ color: #555; line-height: 1.6; }}

  /* Model info table */
  .info-table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
  .info-table td {{ padding: 5px 12px; border-bottom: 1px solid #eee; }}
  .info-table td:first-child {{ font-weight: 600; color: #555; width: 200px; }}
  .section-title {{ font-size: 18px; font-weight: 700; margin: 28px 0 14px;
    color: #1a3a5c; border-bottom: 2px solid #1a3a5c; padding-bottom: 6px; }}

  /* Check cards */
  .check-card {{ background: #fff; border-radius: 10px; padding: 24px 28px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07); margin-bottom: 20px; }}
  .check-header {{ display: flex; justify-content: space-between; align-items: flex-start;
    margin-bottom: 14px; }}
  .check-header h3 {{ font-size: 16px; font-weight: 700; color: #1a3a5c; margin-bottom: 4px; }}
  .check-desc {{ color: #777; font-size: 12px; max-width: 700px; line-height: 1.5; }}
  .score-badge {{ color: #fff; border-radius: 8px; padding: 10px 18px;
    font-size: 26px; font-weight: 800; text-align: center; min-width: 80px; }}
  .score-bar-bg {{ background: #eee; border-radius: 4px; height: 8px; margin-bottom: 16px; }}
  .score-bar-fill {{ height: 8px; border-radius: 4px; transition: width 0.3s; }}

  /* Stats grid */
  .stats-grid {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }}
  .stat-chip {{ background: #eef2f8; border-radius: 20px; padding: 4px 14px;
    font-size: 12px; color: #444; font-weight: 500; }}

  /* Issues table */
  .issues-table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
  .issues-table th {{ background: #f0f4fa; color: #444; font-weight: 600;
    text-align: left; padding: 8px 12px; border-bottom: 2px solid #dde3ed; }}
  .issues-table td {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0;
    vertical-align: top; }}
  .issues-table tr:hover td {{ background: #fafbff; }}

  .sev-error   {{ color: #c62828; font-weight: 700; }}
  .sev-warning {{ color: #e65100; font-weight: 700; }}
  .sev-info    {{ color: #1565c0; font-weight: 700; }}

  .fix-text {{ color: #555; font-style: italic; }}
  .no-issues {{ color: #2e7d32; font-weight: 600; padding: 10px 0; }}

  /* Clash report section */
  .clash-grid {{ display: flex; flex-wrap: wrap; gap: 20px; }}
  .clash-card {{ background: #fafafa; border: 1px solid #e8e8e8; border-radius: 8px;
    padding: 14px; width: 310px; }}
  .clash-num {{ font-size: 11px; font-weight: 700; color: #c62828; text-transform: uppercase;
    letter-spacing: 0.5px; margin-bottom: 8px; }}
  .clash-summary {{ font-size: 11px; color: #555; margin-top: 8px; line-height: 1.5;
    word-break: break-all; }}
  .clash-legend {{ display: flex; gap: 16px; margin-top: 10px; font-size: 11px; color: #555; }}
  .clash-legend span {{ display: flex; align-items: center; gap: 4px; }}
  .clash-note {{ font-size: 12px; color: #888; font-style: italic; margin-top: 16px; }}

  .footer {{ text-align: center; color: #aaa; font-size: 11px; margin-top: 40px; padding-bottom: 40px; }}

  @media print {{
    body {{ background: #fff; }}
    .check-card {{ box-shadow: none; border: 1px solid #ddd; }}
    .download-btn {{ display: none; }}
  }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>IFC FM Readiness Report</h1>
    <p>Generated by ifc-fm-checker &bull; {now}</p>
  </div>
  {download_btn}
</div>

<div class="container">

  <!-- Overall score -->
  <div class="overall-card">
    <div class="overall-score">
      {overall_score}
      <span>/ 100</span>
    </div>
    <div class="overall-info">
      <div class="overall-badge">{label}</div>
      <h2>{model_info.get('filename', 'IFC Model')}</h2>
      <p>
        This model scored <strong>{overall_score}/100</strong> for Facility Management readiness.
        {"✅ The model is ready for CAFM import with minor fixes." if overall_score >= 85 else
         "⚠️ Some work is required before CAFM import." if overall_score >= 70 else
         "❌ Significant data gaps must be resolved before this model can support FM operations."}
      </p>
    </div>
  </div>

  <!-- Model info -->
  <h2 class="section-title">Model Information</h2>
  <div class="check-card" style="padding: 16px 24px;">
    <table class="info-table">
      {model_rows}
    </table>
  </div>

  <!-- Check results -->
  <h2 class="section-title">Check Results</h2>
  {sections_html}

  <!-- Clash diagrams (only if clashes exist) -->
  {clash_section_html}

</div>

<div class="footer">
  ifc-fm-checker v1.0.0 &bull; Author: Fabio Sbriglio &bull;
  Based on ISO 19650, COBie 2.4, Italian DM 312/2021 &bull;
  <a href="https://github.com/fabio-sbriglio/ifc-fm-checker">github.com/fabio-sbriglio/ifc-fm-checker</a>
</div>

</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


# ---------------------------------------------------------------------------
# Clash report section
# ---------------------------------------------------------------------------

def _render_clash_section(results: List[Dict[str, Any]]) -> str:
    """Render the visual clash report section; returns empty string if no clashes."""
    clash_check = next(
        (c for c in results if c.get("check_key") == "clash_detection"), None
    )
    if not clash_check:
        return ""

    clashes = clash_check.get("clashes", [])
    if not clashes:
        return ""

    total = len(clashes)
    shown = clashes[:_MAX_CLASHES_SHOWN]

    legend = """
    <div class="clash-legend">
      <span><svg width="14" height="14"><rect width="14" height="14" fill="#e53935" fill-opacity="0.5" stroke="#c62828" stroke-width="1.5" rx="2"/></svg> Element A</span>
      <span><svg width="14" height="14"><rect width="14" height="14" fill="#1e88e5" fill-opacity="0.5" stroke="#1565c0" stroke-width="1.5" rx="2"/></svg> Element B</span>
      <span><svg width="14" height="14"><rect width="14" height="14" fill="#fdd835" fill-opacity="0.7" stroke="#f9a825" stroke-width="1.5" rx="2"/></svg> Overlap</span>
    </div>"""

    cards_html = ""
    for i, clash in enumerate(shown):
        svg = _render_clash_svg(clash)
        storey = clash.get("storey1") or clash.get("storey2") or "Unknown"
        type1 = _esc(clash.get("type1", "?"))
        id1 = _esc(clash.get("id1", "")[:8])
        type2 = _esc(clash.get("type2", "?"))
        id2 = _esc(clash.get("id2", "")[:8])
        summary = f"{type1} #{i + 1} &mdash; {type2} #{i + 1} &bull; Storey: {_esc(storey)}"
        full_summary = f"{type1} {id1}&hellip; vs {type2} {id2}&hellip; &mdash; Storey: {_esc(storey)}"
        cards_html += f"""
        <div class="clash-card">
          <div class="clash-num">Clash #{i + 1}</div>
          {svg}
          {legend}
          <p class="clash-summary">{full_summary}</p>
        </div>"""

    note = ""
    if total > _MAX_CLASHES_SHOWN:
        note = (
            f'<p class="clash-note">Showing {_MAX_CLASHES_SHOWN} of {total} clashes'
            f" — see JSON report for full list</p>"
        )

    return f"""
  <h2 class="section-title">Clash Report</h2>
  <div class="check-card">
    <div class="clash-grid">{cards_html}</div>
    {note}
  </div>
"""


def _render_clash_svg(clash_data: Dict[str, Any], svg_w: int = 280, svg_h: int = 160) -> str:
    """Generate inline SVG top-view (XY plane) for two clashing bounding boxes."""
    b1 = clash_data.get("bbox1", {})
    b2 = clash_data.get("bbox2", {})

    # Accept both dict {xmin,...} and legacy flat-list [xmin,ymin,zmin,xmax,ymax,zmax]
    if isinstance(b1, list) and len(b1) >= 6:
        b1 = {"xmin": b1[0], "ymin": b1[1], "zmin": b1[2],
              "xmax": b1[3], "ymax": b1[4], "zmax": b1[5]}
    if isinstance(b2, list) and len(b2) >= 6:
        b2 = {"xmin": b2[0], "ymin": b2[1], "zmin": b2[2],
              "xmax": b2[3], "ymax": b2[4], "zmax": b2[5]}

    if not b1 or not b2:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="40">'
            '<text x="10" y="26" font-size="12" fill="#999">No geometry data</text></svg>'
        )

    # Combined XY extent
    cxmin = min(b1["xmin"], b2["xmin"])
    cxmax = max(b1["xmax"], b2["xmax"])
    cymin = min(b1["ymin"], b2["ymin"])
    cymax = max(b1["ymax"], b2["ymax"])

    dw = cxmax - cxmin or 1.0
    dh = cymax - cymin or 1.0

    # 20% padding
    px, py = dw * 0.2, dh * 0.2
    vxmin, vxmax = cxmin - px, cxmax + px
    vymin, vymax = cymin - py, cymax + py
    vw = vxmax - vxmin or 1.0
    vh = vymax - vymin or 1.0

    def sx(x: float) -> float:
        return (x - vxmin) / vw * svg_w

    def sy(y: float) -> float:
        # Flip Y: model Y-up → SVG Y-down
        return svg_h - (y - vymin) / vh * svg_h

    def make_rect(bbox: Dict, fill: str, stroke: str, opacity: float) -> str:
        rx1 = sx(bbox["xmin"])
        ry1 = sy(bbox["ymax"])          # top edge in SVG (smaller y)
        rw = max(sx(bbox["xmax"]) - rx1, 2.0)
        rh = max(sy(bbox["ymin"]) - ry1, 2.0)  # bottom − top, always positive
        return (
            f'<rect x="{rx1:.2f}" y="{ry1:.2f}" width="{rw:.2f}" height="{rh:.2f}" '
            f'fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" '
            f'stroke-width="1.5" rx="2"/>'
        )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
        f'style="border:1px solid #e0e0e0;border-radius:6px;background:#fafafa;display:block">'
    ]

    # Element A (red), Element B (blue)
    parts.append(make_rect(b1, "#e53935", "#c62828", 0.5))
    parts.append(make_rect(b2, "#1e88e5", "#1565c0", 0.5))

    # Overlap area (yellow) — XY intersection
    ovxmin = max(b1["xmin"], b2["xmin"])
    ovxmax = min(b1["xmax"], b2["xmax"])
    ovymin = max(b1["ymin"], b2["ymin"])
    ovymax = min(b1["ymax"], b2["ymax"])
    if ovxmin < ovxmax and ovymin < ovymax:
        ov = {"xmin": ovxmin, "ymin": ovymin, "xmax": ovxmax, "ymax": ovymax}
        parts.append(make_rect(ov, "#fdd835", "#f9a825", 0.7))

    # Labels (white text with black stroke for readability on any background)
    for bbox, label_key_type, label_key_id in [
        (b1, "type1", "id1"),
        (b2, "type2", "id2"),
    ]:
        cx = sx((bbox["xmin"] + bbox["xmax"]) / 2)
        cy = sy((bbox["ymin"] + bbox["ymax"]) / 2)
        lbl = _esc(
            clash_data.get(label_key_type, "?")
            + "\n#"
            + clash_data.get(label_key_id, "")[:6]
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="8" text-anchor="middle" '
            f'dominant-baseline="middle" font-family="monospace" '
            f'stroke="#000" stroke-width="2.5" paint-order="stroke" fill="#fff">'
            f'{lbl}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Issue / stats helpers
# ---------------------------------------------------------------------------

def _render_issues(issues: List[Dict]) -> str:
    if not issues:
        return '<p class="no-issues">&#x2705; No issues found for this check.</p>'

    rows = ""
    for issue in issues:
        sev = issue.get("severity", "info")
        sev_class = f"sev-{sev}"
        sev_label = {"error": "ERROR", "warning": "WARNING", "info": "INFO"}.get(sev, sev.upper())
        rows += f"""
        <tr>
          <td><span class="{sev_class}">{sev_label}</span></td>
          <td>{_esc(issue.get('element', ''))}</td>
          <td>{_esc(issue.get('message', ''))}</td>
          <td class="fix-text">{_esc(issue.get('fix', ''))}</td>
        </tr>"""

    return f"""
    <table class="issues-table">
      <thead>
        <tr>
          <th style="width:80px">Severity</th>
          <th style="width:200px">Element</th>
          <th>Issue</th>
          <th>Recommended Fix</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """


def _render_stats(stats: Dict) -> str:
    if not stats:
        return ""
    chips = []
    for k, v in stats.items():
        if isinstance(v, (int, float, str)) and not isinstance(v, dict):
            chips.append(f'<span class="stat-chip"><strong>{k}</strong>: {v}</span>')
    if not chips:
        return ""
    return f'<div class="stats-grid">{"".join(chips)}</div>'


def _esc(text: str) -> str:
    """Minimal HTML escape."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
