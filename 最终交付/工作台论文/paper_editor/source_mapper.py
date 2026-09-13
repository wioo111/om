"""Stable semantic LaTeX mapping and narrow, validated, atomic source patches."""
from __future__ import annotations

import contextlib
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
from pathlib import Path

try:
    from .migrate_source import comment_free, strip_markers, CODE_ENV
except ImportError:
    from migrate_source import comment_free, strip_markers, CODE_ENV

OPEN = re.compile(r'^%<paper-block id="([A-Za-z][A-Za-z0-9_.-]*)" type="([a-z-]+)">\r?\n', re.M)
MARKERS = re.compile(r'^%<(?:paper-block id="([A-Za-z][A-Za-z0-9_.-]*)" type="([a-z-]+)"|/paper-block)>\r?\n', re.M)
VALID_TYPES = {'heading', 'paragraph', 'caption', 'table-caption', 'list-item', 'equation', 'figure', 'table', 'list', 'code', 'references'}
READ_ONLY = {'figure', 'table', 'list', 'code', 'references'}
FILE_COMMANDS = re.compile(r'\\(?:input|include|includeonly|import|subimport|inputfrom|includefrom|InputIfFileExists|IfFileExists|openin|openout|read|write|write18|immediate|directlua|luaexec|luadirect|catcode|csname|endcsname|usepackage|RequirePackage|documentclass|includegraphics|graphicspath|paperfigure|special|pdfobj|pdfxform|pdfximage|pdfextension|XeTeXpicfile|XeTeXpdffile|newcommand|renewcommand|providecommand|def|gdef|edef|xdef|let|futurelet|expandafter|scantokens|everyjob|everypar|AtBeginDocument|AtEndDocument|verb|lstinputlisting|verbatiminput|inputminted)\b', re.I)
MATH = re.compile(r'(?<!\\)\$\$[\s\S]*?(?<!\\)\$\$|(?<!\\)\$(?!\$)[\s\S]*?(?<!\\)\$|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\\begin\{(equation\*?|align\*?|gather\*?|multline\*?|displaymath|eqnarray\*?)\}[\s\S]*?\\end\{\1\}')
REFERENCES = re.compile(r'\\(?:label|(?:[a-zA-Z]*ref)|cite[a-zA-Z]*)\*?(?:\[[^\]]*\])*\{[^}]*\}')
NUMBERS = re.compile(r'(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?')
THEOREM = re.compile(r'定理|引理|命题|推论|结论|证明|全局最优|全域最优|Jung|充要|当且仅当|充分且必要|保证|所有|任意|单调|等号|上下界|上界|下界|全域共有|严格凹性|取等|极小极大|不存在|必然|总成立|恰好|连续直径')
SAFE_TEXT_COMMANDS = {'textbf', 'textit', 'emph', 'textrm', 'textsf', 'texttt', 'underline', 'noindent', 'small', 'normalfont', 'LaTeX', 'TeX', 'ldots', 'quad', 'qquad'}
LOCK = threading.RLock()


class MapperError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = 'invalid_patch'):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def digest(content: str | bytes) -> str:
    return hashlib.sha256(content.encode('utf-8') if isinstance(content, str) else content).hexdigest()


def clean_tex(text: str) -> str:
    return '\n'.join(comment_free(line) for line in text.splitlines())


def balanced(text: str) -> None:
    """Basic syntax gate, not a replacement for LaTeX compilation."""
    text = clean_tex(text)
    if '\\begin{lstlisting}' in text or '\\begin{verbatim}' in text:
        raise MapperError('代码块只读。', code='readonly')
    depth = 0
    for token in re.finditer(r'\\.|[{}]', text):
        if token[0] == '{':
            depth += 1
        elif token[0] == '}':
            depth -= 1
            if depth < 0:
                raise MapperError('LaTeX 花括号不平衡。', code='unbalanced_braces')
    if depth:
        raise MapperError('LaTeX 花括号不平衡。', code='unbalanced_braces')
    stack = []
    for event in re.finditer(r'\\(begin|end)\{([^}]+)\}', text):
        if event[1] == 'begin':
            stack.append(event[2])
        elif not stack or stack.pop() != event[2]:
            raise MapperError('LaTeX 环境没有正确配对。', code='unbalanced_environment')
    if stack:
        raise MapperError('LaTeX 环境没有正确配对。', code='unbalanced_environment')
    inline = re.sub(MATH, '', text)
    if re.search(r'(?<!\\)\$|\\[\[\]()]', inline):
        raise MapperError('数学公式定界符没有正确配对。', code='unbalanced_math')


