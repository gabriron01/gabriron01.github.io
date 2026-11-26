#!/usr/bin/env python3
"""Convert Gabriel_Nsengiyumva_External_Resume.tex into index.html and sitemap.xml.

Zero external dependencies (Python 3 stdlib only). Reproduces the original 9516aee
HTML layout, styling, SEO tags, and Schema.org Person JSON-LD directly from LaTeX.

Usage:  python3 .github/scripts/tex2html.py Gabriel_Nsengiyumva_External_Resume.tex <out_dir>
"""
import datetime
import html
import json
import re
import subprocess
import sys
from pathlib import Path

PDF_FILENAME = "Gabriel_Nsengiyumva_External_Resume.pdf"
SITE_URL = "https://gabriron01.github.io/"

SEO_KEYWORDS = [
    "Gabriel Nsengiyumva", "Structural FEA Engineer", "Finite Element Analysis",
    "Computational Solid Mechanics", "SIMULIA Abaqus", "LS-DYNA", "Ansys Maxwell",
    "Magnetostatics", "Cohesive Zone Modeling", "Fracture Mechanics", "Drop Impact",
    "High-Performance Computing", "Google Cloud Platform", "Slurm", "Pixel Watch",
    "Tesla Cybertruck", "Tesla Cybercab", "Texas A&M University",
]

KNOWS_ABOUT = [
    "Finite Element Analysis", "Computational Solid Mechanics",
    "Explicit Drop Impact Simulation", "Nonlinear Contact Mechanics",
    "Fracture Mechanics", "Cohesive Zone Modeling", "3D Magnetostatics",
    "SIMULIA Abaqus", "LS-DYNA", "Ansys Mechanical and Maxwell",
    "High-Performance Computing", "Slurm Workload Manager", "Google Cloud Platform",
]

STYLE_CSS = """    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    html, body {
      background-color: #ffffff;
      color: #000000;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 14.5px;
      line-height: 1.52;
      -webkit-font-smoothing: antialiased;
    }

    .page {
      max-width: 800px;
      margin: 0 auto;
      padding: 36px 40px 56px;
      background-color: #ffffff;
      color: #000000;
    }

    .top-actions {
      display: flex;
      justify-content: flex-end;
      flex-wrap: wrap;
      gap: 14px;
      font-size: 12.5px;
      margin-bottom: 14px;
      padding-bottom: 8px;
      border-bottom: 1px solid #000000;
    }

    a {
      color: #000000;
      text-decoration: underline;
      text-decoration-color: #777777;
      text-underline-offset: 2px;
    }

    a:hover {
      text-decoration-color: #000000;
    }

    .action-btn {
      background: none;
      border: none;
      color: #000000;
      font-family: inherit;
      font-size: 12.5px;
      text-decoration: underline;
      text-decoration-color: #777777;
      text-underline-offset: 2px;
      cursor: pointer;
      padding: 0;
    }

    .action-btn:hover {
      text-decoration-color: #000000;
    }

    h1 {
      font-size: 24px;
      font-weight: 700;
      color: #000000;
      line-height: 1.2;
      margin-bottom: 4px;
    }

    .subtitle {
      font-size: 15px;
      font-weight: 400;
      color: #000000;
      margin-bottom: 3px;
    }

    .contact-line {
      font-size: 13.5px;
      color: #000000;
      margin-bottom: 12px;
    }

    .summary {
      font-size: 14.5px;
      color: #000000;
      margin-bottom: 16px;
    }

    h2 {
      font-size: 16px;
      font-weight: 700;
      color: #000000;
      border-bottom: 1px solid #000000;
      padding-bottom: 3px;
      margin-top: 18px;
      margin-bottom: 10px;
    }

    .role-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
      margin-bottom: 4px;
    }

    .role-title {
      font-size: 14.5px;
      font-weight: 700;
      color: #000000;
    }

    .role-meta {
      font-size: 13.5px;
      font-style: italic;
      font-weight: 400;
      color: #000000;
    }

    .substream {
      font-size: 14px;
      font-style: italic;
      font-weight: 400;
      color: #000000;
      margin-top: 8px;
      margin-bottom: 4px;
    }

    ul {
      margin: 0 0 8px 20px;
      padding: 0;
    }

    li {
      margin-bottom: 5px;
      color: #000000;
    }

    .edu-row {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
    }

    .edu-gpa {
      font-style: italic;
      white-space: nowrap;
    }

    .edu-note {
      font-size: 13.5px;
      font-style: italic;
      margin-top: 1px;
    }

    @media print {
      @page {
        size: letter;
        margin: 0.46in 0.52in;
      }
      html, body {
        font-size: 9.5pt;
        line-height: 1.35;
      }
      .page {
        max-width: 100%;
        padding: 0;
        margin: 0;
      }
      .top-actions {
        display: none !important;
      }
      a {
        text-decoration: none;
        color: #000000;
      }
    }"""


