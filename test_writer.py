import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

pkg_spec = importlib.util.spec_from_file_location(
    "paper_scraper",
    ROOT / "__init__.py",
    submodule_search_locations=[str(ROOT)],
)
package = importlib.util.module_from_spec(pkg_spec)
sys.modules["paper_scraper"] = package
pkg_spec.loader.exec_module(package)

writer_spec = importlib.util.spec_from_file_location("paper_scraper.writer", ROOT / "writer.py")
writer_module = importlib.util.module_from_spec(writer_spec)
sys.modules["paper_scraper.writer"] = writer_module
writer_spec.loader.exec_module(writer_module)
_slugify = writer_module._slugify
_to_banglish = writer_module.to_banglish
_MarkdownPaperWriter = writer_module.MarkdownPaperWriter
from paper_scraper.models import Page, Paper


class SlugifyTests(unittest.TestCase):
    def test_slugify_transliterates_bengali_titles(self):
        slug = _slugify("রক্ত-সম্পর্কীয় বিবাহ", max_len=40)
        self.assertTrue(slug)
        self.assertNotIn("%", slug)
        self.assertTrue(slug.isascii())
        self.assertEqual(slug, "rakta-samparkiya-vivaha")

    def test_slugify_decodes_percent_encoded_url_segments(self):
        url = (
            "https://www.shongshoy.com/kb/about-atheism/"
            "%e0%a6%b8%e0%a6%82%e0%a6%b6%e0%a6%af%e0%a6%bc%e0%a6%ac"
            "%e0%a6%be%e0%a6%a6-%e0%a6%95%e0%a6%be%e0%a6%b9%e0%a7%87-"
            "%e0%a6%ac%e0%a6%b2%e0%a7%87/"
        )
        slug = _slugify(url, max_len=80)
        self.assertTrue(slug)
        self.assertNotIn("%", slug)
        self.assertTrue(slug.isascii())

    def test_ascii_title_is_unchanged_by_transliteration(self):
        self.assertEqual(_to_banglish("A sample title"), "A sample title")

    def test_writer_transliterates_filename_but_preserves_markdown_title(self):
        title = "বাংলাদেশের স্বাধীনতা"
        paper = Paper(Page("https://example.com", title, ""), "")
        with tempfile.TemporaryDirectory() as directory:
            path = _MarkdownPaperWriter(Path(directory)).write(paper)
            content = path.read_text(encoding="utf-8")

        self.assertTrue(path.stem.isascii())
        self.assertIn("svadhinata", path.stem)
        self.assertTrue(content.startswith(f"# {title}\n"))


if __name__ == "__main__":
    unittest.main()
