#!/usr/bin/env python3
"""Build the website (index.html), the one-page PDF and sitemap.xml from resume.yaml (+ site.yaml).

    python build.py              build everything (site + PDF + sitemap)
    python build.py --check      validate YAML only, write nothing
    python build.py --html-only  build site + sitemap, skip the PDF
    python build.py --lint       run style and ATS checks (warnings only, exits 0)

Edit resume.yaml (content) and site.yaml (identity, links, PDF/SEO settings), never the
generated files. Any bullet, group, or entry may carry `only: web` or `only: pdf`.
"""
import argparse
import datetime
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is missing. Run ./publish.sh (it creates .venv), or: "
             "python3 -m venv .venv && .venv/bin/pip install -r requirements.txt")

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
DATA = ROOT / "resume.yaml"
SITE = ROOT / "site.yaml"

META_KEYS = ("name", "suffix", "subtitle", "location", "email", "phone", "site", "links", "pdf")


# --------------------------------------------------------------------------- data
def fail(msg):
    sys.exit(f"YAML validation error: {msg}")


def _read_yaml(path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        sys.exit(f"{path.name} is not valid YAML:\n{exc}")


def parse_address(location):
    m = re.match(r"^(.+?),\s*([A-Z]{2})(?:,\s*([A-Z]{2,}))?$", str(location).strip())
    if m:
        return {"locality": m.group(1), "region": m.group(2), "country": m.group(3) or "US"}
    return {"locality": str(location).strip(), "region": "", "country": "US"}


def link_url(val):
    return val["url"] if isinstance(val, dict) else str(val)


def link_pdf_label(label, val):
    if isinstance(val, dict) and val.get("show_in_pdf"):
        return str(val["show_in_pdf"])
    return str(label)


def raw_groups(role):
    if role.get("groups"):
        return role["groups"]
    if role.get("bullets"):
        return [{"bullets": role["bullets"]}]
    return []


def skill_items(d):
    raw = d["skills"]
    if isinstance(raw, dict):
        items = []
        for label, val in raw.items():
            if isinstance(val, dict):
                items.append({"label": label, "text": val.get("text", ""), "only": val.get("only")})
            else:
                items.append({"label": label, "text": val})
        return items
    return list(raw)


def load():
    content = _read_yaml(DATA)
    if not isinstance(content, dict):
        fail("resume.yaml top level must be a mapping")

    data = dict(content)
    if SITE.exists():
        site_cfg = _read_yaml(SITE)
        if not isinstance(site_cfg, dict):
            fail("site.yaml top level must be a mapping")
        meta = {k: site_cfg[k] for k in META_KEYS if k in site_cfg}
        if isinstance(data.get("meta"), dict):
            meta.update(data["meta"])
        data["meta"] = meta
        seo = dict(site_cfg.get("seo") or {})
        if isinstance(data.get("seo"), dict):
            seo.update(data["seo"])
        data["seo"] = seo

    # Derive omitted SEO fields from content/meta so they aren't duplicated
    seo = data.get("seo")
    meta = data.get("meta")
    if isinstance(seo, dict) and isinstance(meta, dict):
        if not seo.get("address") and meta.get("location"):
            seo["address"] = parse_address(meta["location"])
        if not seo.get("works_for") and isinstance(data.get("experience"), list) and data["experience"]:
            seo["works_for"] = data["experience"][0].get("org", "")
        if not seo.get("alumni_of") and isinstance(data.get("education"), list):
            seo["alumni_of"] = [
                re.sub(r"\s*\([^)]*\)$", "", str(e.get("school", ""))).replace("–", "-")
                for e in data["education"] if isinstance(e, dict) and e.get("school")
            ]

    validate(data)
    return data


def validate(d):
    if not isinstance(d, dict):
        fail("top level must be a mapping")
    for key in ("meta", "seo", "summary", "experience", "skills", "education", "languages"):
        if key not in d:
            fail(f"missing required section '{key}'")
    m = d["meta"]
    if not isinstance(m, dict):
        fail("'meta' must be a mapping")
    for key in META_KEYS:
        if not m.get(key):
            fail(f"meta.{key} is missing or empty")
    if not isinstance(m["links"], dict):
        fail("meta.links must be a mapping")
    for label, val in m["links"].items():
        if isinstance(val, dict) and not val.get("url"):
            fail(f"meta.links.{label}: missing 'url'")
        url = link_url(val)
        if not re.match(r"https?://\S+$", url):
            fail(f"meta.links.{label} is not a valid http(s) URL: {url!r}")
    if not re.match(r"https?://\S+/$", m["site"]):
        fail("meta.site must be an http(s) URL ending in '/'")
    fonts = m["pdf"].get("font_pt")
    if not fonts or not all(isinstance(f, (int, float)) for f in fonts):
        fail("meta.pdf.font_pt must be a list of numbers, e.g. [10, 9.5, 9]")

    def check_only(item, where):
        if isinstance(item, dict) and item.get("only") not in (None, "web", "pdf"):
            fail(f"{where}: 'only' must be 'web' or 'pdf', got {item['only']!r}")

    for r, role in enumerate(d["experience"], 1):
        for key in ("org", "title", "place", "dates"):
            if not role.get(key):
                fail(f"experience #{r}: '{key}' is missing or empty")
        if not (role.get("groups") or role.get("bullets")):
            fail(f"experience #{r}: must define either 'groups' or 'bullets'")
        if role.get("groups") and role.get("bullets"):
            fail(f"experience #{r}: define either 'groups' or 'bullets', not both")
        check_only(role, f"experience #{r}")
        for g, grp in enumerate(raw_groups(role), 1):
            check_only(grp, f"experience #{r} group #{g}")
            if not grp.get("bullets"):
                fail(f"experience #{r} group #{g}: no bullets")
            for b, bullet in enumerate(grp["bullets"], 1):
                check_only(bullet, f"experience #{r} group #{g} bullet #{b}")
                if not text_of(bullet).strip():
                    fail(f"experience #{r} group #{g} bullet #{b} is empty")

    if not isinstance(d["skills"], (list, dict)) or not d["skills"]:
        fail("'skills' must be a non-empty list or mapping")
    for s in skill_items(d):
        if not (s.get("label") and s.get("text")):
            fail(f"skills entry needs 'label' and 'text': {s}")
        check_only(s, f"skill {s.get('label')}")

    for e in d["education"]:
        if not (e.get("degree") and e.get("school")):
            fail(f"education entry needs 'degree' and 'school': {e}")
        check_only(e, f"education {e.get('degree')}")
        if e.get("note_only") not in (None, "web", "pdf"):
            fail(f"education {e.get('degree')}: 'note_only' must be 'web' or 'pdf'")


def text_of(item):
    return item["text"] if isinstance(item, dict) else item


def visible(item, target):
    only = item.get("only") if isinstance(item, dict) else None
    return only in (None, target)


def groups_for(role, target):
    out = []
    for grp in raw_groups(role):
        if not visible(grp, target):
            continue
        bullets = [text_of(b) for b in grp["bullets"] if visible(b, target)]
        if bullets:
            out.append({"heading": grp.get("heading"), "bullets": bullets})
    return out


def roles_for(d, target):
    return [r for r in d["experience"] if visible(r, target) and groups_for(r, target)]


# --------------------------------------------------------------------------- HTML
def esc(s):
    return html.escape(str(s), quote=False)


def attr(s):
    return html.escape(str(s), quote=True)


def full_name(m):
    return f"{m['name']}, {m['suffix']}"


def link_a(label, url, new_tab=True):
    extra = ' target="_blank" rel="noopener"' if new_tab else ""
    return f'<a href="{attr(url)}"{extra}>{esc(label)}</a>'


def render_jsonld(d):
    m, seo = d["meta"], d["seo"]
    obj = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": m["name"],
        "honorificSuffix": m["suffix"],
        "jobTitle": m["subtitle"],
        "url": m["site"],
        "email": f"mailto:{m['email']}",
        "address": {
            "@type": "PostalAddress",
            "addressLocality": seo["address"]["locality"],
            "addressRegion": seo["address"]["region"],
            "addressCountry": seo["address"]["country"],
        },
        "worksFor": {"@type": "Organization", "name": seo["works_for"]},
        "alumniOf": [{"@type": "CollegeOrUniversity", "name": n} for n in seo["alumni_of"]],
        "knowsAbout": seo["knows_about"],
        "sameAs": [link_url(v) for v in m["links"].values()],
    }
    text = json.dumps(obj, indent=2, ensure_ascii=False).replace("</", "<\\/")
    return "\n".join("  " + line for line in text.splitlines())


