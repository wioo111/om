"""Mapper acceptance tests always mutate a temporary copy, never the paper."""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from paper_editor.source_mapper import MapperError, SourceMapper, digest
from paper_editor.migrate_source import insert_blocks, migrate, strip_markers


@pytest.fixture
def mapper(tmp_path):
    for relative in ['paper/source', 'paper_editor/baseline']:
        shutil.copytree(PROJECT / relative, tmp_path / relative)
    shutil.copyfile(PROJECT / 'paper/main.tex', tmp_path / 'paper/main.tex')
    shutil.copyfile(PROJECT / 'source_registry.json', tmp_path / 'source_registry.json')
    return SourceMapper(tmp_path)


def editable(mapper, prefix='introduction.'):
    return next(b for b in mapper.document()['blocks'] if b['id'].startswith(prefix) and b['type'] == 'paragraph' and not b['protected_conclusion'])


def assert_rejected(mapper, block, replacement, code, **kwargs):
    before = mapper._path(block['source']).read_bytes()
    with pytest.raises(MapperError) as err:
        mapper.patch_block(block['id'], replacement, block['version'], **kwargs)
    assert err.value.code == code
    assert mapper._path(block['source']).read_bytes() == before


def test_import_is_lossless_and_source_is_unique():
    registry = json.loads((PROJECT / 'source_registry.json').read_text(encoding='utf-8'))
    archive = (PROJECT / registry['import_archive']).read_bytes()
    reconstructed = ''.join(strip_markers((PROJECT / p).read_text(encoding='utf-8')) for p in registry['source_files'])
    assert digest(archive) == registry['import_sha256']
    assert digest(reconstructed) == registry['normalized_import_sha256']
    assert not (PROJECT / 'main_图文补全.tex').exists()
    assert (PROJECT / 'paper/main.tex').read_text(encoding='utf-8').count('\\input{') == len(registry['source_files'])


def test_mapping_ids_are_unique_and_nested_caption_is_exact(mapper):
    document = mapper.document()
    assert len({b['id'] for b in document['blocks']}) == len(document['blocks'])
    captions = [b for b in document['blocks'] if b['type'] == 'caption']
    assert len(captions) == 17
    for caption in captions:
        parent = mapper.get_block(caption['parent_id'])
        assert parent['type'] == 'figure'
        assert caption['content'] in parent['content']
        assert caption['content'].lstrip().startswith('\\caption{')


def test_only_selected_block_changes_and_ids_remain_stable(mapper):
    block = editable(mapper)
    before_doc = mapper.document()
    path = mapper._path(block['source'])
    before = path.read_text(encoding='utf-8')
    replacement = block['content'].replace('干扰源的发现', '干扰源发现', 1)
    result = mapper.patch_block(block['id'], replacement, block['version'])
    assert path.read_text(encoding='utf-8') == before[:block['content_start']] + replacement + before[block['content_end']:]
    assert result['id'] == block['id']
    assert [b['id'] for b in mapper.document()['blocks']] == [b['id'] for b in before_doc['blocks']]
    assert result['version'] != block['version']
    assert mapper.history(block['id'])[-1]['before'] == block['content']


def test_duplicate_id_blocks_all_writes(mapper):
    block = editable(mapper)
    other = next(b for b in mapper.document()['blocks'] if b['id'] != block['id'] and b['type'] == 'paragraph')
    path = mapper._path(other['source'])
    path.write_text(path.read_text(encoding='utf-8').replace(f'id="{other["id"]}"', f'id="{block["id"]}"'), encoding='utf-8')
    with pytest.raises(MapperError, match='重复') as err:
        mapper.patch_block(block['id'], block['content'] + '修改', block['version'])
    assert err.value.code == 'duplicate_id'


def test_external_file_change_is_conflict(mapper):
    block = editable(mapper)
    path = mapper._path(block['source'])
    path.write_text(path.read_text(encoding='utf-8') + '% external edit\n', encoding='utf-8')
    assert_rejected(mapper, block, block['content'] + '额外正文', 'version_conflict')


def test_two_clients_cannot_overwrite_same_file(mapper):
    a = editable(mapper)
    b = next(x for x in mapper.document()['blocks'] if x['source'] == a['source'] and x['type'] == 'paragraph' and x['id'] != a['id'])
    mapper.patch_block(a['id'], a['content'].replace('干扰源的发现', '干扰源发现'), a['version'])
    assert_rejected(mapper, b, b['content'].replace('本文', '本研究'), 'version_conflict')


