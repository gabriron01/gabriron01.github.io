# gabriron01.github.io

Source for my resume site: <https://gabriron01.github.io/>

**Two small YAML files drive everything:**
- `resume.yaml` — the content a recruiter reads (summary, experience, skills, education, languages, interests).
- `site.yaml` — identity, links, PDF settings and SEO metadata (rarely edited).

Together they generate the website (`index.html`), the one-page PDF
(`Gabriel_Nsengiyumva_External_Resume.pdf`, built with LaTeX) and `sitemap.xml`.
Do not edit those three files by hand; they are overwritten on every build.

## Update the resume

1. Edit `resume.yaml`.
2. Run:

   ```bash
   ./publish.sh "Describe the change"
   ```

   It validates the YAML, rebuilds the site and PDF, runs style/ATS lint checks, shows
   what changed, asks for confirmation, then commits and pushes to `main`. GitHub Pages
   redeploys in about a minute. (`./publish.sh "message" -y` skips the confirmation.)

To preview without publishing:

```bash
.venv/bin/python build.py && .venv/bin/python build.py --lint && open index.html Gabriel_Nsengiyumva_External_Resume.pdf
```

## Keeping the PDF to one page

The site can be as long as needed, but the PDF is limited to one page. The build tries
font sizes `10 → 9.5 → 9 pt` and **fails** if it still does not fit. To keep a detail on
the site only, mark it `only: web`:

```yaml
- only: web
  text: >-
    A long bullet that stays on the website but is trimmed from the PDF.
```

`only: pdf` does the same in the other direction. Education notes use `note_only: web` /
`note_only: pdf`. A role can use `bullets:` directly (no `groups:` wrapper needed unless
you have sub-headings) and `pdf_title:` for a shorter title in the PDF.

## ATS & style checks

Run `.venv/bin/python build.py --lint` (also run automatically by `publish.sh`) for
advisory warnings on:
- Long YAML lines (> 110 chars), long bullets (> 30 words), > 6 PDF bullets in one role, and duplicate skills.
- PDF text extraction (via macOS PDFKit): confirms `Finite Element Analysis`, email, phone, visible LinkedIn/GitHub URLs, section headings, clean ASCII/punctuation, and expanded domain acronyms.

## Requirements

- Python 3 (a local `.venv` with PyYAML is created automatically by `publish.sh`)
- MacTeX / BasicTeX (`latexmk`, `pdflatex`) at `/Library/TeX/texbin`
- `git` authenticated to GitHub (HTTPS via `gh auth` is already set up)

## Files

| File | Purpose |
| --- | --- |
| `resume.yaml` | Resume content (edit this most often) |
| `site.yaml` | Identity, links (`show_in_pdf`), PDF settings and SEO metadata |
| `build.py` | Validates YAML, renders HTML + LaTeX, builds the 1-page PDF, runs `--lint` |
| `publish.sh` | Build, lint, review, commit and push in one step |
| `templates/style.css` | Website styling |
| `templates/resume.tex.in` | PDF layout (Times, ATS-clean role headers, ruled section headers) |