def esc(s):
    return html.escape(str(s), quote=False)


def attr(s):
    return html.escape(str(s), quote=True)


def strip_comments(tex):
    out = []
    for line in tex.splitlines():
        i = 0
        while i < len(line):
            if line[i] == "\\" and i + 1 < len(line):
                i += 2
                continue
            if line[i] == "%":
                line = line[:i]
                break
            i += 1
        out.append(line)
    return "\n".join(out)


def read_brace(s, pos):
    """Read a balanced {...} group starting at or after pos. Returns (content, next_pos)."""
    n = len(s)
    while pos < n and s[pos].isspace():
        pos += 1
    if pos >= n or s[pos] != "{":
        raise ValueError(f"Expected '{{' near: {s[pos:pos+40]!r}")
    depth = 0
    start = pos + 1
    i = pos
    while i < n:
        ch = s[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start:i], i + 1
        i += 1
    raise ValueError(f"Unclosed '{{' near: {s[pos:pos+40]!r}")


def read_args(s, pos, count):
    args = []
    for _ in range(count):
        val, pos = read_brace(s, pos)
        args.append(val)
    return args, pos


def skip_optional(s, pos):
    n = len(s)
    while pos < n and s[pos].isspace():
        pos += 1
    if pos < n and s[pos] == "[":
        depth = 0
        while pos < n:
            if s[pos] == "[":
                depth += 1
            elif s[pos] == "]":
                depth -= 1
                if depth == 0:
                    return pos + 1
            pos += 1
    return pos