def protected_tokens(text: str) -> dict:
    text = clean_tex(text)
    return {
        'math': [re.sub(r'\s+', '', item[0]) for item in MATH.finditer(text)],
        'numbers': NUMBERS.findall(text),
        'references': REFERENCES.findall(text),
        'symbols': re.findall(r'\\[A-Za-z]+(?:[_^](?:\{[^}]*\}|.))?', re.sub(MATH, '', text)),
        'bare_symbols': re.findall(r'(?<![A-Za-z])(?:D|R|S|J|t|p|q|P|F|C|Omega)(?:[_^](?:\{[^}]*\}|[A-Za-z0-9*])|\*|\\\*)?(?![A-Za-z])', re.sub(MATH, '', text)),
    }


def imported_frozen_ids(blocks: list[dict]) -> list[str]:
    """Run only at first import; subsequent edits cannot alter frozen membership."""
    q12_figures = {b['id'] for b in blocks if b['type'] == 'figure' and re.search(r'fig_app_q[12]_', b['content'])}
    return [b['id'] for b in blocks if (
        b['id'].startswith(('q1.', 'q2.'))
        or (b['id'].startswith('abstract.') and re.search(r'针对问题[一二]', b['content']))
        or (b['id'].startswith('introduction.') and re.search(r'问题[一二]的分析', b['section']))
        or b['id'] in q12_figures or b.get('parent_id') in q12_figures
    )]


