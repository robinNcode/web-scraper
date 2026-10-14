import importlib.util
import sys
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


class SlugifyTests(unittest.TestCase):
    def test_slugify_keeps_unicode_bengali_titles(self):
        slug = _slugify("রক্ত-সম্পর্কীয় বিবাহ", max_len=40)
        self.assertTrue(slug)
        self.assertNotIn("%", slug)
        self.assertTrue(any("\u0980" <= ch <= "\u09FF" for ch in slug))

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
        self.assertTrue(any("\u0980" <= ch <= "\u09FF" for ch in slug))


if __name__ == "__main__":
    unittest.main()