def inline_to_html(s):
    """Convert inline LaTeX text (bold, italic, href, escapes, dashes) to clean HTML."""
    out = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "\\":
            if i + 1 >= n:
                break
            nxt = s[i + 1]
            if nxt in "&%$#_{}":
                out.append(esc(nxt))
                i += 2
                continue
            if nxt == " ":
                out.append(" ")
                i += 2
                continue
            if nxt == "\\":
                out.append("<br />")
                i += 2
                continue
            m = re.match(r"([a-zA-Z]+)\*?", s[i + 1:])
            if not m:
                i += 2
                continue
            cmd = m.group(1)
            pos = i + 1 + len(m.group(0))
            if cmd == "textbf":
                arg, pos = read_brace(s, pos)
                out.append(f"<strong>{inline_to_html(arg)}</strong>")
                i = pos
                continue
            if cmd in ("textit", "emph"):
                arg, pos = read_brace(s, pos)
                out.append(f"<em>{inline_to_html(arg)}</em>")
                i = pos
                continue
            if cmd == "texttt":
                arg, pos = read_brace(s, pos)
                out.append(f"<code>{inline_to_html(arg)}</code>")
                i = pos
                continue
            if cmd == "href":
                (url, label), pos = read_args(s, pos, 2)
                url = url.replace(r"\%", "%").replace(r"\#", "#").strip()
                extra = "" if url.startswith("mailto:") else ' target="_blank" rel="noopener"'
                out.append(f'<a href="{attr(url)}"{extra}>{inline_to_html(label)}</a>')
                i = pos
                continue
            if cmd == "url":
                url, pos = read_brace(s, pos)
                url = url.strip()
                out.append(f'<a href="{attr(url)}" target="_blank" rel="noopener">{esc(url)}</a>')
                i = pos
                continue
            if cmd == "textbar":
                out.append("|")
                i = pos
                continue
            if cmd == "textasciitilde":
                if pos < n and s[pos:pos + 2] == "{}":
                    pos += 2
                out.append("~")
                i = pos
                continue
            if cmd == "textbullet":
                out.append("·")
                i = pos
                continue
            if cmd in ("vspace", "hspace", "textcolor"):
                if cmd == "textcolor":
                    _, pos = read_brace(s, pos)
                    arg, pos = read_brace(s, pos)
                    out.append(inline_to_html(arg))
                else:
                    _, pos = read_brace(s, pos)
                i = pos
                continue
            if cmd in ("hfill", "par", "noindent", "small", "normalsize", "large", "LARGE"):
                i = pos
                continue
            if pos < n and s[pos] == "{":
                arg, pos = read_brace(s, pos)
                out.append(inline_to_html(arg))
                i = pos
                continue
            i = pos
            continue

        if ch == "$":
            end = s.find("$", i + 1)
            if end != -1:
                inner = s[i + 1:end].strip()
                if inner == r"\bullet":
                    out.append("·")
                elif inner == r"\vert":
                    out.append("|")
                elif inner == r"\sim":
                    out.append("~")
                else:
                    out.append(esc(inner))
                i = end + 1
                continue

        if ch == "~":
            out.append(" ")
            i += 1
            continue
        if s.startswith("---", i):
            out.append("—")
            i += 3
            continue
        if s.startswith("--", i):
            out.append("–")
            i += 2
            continue
        if s.startswith("``", i):
            out.append("“")
            i += 2
            continue
        if s.startswith("''", i):
            out.append("”")
            i += 2
            continue
        if ch in "{}":
            i += 1
            continue

        out.append(esc(ch))
        i += 1

    return re.sub(r"[ \t\n]+", " ", "".join(out)).strip()


def strip_tags(h):
    return html.unescape(re.sub(r"<[^>]+>", "", h)).strip()


def pretty_link_label(url, raw_label):
    u = url.lower()
    if "linkedin.com" in u:
        return "LinkedIn"
    if "github.com" in u:
        return "GitHub"
    if "scholar.google.com" in u:
        return "Google Scholar"
    return raw_label


def parse_itemize(block):
    """Parse \item, \eduitem{text}{gpa}, and \eduitemnote{text}{gpa}{note} entries in order."""
    entries = []
    i = 0
    n = len(block)
    while i < n:
        m = re.search(r"\\(eduitemnote|eduitem|item)\b", block[i:])
        if not m:
            break
        cmd = m.group(1)
        pos = i + m.end()
        if cmd == "eduitemnote":
            (text, gpa, note), pos = read_args(block, pos, 3)
            entries.append({"kind": "edu", "text": text, "gpa": gpa, "note": note})
            i = pos
        elif cmd == "eduitem":
            (text, gpa), pos = read_args(block, pos, 2)
            entries.append({"kind": "edu", "text": text, "gpa": gpa, "note": ""})
            i = pos
        else:
            pos = skip_optional(block, pos)
            nxt = re.search(r"\\(eduitemnote|eduitem|item)\b", block[pos:])
            end = pos + nxt.start() if nxt else n
            text = block[pos:end].strip()
            if text:
                entries.append({"kind": "plain", "text": text})
            i = end
    return entries