def render_html(d):
    m, seo = d["meta"], d["seo"]
    title = f"{full_name(m)} — {m['subtitle']}"
    css = "\n".join(("    " + ln) if ln.strip() else "" for ln in
                    (ROOT / "templates" / "style.css").read_text(encoding="utf-8").splitlines())
    site_label = re.sub(r"^https?://", "", m["site"]).rstrip("/")

    head = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(title)}</title>
  <meta name="author" content="{attr(full_name(m))}" />
  <meta name="description" content="{attr(full_name(m) + ' — ' + d['summary'])}" />
  <meta name="keywords" content="{attr(', '.join(seo['keywords']))}" />
  <link rel="canonical" href="{attr(m['site'])}" />

  <!-- OpenGraph / Social Discovery -->
  <meta property="og:type" content="profile" />
  <meta property="og:title" content="{attr(title)}" />
  <meta property="og:description" content="{attr(seo['og_description'])}" />
  <meta property="og:url" content="{attr(m['site'])}" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="{attr(title)}" />
  <meta name="twitter:description" content="{attr(seo['twitter_description'])}" />

  <!-- Schema.org Person Structured Data for Search Indexing -->
  <script type="application/ld+json">
{render_jsonld(d)}
  </script>

  <style>
{css}
  </style>
</head>
"""

    nav = ['    <nav class="top-actions" aria-label="Links and Downloads">',
           f'      <a href="{attr(m["pdf"]["file"])}" download>Download Resume (PDF)</a>']
    for label, val in m["links"].items():
        nav += ["      <span>·</span>", "      " + link_a(label, link_url(val))]
    nav += ["      <span>·</span>",
            '      <button type="button" class="action-btn" onclick="window.print()">Print</button>',
            "    </nav>"]

    contact_items = [esc(m["location"]),
                     link_a(m["email"], f"mailto:{m['email']}", new_tab=False),
                     esc(m["phone"])]
    contact_items += [link_a(label, link_url(val)) for label, val in m["links"].items()]
    contact_items.append(link_a(site_label, m["site"]))
    contact = [f"        {item} ·" for item in contact_items[:-1]] + [f"        {contact_items[-1]}"]

    header = (["    <header>",
               f"      <h1>{esc(full_name(m))}</h1>",
               f'      <div class="subtitle">{esc(m["subtitle"])}</div>',
               '      <div class="contact-line">'] + contact +
              ["      </div>",
               '      <p class="summary">',
               f"        {esc(d['summary'])}",
               "      </p>",
               "    </header>"])

    # Experience
    exp = ["    <section>", "      <h2>Experience</h2>", ""]
    roles = roles_for(d, "web")
    for i, role in enumerate(roles):
        exp += ['      <div class="role-header">',
                f'        <span class="role-title">{esc(role["org"])} — {esc(role["title"])}</span>',
                f'        <span class="role-meta">{esc(role["place"])} | {esc(role["dates"])}</span>',
                "      </div>"]
        for grp in groups_for(role, "web"):
            if grp["heading"]:
                exp += ["", f'      <div class="substream">{esc(grp["heading"])}</div>']
            exp.append("      <ul>")
            exp += [f"        <li>{esc(b)}</li>" for b in grp["bullets"]]
            exp.append("      </ul>")
        if i < len(roles) - 1:
            exp.append("")
    exp.append("    </section>")

    # Skills
    skills = ["    <section>", "      <h2>Technical Skills</h2>", "      <ul>"]
    skills += [f"        <li>{esc(s['label'])}: {esc(s['text'])}</li>"
               for s in skill_items(d) if visible(s, "web")]
    skills += ["      </ul>", "    </section>"]

    # Education (+ languages, interests)
    edu = ["    <section>", "      <h2>Education</h2>", "      <ul>"]
    for e in d["education"]:
        if not visible(e, "web"):
            continue
        edu += ["        <li>", '          <div class="edu-row">',
                f"            <span>{esc(e['degree'])}, {esc(e['school'])}</span>"]
        if e.get("gpa"):
            edu.append(f'            <span class="edu-gpa">GPA: {esc(e["gpa"])}</span>')
        edu.append("          </div>")
        if e.get("note") and e.get("note_only") in (None, "web"):
            edu.append(f'          <div class="edu-note">{esc(e["note"])}</div>')
        edu.append("        </li>")
    edu.append(f"        <li>Languages: {esc(d['languages'])}</li>")
    if d.get("interests"):
        edu.append(f"        <li>Interests: {esc(d['interests'])}</li>")
    edu += ["      </ul>", "    </section>"]

    body = ["<body>", '  <main class="page">'] + nav + [""] + header + [""] + exp + [""] + \
           skills + [""] + edu + ["  </main>", "</body>", "</html>"]
    return head + "\n".join(body) + "\n"


# --------------------------------------------------------------------------- LaTeX
TEX_MAP = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
           "_": r"\_", "{": r"\{", "}": r"\}", "^": r"\textasciicircum{}", "~": r"\textasciitilde{}"}


def tex(s):
    return "".join(TEX_MAP.get(ch, ch) for ch in str(s))


def tex_url(u):
    return str(u).replace("%", r"\%").replace("#", r"\#")


def render_tex(d, pt):
    m = d["meta"]
    site_label = re.sub(r"^https?://", "", m["site"]).rstrip("/")
    sep = r" \ $\bullet$ \ "
    primary = [tex(m["location"]), rf"\href{{mailto:{m['email']}}}{{{tex(m['email'])}}}",
               tex(m["phone"]), rf"\href{{{tex_url(m['site'])}}}{{{tex(site_label)}}}"]
    profile_links = [
        rf"\href{{{tex_url(link_url(val))}}}{{{tex(link_pdf_label(label, val))}}}"
        for label, val in m["links"].items()
    ]
    has_visible_urls = any(isinstance(v, dict) and v.get("show_in_pdf") for v in m["links"].values())

    out = [rf"{{\LARGE \textbf{{{tex(full_name(m))}}}}}\par", r"\vspace{2.5pt}",
           rf"{{\normalsize \textbf{{{tex(m['subtitle'])}}}}}\par", r"\vspace{2pt}"]
    if has_visible_urls:
        out += [rf"{{\small \textit{{{sep.join(primary)}}}}}\par",
                r"\vspace{1pt}",
                rf"{{\small \textit{{{sep.join(profile_links)}}}}}\par"]
    else:
        combined = primary[:-1] + profile_links + primary[-1:]
        out += [rf"{{\small \textit{{{sep.join(combined)}}}}}\par"]
    out += [r"\vspace{3pt}", rf"{{\normalsize {tex(d['summary'])}}}\par"]

    out += [r"\section*{Professional Experience}"]
    roles = roles_for(d, "pdf")
    for role in roles:
        title = role.get("pdf_title") or role["title"]
        out.append(rf"\roleheader{{{tex(role['org'])}}}{{{tex(title)}}}{{{tex(role['place'])}}}{{{tex(role['dates'])}}}")
        for grp in groups_for(role, "pdf"):
            if grp["heading"]:
                out.append(rf"\subhead{{{tex(grp['heading'])}}}")
            out.append(r"\begin{itemize}")
            out += [rf"  \item {tex(b)}" for b in grp["bullets"]]
            out.append(r"\end{itemize}")

    out += [r"\section*{Technical Skills}", r"\begin{itemize}"]
    out += [rf"  \item \textbf{{{tex(s['label'])}:}} {tex(s['text'])}"
            for s in skill_items(d) if visible(s, "pdf")]
    out.append(r"\end{itemize}")

    out += [r"\section*{Education}", r"\begin{itemize}"]
    for e in d["education"]:
        if not visible(e, "pdf"):
            continue
        line = rf"  \item \textbf{{{tex(e['degree'])}}} \textbar\ {tex(e['school'])}"
        if e.get("gpa"):
            line += rf" \hfill \textit{{GPA: {tex(e['gpa'])}}}"
        out.append(line)
        if e.get("note") and e.get("note_only") in (None, "pdf"):
            out.append(rf"  \\ {{\small \textit{{{tex(e['note'])}}}}}")
    out.append(rf"  \item \textbf{{Languages:}} {tex(d['languages'])}")
    if d.get("interests"):
        out.append(rf"  \item \textbf{{Interests:}} {tex(d['interests'])}")
    out.append(r"\end{itemize}")

    lead = lambda x: f"{x * 1.18:.2f}"
    tmpl = (ROOT / "templates" / "resume.tex.in").read_text(encoding="utf-8")
    pdftitle = f"{full_name(m)} - {m['subtitle']}".replace("&", "and")
    subs = {"@@PDFTITLE@@": pdftitle, "@@PDFAUTHOR@@": full_name(m),
            "@@BASE@@": f"{pt}", "@@LEAD@@": lead(pt),
            "@@SMALL@@": f"{pt - 1}", "@@SMALLLEAD@@": lead(pt - 1),
            "@@LARGE@@": f"{pt + 2}", "@@LARGELEAD@@": lead(pt + 2),
            "@@HUGE@@": f"{pt + 6}", "@@HUGELEAD@@": lead(pt + 6),
            "@@BODY@@": "\n".join(out)}
    for k, v in subs.items():
        tmpl = tmpl.replace(k, v)
    return tmpl


def build_pdf(d):
    """Try each font size until the PDF fits max_pages. Returns (path, pages, pt)."""
    if not shutil.which("latexmk"):
        sys.exit("latexmk not found. Install MacTeX/BasicTeX and make sure /Library/TeX/texbin is on PATH.")
    pdf_cfg = d["meta"]["pdf"]
    max_pages = int(pdf_cfg.get("max_pages", 1))
    BUILD.mkdir(exist_ok=True)
    last = None
    for pt in pdf_cfg["font_pt"]:
        (BUILD / "resume.tex").write_text(render_tex(d, pt), encoding="utf-8")
        proc = subprocess.run(
            ["latexmk", "-pdf", "-g", "-interaction=nonstopmode", "-halt-on-error",
             "-outdir=build", "build/resume.tex"],
            cwd=ROOT, capture_output=True, text=True)
        if proc.returncode != 0:
            log = (BUILD / "resume.log")
            tail = "\n".join(log.read_text(errors="replace").splitlines()[-25:]) if log.exists() else proc.stdout[-2000:]
            sys.exit(f"LaTeX failed at {pt}pt:\n{tail}")
        log_text = (BUILD / "resume.log").read_text(errors="replace")
        match = re.search(r"Output written on .*?\((\d+) pages?", log_text)
        pages = int(match.group(1)) if match else None
        if pages is None:
            sys.exit("Could not read the page count from build/resume.log")
        print(f"  PDF at {pt}pt: {pages} page{'s' if pages != 1 else ''}")
        info = re.search(r"BUILDINFO pagetotal=([\d.]+)pt; textheight=([\d.]+)pt;", log_text)
        last_used = None
        if info:
            pagetotal, textheight = float(info.group(1)), float(info.group(2))
            last_used = (pagetotal - textheight) if (pages > 1 and pagetotal > textheight) else pagetotal
        if last_used is not None and pages > 1:
            print(f"    (last page holds {last_used:.0f}pt of content, ~{last_used / (pt * 1.18 + 1.8):.1f} lines)")
        last = (BUILD / "resume.pdf", pages, pt, last_used)
        if pages <= max_pages:
            return last[:3]
    extra = ""
    if last[3] is not None and last[1] == max_pages + 1:
        extra = (f" About {last[3]:.0f}pt (~{last[3] / (last[2] * 1.18 + 1.8):.0f} lines) spill onto the extra page.")
    sys.exit(f"The PDF is {last[1]} pages even at {last[2]}pt (limit {max_pages}).{extra} "
             "Trim the PDF: mark some bullets in resume.yaml with `only: web`, or shorten them.")


# --------------------------------------------------------------------------- lint
TRACKED_ACRONYMS = {
    "FEA": "finite element analysis",
    "CAE": "computer-aided engineering",
    "HPC": "high-performance computing",
    "DIC": "digital image correlation",
    "UTM": "universal testing machine",
    "DMA": "dynamic mechanical analysis",
    "DVT": "design validation test",
    "EVT": "engineering validation test",
    "GCP": "google cloud platform",
    "CZM": "cohesive zone modeling",
    "BIW": "body-in-white",
    "CFD": "computational fluid dynamics",
}


def extract_pdf_text(pdf_path):
    """Extract visible text from a PDF via macOS PDFKit (returns None if unavailable)."""
    if not shutil.which("osascript") or not pdf_path.exists():
        return None
    script = (
        'ObjC.import("PDFKit"); '
        f'var u = $.NSURL.fileURLWithPath({json.dumps(str(pdf_path))}); '
        'var doc = $.PDFDocument.alloc.initWithURL(u); '
        'doc ? doc.string.js : "";'
    )
    proc = subprocess.run(["osascript", "-l", "JavaScript", "-e", script],
                          capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else None


def run_lint(d):
    warnings = []

    # 1. YAML line length (resume.yaml + site.yaml)
    for path in [p for p in (DATA, SITE) if p.exists()]:
        long_lines = [(i, len(ln)) for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
                      if len(ln) > 110 and not ln.lstrip().startswith("#")]
        if long_lines:
            sample = ", ".join(f"L{i} ({n}ch)" for i, n in long_lines[:5])
            more = f" +{len(long_lines) - 5} more" if len(long_lines) > 5 else ""
            warnings.append(f"[style] {path.name}: {len(long_lines)} line(s) > 110 chars ({sample}{more})")

    # 2. Bullet length & bullets per role
    for role in d["experience"]:
        all_bullets = [text_of(b) for grp in raw_groups(role) for b in grp["bullets"]]
        if len(all_bullets) > 6:
            pdf_count = sum(len(g["bullets"]) for g in groups_for(role, "pdf"))
            if pdf_count > 6:
                warnings.append(f"[style] {role['org']}: {pdf_count} bullets in PDF (recommended <= 6)")
        for b in all_bullets:
            words = len(b.split())
            if words > 30:
                warnings.append(f"[style] {role['org']}: bullet has {words} words (> 30): {b[:60]}...")

    # 3. Duplicate skill tokens
    seen = {}
    for s in skill_items(d):
        tokens = [x.strip() for x in re.split(r",\s*(?![^()]*\))", s["text"]) if x.strip()]
        for tok in tokens:
            key = tok.lower()
            if key in seen:
                warnings.append(f"[style] duplicate skill token {tok!r} (in {seen[key]!r} and {s['label']!r})")
            else:
                seen[key] = s["label"]

    # 4. ATS & PDF text extraction checks
    pdf_path = ROOT / d["meta"]["pdf"]["file"]
    pdf_text = extract_pdf_text(pdf_path)
    if pdf_text is None:
        warnings.append(f"[ats] skipped PDF text checks ({pdf_path.name} missing or PDFKit unavailable)")
    else:
        flat = re.sub(r"\s+", " ", pdf_text)
        flat_low = flat.lower()
        m = d["meta"]
        required = [
            ("Finite Element Analysis", "finite element analysis"),
            ("email", m["email"].lower()),
            ("phone", m["phone"].lower()),
            ("heading 'Professional Experience'", "professional experience"),
            ("heading 'Technical Skills'", "technical skills"),
            ("heading 'Education'", "education"),
        ]
        for label, needle in required:
            if needle not in flat_low:
                warnings.append(f"[ats] PDF text missing {label}")
        for label, val in m["links"].items():
            if isinstance(val, dict) and val.get("show_in_pdf"):
                if val["show_in_pdf"].lower() not in flat_low:
                    warnings.append(f"[ats] PDF text missing visible {label} URL ({val['show_in_pdf']})")
        if "linkedin.com/in/" not in flat_low:
            warnings.append("[ats] PDF text has no visible LinkedIn URL (linkedin.com/in/...)")

        odd_chars = sorted({(ch, hex(ord(ch))) for ch in pdf_text if ord(ch) > 127 and ch not in ("–", "•")})
        if odd_chars:
            warnings.append(f"[ats] unexpected non-ASCII glyph(s) in PDF text: {odd_chars}")

        # 5. Acronym expansion checks on the PDF text
        for acr, expanded in TRACKED_ACRONYMS.items():
            if re.search(rf"\b{re.escape(acr)}\b", flat) and expanded not in flat_low:
                warnings.append(f"[ats] acronym '{acr}' used in PDF without '{expanded}'")

    if warnings:
        print(f"Lint: {len(warnings)} warning(s):")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("Lint: 0 warnings (style & ATS OK)")
    return warnings


# --------------------------------------------------------------------------- sitemap
def sitemap_date():
    today = datetime.date.today().isoformat()
    sources = [p.name for p in (DATA, SITE) if p.exists()]
    try:
        for src in sources:
            dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", src], cwd=ROOT).returncode != 0
            tracked = subprocess.run(["git", "ls-files", "--error-unmatch", src], cwd=ROOT,
                                     capture_output=True).returncode == 0
            if dirty or not tracked:
                return today
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--"] + sources, cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()
        return out or today
    except OSError:
        return today


def render_sitemap(d):
    m = d["meta"]
    date = sitemap_date()
    entries = [(m["site"], "1.0"), (m["site"] + m["pdf"]["file"], "0.9")]
    body = "".join(
        f"  <url>\n    <loc>{esc(loc)}</loc>\n    <lastmod>{date}</lastmod>\n"
        f"    <changefreq>monthly</changefreq>\n    <priority>{prio}</priority>\n  </url>\n"
        for loc, prio in entries)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n")


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="validate YAML only")
    ap.add_argument("--html-only", action="store_true", help="skip the PDF build")
    ap.add_argument("--lint", action="store_true", help="run style and ATS lint checks (warnings only)")
    args = ap.parse_args()

    d = load()
    print("YAML OK")
    if args.check:
        return
    if args.lint:
        run_lint(d)
        return

    # Render everything first; write outputs only if every step succeeded (all-or-nothing).
    html_text = render_html(d)
    sitemap_text = render_sitemap(d)
    pdf = None
    if not args.html_only:
        pdf, pages, pt = build_pdf(d)

    (ROOT / "index.html").write_text(html_text, encoding="utf-8")
    print("  wrote index.html")
    (ROOT / "sitemap.xml").write_text(sitemap_text, encoding="utf-8")
    print("  wrote sitemap.xml")
    if pdf:
        shutil.copyfile(pdf, ROOT / d["meta"]["pdf"]["file"])
        print(f"  wrote {d['meta']['pdf']['file']} ({pages} page, {pt}pt)")
    print("Build complete.")


if __name__ == "__main__":
    main()