@pytest.mark.parametrize('suffix,code', [('\n%<paper-block id="evil.p1" type="paragraph">\n', 'marker_mutation'), ('{', 'unbalanced_braces'), ('\\input{evil.tex}', 'unsafe_command'), ('\\write18{echo injected}', 'unsafe_command'), ('\\csname input\\endcsname{evil}', 'unsafe_command'), ('^^5cinput{evil}', 'unsafe_command'), ('\\@input{evil}', 'unsafe_command')])
def test_unsafe_patch_rejected(mapper, suffix, code):
    block = editable(mapper)
    assert_rejected(mapper, block, block['content'] + suffix, code)


def test_unbalanced_environment_rejected(mapper):
    block = next(x for x in mapper.document()['blocks'] if x['type'] == 'equation')
    replacement = block['content'].replace('\\end{equation}', '\\end{align}')
    assert_rejected(mapper, block, replacement, 'unbalanced_environment', edit_equation=True, allow_math_changes=True)


def test_inline_math_readonly_even_outside_frozen(mapper):
    block = next(x for x in mapper.document()['blocks'] if x['id'].startswith('q3.') and x['type'] == 'paragraph' and '$' in x['content'])
    first = block['content'].index('$') + 1
    replacement = block['content'][:first] + '2' + block['content'][first:]
    assert_rejected(mapper, block, replacement, 'protected_math')


def test_frozen_numeric_constant_rejected(mapper):
    block = next(x for x in mapper.document()['blocks'] if x['frozen'] and x['type'] == 'paragraph' and not x['protected_conclusion'] and re.search(r'\d', x['content']))
    replacement = re.sub(r'\d', '9', block['content'], count=1)
    assert_rejected(mapper, block, replacement, 'protected_math' if re.search(r'\$', block['content'][:re.search(r'\d', block['content']).start()]) else 'frozen_math')


def test_frozen_conclusion_rejected(mapper):
    block = next(x for x in mapper.document()['blocks'] if x['protected_conclusion'])
    assert_rejected(mapper, block, block['content'] + '该结论不再成立。', 'frozen_conclusion')


@pytest.mark.parametrize('kind', ['heading', 'paragraph', 'caption'])
def test_nonnumeric_mathematical_claim_frozen_across_block_types(mapper, kind):
    block = next(x for x in mapper.document()['blocks'] if x['protected_conclusion'] and x['type'] == kind)
    assert_rejected(mapper, block, block['content'].rstrip() + '（仅局部成立）\n', 'frozen_conclusion')


def test_references_cannot_be_changed(mapper):
    block = editable(mapper)
    assert '\\cite{' in block['content']
    assert_rejected(mapper, block, block['content'].replace('ref1', 'ref8'), 'protected_reference')


def test_figure_readonly_but_caption_patch_preserves_image(mapper):
    caption = next(x for x in mapper.document()['blocks'] if x['type'] == 'caption')
    parent = mapper.get_block(caption['parent_id'])
    assert_rejected(mapper, parent, parent['content'], 'readonly')
    replacement = caption['content'].replace('几何关系', '几何示意关系')
    new = mapper.patch_block(caption['id'], replacement, caption['version'])
    updated_parent = mapper.get_block(parent['id'])
    assert updated_parent['content'] == parent['content'].replace(caption['content'], new['content'])
    assert '\\paperfigure' in updated_parent['content']


def test_equation_mode_explicit_and_frozen_second_gate(mapper):
    block = next(x for x in mapper.document()['blocks'] if x['type'] == 'equation' and x['frozen'])
    replacement = block['content'].replace('180', '181', 1)
    if replacement == block['content']:
        replacement = block['content'].replace('=', '=1+', 1)
    assert replacement != block['content']
    assert_rejected(mapper, block, replacement, 'equation_readonly')
    assert_rejected(mapper, block, replacement, 'frozen_math', edit_equation=True)
    result = mapper.patch_block(block['id'], replacement, block['version'], edit_equation=True, allow_math_changes=True)
    assert result['content'] == replacement


def test_text_block_cannot_elevate_math_privileges(mapper):
    block = editable(mapper)
    assert_rejected(mapper, block, block['content'], 'protected_math', edit_equation=True, allow_math_changes=True)


