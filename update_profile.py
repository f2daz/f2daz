"""Rendert dark_mode.svg / light_mode.svg (neofetch-Stil) mit aktuellen GitHub-Zahlen.

Läuft täglich per GitHub Actions. Nur Standardbibliothek.
Lokal ohne Token: `python update_profile.py --offline` (nur öffentliche REST-Daten).
"""
import html
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timezone

USER = "f2daz"
SINCE = date(2015, 3, 3)  # GitHub-Account angelegt
W = 54  # Breite der Info-Spalte in Zeichen

# ── Inhalte: hier anpassen ─────────────────────────────────────────────
PROFILE = [
    ("OS", "Debian, macOS"),
    ("Host", "Stadtwerk Haßfurt"),
    ("Kernel", "Energiewirtschaft & Smart Metering"),
    ("IDE", "Claude Code, VS Code"),
    None,
    ("Languages.Programming", "Python, TypeScript, JavaScript"),
    ("Languages.Real", "Deutsch, Englisch"),
    ("Hobbies", "Home Assistant, ESP32, PCB-Design"),
]
CONTACT = [
    ("Web", "zoesch.art"),
    ("GitHub", "github.com/f2daz"),
]
# ───────────────────────────────────────────────────────────────────────

ART = r"""
               ::::::-----:
          :--      ::------:
         --:      :  -----=--:
        --::  :: :--::----====-:
     : :--::    :-:--==++***+*+--::
     :::-::---===+**##%@@@@@@@@#+==
    :::-=---=+**##%%%@@@@@@@@@@@#*+=
   :-=-=+---=+*####%%@@@@@@@@@@@%***:
   -++==+----=**##%%%%@@@@@@@@@@%%#+:
   =***==---==*##%%%%%%@@@@@@@@@@%*+: ::
   +*%%*---==+*#%%@@%%@@@@@@@@@@@@%+-=:
  =-+@%#+--==+++++##**+***####%%%@%+%%+
 := +*++=-:::  ::=+++===-::-=+*##+*#%*= -:
  :-*#-------::  :-:==%+-=-+***%%*@*%*  :
   -+@=-=---===- ::*@**@**#%%@@@@%@#%:
   -*@*=++*+++=--- +@@*%@@@%%%@@#%%#%
    *%#-==+**+=-: -*@@@##%%%##%%%@%*=
    -#*-:--====  ::+%@%@%*#%%@@@@@%+    ::
     +*==:-=++-     +%*#@@%%%@@%@%*=    ::
     ++==-:==-:    ===***#*#%%%@#**-
     -+=--:-:   ::-++=****+=*#%*+++     -:
      -=--:       -=**###%%+=*#=++:     :
       ---:   :::-===+*#%%##+++===::
      -::-:    ::--==+*##*++*+--%= -:
     :=   :::  :-=++***#*+*+-:=%@ :--:::
     =-      :  :--=+-=++==--#@@= -----::
    :-         ::  -::::::-*%@%+ :-----: :
    :-                 -=*%%%%+  ------ ::
     :             :-=+*#%%%#=  :------::
              --=--=+**#####=  ::------::
"""

# GITHUB_TOKEN (Actions) liefert Contribution-Zahlen; optional ACCESS_TOKEN (PAT)
# sieht auch private Repos für Repo-Liste und LOC. Jeweils Fallback auf den anderen.
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("ACCESS_TOKEN") or ""
PRIV_TOKEN = os.environ.get("ACCESS_TOKEN") or TOKEN


def gh(url, payload=None, token=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-readme"}
    if token or TOKEN:
        headers["Authorization"] = f"Bearer {token or TOKEN}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode() if payload else None, headers=headers)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or "{}")


def graphql(query, variables=None, token=None):
    resp = gh("https://api.github.com/graphql", {"query": query, "variables": variables or {}}, token)
    if resp.get("errors"):
        raise RuntimeError(resp["errors"])
    return resp["data"]


def uptime(b, t):
    months = (t.year - b.year) * 12 + t.month - b.month - (t.day < b.day)
    anchor_y, anchor_m = b.year + (b.month - 1 + months) // 12, (b.month - 1 + months) % 12 + 1
    days = (t - date(anchor_y, anchor_m, min(b.day, 28 if anchor_m == 2 else 30))).days
    return months // 12, months % 12, days


def fetch_stats():
    years = range(SINCE.year, datetime.now(timezone.utc).year + 1)
    aliases = "\n".join(
        f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y + 1}-01-01T00:00:00Z")'
        " { totalCommitContributions restrictedContributionsCount }"
        for y in years
    )
    contrib = graphql(f'query {{ user(login: "{USER}") {{ {aliases} }} }}')["user"]
    commits = sum(v["totalCommitContributions"] + v["restrictedContributionsCount"] for v in contrib.values())
    u = graphql(f"""
    query {{
      user(login: "{USER}") {{
        id
        followers {{ totalCount }}
        repositories(first: 100, ownerAffiliations: OWNER) {{
          totalCount
          nodes {{ name stargazerCount isFork }}
        }}
        repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) {{
          totalCount
        }}
      }}
    }}""", token=PRIV_TOKEN)["user"]
    stats = {
        "followers": u["followers"]["totalCount"],
        "repos": u["repositories"]["totalCount"],
        "contributed": u["repositoriesContributedTo"]["totalCount"],
        "stars": sum(n["stargazerCount"] for n in u["repositories"]["nodes"]),
        "commits": commits,
    }
    stats.update(loc([n["name"] for n in u["repositories"]["nodes"] if not n["isFork"]], u["id"]))
    return stats


