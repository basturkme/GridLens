"""Bundle the GridLens *core* source into a single HTML file for the submission PDF.

Exports only the computational core (the network model, file parser, and VA
power-flow solver) — the graded engine — not the UI. Run it, then open the
generated ``dist/source_code.html`` in a browser and use "Print -> Save as PDF"
(Ctrl+P) to produce the source-code PDF.

If the optional ``pygments`` package is installed the code is syntax-highlighted;
otherwise it falls back to plain monospace (still fine for submission).

    python tools/export_source.py
"""
from __future__ import annotations

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "source_code.html"

# Core engine only, in reading order (model -> parser -> solver).
CORE = [
    "src/gridlens/core/models.py",
    "src/gridlens/core/parser.py",
    "src/gridlens/core/solver.py",
    "src/gridlens/core/__init__.py",
]


def collect() -> list[Path]:
    ordered: list[Path] = []
    for rel in CORE:
        p = (ROOT / rel).resolve()
        if p.exists():
            ordered.append(p)
    return ordered


def _highlight(text: str, filename: str):
    """Return (html_body, css) — syntax-highlighted if pygments is available."""
    try:
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import get_lexer_for_filename, TextLexer

        try:
            lexer = get_lexer_for_filename(filename)
        except Exception:
            lexer = TextLexer()
        fmt = HtmlFormatter(linenos="table", nowrap=False)
        return highlight(text, lexer, fmt), fmt.get_style_defs(".highlight")
    except Exception:
        # Plain fallback: numbered monospace lines.
        rows = []
        for i, line in enumerate(text.splitlines(), 1):
            rows.append(f'<span class="ln">{i:>4}</span>  {html.escape(line)}')
        return '<pre class="plain">' + "\n".join(rows) + "</pre>", ""


def main() -> int:
    files = collect()
    OUT.parent.mkdir(parents=True, exist_ok=True)

    bodies = []
    pyg_css = ""
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        text = p.read_text(encoding="utf-8")
        body, css = _highlight(text, p.name)
        if css:
            pyg_css = css  # same style block for all files
        bodies.append(
            f'<section class="file"><h2>{html.escape(rel)}</h2>{body}</section>'
        )

    toc = "\n".join(
        f'<li>{html.escape(p.relative_to(ROOT).as_posix())}</li>' for p in files
    )

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>GridLens — Source Code</title>
<style>
  @page {{ margin: 1.6cm; }}
  body {{ font-family: "Segoe UI", Arial, sans-serif; color: #111; }}
  h1 {{ font-size: 22pt; margin: 0 0 4px; }}
  .sub {{ color: #555; margin-bottom: 18px; }}
  .file {{ page-break-before: always; }}
  .file h2 {{
    font-size: 12pt; background: #1f2a44; color: #fff;
    padding: 6px 10px; border-radius: 4px; margin: 0 0 8px;
    font-family: Consolas, "Courier New", monospace;
  }}
  pre, code, .highlight, table.highlighttable {{
    font-family: Consolas, "Courier New", monospace;
    font-size: 8.2pt; line-height: 1.35;
  }}
  pre.plain {{ white-space: pre-wrap; word-break: break-word; margin: 0; }}
  .plain .ln {{ color: #999; }}
  .highlight {{ background: #fafafa; }}
  table.highlighttable td.linenos {{ color: #999; padding-right: 8px; text-align: right; }}
  table.highlighttable {{ border-collapse: collapse; width: 100%; }}
  ul.toc {{ columns: 2; font-family: Consolas, monospace; font-size: 9pt; }}
  {pyg_css}
</style></head>
<body>
  <h1>GridLens — Core Source Code</h1>
  <div class="sub">Computational engine (model · parser · VA solver) · EE 374 Term Project · {len(files)} files</div>
  <h2>Contents</h2>
  <ul class="toc">{toc}</ul>
  {''.join(bodies)}
</body></html>
"""
    OUT.write_text(doc, encoding="utf-8")
    print(f"Wrote {OUT}  ({len(files)} files)")
    print("Open it in a browser and use Ctrl+P -> Save as PDF.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
