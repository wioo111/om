"""Nonvisual tests of the HTML projection; never patch the real paper."""
import re
import tempfile
import unittest
from pathlib import Path

from paper_editor.renderer import Renderer


class FakeMapper:
    def __init__(self, blocks, source_texts=None):
        self.blocks = blocks
        self.sources = source_texts or {}

    def document(self):
        return {"revision": "test-revision", "blocks": self.blocks,
                "source_texts": self.sources, "source_files": list(self.sources)}


def block(identifier, kind, content, parent=None, readonly=False):
    return {"id": identifier, "type": kind, "content": content,
            "source": "paper/source/q2.tex", "section": "问题二 / 测试",
            "parent_id": parent, "readonly": readonly, "frozen": True,
            "version": "file-version"}


class RendererTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def render(self, blocks, sources=None):
        return Renderer(self.root, FakeMapper(blocks, sources)).render_document()

    def test_math_text_and_bibliography_are_semantic_and_escaped(self):
        blocks = [
            block("q2.h001", "heading", r"\section{问题二}"),
            block("q2.p001", "paragraph", r"\textbf{结论}：$D_*=110.969319$；式\eqref{eq:opt}及\cite{ref1}。<script>alert(1)</script>"),
            block("q2.e001", "equation", r"\begin{equation}\label{eq:opt}D_*=2R^*/q\end{equation}"),
            block("refs.r001", "references", r"\begin{thebibliography}{9}\bibitem{ref1}示例文献。\end{thebibliography}", readonly=True),
        ]
        result = self.render(blocks)
        self.assertIn("<strong>结论</strong>", result["html"])
        self.assertIn(r"\(D_*=110.969319\)", result["html"])
        self.assertIn('href="#block-q2.e001">(1)</a>', result["html"])
        self.assertIn('href="#block-refs.r001">1</a>', result["html"])
        self.assertNotIn("<script>", result["html"])
        self.assertIn("&lt;script&gt;", result["html"])
        self.assertEqual(result["revision"], "test-revision")

    def test_parent_figure_and_caption_map_once_each(self):
        images = self.root / "paper" / "figures"
        images.mkdir(parents=True)
        (images / "geometry.png").write_bytes(b"test fixture path only")
        blocks = [
            block("q2.f001", "figure", r"\begin{figure}\paperfigure{.9}{geometry.png}{1}\caption{几何图。}\end{figure}", readonly=True),
            block("q2.c001", "caption", r"\caption{几何图。}", parent="q2.f001"),
        ]
        result = self.render(blocks)
        self.assertEqual(result["html"].count('data-block-id="q2.f001"'), 1)
        self.assertEqual(result["html"].count('data-block-id="q2.c001"'), 1)
        self.assertIn('<figcaption ', result["html"])
        self.assertIn('/assets/paper/figures/geometry.png', result["html"])
        self.assertEqual(result["html"].count("几何图。"), 1)
        self.assertEqual(result["warnings"], [])

    def test_longtable_header_is_not_duplicated_and_cells_keep_math(self):
        table = r"""\begin{longtable}{ll}
\toprule 符号 & 含义 \\ \midrule \endfirsthead
\toprule 符号 & 含义 \\ \midrule \endhead
$D_*$ & 最优值 \\
\texttt{a\_b} & 路径 \& 标识 \\
\bottomrule\end{longtable}"""
        result = self.render([block("q2.t001", "table", table, readonly=True)])
        self.assertEqual(result["html"].count("<tr>"), 3)
        self.assertEqual(result["html"].count("符号"), 1)
        self.assertIn("<code>a_b</code>", result["html"])
        self.assertIn("路径 &amp; 标识", result["html"])
        self.assertIn(r"\(D_*\)", result["html"])

    def test_list_children_are_semantic_and_have_independent_ids(self):
        blocks = [
            block("q2.l001", "list", r"\begin{enumerate}\item 第一条\item 第二条\end{enumerate}", readonly=True),
            block("q2.i001", "list-item", r"\item 第一条", "q2.l001"),
            block("q2.i002", "list-item", r"\item 第二条", "q2.l001"),
        ]
        result = self.render(blocks)
        self.assertIn("<ol ", result["html"])
        self.assertEqual(result["html"].count("<li "), 2)
        self.assertEqual(result["html"].count("第一条"), 1)
        self.assertEqual(len(re.findall('data-block-id=', result["html"])), 3)

    def test_code_is_collapsed_readonly_and_does_not_strip_percent(self):
        code = "\\begin{lstlisting}\nprint(value % 10)\n# <script>\n\\end{lstlisting}"
        result = self.render([block("app.code001", "code", code, readonly=True)])
        self.assertIn("<details ", result["html"])
        self.assertNotIn(" open", result["html"])
        self.assertIn("print(value % 10)", result["html"])
        self.assertIn("# &lt;script&gt;", result["html"])
        self.assertIn('data-readonly="true"', result["html"])

    def test_pdf_page_is_converted_without_changing_original(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF is the image-conversion runtime dependency")
        atlas = self.root / "paper_figures.pdf"
        doc = fitz.open()
        doc.new_page(width=300, height=200)
        doc.save(atlas)
        doc.close()
        before = atlas.read_bytes()
        result = self.render([block("q2.f001", "figure", r"\begin{figure}\paperfigure{.9}{missing.png}{1}\end{figure}", readonly=True)])
        self.assertIn("/assets/paper_editor/cache/figure-", result["html"])
        self.assertEqual(atlas.read_bytes(), before)
        self.assertEqual(result["warnings"], [])
        self.assertEqual(len(list((self.root / "paper_editor" / "cache").glob("*.png"))), 1)

    def test_rejects_duplicate_or_orphan_ids(self):
        first = block("q2.p001", "paragraph", "重复")
        with self.assertRaisesRegex(ValueError, "重复 block"):
            self.render([first, first])
        with self.assertRaisesRegex(ValueError, "映射不完整"):
            self.render([block("q2.c001", "caption", "孤立", "missing-parent")])

    def test_asset_path_traversal_and_unsafe_links_are_blocked(self):
        renderer = Renderer(self.root, FakeMapper([]))
        for path in ("../private.png", "C:/private.png", "/private.png"):
            with self.assertRaises(ValueError):
                renderer._safe_asset(path)
        rendered = renderer.inline(r"\href{javascript:alert(1)}{点击}")
        self.assertEqual(rendered, "点击")
        self.assertNotIn("href", renderer._math(r"\href{javascript:alert(1)}{x}").split(">", 1)[0])
        self.assertIn("math-rejected", renderer._math(r"\href{javascript:alert(1)}{x}"))

    def test_source_macros_expand_only_in_projection(self):
        source = r"\providecommand{\measHist}{\mathcal D}"
        equation = r"\[\measHist_h=\emptyset\]"
        result = self.render([block("q3.e001", "equation", equation)], {"paper/main.tex": source})
        self.assertIn(r"\mathcal D_h", result["html"])
        self.assertEqual(result["math_macros"]["measHist"], r"\mathcal D")
        self.assertEqual(equation, r"\[\measHist_h=\emptyset\]")

    def test_unknown_environment_remains_accessible(self):
        source = r"\begin{custom}不可丢失的正文\end{custom}"
        result = self.render([block("app.raw001", "raw", source, readonly=True)])
        self.assertIn("不可丢失的正文", result["html"])
        self.assertIn("完整 LaTeX 源码", result["html"])
        self.assertIn(source, result["html"])


if __name__ == "__main__":
    unittest.main()