def parse_document(tex_src):
    clean = strip_comments(tex_src)
    m = re.search(r"\\begin\{document\}(.*)\\end\{document\}", clean, re.S)
    if not m:
        sys.exit("Could not find \\begin{document}...\\end{document} in LaTeX source")
    body = m.group(1)

    doc = {
        "name": "",
        "subtitle": "",
        "contacts": [],
        "summary": "",
        "sections": [],
    }
    current_section = None

    i = 0
    n = len(body)
    while i < n:
        while i < n and body[i].isspace():
            i += 1
        if i >= n:
            break

        if body[i] == "\\":
            mc = re.match(r"\\([a-zA-Z]+)\*?", body[i:])
            if not mc:
                i += 1
                continue
            cmd = mc.group(1)
            pos = i + len(mc.group(0))

            if cmd == "name":
                arg, pos = read_brace(body, pos)
                doc["name"] = inline_to_html(arg)
                i = pos
                continue
            if cmd == "subtitle":
                arg, pos = read_brace(body, pos)
                doc["subtitle"] = inline_to_html(arg)
                i = pos
                continue
            if cmd == "contact":
                arg, pos = read_brace(body, pos)
                doc["contacts"].append(arg)
                i = pos
                continue
            if cmd == "summary":
                arg, pos = read_brace(body, pos)
                doc["summary"] = inline_to_html(arg)
                i = pos
                continue
            if cmd == "section":
                arg, pos = read_brace(body, pos)
                current_section = {"title": inline_to_html(arg), "blocks": []}
                doc["sections"].append(current_section)
                i = pos
                continue
            if cmd == "roleheader":
                (org, title, place, dates), pos = read_args(body, pos, 4)
                if current_section is None:
                    current_section = {"title": "Experience", "blocks": []}
                    doc["sections"].append(current_section)
                current_section["blocks"].append({
                    "type": "role",
                    "org": inline_to_html(org),
                    "title": inline_to_html(title),
                    "place": inline_to_html(place),
                    "dates": inline_to_html(dates),
                })
                i = pos
                continue
            if cmd == "subhead":
                arg, pos = read_brace(body, pos)
                if current_section is not None:
                    current_section["blocks"].append({
                        "type": "subhead",
                        "text": inline_to_html(arg),
                    })
                i = pos
                continue
            if cmd == "begin":
                env, pos = read_brace(body, pos)
                end_tag = f"\\end{{{env}}}"
                end_idx = body.find(end_tag, pos)
                if end_idx == -1:
                    sys.exit(f"Unclosed \\begin{{{env}}}")
                inner = body[pos:end_idx]
                if env == "itemize":
                    inner = inner[skip_optional(inner, 0):]
                    if current_section is not None:
                        current_section["blocks"].append({
                            "type": "list",
                            "items": parse_itemize(inner),
                        })
                i = end_idx + len(end_tag)
                continue
            if cmd in ("vspace", "hspace"):
                _, pos = read_brace(body, pos)
                i = pos
                continue
            if cmd in ("par", "noindent", "hfill", "newpage", "clearpage"):
                i = pos
                continue
            i = pos
            continue

        end = re.search(
            r"\n\s*\n|\\(?:section|roleheader|subhead|begin|name|subtitle|contact|summary)\b",
            body[i:],
        )
        chunk = body[i:i + end.start()] if end else body[i:]
        i = i + end.start() if end else n
        rendered = inline_to_html(chunk)
        if rendered and current_section is not None:
            current_section["blocks"].append({"type": "para", "text": rendered})

    return doc


def parse_contacts(raw_contacts):
    items = []
    profiles = []
    email = ""
    location = ""
    site_url = SITE_URL

    for raw in raw_contacts:
        pieces = re.split(r"(?:\\[,;\s]|\s)*\$\\bullet\$(?:\\[,;\s]|\s)*|\s*\\textbullet\s*", raw)
        for p in pieces:
            p = p.strip()
            if not p:
                continue
            hm = re.match(r"^\\href\{([^}]+)\}\{(.+)\}$", p)
            if hm:
                url = hm.group(1).replace(r"\%", "%").replace(r"\#", "#").strip()
                label = strip_tags(inline_to_html(hm.group(2)))
                if url.startswith("mailto:"):
                    email = url[len("mailto:"):]
                    items.append(f'<a href="{attr(url)}">{esc(label)}</a>')
                elif "github.io" in url.lower():
                    site_url = url if url.endswith("/") else url + "/"
                    site_label = re.sub(r"^https?://", "", site_url).rstrip("/")
                    items.append(f'<a href="{attr(url)}" target="_blank" rel="noopener">{esc(site_label)}</a>')
                else:
                    short = pretty_link_label(url, label)
                    profiles.append((short, url))
                    items.append(f'<a href="{attr(url)}" target="_blank" rel="noopener">{esc(short)}</a>')
            else:
                txt = inline_to_html(p)
                if not location:
                    location = strip_tags(txt)
                items.append(txt)

    return items, profiles, email, location, site_url


