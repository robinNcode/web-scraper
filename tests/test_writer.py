import tempfile
import unittest
from pathlib import Path

from paper_scraper.models import Page, Paper
from paper_scraper.writer import MarkdownPaperWriter, _slugify, to_banglish


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
        self.assertEqual(to_banglish("A sample title"), "A sample title")

    def test_writer_transliterates_filename_but_preserves_markdown_title(self):
        title = "বাংলাদেশের স্বাধীনতা"
        paper = Paper(Page("https://example.com", title, ""), "")
        with tempfile.TemporaryDirectory() as directory:
            path = MarkdownPaperWriter(Path(directory)).write(paper)
            content = path.read_text(encoding="utf-8")

        self.assertTrue(path.stem.isascii())
        self.assertIn("svadhinata", path.stem)
        self.assertTrue(content.startswith(f"# {title}\n"))


if __name__ == "__main__":
    unittest.main()