@contextlib.contextmanager
def process_lock(path: Path):
    """Serialize independent server processes using a one-byte OS file lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise MapperError('另一个进程正在写入论文，请稍后重试。', 409, 'write_locked') from exc
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class SourceMapper:
    def __init__(self, project_root: Path):
        self.root = Path(project_root).resolve()
        self.registry_path = self.root / 'source_registry.json'
        if not self.registry_path.is_file():
            raise MapperError('没有正式论文源码登记，请先执行 migrate_source.py。', 500, 'missing_registry')
        self.registry = json.loads(self.registry_path.read_text(encoding='utf-8'))
        self.source_files = list(self.registry['source_files'])
        self.allowed = set(self.registry.get('editable_source_files', self.source_files))
        self.frozen_ids = set(self.registry.get('frozen_block_ids', []))
        self.history_path = self.root / self.registry.get('history_file', 'paper_editor/history.jsonl')
        self.lock_path = self.root / 'paper_editor' / '.source.lock'
        for relative in self.source_files:
            self._path(relative)

    def _path(self, relative: str) -> Path:
        if relative not in self.source_files:
            raise MapperError('源码路径不在登记白名单内。', 403, 'invalid_path')
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root / 'paper' / 'source') or path.suffix != '.tex':
            raise MapperError('源码路径必须在 paper/source 内。', 403, 'invalid_path')
        return path

    def document(self) -> dict:
        blocks = []
        seen = set()
        source_texts = {}
        versions = {}
        section_stack: dict[int, str] = {}
        for relative in self.source_files:
            raw = self._path(relative).read_bytes()
            text = raw.decode('utf-8')
            version = digest(raw)
            versions[relative] = version
            source_texts[relative] = text
            nesting = []
            for event in MARKERS.finditer(text):
                if event[1]:
                    block_id, kind = event[1], event[2]
                    if block_id in seen:
                        raise MapperError(f'重复 block ID：{block_id}', 409, 'duplicate_id')
                    if kind not in VALID_TYPES:
                        raise MapperError(f'未知块类型：{kind}', 500, 'invalid_marker')
                    seen.add(block_id)
                    block = {'id': block_id, 'type': kind, 'source': relative, 'section': '', 'start': event.start(), 'content_start': event.end(), 'parent_id': nesting[-1]['id'] if nesting else None}
                    blocks.append(block)
                    nesting.append(block)
                else:
                    if not nesting:
                        raise MapperError('出现没有起始标记的结束 marker。', 500, 'invalid_marker')
                    block = nesting.pop()
                    block.update(end=event.end(), content_end=event.start())
                    content = text[block['content_start']:block['content_end']]
                    block.update(content=content, version=version, block_hash=digest(content), readonly=block['type'] in READ_ONLY or block['type'] == 'equation', frozen=block['id'].startswith(('q1.', 'q2.')) or block['id'] in self.frozen_ids)
            if nesting:
                raise MapperError('存在没有结束的 block marker。', 500, 'invalid_marker')
            # Detect malformed marker-like comment lines in addition to valid regex matches.
            marker_lines = re.findall(r'^%<[^\n]*paper-block[^\n]*', text, re.M)
            if len(marker_lines) != len(list(MARKERS.finditer(text))):
                raise MapperError('发现格式错误的 block marker。', 500, 'invalid_marker')
        for block in blocks:
            if block['type'] == 'heading':
                heading = re.search(r'\\(title|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?(?:\[[^\]]*\])?\{(.*)\}', block['content'], re.S)
                if heading:
                    level = {'title': 0, 'chapter': 1, 'section': 1, 'subsection': 2, 'subsubsection': 3, 'paragraph': 4, 'subparagraph': 5}[heading[1]]
                    section_stack = {k: value for k, value in section_stack.items() if k < level}
                    section_stack[level] = heading[2].strip()
            block['section'] = ' / '.join(section_stack.values()) or '摘要'
            if block['source'].endswith('/abstract.tex'):
                block['section'] = '摘要'
            block['protected_conclusion'] = bool(block['frozen'] and block['type'] in {'heading', 'paragraph', 'caption', 'table-caption', 'list-item'} and (THEOREM.search(clean_tex(block['content'])) or re.search(r'证明|连续全局最优|结论|Jung', block['section'])))
        return {'revision': digest(json.dumps(versions, sort_keys=True)), 'blocks': blocks, 'source_files': self.source_files, 'source_texts': source_texts, 'entrypoint': self.registry['entrypoint']}

    def get_block(self, block_id: str) -> dict:
        for block in self.document()['blocks']:
            if block['id'] == block_id:
                return block
        raise MapperError(f'未找到块：{block_id}', 404, 'block_not_found')

    def _validate(self, block: dict, content: str, expected_version: str, operation: str = 'manual', edit_equation: bool = False, allow_math_changes: bool = False) -> str:
        if not expected_version or block['version'] != expected_version:
            raise MapperError('文件已被其他操作修改，请重新选择该块后重试。', 409, 'version_conflict')
        if block['source'] not in self.allowed:
            raise MapperError('该源码文件不允许网页编辑。', 403, 'readonly')
        if block['type'] in READ_ONLY:
            raise MapperError('此结构块只读；图片请选中其图注，列表请选中单个条目。', 403, 'readonly')
        if allow_math_changes and not (block['type'] == 'equation' and edit_equation):
            raise MapperError('只有独立公式块在显式公式模式下才能申请修改数学内容。', 403, 'protected_math')
        if not isinstance(content, str) or len(content.encode('utf-8')) > 200_000:
            raise MapperError('替换内容不是文字或超过 200 KB。', code='invalid_content')
        if re.search(r'paper-block|^\s*%\s*[<>]', content, re.M):
            raise MapperError('禁止在替换内容中加入或修改 block marker。', code='marker_mutation')
        if re.search(r'\^\^|[\x00-\x08\x0b\x0c\x0e-\x1f]', content):
            raise MapperError('禁止 TeX 字符重编码或控制字符。', code='unsafe_command')
        unsafe = FILE_COMMANDS.search(clean_tex(content))
        if unsafe:
            raise MapperError(f'禁止正文块中的文件、宏定义或系统命令：{unsafe[0]}', code='unsafe_command')
        old_commands = set(re.findall(r'\\([A-Za-z@]+)', clean_tex(block['content'])))
        new_commands = set(re.findall(r'\\([A-Za-z@]+)', clean_tex(content)))
        extra_commands = new_commands - old_commands - SAFE_TEXT_COMMANDS
        if extra_commands:
            raise MapperError('不允许在微调块中引入新 LaTeX 指令：' + ', '.join(sorted(extra_commands)), code='unsafe_command')
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        if not content.endswith('\n'):
            content += '\n'
        balanced(content)
        preserve_crlf = '\r\n' in block['content']
        before = block['content'].replace('\r\n', '\n').replace('\r', '\n')
        if block['type'] == 'equation' and before != content and not edit_equation:
            raise MapperError('公式默认只读，请显式启用“编辑公式”模式。', 403, 'equation_readonly')
        old, new = protected_tokens(before), protected_tokens(content)
        if before != content and block.get('protected_conclusion') and not allow_math_changes:
            raise MapperError('Q1/Q2 定理或结论段已冻结，普通润色不得改变该段。', 403, 'frozen_conclusion')
        if old['references'] != new['references']:
            raise MapperError('引用、标签和编号受保护，不允许微调改动。', 403, 'protected_reference')
        if old['math'] != new['math'] and not (edit_equation and block['type'] == 'equation'):
            raise MapperError('检测到公式改变；请显式启用“编辑公式”模式。', 403, 'protected_math')
        if block['frozen'] and not allow_math_changes:
            old_symbols = [x for x in old['symbols'] if x.lstrip('\\') not in SAFE_TEXT_COMMANDS]
            new_symbols = [x for x in new['symbols'] if x.lstrip('\\') not in SAFE_TEXT_COMMANDS]
            if old['math'] != new['math'] or old['numbers'] != new['numbers'] or old_symbols != new_symbols or old['bare_symbols'] != new['bare_symbols'] or (block['type'] == 'equation' and before != content):
                raise MapperError('Q1/Q2 的公式、数学常数及最优值已冻结，禁止写入。', 403, 'frozen_math')
        # Keep structural identity: a heading/caption/item remains the same command.
        structural = {'heading': r'\\(?:title|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?', 'caption': r'\\caption\*?', 'table-caption': r'\\caption\*?', 'list-item': r'\\item'}
        if block['type'] in structural:
            pattern = structural[block['type']]
            if re.findall(pattern, before) != re.findall(pattern, content):
                raise MapperError('禁止改变标题、图注或列表项的结构命令。', code='structure_change')
        if block['type'] not in {'equation'} and re.findall(r'\\(?:begin|end)\{[^}]+\}', before) != re.findall(r'\\(?:begin|end)\{[^}]+\}', content):
            raise MapperError('普通文字块不能增加或删除 LaTeX 环境。', code='structure_change')
        return content.replace('\n', '\r\n') if preserve_crlf else content

    def validate_patch(self, block_id: str, content: str, expected_version: str, operation: str = 'manual', edit_equation: bool = False, allow_math_changes: bool = False, **kwargs) -> dict:
        with LOCK, process_lock(self.lock_path):
            block = self.get_block(block_id)
            normalized = self._validate(block, content, expected_version, operation, edit_equation, allow_math_changes)
            return {'valid': True, 'block_id': block_id, 'content': normalized, 'version': block['version']}

    def patch_block(self, block_id: str, content: str, expected_version: str, operation: str = 'manual', edit_equation: bool = False, allow_math_changes: bool = False, **kwargs) -> dict:
        with LOCK, process_lock(self.lock_path):
            return self._patch(block_id, content, expected_version, operation, edit_equation, allow_math_changes)

    def _patch(self, block_id, content, expected_version, operation, edit_equation=False, allow_math_changes=False, undo_of=None):
        block = self.get_block(block_id)
        content = self._validate(block, content, expected_version, operation, edit_equation, allow_math_changes)
        if content == block['content']:
            return block
        path = self._path(block['source'])
        raw = path.read_bytes()
        if digest(raw) != expected_version:
            raise MapperError('写入前检测到文件竞争变化。', 409, 'version_conflict')
        original = raw.decode('utf-8')
        replacement = original[:block['content_start']] + content + original[block['content_end']:]
        original_markers = [match[0] for match in MARKERS.finditer(original)]
        if original_markers != [match[0] for match in MARKERS.finditer(replacement)]:
            raise MapperError('稳定 marker 必须保持不变。', code='marker_mutation')
        fd, temp_path = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(replacement.encode('utf-8'))
                handle.flush()
                os.fsync(handle.fileno())
            # Optimistic compare also catches writers that do not use the editor lock.
            if digest(path.read_bytes()) != expected_version:
                raise MapperError('原子替换前检测到外部文件修改。', 409, 'version_conflict')
            os.replace(temp_path, path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        record = {'id': block_id, 'block_id': block_id, 'time': dt.datetime.now(dt.timezone.utc).isoformat(), 'source': block['source'], 'before': block['content'], 'after': content, 'operation': operation, 'before_hash': digest(block['content']), 'after_hash': digest(content), 'file_before': expected_version, 'file_after': digest(replacement)}
        if undo_of:
            record['undo_of'] = undo_of
        record['event_id'] = digest(json.dumps(record, ensure_ascii=False))[:24]
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open('a', encoding='utf-8', newline='\n') as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        return self.get_block(block_id)

    def history(self, block_id: str | None = None, **kwargs) -> list:
        block_id = block_id or kwargs.get('id')
        if not self.history_path.exists():
            return []
        result = []
        for line in self.history_path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise MapperError('修改历史损坏，已停止历史操作。', 500, 'invalid_history') from exc
                if block_id is None or record['block_id'] == block_id:
                    result.append(record)
        return result

    def undo(self, block_id: str, expected_version: str, **kwargs) -> dict:
        with LOCK, process_lock(self.lock_path):
            records = self.history(block_id)
            undone = {record['undo_of'] for record in records if record.get('undo_of')}
            candidates = [record for record in records if record['operation'] != 'undo' and record['event_id'] not in undone]
            if not candidates:
                raise MapperError('该块没有可撤销的修改。', 409, 'nothing_to_undo')
            record = candidates[-1]
            block = self.get_block(block_id)
            if block['content'] != record['after']:
                raise MapperError('该块已发生历史以外的改变，不能安全撤销。', 409, 'undo_conflict')
            # Undo restores a previously accepted exact block, never a whole file.
            equation = block['type'] == 'equation'
            return self._patch(block_id, record['before'], expected_version, 'undo', edit_equation=equation, allow_math_changes=equation, undo_of=record['event_id'])

    def diff(self) -> dict:
        text = []
        changed_pairs = []
        baseline = self.root / self.registry.get('baseline_directory', 'paper_editor/baseline')
        paths = [self.registry['entrypoint']] + self.source_files
        for relative in paths:
            base = baseline / (Path(relative).name + '.baseline')
            current = self.root / relative
            before = base.read_text(encoding='utf-8') if base.exists() else ''
            after = current.read_text(encoding='utf-8') if current.exists() else ''
            if before != after:
                text.extend(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), fromfile='baseline/' + relative, tofile=relative))
                changed_pairs.append((base, current))
        git_text = ''
        git_available = False
        try:
            result = subprocess.run(['git', 'diff', '--no-ext-diff', '--', *[str(self.root / path) for path in paths]], cwd=self.root, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            git_available = result.returncode == 0
            git_text = result.stdout if git_available else result.stderr
        except (OSError, subprocess.TimeoutExpired) as exc:
            git_text = str(exc)
        no_index_diffs = []
        for base, current in changed_pairs:
            try:
                tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', '--', str(current)], cwd=self.root, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if tracked.returncode != 0 and base.is_file() and current.is_file():
                    compared = subprocess.run(['git', 'diff', '--no-index', '--no-ext-diff', '--', str(base), str(current)], cwd=self.root, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    if compared.returncode in (0, 1):
                        git_available = True
                        if compared.stdout:
                            no_index_diffs.append(compared.stdout)
                    elif compared.stderr:
                        no_index_diffs.append(compared.stderr)
            except (OSError, subprocess.TimeoutExpired) as exc:
                no_index_diffs.append(str(exc))
        if no_index_diffs:
            git_text += ('\n' if git_text else '') + '\n'.join(no_index_diffs)
        return {'text': ''.join(text), 'git_text': git_text, 'git_available': git_available, 'git_mode': 'working-tree + imported-baseline-no-index' if no_index_diffs else 'working-tree', 'git_note': '已跟踪文件显示工作区 Git diff；未跟踪正式源的改动显示 Git --no-index 相对导入基线的实际差异。本工具没有执行暂存、提交或初始化仓库。', 'baseline': 'imported formal source', 'source_files': paths}