def render_html(doc):
    full_name = strip_tags(doc["name"])
    subtitle = strip_tags(doc["subtitle"])
    summary = strip_tags(doc["summary"])
    contact_items, profiles, email, location, site_url = parse_contacts(doc["contacts"])

    if "," in full_name:
        person_name, suffix = [x.strip() for x in full_name.split(",", 1)]
    else:
        person_name, suffix = full_name, ""

    works_for = ""
    alumni = []
    for sec in doc["sections"]:
        for blk in sec["blocks"]:
            if blk["type"] == "role" and not works_for:
                works_for = strip_tags(blk["org"])
            if "education" in strip_tags(sec["title"]).lower() and blk["type"] == "list":
                for entry in blk["items"]:
                    if entry["kind"] == "edu":
                        plain = strip_tags(inline_to_html(entry["text"]))
                        if "," in plain:
                            school = plain.rsplit(",", 1)[1].strip()
                            school = re.sub(r"\s*\([^)]*\)$", "", school).replace("–", "-")
                            if school:
                                alumni.append(school)

    loc_m = re.match(r"^(.+?),\s*([A-Z]{2})(?:,\s*([A-Z]{2,}))?$", location)
    address = {
        "@type": "PostalAddress",
        "addressLocality": loc_m.group(1) if loc_m else location,
        "addressRegion": loc_m.group(2) if loc_m else "",
        "addressCountry": (loc_m.group(3) or "US") if loc_m else "US",
    }

    person_ld = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": person_name,
        "honorificSuffix": suffix,
        "jobTitle": subtitle,
        "url": site_url,
        "email": f"mailto:{email}" if email else "",
        "address": address,
        "worksFor": {"@type": "Organization", "name": works_for},
        "alumniOf": [{"@type": "CollegeOrUniversity", "name": a} for a in alumni],
        "knowsAbout": KNOWS_ABOUT,
        "sameAs": [u for _, u in profiles],
    }
    ld_json = "\n".join(
        "  " + line
        for line in json.dumps(person_ld, indent=2, ensure_ascii=False).replace("</", "<\\/").splitlines()
    )

    page_title = f"{full_name} — {subtitle}"
    og_desc = summary
    twitter_desc = "Structural FEA engineer specializing in hardware drop-impact, fracture, and magnetostatic simulation."

    nav = [
        '    <nav class="top-actions" aria-label="Links and Downloads">',
        f'      <a href="{attr(PDF_FILENAME)}" download>Download Resume (PDF)</a>',
    ]
    for label, url in profiles:
        nav += [
            "      <span>·</span>",
            f'      <a href="{attr(url)}" target="_blank" rel="noopener">{esc(label)}</a>',
        ]
    nav += [
        "      <span>·</span>",
        '      <button type="button" class="action-btn" onclick="window.print()">Print</button>',
        "    </nav>",
    ]

    contact_lines = [f"        {c} ·" for c in contact_items[:-1]] + (
        [f"        {contact_items[-1]}"] if contact_items else []
    )

    header = (
        [
            "    <header>",
            f"      <h1>{doc['name']}</h1>",
            f'      <div class="subtitle">{doc["subtitle"]}</div>',
            '      <div class="contact-line">',
        ]
        + contact_lines
        + [
            "      </div>",
            '      <p class="summary">',
            f"        {doc['summary']}",
            "      </p>",
            "    </header>",
        ]
    )

    sections_html = []
    for sec in doc["sections"]:
        sec_title_plain = strip_tags(sec["title"])
        is_edu = "education" in sec_title_plain.lower()
        lines = ["    <section>", f"      <h2>{sec['title']}</h2>"]
        for blk in sec["blocks"]:
            btype = blk["type"]
            if btype == "role":
                lines += [
                    "",
                    '      <div class="role-header">',
                    f'        <span class="role-title">{blk["org"]} — {blk["title"]}</span>',
                    f'        <span class="role-meta">{blk["place"]} | {blk["dates"]}</span>',
                    "      </div>",
                ]
            elif btype == "subhead":
                lines += ["", f'      <div class="substream">{blk["text"]}</div>']
            elif btype == "para":
                lines.append(f"      <p>{blk['text']}</p>")
            elif btype == "list":
                lines.append("      <ul>")
                for entry in blk["items"]:
                    if entry["kind"] == "edu":
                        lines += [
                            "        <li>",
                            '          <div class="edu-row">',
                            f"            <span>{inline_to_html(entry['text'])}</span>",
                            f'            <span class="edu-gpa">{inline_to_html(entry["gpa"])}</span>',
                            "          </div>",
                        ]
                        if entry["note"]:
                            lines.append(f'          <div class="edu-note">{inline_to_html(entry["note"])}</div>')
                        lines.append("        </li>")
                        continue
                    raw_item = entry["text"]
                    if is_edu:
                        gm = re.search(r"(?:---|\\hfill)\s*\\textit\{(GPA:[^}]+)\}\s*$", raw_item)
                        if gm:
                            left = inline_to_html(raw_item[:gm.start()].strip())
                            gpa = inline_to_html(gm.group(1))
                            lines += [
                                "        <li>",
                                '          <div class="edu-row">',
                                f"            <span>{left}</span>",
                                f'            <span class="edu-gpa">{gpa}</span>',
                                "          </div>",
                                "        </li>",
                            ]
                            continue
                    lines.append(f"        <li>{inline_to_html(raw_item)}</li>")
                lines.append("      </ul>")
        lines.append("    </section>")
        sections_html.append("\n".join(lines))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(page_title)}</title>
  <meta name="author" content="{attr(full_name)}" />
  <meta name="description" content="{attr(full_name + ' — ' + summary)}" />
  <meta name="keywords" content="{attr(', '.join(SEO_KEYWORDS))}" />
  <link rel="canonical" href="{attr(site_url)}" />

  <!-- OpenGraph / Social Discovery -->
  <meta property="og:type" content="profile" />
  <meta property="og:title" content="{attr(page_title)}" />
  <meta property="og:description" content="{attr(og_desc)}" />
  <meta property="og:url" content="{attr(site_url)}" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="{attr(page_title)}" />
  <meta name="twitter:description" content="{attr(twitter_desc)}" />

  <!-- Schema.org Person Structured Data for Search Indexing -->
  <script type="application/ld+json">
{ld_json}
  </script>

  <style>
{STYLE_CSS}
  </style>
