"""Gera os cards SVG do perfil (stats, linguagens e atividade) sem serviços externos.

Uso:  python .github/scripts/gen_stats.py [usuario] [pasta_saida]
Com GITHUB_TOKEN no ambiente usa a API GraphQL (calendário de contribuições);
sem token cai para a API REST pública (eventos dos últimos 90 dias).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

USER = sys.argv[1] if len(sys.argv) > 1 else "Luca-css"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "assets")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"

BG, PANEL, CYAN, TEXT, DIM, GRID = "#020c1b", "#06182b", "#00d4ff", "#7ecfff", "#3b6b8c", "#0a2a4a"
FONT = "ui-monospace,SFMono-Regular,'Cascadia Code',Consolas,'Liberation Mono',monospace"
LANG_COLORS = {
    "Go": "#00ADD8", "Python": "#3776AB", "TypeScript": "#3178C6", "JavaScript": "#F7DF1E",
    "PowerShell": "#5391FE", "Shell": "#4EAA25", "Rust": "#DEA584", "Kotlin": "#A97BFF",
    "HTML": "#E34C26", "CSS": "#2965f1", "Dockerfile": "#384d54", "C#": "#178600",
    "Java": "#b07219", "C": "#555555", "C++": "#f34b7d", "Makefile": "#427819",
}
IGNORED_LANGS = {"HTML", "CSS", "Makefile", "Dockerfile", "Batchfile"}


def _req(url: str, data: bytes | None = None) -> object:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-stats-generator"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=30) as r:
        return json.load(r)


def fetch_repos() -> list[dict]:
    repos: list[dict] = []
    page = 1
    while True:
        batch = _req(f"{API}/users/{USER}/repos?per_page=100&type=owner&page={page}")
        assert isinstance(batch, list)
        repos += batch
        if len(batch) < 100:
            return [r for r in repos if not r["fork"]]
        page += 1


def fetch_languages(repos: list[dict]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for r in repos:
        if r["name"].lower() == USER.lower():
            continue
        langs = _req(r["languages_url"])
        assert isinstance(langs, dict)
        for lang, size in langs.items():
            if lang not in IGNORED_LANGS:
                totals[lang] = totals.get(lang, 0) + size
    return dict(sorted(totals.items(), key=lambda kv: -kv[1]))


def fetch_activity() -> tuple[dict[str, int], dict[str, int]]:
    """Retorna (contagem diária dos últimos 31 dias, métricas agregadas)."""
    today = dt.date.today()
    days = {(today - dt.timedelta(days=i)).isoformat(): 0 for i in range(30, -1, -1)}
    if TOKEN:
        query = """query($u:String!){user(login:$u){contributionsCollection{
          totalCommitContributions totalPullRequestContributions totalIssueContributions
          restrictedContributionsCount
          contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
        body = json.dumps({"query": query, "variables": {"u": USER}}).encode()
        res = _req(f"{API}/graphql", body)
        assert isinstance(res, dict)
        cc = res["data"]["user"]["contributionsCollection"]
        for week in cc["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                if d["date"] in days:
                    days[d["date"]] = d["contributionCount"]
        metrics = {
            "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
            "prs": cc["totalPullRequestContributions"],
            "issues": cc["totalIssueContributions"],
            "contribs": cc["contributionCalendar"]["totalContributions"],
        }
        return days, metrics
    commits = prs = issues = 0
    year_total = _calendar_fallback(days)
    for page in (1, 2, 3):
        events = _req(f"{API}/users/{USER}/events/public?per_page=100&page={page}")
        assert isinstance(events, list)
        for e in events:
            day = e["created_at"][:10]
            n = len(e["payload"].get("commits", [])) if e["type"] == "PushEvent" else 1
            if e["type"] == "PushEvent":
                commits += n
            elif e["type"] == "PullRequestEvent":
                prs += 1
            elif e["type"] == "IssuesEvent":
                issues += 1
        if len(events) < 100:
            break
    return days, {"commits": commits, "prs": prs, "issues": issues, "contribs": year_total}


def _calendar_fallback(days: dict[str, int]) -> int:
    """Lê o calendário público de contribuições (HTML) e preenche `days`; retorna o total do ano."""
    import re

    req = urllib.request.Request(f"https://github.com/users/{USER}/contributions",
                                 headers={"User-Agent": "profile-stats-generator"})
    with urllib.request.urlopen(req, timeout=30) as r:
        page = r.read().decode("utf-8", "replace")
    ids = dict(re.findall(r'data-date="([\d-]+)" id="([^"]+)"', page))
    by_id = {v: k for k, v in ids.items()}
    total = 0
    for cell, count in re.findall(r'for="([^"]+)"[^>]*>(\d+) contributions? on', page):
        total += int(count)
        date = by_id.get(cell)
        if date in days:
            days[date] = int(count)
    return total


def frame(w: int, h: int, title: str, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">
<style>
 text{{font-family:{FONT};}}
 .t{{fill:{CYAN};font-size:15px;font-weight:700;letter-spacing:.5px}}
 .l{{fill:{TEXT};font-size:12.5px}} .v{{fill:#e6f7ff;font-size:13px;font-weight:700}}
 .d{{fill:{DIM};font-size:10.5px}}
 .cur{{animation:blink 1s steps(1) infinite}} @keyframes blink{{50%{{opacity:0}}}}
</style>
<defs><linearGradient id="edge" x1="0" x2="1"><stop offset="0" stop-color="{CYAN}"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></linearGradient></defs>
<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="10" fill="{BG}" stroke="{GRID}"/>
<rect x="1" y="1" width="{w * 0.6:.0f}" height="2" rx="1" fill="url(#edge)"/>
<text x="20" y="30" class="t">&gt; {escape(title)}<tspan class="cur" fill="{CYAN}">_</tspan></text>
{body}
</svg>
"""


def stats_card(repos: list[dict], metrics: dict[str, int]) -> str:
    stars = sum(r["stargazers_count"] for r in repos)
    forks = sum(r["forks_count"] for r in repos)
    rows = [
        ("★", "Stars recebidas", stars),
        ("⎇", "Commits (12 meses)", metrics["commits"]),
        ("⇄", "Pull requests", metrics["prs"]),
        ("◎", "Issues", metrics["issues"]),
        ("▣", "Repositórios públicos", len(repos)),
        ("⑂", "Forks", forks),
    ]
    body = []
    for i, (icon, label, value) in enumerate(rows):
        y = 62 + i * 24
        body.append(
            '<g>'
            f'<text x="22" y="{y}" fill="{CYAN}" font-size="13">{icon}</text>'
            f'<text x="44" y="{y}" class="l">{label}</text>'
            f'<text x="300" y="{y}" class="v" text-anchor="end">{value}</text></g>'
        )
    contribs = metrics["contribs"]
    level = min(contribs / 600, 1.0)
    cx, cy, r = 385, 112, 46
    circ = 2 * 3.14159 * r
    body.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{GRID}" stroke-width="7"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{CYAN}" stroke-width="7" stroke-linecap="round"'
        f' stroke-dasharray="{circ * level:.1f} {circ:.1f}" transform="rotate(-90 {cx} {cy})">'
        f'<animate attributeName="stroke-dasharray" from="0 {circ:.1f}" to="{circ * level:.1f} {circ:.1f}" dur="1.2s" fill="freeze"/></circle>'
        f'<text x="{cx}" y="{cy + 2}" text-anchor="middle" fill="#e6f7ff" font-size="22" font-weight="700">{contribs}</text>'
        f'<text x="{cx}" y="{cy + 20}" text-anchor="middle" class="d">contribuições/ano</text>'
    )
    return frame(470, 210, f"stats --user {USER}", "\n".join(body))


def langs_card(langs: dict[str, int]) -> str:
    top = list(langs.items())[:8]
    total = sum(v for _, v in top) or 1
    body, x = [], 20.0
    body.append('<clipPath id="bar"><rect x="20" y="46" width="430" height="9" rx="4.5"/></clipPath><g clip-path="url(#bar)">')
    for lang, size in top:
        w = 430 * size / total
        body.append(f'<rect x="{x:.1f}" y="46" width="{w + 0.5:.1f}" height="9" fill="{LANG_COLORS.get(lang, CYAN)}"/>')
        x += w
    body.append("</g>")
    for i, (lang, size) in enumerate(top):
        col, row = i % 2, i // 2
        px, py = 22 + col * 220, 82 + row * 24
        pct = 100 * size / total
        body.append(
            '<g>'
            f'<circle cx="{px + 5}" cy="{py - 4}" r="5" fill="{LANG_COLORS.get(lang, CYAN)}"/>'
            f'<text x="{px + 18}" y="{py}" class="l">{escape(lang)}</text>'
            f'<text x="{px + 200}" y="{py}" class="v" text-anchor="end">{pct:.1f}%</text></g>'
        )
    return frame(470, 82 + ((len(top) + 1) // 2) * 24, "lang --top", "\n".join(body))


def activity_card(days: dict[str, int]) -> str:
    w, h, l, r, t, b = 940, 260, 50, 24, 56, 40
    vals = list(days.values())
    peak = max(max(vals), 4)
    step = (w - l - r) / (len(vals) - 1)
    pts = [(l + i * step, t + (h - t - b) * (1 - v / peak)) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{l},{h - b} {line} {w - r},{h - b}"
    body = [
        '<defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{CYAN}" stop-opacity=".35"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></linearGradient>'
        '<clipPath id="reveal"><rect x="0" y="0" width="0" height="300"><animate attributeName="width" from="0" to="960" dur="1.6s" fill="freeze"/></rect></clipPath></defs>'
    ]
    for i in range(5):
        y = t + (h - t - b) * i / 4
        body.append(f'<line x1="{l}" x2="{w - r}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}" stroke-dasharray="3 5"/>')
        body.append(f'<text x="{l - 10}" y="{y + 4:.1f}" class="d" text-anchor="end">{round(peak * (1 - i / 4))}</text>')
    keys = list(days)
    for i in range(0, len(keys), 5):
        d = dt.date.fromisoformat(keys[i])
        body.append(f'<text x="{pts[i][0]:.1f}" y="{h - b + 20}" class="d" text-anchor="middle">{d:%d/%m}</text>')
    body.append(f'<g clip-path="url(#reveal)"><polygon points="{area}" fill="url(#area)"/>'
                f'<polyline points="{line}" fill="none" stroke="{CYAN}" stroke-width="2.2" stroke-linejoin="round"/>')
    for (x, y), v in zip(pts, vals):
        if v:
            body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{BG}" stroke="{CYAN}" stroke-width="1.8"/>')
    body.append("</g>")
    body.append(f'<text x="{w - r}" y="30" class="d" text-anchor="end">{sum(vals)} contribuições nos últimos 31 dias</text>')
    return frame(w, h, "activity --last 31d", "\n".join(body))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    repos = fetch_repos()
    days, metrics = fetch_activity()
    (OUT / "stats.svg").write_text(stats_card(repos, metrics), encoding="utf-8")
    (OUT / "langs.svg").write_text(langs_card(fetch_languages(repos)), encoding="utf-8")
    (OUT / "activity.svg").write_text(activity_card(days), encoding="utf-8")
    print(f"ok: {len(repos)} repos, metrics={metrics}")


if __name__ == "__main__":
    main()
