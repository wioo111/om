"""One-time, lossless migration from the delivered monolithic LaTeX source.

Markers occupy complete comment lines. Removing them and concatenating the
registered inputs reconstructs the imported source (normalizing CRLF to LF).
Existing registries are never regenerated or renumbered.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


MARKER_LINE = re.compile(r'^%<(?:paper-block\b[^>]*|/paper-block)>\r?\n', re.M)
ENV = re.compile(r'\\(begin|end)\{([^}]+)\}')
HEAD = re.compile(r'^\s*\\(?:part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?(?:\[[^\]]*\])?\{')
MATH_ENV = {'equation', 'equation*', 'align', 'align*', 'gather', 'gather*', 'multline', 'multline*', 'displaymath', 'eqnarray', 'eqnarray*'}
CODE_ENV = {'lstlisting', 'verbatim', 'Verbatim', 'minted'}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strip_markers(text: str) -> str:
    return MARKER_LINE.sub('', text)


def comment_free(line: str) -> str:
    """LaTeX comments start at percent preceded by an even number of slashes."""
    for i, char in enumerate(line):
        if char == '%':
            j = i - 1
            while j >= 0 and line[j] == '\\':
                j -= 1
            if (i - j - 1) % 2 == 0:
                return line[:i]
    return line


def environment_end(lines: list[str], index: int, env: str) -> int:
    if env in CODE_ENV:
        for j in range(index + 1, len(lines)):
            if re.match(r'\s*\\end\{' + re.escape(env) + r'\}', lines[j]):
                return j + 1
        raise ValueError(f'Unclosed {env}')
    depth = 0
    for j in range(index, len(lines)):
        for event in ENV.finditer(comment_free(lines[j])):
            if event[2] == env:
                depth += 1 if event[1] == 'begin' else -1
                if depth == 0:
                    return j + 1
    raise ValueError(f'Unclosed {env}')


def caption_end(lines: list[str], index: int) -> int:
    depth = 0
    opened = False
    for j in range(index, len(lines)):
        text = comment_free(lines[j])
        for m in re.finditer(r'\\.|[{}]', text):
            if m[0] == '{':
                depth += 1
                opened = True
            elif m[0] == '}':
                depth -= 1
                if opened and depth == 0:
                    return j + 1
    raise ValueError('Unclosed caption')


def insert_blocks(text: str, prefix: str) -> tuple[str, list[dict]]:
    """Assign stable semantic IDs only to an unmarked first import."""
    if 'paper-block' in text:
        raise ValueError('Import already contains markers: use existing registry, never renumber.')
    if prefix == 'ending':
        return text, []
    if prefix == 'preamble':
        title = re.search(r'^\\title\{.*\}[^\n]*\n', text, re.M)
        if not title:
            return text, []
        result = text[:title.start()] + '%<paper-block id="title.h001" type="heading">\n' + title[0] + '%</paper-block>\n' + text[title.end():]
        assert strip_markers(result) == text
        return result, [{'id': 'title.h001', 'type': 'heading'}]
    lines = text.splitlines(keepends=True)
    spans: list[dict] = []

    def add(start: int, end: int, kind: str, parent=None):
        span = {'line_start': start, 'line_end': end, 'type': kind, 'parent': parent}
        spans.append(span)
        return span

    def scan(first: int, last: int, parent=None):
        i = first
        while i < last:
            clean = comment_free(lines[i]).strip()
            if not clean:
                i += 1
                continue
            if HEAD.match(lines[i]):
                add(i, caption_end(lines, i), 'heading', parent)
                i = caption_end(lines, i)
                continue
            event = re.match(r'\\begin\{([^}]+)\}', clean)
            if event and event[1] in {'figure', 'figure*', 'table', 'table*', 'longtable', 'tabular', 'tabular*', 'enumerate', 'itemize', 'description', 'thebibliography'} | MATH_ENV | CODE_ENV:
                env = event[1]
                end = environment_end(lines, i, env)
                if env in CODE_ENV:
                    add(i, end, 'code', parent)
                elif env in MATH_ENV:
                    add(i, end, 'equation', parent)
                elif env in {'enumerate', 'itemize', 'description'}:
                    container = add(i, end, 'list', parent)
                    items = [j for j in range(i + 1, end - 1) if re.match(r'\s*\\item(?:\b|\[)', lines[j])]
                    for k, j in enumerate(items):
                        add(j, items[k + 1] if k + 1 < len(items) else end - 1, 'list-item', container)
                else:
                    kind = 'figure' if env.startswith('figure') else ('references' if env == 'thebibliography' else 'table')
                    container = add(i, end, kind, parent)
                    for j in range(i + 1, end - 1):
                        if re.match(r'\s*\\caption\*?(?:\[[^\]]*\])?\{', lines[j]):
                            add(j, caption_end(lines, j), 'caption' if kind == 'figure' else 'table-caption', container)
                i = end
                continue
            if clean.startswith('\\[') or clean.startswith('$$'):
                end = i + 1
                closer = '\\]' if clean.startswith('\\[') else '$$'
                if closer not in clean[2:]:
                    while end < last and closer not in comment_free(lines[end]):
                        end += 1
                    end += 1
                add(i, min(end, last), 'equation', parent)
                i = end
                continue
            # Layout and structural commands remain outside the editable body.
            if re.match(r'^\\(?:begin|end|clearpage|newpage|vspace|hspace|setlength|renewcommand|linespread|selectfont|zihao|maketitle|typeout|begingroup|endgroup|small|footnotesize|noindent\s*$|centering)\b', clean):
                i += 1
                continue
            j = i + 1
            while j < last:
                nxt = comment_free(lines[j]).strip()
                if not nxt or HEAD.match(lines[j]) or re.match(r'\\(?:begin|end)\{', nxt) or nxt.startswith('\\[') or nxt.startswith('$$'):
                    break
                if re.match(r'\\(?:clearpage|newpage|typeout|linespread|vspace|begingroup|endgroup)\b', nxt):
                    break
                j += 1
            add(i, j, 'paragraph', parent)
            i = j

    scan(0, len(lines))
    spans.sort(key=lambda s: (s['line_start'], -s['line_end']))
    counts: dict[str, int] = {}
    abbreviations = {'heading': 'h', 'paragraph': 'p', 'caption': 'c', 'table-caption': 'tc', 'list-item': 'li', 'equation': 'e', 'figure': 'f', 'table': 't', 'list': 'l', 'code': 'code', 'references': 'refs'}
    for span in spans:
        key = abbreviations[span['type']]
        counts[key] = counts.get(key, 0) + 1
        span['id'] = f'{prefix}.{key}{counts[key]:03d}'
    starts: dict[int, list[dict]] = {}
    ends: dict[int, list[dict]] = {}
    for span in spans:
        starts.setdefault(span['line_start'], []).append(span)
        ends.setdefault(span['line_end'], []).append(span)
    out = []
    for i in range(len(lines) + 1):
        for span in sorted(ends.get(i, []), key=lambda s: -s['line_start']):
            out.append('%</paper-block>\n')
        for span in sorted(starts.get(i, []), key=lambda s: -s['line_end']):
            out.append(f'%<paper-block id="{span["id"]}" type="{span["type"]}">\n')
        if i < len(lines):
            out.append(lines[i])
    result = ''.join(out)
    assert strip_markers(result) == text, 'Migration changed imported text'
    return result, [{k: v for k, v in s.items() if k != 'parent'} for s in spans]


def migrate(project_root: Path, source: Path | None = None) -> dict:
    root = project_root.resolve()
    registry_path = root / 'source_registry.json'
    if registry_path.exists():
        return json.loads(registry_path.read_text(encoding='utf-8'))
    source = source or root / 'main_图文补全.tex'
    raw = source.read_bytes()
    original = raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    # Every boundary is the start of a complete original line.
    boundaries = [('preamble', 0)]
    patterns = [
        ('abstract', r'^\s*\\begin\{document\}'),
        ('introduction', r'^\s*\\section\{引言\}'),
        ('q1', r'^\s*\\section\{问题一模型的建立与求解\}'),
        ('q2', r'^\s*\\section\{问题二模型的建立与求解\}'),
        ('q3', r'^\s*\\section\{问题三模型的建立与求解\}'),
        ('q4', r'^\s*\\section\{问题四模型的建立与求解\}'),
        ('conclusion', r'^\s*\\section\{模型的评价、改进与推广\}'),
        ('appendix', r'^\s*\\section\*\{附录A'),
        ('ending', r'^\s*\\end\{document\}'),
    ]
    for name, pattern in patterns:
        match = re.search(pattern, original, re.M)
        if not match:
            raise ValueError(f'Missing section boundary: {name}')
        # \s can include newline: preserve every byte even when blank lines join.
        boundaries.append((name, match.start()))
    boundaries.sort(key=lambda pair: pair[1])
    paper = root / 'paper'
    (paper / 'source').mkdir(parents=True, exist_ok=True)
    archive = root / 'archive'
    archive.mkdir(exist_ok=True)
    archive_path = archive / (source.name + '.import')
    if archive_path.exists():
        raise ValueError('Archive exists without registry; refuse to overwrite.')
    archive_path.write_bytes(raw)
    source_files = []
    baseline = root / 'paper_editor' / 'baseline'
    baseline.mkdir(parents=True, exist_ok=True)
    block_count = 0
    for i, (name, start) in enumerate(boundaries):
        end = boundaries[i + 1][1] if i + 1 < len(boundaries) else len(original)
        segment = original[start:end]
        marked, blocks = insert_blocks(segment, name)
        relative = f'paper/source/{name}.tex'
        (root / relative).write_text(marked, encoding='utf-8', newline='\n')
        (baseline / f'{name}.tex.baseline').write_text(marked, encoding='utf-8', newline='\n')
        source_files.append(relative)
        block_count += len(blocks)
    reconstructed = ''.join(strip_markers((root / path).read_text(encoding='utf-8')) for path in source_files)
    assert reconstructed == original, 'Reconstruction differs from original source'
    main = '% !TeX program = xelatex\n% 唯一正式论文入口；正文只编辑 source/*.tex 中的稳定语义块。\n% 原生成链未接入此目录，导入原稿已移至 archive/*.import，禁止从旧稿覆盖。\n' + ''.join('\\input{' + path.removeprefix('paper/') + '}\n' for path in source_files)
    (paper / 'main.tex').write_text(main, encoding='utf-8', newline='\n')
    (baseline / 'main.tex.baseline').write_text(main, encoding='utf-8', newline='\n')
    if (root / 'paper_figures.pdf').exists():
        shutil.copyfile(root / 'paper_figures.pdf', paper / 'paper_figures.pdf')
    registry = {
        'schema_version': 1, 'phase': 'final-latex', 'entrypoint': 'paper/main.tex',
        'source_files': source_files, 'editable_source_files': [p for p in source_files if not p.endswith('/ending.tex')],
        'import_archive': archive_path.relative_to(root).as_posix(),
        'import_sha256': sha(raw), 'normalized_import_sha256': sha(original.encode('utf-8')),
        'reconstruction_sha256': sha(reconstructed.encode('utf-8')),
        'block_count_at_import': block_count,
        'baseline_directory': 'paper_editor/baseline', 'history_file': 'paper_editor/history.jsonl',
        'generator_policy': 'disabled: this directory is final LaTeX; no generator may overwrite paper/main.tex or paper/source/*.tex',
    }
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    try:
        from .source_mapper import SourceMapper, imported_frozen_ids
    except ImportError:
        from source_mapper import SourceMapper, imported_frozen_ids
    registry['frozen_block_ids'] = imported_frozen_ids(SourceMapper(root).document()['blocks'])
    registry['frozen_policy'] = 'Stable IDs captured from the first imported source, including Q1/Q2 summaries, analysis and appendix figures; never inferred again from edited text.'
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # Only after reconstruction succeeds, remove the second editable .tex source.
    source.unlink()
    return registry


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(migrate(args.project_root), ensure_ascii=False, indent=2))