</head>
<body>
  <main class="page">
{chr(10).join(nav)}

{chr(10).join(header)}

{chr(10).join(chr(10) + s for s in sections_html).lstrip(chr(10))}
  </main>
</body>
</html>
""", site_url


def sitemap_lastmod(src_path):
    today = datetime.date.today().isoformat()
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(src_path)],
            capture_output=True, text=True, cwd=src_path.parent,
        ).stdout.strip()
        return out or today
    except OSError:
        return today


def render_sitemap(site_url, lastmod):
    entries = [(site_url, "1.0"), (site_url + PDF_FILENAME, "0.9")]
    body = "".join(
        f"  <url>\n    <loc>{esc(loc)}</loc>\n    <lastmod>{lastmod}</lastmod>\n"
        f"    <changefreq>monthly</changefreq>\n    <priority>{prio}</priority>\n  </url>\n"
        for loc, prio in entries
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + body
        + "</urlset>\n"
    )


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: tex2html.py <resume.tex> <out_dir>")
    src = Path(sys.argv[1]).resolve()
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = parse_document(src.read_text(encoding="utf-8"))
    html_out, site_url = render_html(doc)
    (out_dir / "index.html").write_text(html_out, encoding="utf-8")
    (out_dir / "sitemap.xml").write_text(render_sitemap(site_url, sitemap_lastmod(src)), encoding="utf-8")
    print(f"Generated {out_dir / 'index.html'} and {out_dir / 'sitemap.xml'}")


if __name__ == "__main__":
    main()
