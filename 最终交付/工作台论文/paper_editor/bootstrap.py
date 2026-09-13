"""Portable launcher: a local venv, integrity-checked MathJax, loopback service.

Run with Python >= 3.10. No Node.js, administrator access, or source migration
is needed. The first setup downloads dependencies; subsequent starts are local.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
MIN_PYTHON = (3, 10)
MATHJAX_ENTRY = 'tex-svg.js'


class LaunchError(RuntimeError):
    """Actionable setup or startup failure."""


def note(text: str) -> None:
    print(text, flush=True)


def json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


@contextlib.contextmanager
def setup_lock(root: Path):
    """An OS-held lock is released automatically even if a launcher crashes."""
    runtime = root / 'paper_editor/runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    handle = (runtime / 'bootstrap.lock').open('a+b')
    handle.seek(0)
    if not handle.read(1):
        handle.write(b'0')
        handle.flush()
    handle.seek(0)
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        handle.close()
        raise LaunchError('另一个启动器正在准备此工作台。请等待该窗口完成后重试。') from error
    try:
        yield
    finally:
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def run_checked(command: list[str], root: Path, explanation: str) -> None:
    try:
        subprocess.run(command, cwd=root, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise LaunchError(explanation) from error


def ensure_python_environment(root: Path) -> Path:
    environment = root / '.venv'
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file():
        note('首次准备：在工作台内创建独立 Python 环境（不安装系统级组件）。')
        run_checked([sys.executable, '-m', 'venv', str(environment)], root,
                    '无法创建 .venv。请确认已安装完整的 Python 3.10+（包含 venv/pip），且工作台目录可写。')
    requirement = root / 'paper_editor/requirements.txt'
    fingerprint = hashlib.sha256(requirement.read_bytes()).hexdigest()
    stamp = environment / '.paper-editor-requirements.sha256'
    installed = stamp.read_text(encoding='ascii').strip() if stamp.is_file() else ''
    if installed != fingerprint:
        note('正在安装工作台依赖；首次启动需要网络，之后可离线启动。')
        run_checked([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(requirement)], root,
                    '依赖安装失败。请检查网络和上方 pip 提示；修复后再次运行启动器即可继续。')
        stamp.write_text(fingerprint + '\n', encoding='ascii')
    run_checked([str(python), '-c', 'import fastapi, uvicorn, httpx, fitz'], root,
                '本地 .venv 依赖不可用。请在 .venv 中重新执行 pip install -r paper_editor/requirements.txt。')
    return python


def mathjax_package(root: Path) -> dict:
    try:
        package = json.loads((root / 'package-lock.json').read_text(encoding='utf-8'))['packages']['node_modules/mathjax']
        resolved = package['resolved']
        integrity = next(value for value in package['integrity'].split() if value.startswith('sha512-'))
        expected = base64.b64decode(integrity.removeprefix('sha512-'), validate=True)
        if len(expected) != 64 or urllib.parse.urlsplit(resolved).scheme != 'https':
            raise ValueError('MathJax lock requires HTTPS and SHA-512')
        return {'version': package['version'], 'resolved': resolved, 'integrity': integrity, 'expected': expected}
    except (KeyError, ValueError, StopIteration, OSError) as error:
        raise LaunchError('package-lock.json 缺少有效的 MathJax HTTPS 地址或 SHA-512 校验值。') from error


def download_package(url: str) -> bytes:
    request = urllib.request.Request(url, headers={'User-Agent': 'LocalPaperWorkbench/1.0'})
    maximum = 64 * 1024 * 1024
    content = bytearray()
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            if urllib.parse.urlsplit(response.geturl()).scheme != 'https':
                raise LaunchError('MathJax 下载被重定向到非 HTTPS 地址，已终止。')
            while chunk := response.read(1024 * 1024):
                content.extend(chunk)
                if len(content) > maximum:
                    raise LaunchError('MathJax 安装包超过预期大小，已终止下载。')
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise LaunchError('MathJax 下载失败。请检查网络后再次运行；不需要安装 Node.js。') from error
    return bytes(content)


def extract_mathjax(archive: bytes, destination: Path) -> None:
    """Copy only regular package/es5 files; never extract links or path escapes."""
    total_size = 0
    file_count = 0
    target_root = destination.resolve()
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as package:
        for member in package:
            name = PurePosixPath(member.name)
            if '\\' in member.name or name.is_absolute() or '..' in name.parts:
                raise LaunchError('MathJax 安装包包含不安全路径，已终止。')
            if name.parts[:2] != ('package', 'es5'):
                continue
            if not member.isfile() and not member.isdir():
                raise LaunchError('MathJax 安装包包含链接或特殊文件，已终止。')
            relative = Path(*name.parts[2:])
            target = (target_root / relative).resolve()
            if not target.is_relative_to(target_root):
                raise LaunchError('MathJax 解包目标超出本地 vendor 目录。')
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            total_size += member.size
            file_count += 1
            if total_size > 256 * 1024 * 1024 or file_count > 10000:
                raise LaunchError('MathJax 解包大小超过安全上限。')
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = package.extractfile(member)
            if stream is None:
                raise LaunchError('MathJax 安装包无法读取。')
            with stream, target.open('wb') as output:
                shutil.copyfileobj(stream, output)
    if not (destination / MATHJAX_ENTRY).is_file():
        raise LaunchError('MathJax 安装包缺少 tex-svg.js，安装未完成。')


def ensure_mathjax(root: Path) -> None:
    package = mathjax_package(root)
    vendor = root / 'paper_editor/vendor'
    destination = vendor / 'mathjax'
    stamp = destination / '.package-integrity.json'
    if stamp.is_file() and (destination / MATHJAX_ENTRY).is_file():
        try:
            installed = json.loads(stamp.read_text(encoding='utf-8'))
            if installed.get('integrity') == package['integrity']:
                return
        except (ValueError, OSError):
            pass
    note(f"正在下载并校验本地 MathJax {package['version']}（无需 Node.js）。")
    archive = download_package(package['resolved'])
    if not hashlib.sha512(archive).digest() == package['expected']:
        raise LaunchError('MathJax SHA-512 与 package-lock.json 不一致，已拒绝安装。')
    vendor.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='mathjax-install-', dir=vendor) as temporary:
        stage = Path(temporary) / 'mathjax'
        stage.mkdir()
        extract_mathjax(archive, stage)
        json_atomic(stage / '.package-integrity.json', {key: package[key] for key in ('version', 'resolved', 'integrity')})
        if destination.exists():
            # This is a generated dependency inside an explicitly resolved vendor dir.
            backup = Path(temporary) / 'previous-mathjax'
            os.replace(destination, backup)
        os.replace(stage, destination)


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.5)
        return connection.connect_ex(('127.0.0.1', port)) == 0


def same_workbench(root: Path, port: int) -> bool:
    """Do not reuse another clone or another program on the requested port."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f'http://127.0.0.1:{port}/api/status', timeout=2) as response:
            data = json.loads(response.read(64 * 1024))
        return (Path(data.get('entry', '')).resolve() == (root / 'paper/main.tex').resolve()
                and Path(data.get('source_root', '')).resolve() == (root / 'paper/source').resolve())
    except (OSError, ValueError, urllib.error.URLError):
        return False


