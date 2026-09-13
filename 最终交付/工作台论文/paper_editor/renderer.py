"""Deterministic, read-only LaTeX-to-HTML projection of the canonical paper.

This module never writes TeX. The only generated files are browser images in
``paper_editor/cache``. SourceMapper remains the sole authority for block IDs.
It deliberately supports the semantic LaTeX vocabulary used by this paper;
unrecognised constructs remain accessible as escaped source, never disappear.
"""
from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit


MARKER = re.compile(r"^[ \t]*%\s*\\?<\/?paper-block\b[^>]*>[^\n]*(?:\n|$)", re.M)
DISPLAY_ENVS = {"equation", "equation*", "align", "align*", "gather", "gather*", "multline", "multline*", "displaymath"}
ESCAPED = {"%": "%", "％": "％", "_": "_", "&": "&", "#": "#", "$": "$", "{": "{", "}": "}", " ": " ", "~": "~"}


def _group(text: str, pos: int, opening: str = "{", closing: str = "}") -> tuple[str, int]:
    """Read one balanced TeX group without changing any of its contents."""
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text) or text[pos] != opening:
        return "", pos
    start = pos + 1
    depth = 1
    pos += 1
    while pos < len(text):
        if text[pos] == "\\":
            pos += 2
            continue
        if text[pos] == opening:
            depth += 1
        elif text[pos] == closing:
            depth -= 1
            if depth == 0:
                return text[start:pos], pos + 1
        pos += 1
    return text[start:], len(text)


def _uncomment(text: str) -> str:
    text = MARKER.sub("", text)
    return re.sub(r"(?<!\\)%[^\n]*", "", text)


def _commands(text: str, names: tuple[str, ...], nargs: int = 1):
    pattern = re.compile(r"\\(" + "|".join(map(re.escape, names)) + r")(?![A-Za-z])\*?")
    for match in pattern.finditer(text):
        pos = match.end()
        optional = ""
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos < len(text) and text[pos] == "[":
            optional, pos = _group(text, pos, "[", "]")
        args = []
        for _ in range(nargs):
            value, end = _group(text, pos)
            if end == pos:
                break
            args.append(value)
            pos = end
        if len(args) == nargs:
            yield match.start(), pos, match.group(1), args, optional


def _remove_commands(text: str, names: tuple[str, ...], nargs: int = 1) -> str:
    for start, end, *_ in reversed(list(_commands(text, names, nargs))):
        text = text[:start] + text[end:]
    return text


def _split_tex(text: str, separator: str) -> list[str]:
    """Split table cells/rows only outside balanced groups and inline maths."""
    parts, start, pos, depth = [], 0, 0, 0
    math = False
    while pos < len(text):
        char = text[pos]
        if char == "$" and (pos == 0 or text[pos - 1] != "\\"):
            math = not math
        if depth == 0 and not math and text.startswith(separator, pos):
            parts.append(text[start:pos])
            pos += len(separator)
            if separator == "\\\\" and pos < len(text) and text[pos] == "[":
                _, pos = _group(text, pos, "[", "]")
            start = pos
            continue
        if char == "\\":
            pos += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        pos += 1
    parts.append(text[start:])
    return parts