def fetch_stats_offline():
    """Nur öffentliche REST-Daten, ohne Token – für die lokale Vorschau."""
    user = gh(f"https://api.github.com/users/{USER}")
    repos = gh(f"https://api.github.com/users/{USER}/repos?per_page=100")
    return {"followers": user["followers"], "repos": user["public_repos"], "contributed": "?",
            "stars": sum(r["stargazers_count"] for r in repos), "commits": None,
            "loc": None, "loc_add": None, "loc_del": None}


LOC_QUERY = """
query($owner: String!, $name: String!, $id: ID!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef { target { ... on Commit {
      history(first: 100, author: {id: $id}, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes { additions deletions }
      }
    } } }
  }
}"""


def loc(repo_names, user_id):
    add = rem = 0
    for name in repo_names:
        cursor = None
        try:
            while True:
                ref = graphql(LOC_QUERY, {"owner": USER, "name": name, "id": user_id, "cursor": cursor},
                              token=PRIV_TOKEN)["repository"]["defaultBranchRef"]
                if ref is None:
                    break
                h = ref["target"]["history"]
                add += sum(n["additions"] for n in h["nodes"])
                rem += sum(n["deletions"] for n in h["nodes"])
                if not h["pageInfo"]["hasNextPage"]:
                    break
                cursor = h["pageInfo"]["endCursor"]
        except Exception as e:  # einzelnes Repo darf scheitern
            print(f"loc {name}: {e}")
    return {"loc_add": add, "loc_del": rem, "loc": add - rem}


PALETTES = {
    "dark": {"bg": "#0d1117", "border": "#30363d", "art": "#8b949e", "h": "#58a6ff",
             "k": "#ffa657", "v": "#c9d1d9", "d": "#484f58", "g": "#3fb950", "r": "#f85149"},
    "light": {"bg": "#ffffff", "border": "#d0d7de", "art": "#57606a", "h": "#0969da",
              "k": "#953800", "v": "#24292f", "d": "#afb8c1", "g": "#1a7f37", "r": "#cf222e"},
}


def fmt(x):
    return "–" if x is None else f"{x:,}".replace(",", ".") if isinstance(x, int) else str(x)


def kv(key, val, width=W):
    val = fmt(val)
    dots = "." * max(width - len(key) - len(val) - 3, 1)
    return [(f"{key}: ", "k"), (dots + " ", "d"), (val, "v")]


def kv2(k1, v1, k2, v2):
    return kv(k1, v1, 29) + [(" | ", "d")] + kv(k2, v2, W - 32)


def rule(title):
    label = f"─ {title} "
    return [(label, "h"), ("─" * (W - len(label)), "d")]


def info_lines(s):
    y, m, d = uptime(SINCE, date.today())
    head = f"{USER}@github "
    lines = [[(head, "h"), ("─" * (W - len(head)), "d")], []]
    lines.append(kv("Uptime", f"{y} Jahre, {m} Monate, {d} Tage"))
    lines += [kv(*p) if p else [] for p in PROFILE]
    lines += [[], rule("Kontakt")] + [kv(*c) for c in CONTACT]
    lines += [[], rule("GitHub Stats"),
              kv2("Repos", f"{fmt(s['repos'])} {{Contrib: {fmt(s['contributed'])}}}", "Stars", s["stars"]),
              kv2("Commits", s["commits"], "Followers", s["followers"]),
              [("Lines of Code: ", "k"), (fmt(s["loc"]), "v"), (" ( ", "d"),
               (fmt(s["loc_add"]) + "++", "g"), (", ", "d"), (fmt(s["loc_del"]) + "--", "r"), (" )", "d")]]
    return lines


def render(mode, stats):
    p = PALETTES[mode]
    art = ART.strip("\n").split("\n")
    h = max(40 + len(art) * 15, 45 + len(info_lines(stats)) * 21) + 20
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="860" height="{h}" viewBox="0 0 860 {h}" '
        'font-family="Consolas, Menlo, \'DejaVu Sans Mono\', monospace" font-size="13px">',
        f'<rect x="0.5" y="0.5" width="859" height="{h - 1}" rx="10" fill="{p["bg"]}" stroke="{p["border"]}"/>',
    ]
    for i, line in enumerate(art):
        out.append(f'<text x="22" y="{40 + i * 15}" fill="{p["art"]}" xml:space="preserve">{html.escape(line)}</text>')
    for i, segs in enumerate(info_lines(stats)):
        if segs:
            spans = "".join(f'<tspan fill="{p[c]}">{html.escape(t)}</tspan>' for t, c in segs)
            out.append(f'<text x="385" y="{45 + i * 21}" xml:space="preserve">{spans}</text>')
    out.append("</svg>")
    return "\n".join(out)


def selfcheck():
    assert uptime(date(2015, 3, 3), date(2026, 11, 12)) == (11, 8, 9)
    assert uptime(date(2015, 3, 3), date(2016, 3, 3)) == (1, 0, 0)
    assert len("".join(t for t, _ in kv("OS", "Debian, macOS"))) == W
    assert len("".join(t for t, _ in kv2("Commits", 1234, "Followers", 8))) == W


if __name__ == "__main__":
    selfcheck()
    stats = fetch_stats_offline() if "--offline" in sys.argv else fetch_stats()
    print("stats:", stats)
    for mode in PALETTES:
        with open(f"{mode}_mode.svg", "w", encoding="utf-8") as f:
            f.write(render(mode, stats))
    print("wrote dark_mode.svg, light_mode.svg")