def start_server(root: Path, python: Path, port: int) -> None:
    runtime = root / 'paper_editor/runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    log_path = runtime / f'server-{port}.log'
    command = [str(python), '-m', 'paper_editor.run', '--port', str(port)]
    settings = {'cwd': str(root), 'stdin': subprocess.DEVNULL, 'close_fds': True}
    if os.name == 'nt':
        settings['creationflags'] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        settings['start_new_session'] = True
    with log_path.open('ab') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, **settings)
    json_atomic(runtime / f'server-{port}.json', {'pid': process.pid, 'root': str(root), 'port': port,
                'started_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'log': str(log_path)})
    note('本地服务正在后台启动；就绪后将打开浏览器。')
    deadline = time.monotonic() + 75
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise LaunchError(f'工作台服务启动失败（退出码 {process.returncode}）。请查看日志：{log_path}')
        if same_workbench(root, port):
            return
        time.sleep(0.35)
    process.terminate()
    raise LaunchError(f'等待本地服务就绪超时，已停止本次启动的进程。请查看日志：{log_path}')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Prepare and launch the local paper workbench.')
    parser.add_argument('--port', type=int, default=8765, help='Loopback port (default: 8765).')
    parser.add_argument('--no-browser', action='store_true', help='Start/reuse the server without opening a browser.')
    args = parser.parse_args(argv)
    if sys.version_info < MIN_PYTHON:
        parser.exit(1, '需要预先安装 Python 3.10 或更高版本；启动器不会安装系统级 Python。\n')
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    root = ROOT.resolve()
    url = f'http://127.0.0.1:{args.port}'
    try:
        if not (root / 'paper/main.tex').is_file() or not (root / 'source_registry.json').is_file():
            raise LaunchError('正式论文源码或 source_registry.json 缺失。请完整拉取仓库；启动器不会重新迁移或覆盖论文。')
        with setup_lock(root):
            if same_workbench(root, args.port):
                note('此目录的工作台已经运行，复用现有本地服务。')
            else:
                if port_in_use(args.port):
                    raise LaunchError(f'端口 {args.port} 被其他程序或另一份工作台占用。请使用 --port 8766，或 PowerShell -Port 8766；不会关闭已有进程。')
                python = ensure_python_environment(root)
                ensure_mathjax(root)
                if port_in_use(args.port):
                    raise LaunchError(f'准备期间端口 {args.port} 已被占用，请选择另一端口重试。')
                start_server(root, python, args.port)
        note(f'工作台已就绪：{url}')
        note('关闭浏览器不会停止后台服务。修改仅作用于此目录的正式论文源码。')
        if not args.no_browser:
            try:
                if not webbrowser.open(url, new=2):
                    note('未能自动打开默认浏览器，请手动打开上方地址。')
            except (OSError, webbrowser.Error):
                note('未能自动打开默认浏览器，请手动打开上方地址。')
        return 0
    except (LaunchError, OSError, tarfile.TarError) as error:
        note(f'启动失败：{error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