def test_validate_does_not_write_or_log(mapper):
    block = editable(mapper)
    before = mapper._path(block['source']).read_bytes()
    result = mapper.validate_patch(block['id'], block['content'].replace('干扰源的发现', '干扰源发现'), block['version'])
    assert result['valid']
    assert mapper._path(block['source']).read_bytes() == before
    assert mapper.history() == []


def test_undo_restores_only_one_block_preserving_later_other_edit(mapper):
    first = editable(mapper)
    mapper.patch_block(first['id'], first['content'].replace('干扰源的发现', '干扰源发现'), first['version'])
    second = next(x for x in mapper.document()['blocks'] if x['source'] == first['source'] and x['type'] == 'paragraph' and x['id'] != first['id'])
    replacement = second['content'].replace('本文', '本研究')
    mapper.patch_block(second['id'], replacement, second['version'])
    updated_first = mapper.get_block(first['id'])
    mapper.undo(first['id'], updated_first['version'])
    assert mapper.get_block(first['id'])['content'] == first['content']
    assert mapper.get_block(second['id'])['content'] == replacement
    assert mapper.history(first['id'])[-1]['operation'] == 'undo'


def test_crlf_patch_and_undo_preserve_original_bytes(mapper):
    block = editable(mapper)
    path = mapper._path(block['source'])
    original = path.read_bytes().replace(b'\n', b'\r\n')
    path.write_bytes(original)
    block = mapper.get_block(block['id'])
    replacement = block['content'].replace('干扰源的发现', '干扰源发现').replace('\r\n', '\n')
    updated = mapper.patch_block(block['id'], replacement, block['version'])
    assert path.read_bytes() == original.replace('干扰源的发现'.encode(), '干扰源发现'.encode(), 1)
    mapper.undo(block['id'], updated['version'])
    assert path.read_bytes() == original


def test_diff_tracks_untracked_source_against_import_baseline(mapper):
    assert mapper.diff()['text'] == ''
    block = editable(mapper)
    mapper.patch_block(block['id'], block['content'].replace('干扰源的发现', '干扰源发现'), block['version'])
    actual = mapper.diff()['text']
    assert 'paper/source/introduction.tex' in actual
    assert '-干扰源的发现' in actual
    assert '+干扰源发现' in actual


def test_git_diff_also_shows_untracked_source_changes(mapper):
    block = editable(mapper)
    mapper.patch_block(block['id'], block['content'].replace('干扰源的发现', '干扰源发现'), block['version'])
    difference = mapper.diff()
    assert difference['git_available']
    assert difference['git_mode'] == 'working-tree + imported-baseline-no-index'
    assert '-干扰源的发现' in difference['git_text']
    assert '+干扰源发现' in difference['git_text']
    assert '没有执行暂存' in difference['git_note']


def test_q12_summary_and_appendix_protection_stable_after_heading_change(mapper):
    summary = next(b for b in mapper.document()['blocks'] if b['id'].startswith('abstract.') and '针对问题二' in b['content'])
    assert summary['frozen'] and summary['protected_conclusion']
    captions = [b for b in mapper.document()['blocks'] if b['type'] == 'caption' and b['id'].startswith('appendix.') and b['frozen']]
    assert len(captions) == 4
    analysis = next(b for b in mapper.document()['blocks'] if b['id'].startswith('introduction.') and '问题二的分析' in b['section'] and b['type'] == 'paragraph')
    assert analysis['frozen']
    path = mapper._path(analysis['source'])
    path.write_bytes(path.read_bytes().replace('问题二的分析'.encode(), '第二部分分析'.encode()))
    assert mapper.get_block(analysis['id'])['frozen']


def test_migration_idempotent_without_renumbering(mapper):
    before = mapper.document()
    registry = migrate(mapper.root)
    assert registry['phase'] == 'final-latex'
    assert mapper.document()['revision'] == before['revision']


def test_code_marked_once_and_preserved_verbatim():
    source = '\\section{附录}\n\\begin{lstlisting}\nx = {"nested": "\\\\section{not a heading}"}\n\\end{lstlisting}\n'
    marked, blocks = insert_blocks(source, 'appendix')
    assert [b['type'] for b in blocks] == ['heading', 'code']
    assert strip_markers(marked) == source