class Renderer:
    def __init__(self, project_root: Path, mapper: Any):
        self.root = Path(project_root).resolve()
        self.mapper = mapper
        self.cache = self.root / "paper_editor" / "cache"
        self.labels: dict[str, tuple[str, str]] = {}
        self.citations: dict[str, tuple[int, str]] = {}
        self.macros: dict[str, str] = {}
        self.blocks: dict[str, dict] = {}
        self.children: dict[str, list[dict]] = {}
        self.numbers: dict[str, str] = {}
        self.warnings: list[str] = []

    def _attr(self, block: dict, extra: str = "") -> str:
        escape = lambda x: html.escape(str(x), quote=True)
        kind = block.get("type", "paragraph")
        readonly = block.get("readonly", False)
        return (f'id="block-{escape(block["id"])}" data-block-id="{escape(block["id"])}" '
                f'data-block-type="{escape(kind)}" data-readonly="{str(bool(readonly)).lower()}" '
                f'data-frozen="{str(bool(block.get("frozen", False))).lower()}" '
                f'class="paper-block block-{escape(kind)} {extra}" tabindex="0"')

    def _math(self, content: str, display: bool = False) -> str:
        content = _remove_commands(content, ("label",))
        # Expand the source's own zero-argument macros, rather than inventing
        # display notation or requiring an independently maintained macro file.
        for _ in range(4):
            expanded = re.sub(r"\\([A-Za-z]+)", lambda m: self.macros.get(m.group(1), m.group(0)), content)
            if expanded == content:
                break
            content = expanded
        if re.search(r"\\(?:href|url|html\w*|class|cssId|style|require|input|include)(?![A-Za-z])", content):
            self.warnings.append("一处公式包含浏览器不允许的扩展命令，已保留为只读源码。")
            return '<code class="math-rejected">' + html.escape(content) + '</code>'
        delimiter = (r"\[", r"\]") if display else (r"\(", r"\)")
        kind = "display" if display else "inline"
        return f'<span class="math math-{kind}">' + delimiter[0] + html.escape(content) + delimiter[1] + '</span>'

    def inline(self, text: str) -> str:
        text = _uncomment(text)
        out, pos = [], 0
        style_commands = {"textbf": "strong", "textit": "em", "emph": "em", "texttt": "code", "underline": "u", "textrm": "span", "textnormal": "span", "textsf": "span", "mbox": "span", "text": "span"}
        noarg = {"centering", "raggedright", "raggedleft", "noindent", "small", "footnotesize", "scriptsize", "tiny", "normalsize", "large", "Large", "LARGE", "selectfont", "clearpage", "newpage", "pagebreak", "begingroup", "endgroup", "maketitle", "appendix", "hfill", "vfill", "hline", "toprule", "midrule", "bottomrule", "endfirsthead", "endhead", "endfoot", "endlastfoot"}
        arg_counts = {"vspace": 1, "hspace": 1, "zihao": 1, "linespread": 1, "fontsize": 2, "setlength": 2, "renewcommand": 2, "typeout": 1, "needspace": 1, "captionsetup": 1, "label": 1, "allowbreak": 0}
        while pos < len(text):
            if text[pos] == "$":
                delim = "$$" if text.startswith("$$", pos) else "$"
                end = pos + len(delim)
                while True:
                    end = text.find(delim, end)
                    if end < 0 or text[end - 1] != "\\":
                        break
                    end += len(delim)
                if end >= 0:
                    out.append(self._math(text[pos + len(delim):end], delim == "$$"))
                    pos = end + len(delim)
                    continue
            if text.startswith((r"\(", r"\["), pos):
                display = text[pos + 1] == "["
                close = r"\]" if display else r"\)"
                end = text.find(close, pos + 2)
                if end >= 0:
                    out.append(self._math(text[pos + 2:end], display))
                    pos = end + 2
                    continue
            if text[pos] == "{" :
                content, pos = _group(text, pos)
                out.append(self.inline(content))
                continue
            if text[pos] == "\\":
                if pos + 1 >= len(text):
                    out.append("\\")
                    pos += 1
                    continue
                if text[pos + 1] in ESCAPED:
                    out.append(html.escape(ESCAPED[text[pos + 1]]))
                    pos += 2
                    continue
                if text.startswith("\\\\", pos):
                    out.append("<br>")
                    pos += 2
                    continue
                if text[pos + 1] in ",;:!":
                    out.append("&thinsp;" if text[pos + 1] != "!" else "")
                    pos += 2
                    continue
                found = re.match(r"\\([A-Za-z]+)\*?", text[pos:])
                if not found:
                    out.append(html.escape(text[pos:pos + 2]))
                    pos += 2
                    continue
                command = found.group(1)
                pos += len(found.group(0))
                if command in style_commands:
                    inner, pos = _group(text, pos)
                    tag = style_commands[command]
                    out.append(f"<{tag}>" + self.inline(inner) + f"</{tag}>")
                elif command in {"cite", "citep", "citet", "ref", "eqref", "pageref", "autoref"}:
                    while pos < len(text) and text[pos] == "[":
                        _, pos = _group(text, pos, "[", "]")
                    keys, pos = _group(text, pos)
                    if command.startswith("cite"):
                        values = []
                        for key in keys.split(","):
                            key = key.strip()
                            number, block_id = self.citations.get(key, (key, ""))
                            values.append(f'<a class="citation" href="#block-{html.escape(block_id, quote=True)}">{html.escape(str(number))}</a>')
                        out.append("[" + ", ".join(values) + "]")
                    else:
                        number, block_id = self.labels.get(keys, (keys, ""))
                        label = f"({number})" if command == "eqref" else str(number)
                        out.append(f'<a class="cross-reference" href="#block-{html.escape(block_id, quote=True)}">{html.escape(label)}</a>')
                elif command in {"href", "url"}:
                    url, pos = _group(text, pos)
                    body = url
                    if command == "href":
                        body, pos = _group(text, pos)
                    if urlsplit(url).scheme.lower() in {"http", "https", "mailto"}:
                        out.append(f'<a href="{html.escape(url, quote=True)}" rel="noopener noreferrer" target="_blank">{self.inline(body)}</a>')
                    else:
                        out.append(self.inline(body))
                elif command == "textcolor":
                    _, pos = _group(text, pos)
                    value, pos = _group(text, pos)
                    out.append(self.inline(value))
                elif command in {"quad", "qquad"}:
                    out.append("&emsp;" * (2 if command == "qquad" else 1))
                elif command in {"ldots", "dots"}:
                    out.append("…")
                elif command == "LaTeX":
                    out.append("LaTeX")
                elif command == "textbackslash":
                    out.append("\\")
                elif command in noarg:
                    pass
                elif command in arg_counts:
                    for _ in range(arg_counts[command]):
                        _, pos = _group(text, pos)
                elif command in {"begin", "end"}:
                    environment, pos = _group(text, pos)
                    if environment not in {"abstract", "document", "center", "flushleft", "flushright", "enumerate", "itemize", "thebibliography"}:
                        out.append(f'<code class="unsupported-tex">{html.escape(chr(92) + command + "{" + environment + "}")}</code>')
                else:
                    # A visible, escaped fallback is safer than a converter that
                    # silently drops commands it does not understand.
                    out.append(f'<code class="unsupported-tex">{html.escape(chr(92) + command)}</code>')
                continue
            if text[pos] == "~":
                out.append("&nbsp;")
            elif text[pos] == "\n":
                out.append(" ")
            elif text[pos] != "}":
                out.append(html.escape(text[pos]))
            pos += 1
        return "".join(out).strip()

    def _safe_asset(self, relative: str, source: str = "") -> Path:
        relative = relative.replace("\\", "/")
        if re.match(r"^[A-Za-z]+:", relative) or relative.startswith("/") or ".." in Path(relative).parts:
            raise ValueError("图片路径必须位于当前工作台内")
        bases = [self.root / "paper", self.root]
        if source:
            bases.append((self.root / source).parent)
        for base in bases:
            candidate = (base / relative).resolve()
            if not candidate.is_relative_to(self.root):
                raise ValueError("图片路径越出当前工作台")
            if candidate.is_file():
                return candidate
        raise FileNotFoundError(relative)

    def _asset_url(self, path: Path) -> str:
        relative = path.resolve().relative_to(self.root).as_posix()
        return "/assets/" + quote(relative, safe="/")

    def _browser_image(self, path: Path, page: int = 1) -> Path:
        if path.suffix.lower() != ".pdf":
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}:
                raise ValueError("浏览器不支持此图片格式")
            return path
        stat = path.stat()
        fingerprint = hashlib.sha256(f"{path.relative_to(self.root)}:{stat.st_mtime_ns}:{stat.st_size}:{page}:180".encode()).hexdigest()[:20]
        self.cache.mkdir(parents=True, exist_ok=True)
        target = self.cache / f"figure-{fingerprint}-p{page}.png"
        if not target.exists():
            import fitz
            with fitz.open(path) as document:
                if not 1 <= page <= len(document):
                    raise ValueError("图册页码不存在")
                pixmap = document[page - 1].get_pixmap(dpi=180, alpha=False)
                temp = target.with_name(target.stem + ".tmp.png")
                pixmap.save(str(temp))
                temp.replace(target)
        return target

    def _figure(self, block: dict) -> str:
        content = _uncomment(block["content"])
        media = []
        calls = [(start, args, optional, command) for start, _, command, args, optional in _commands(content, ("paperfigure",), 3)]
        calls += [(start, args, optional, command) for start, _, command, args, optional in _commands(content, ("includegraphics",), 1)]
        for _, args, options, command in sorted(calls):
            try:
                if command == "paperfigure":
                    _, name, rawpage = args
                    try:
                        path = self._safe_asset("figures/" + name, block.get("source", ""))
                        page = 1
                    except FileNotFoundError:
                        path = self._safe_asset("paper_figures.pdf")
                        page = int(rawpage)
                else:
                    name = args[0]
                    try:
                        path = self._safe_asset(name, block.get("source", ""))
                    except FileNotFoundError:
                        path = self._safe_asset("figures/" + name, block.get("source", ""))
                    match = re.search(r"(?:^|,)\s*page\s*=\s*(\d+)", options)
                    page = int(match.group(1)) if match else 1
                image = self._browser_image(path, page)
                media.append(f'<div class="figure-image"><img loading="lazy" decoding="async" src="{self._asset_url(image)}" alt="{html.escape(name, quote=True)}"></div>')
                media.append(f'<a class="asset-original" href="{self._asset_url(path)}' + (f'#page={page}' if path.suffix.lower() == ".pdf" else "") + '" target="_blank" rel="noopener">打开原图</a>')
            except (ValueError, FileNotFoundError, ImportError, RuntimeError) as exc:
                self.warnings.append(f"{block['id']}：图片读取失败（{exc}）")
                media.append('<div class="asset-missing">图片暂不可用：' + html.escape(str(exc)) + '</div>')
        if not calls:
            media.append('<details><summary>原始图形代码（只读）</summary><pre>' + html.escape(content) + '</pre></details>')
        children = self.children.get(block["id"], [])
        captions = "".join(self.render_block(child) for child in children)
        if not children:
            for _, _, _, args, _ in _commands(content, ("caption",)):
                captions += '<figcaption>' + self.inline(args[0]) + '</figcaption>'
        return f'<figure {self._attr(block)}>' + "".join(media) + captions + '</figure>'

    def _table(self, block: dict) -> str:
        content = _uncomment(block["content"])
        match = re.search(r"\\begin\{(tabular\*?|longtable)\}", content)
        captions = "".join(self.render_block(child) for child in self.children.get(block["id"], []))
        if not match:
            return f'<div {self._attr(block)}>{captions}<details><summary>表格源码（只读）</summary><pre>{html.escape(content)}</pre></details></div>'
        pos = match.end()
        if match.group(1) == "tabular*":
            _, pos = _group(content, pos)
        if pos < len(content) and content[pos] == "[":
            _, pos = _group(content, pos, "[", "]")
        _, pos = _group(content, pos)
        end = content.find(r"\end{" + match.group(1) + "}", pos)
        body = content[pos:end if end >= 0 else len(content)]
        if r"\endfirsthead" in body:
            first, rest = body.split(r"\endfirsthead", 1)
            if r"\endhead" in rest:
                rest = rest.split(r"\endhead", 1)[1]
            body = first + rest
        body = re.sub(r"\\(?:toprule|midrule|bottomrule|hline)(?:\[[^\]]*\])?", "", body)
        body = _remove_commands(body, ("cline", "cmidrule", "caption", "label"))
        rows = []
        for row_index, rawrow in enumerate(row for row in _split_tex(body, "\\\\") if row.strip()):
            columns = []
            for cell in _split_tex(rawrow, "&"):
                cell = cell.strip()
                attrs = ' scope="col"' if row_index == 0 else ""
                match_span = re.match(r"\\multicolumn", cell)
                if match_span:
                    size, cp = _group(cell, match_span.end())
                    _, cp = _group(cell, cp)
                    cell, _ = _group(cell, cp)
                    if size.isdigit():
                        attrs += f' colspan="{int(size)}"'
                tag = "th" if row_index == 0 else "td"
                columns.append(f'<{tag}{attrs}>' + self.inline(cell) + f'</{tag}>')
            rows.append('<tr>' + "".join(columns) + '</tr>')
        table = '<table><thead>' + (rows[0] if rows else "") + '</thead><tbody>' + "".join(rows[1:]) + '</tbody></table>'
        return f'<div {self._attr(block, "paper-table")}>' + captions + '<div class="table-scroll">' + table + '</div></div>'

    def _bibliography(self, block: dict) -> str:
        content = _uncomment(block["content"])
        items = list(_commands(content, ("bibitem",)))
        rendered = []
        for index, (_, end, _, args, _) in enumerate(items):
            stop = items[index + 1][0] if index + 1 < len(items) else len(content)
            body = re.sub(r"\\end\{thebibliography\}.*", "", content[end:stop], flags=re.S)
            number = self.citations.get(args[0], (index + 1, ""))[0]
            rendered.append(f'<li value="{number}">' + self.inline(body) + '</li>')
        return f'<div {self._attr(block)}><ol class="bibliography">' + "".join(rendered) + '</ol></div>'

    def render_block(self, block: dict) -> str:
        kind = block.get("type", "paragraph")
        content = _uncomment(block.get("content", ""))
        if kind == "figure":
            return self._figure(block)
        if kind == "table" or re.search(r"\\begin\{(?:tabular|longtable)\}", content):
            return self._table(block)
        if kind in {"code", "listing"}:
            match = re.search(r"\\begin\{(?:lstlisting|verbatim)\}(?:\[[^\]]*\])?\s*\n?(.*?)\\end\{(?:lstlisting|verbatim)\}", block.get("content", ""), re.S)
            source = match.group(1) if match else block.get("content", "")
            lines = len(source.splitlines())
            return f'<details {self._attr(block, "source-code")}><summary>源程序 · {lines} 行 · 只读（点击展开）</summary><pre><code>' + html.escape(source) + '</code></pre></details>'
        if kind in {"bibliography", "references"} or r"\begin{thebibliography}" in content:
            return self._bibliography(block)
        if kind in {"list", "enumerate", "itemize"}:
            tag = "ul" if r"\begin{itemize}" in content else "ol"
            children = self.children.get(block["id"], [])
            if children:
                body = "".join(self.render_block(child) for child in children)
            else:
                split = re.split(r"\\item(?![A-Za-z])", content)[1:]
                body = "".join('<li>' + self.inline(re.sub(r"\\end\{(?:enumerate|itemize)\}", "", item)) + '</li>' for item in split)
            return f'<{tag} {self._attr(block)}>' + body + f'</{tag}>'
        if kind == "list-item":
            content = re.sub(r"^\s*\\item(?:\[([^\]]*)\])?\s*", lambda m: (m.group(1) + " " if m.group(1) else ""), content)
            return f'<li {self._attr(block)}>' + self.inline(content) + '</li>'
        if kind in {"heading", "title"}:
            match = next(iter(_commands(content, ("section", "subsection", "subsubsection", "paragraph", "subparagraph", "title"))), None)
            if match:
                _, _, command, args, _ = match
                levels = {"title": 1, "section": 2, "subsection": 3, "subsubsection": 4, "paragraph": 5, "subparagraph": 6}
                level, value = levels[command], args[0]
            else:
                level, value = 2, content
            number = self.numbers.get(block["id"], "")
            prefix = '<span class="heading-number">' + html.escape(number) + '</span> ' if number else ""
            return f'<h{level} {self._attr(block)}>' + prefix + self.inline(value) + f'</h{level}>'
        if kind in {"caption", "table-caption"}:
            match = next(iter(_commands(content, ("caption",))), None)
            value = match[3][0] if match else content
            parent = self.blocks.get(block.get("parent_id"), {})
            number = self.numbers.get(parent.get("id", ""), "")
            label = ("表" if kind == "table-caption" else "图") + (" " + number if number else "")
            tag = "div" if kind == "table-caption" else "figcaption"
            return f'<{tag} {self._attr(block)}><span class="caption-label">{label}</span> ' + self.inline(value) + f'</{tag}>'
        if kind == "equation":
            match = re.match(r"\s*\\begin\{([^}]+)\}(.*?)\\end\{\1\}\s*$", content, re.S)
            if match and match.group(1) in DISPLAY_ENVS:
                value = match.group(2)
                if match.group(1).startswith("align"):
                    value = r"\begin{aligned}" + value + r"\end{aligned}"
            elif content.strip().startswith(r"\["):
                value = content.strip()[2:-2]
            else:
                value = content.strip().strip("$")
            number = self.numbers.get(block["id"], "")
            number_html = '<span class="equation-number">(' + number + ')</span>' if number else ""
            return f'<div {self._attr(block, "paper-equation")}>' + self._math(value, True) + number_html + '</div>'
        if re.match(r"\s*\\bibitem", content):
            item = next(iter(_commands(content, ("bibitem",))), None)
            if item:
                number = self.citations.get(item[3][0], ("", ""))[0]
                return f'<p {self._attr(block, "bibliography-item")}>[{number}] ' + self.inline(content[item[1]:]) + '</p>'
        rendered = self.inline(content)
        # A mapper may designate an unrecognised environment as readonly.
        # Keep its full source available, in addition to the readable projection.
        if "unsupported-tex" in rendered and block.get("readonly"):
            return f'<div {self._attr(block)}>' + rendered + '<details><summary>完整 LaTeX 源码（只读）</summary><pre>' + html.escape(block["content"]) + '</pre></details></div>'
        return f'<p {self._attr(block)}>' + rendered + '</p>'

    def _index(self, blocks: list[dict], sources: dict[str, str]):
        self.blocks = {block["id"]: block for block in blocks}
        self.children, self.numbers, self.labels, self.citations = {}, {}, {}, {}
        self.macros, self.warnings = {}, []
        for source in sources.values():
            for _, _, _, args, _ in _commands(_uncomment(source), ("providecommand", "newcommand"), 2):
                name = args[0].lstrip("\\")
                if re.fullmatch(r"[A-Za-z]+", name):
                    self.macros[name] = args[1]
        # Read the canonical preamble for macros/title; it is not an HTML source.
        preamble = self.root / "paper" / "main.tex"
        if preamble.exists():
            main = preamble.read_text(encoding="utf-8")
            for _, _, _, args, _ in _commands(_uncomment(main), ("providecommand", "newcommand"), 2):
                name = args[0].lstrip("\\")
                if re.fullmatch(r"[A-Za-z]+", name):
                    self.macros[name] = args[1]
        figure, table, equation = 0, 0, 0
        sections = [0, 0, 0]
        ref_number = 0
        for block in blocks:
            parent = block.get("parent_id")
            if parent:
                self.children.setdefault(parent, []).append(block)
            kind, text = block.get("type"), _uncomment(block.get("content", ""))
            if kind == "figure":
                figure += 1
                self.numbers[block["id"]] = str(figure)
            elif kind == "table" and r"\caption" in text:
                table += 1
                self.numbers[block["id"]] = str(table)
            elif kind == "equation" and re.search(r"\\begin\{(?:equation|align|gather|multline)\}", text):
                equation += 1
                self.numbers[block["id"]] = str(equation)
            elif kind == "heading":
                heading = re.match(r"\s*\\(section|subsection|subsubsection)(\*?)", text)
                if heading and not heading.group(2):
                    level = ["section", "subsection", "subsubsection"].index(heading.group(1))
                    sections[level] += 1
                    for lower in range(level + 1, 3):
                        sections[lower] = 0
                    self.numbers[block["id"]] = ".".join(map(str, sections[:level + 1]))
            for _, _, _, args, _ in _commands(text, ("label",)):
                owner = parent or block["id"]
                self.labels[args[0]] = (self.numbers.get(owner, args[0]), owner)
            if not parent:
                for _, _, _, args, _ in _commands(text, ("bibitem",)):
                    ref_number += 1
                    self.citations[args[0]] = (ref_number, block["id"])
        # Aux labels produced by the formal TeX build are authoritative for
        # numbering, when available; the source counter fallback works at startup.
        aux_candidates = [self.root / "paper" / "build" / "main.aux", self.root / "paper" / "main.aux"]
        for aux in aux_candidates:
            if aux.is_file():
                for _, _, _, args, _ in _commands(aux.read_text(encoding="utf-8", errors="replace"), ("newlabel",), 2):
                    value, _ = _group(args[1], 0)
                    if args[0] in self.labels and value:
                        _, owner = self.labels[args[0]]
                        self.labels[args[0]] = (value, owner)
                break

    def render_document(self) -> dict:
        document = self.mapper.document()
        blocks = document["blocks"]
        if len({block["id"] for block in blocks}) != len(blocks):
            raise ValueError("重复 block ID；拒绝生成有歧义的阅读视图")
        sources = document.get("source_texts", {})
        self._index(blocks, sources)
        title = "论文微调工作台"
        title_found = False
        for block in blocks:
            candidate = next(iter(_commands(block.get("content", ""), ("title",))), None)
            if candidate:
                title, title_found = candidate[3][0], True
                break
        if not title_found:
            main_path = self.root / "paper" / "main.tex"
            if main_path.exists():
                candidate = next(iter(_commands(main_path.read_text(encoding="utf-8"), ("title",))), None)
                if candidate:
                    title = candidate[3][0]
        parts = []
        if not title_found:
            parts.append('<header class="paper-title"><h1>' + self.inline(title) + '</h1></header>')
        for block in blocks:
            if not block.get("parent_id"):
                parts.append(self.render_block(block))
        metadata = [{key: block.get(key) for key in ("id", "type", "source", "section", "readonly", "frozen", "parent_id", "version")} for block in blocks]
        output = '<article class="paper-document">' + "\n".join(parts) + '</article>'
        ids = re.findall(r'data-block-id="([^"]+)"', output)
        missing = set(self.blocks) - set(ids)
        if missing or len(ids) != len(set(ids)):
            raise ValueError("HTML block 映射不完整或重复：" + ", ".join(sorted(missing)))
        return {"html": output, "revision": document["revision"], "blocks": metadata,
                "title": title, "math_macros": self.macros, "warnings": list(dict.fromkeys(self.warnings)),
                "stats": {"blocks": len(blocks), "figures": sum(b.get("type") == "figure" for b in blocks),
                          "tables": sum(b.get("type") == "table" for b in blocks),
                          "code_blocks": sum(b.get("type") == "code" for b in blocks)}}
