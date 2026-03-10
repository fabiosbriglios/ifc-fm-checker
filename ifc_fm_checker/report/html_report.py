"""
HTML Report Generator
Produces a professional, self-contained HTML report from check results.
"""

import json
from datetime import datetime
from typing import Dict, Any, List
from ifc_fm_checker.config import RATING_THRESHOLDS, RATING_COLORS, RATING_LABELS


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

    # Build check sections HTML
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
  .header {{ background: #1a3a5c; color: #fff; padding: 28px 40px; }}
  .header h1 {{ font-size: 26px; font-weight: 700; letter-spacing: 0.5px; }}
  .header p {{ color: #a8c4e0; margin-top: 4px; font-size: 13px; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 28px 24px; }}

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

  .footer {{ text-align: center; color: #aaa; font-size: 11px; margin-top: 40px; padding-bottom: 40px; }}

  @media print {{
    body {{ background: #fff; }}
    .check-card {{ box-shadow: none; border: 1px solid #ddd; }}
  }}
</style>
</head>
<body>

<div class="header">
  <h1>IFC FM Readiness Report</h1>
  <p>Generated by ifc-fm-checker &bull; {now}</p>
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


def _render_issues(issues: List[Dict]) -> str:
    if not issues:
        return '<p class="no-issues">✅ No issues found for this check.</p>'

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
