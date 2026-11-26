import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import sync_notion_ideas as sync
from render_idea_cards import render_cards, wrap, font
from PIL import Image


def idea(title="An idea", summary="A summary", **extra):
    return {
        "properties": {
            "Title": {"type": "title", "title": [{"plain_text": title}]},
            "Summary": {"type": "rich_text", "rich_text": [{"plain_text": summary}]},
            "Link to ChatGPT chat": {"url": "https://private.example/never-export"},
        },
        **extra,
    }


class SyncTests(unittest.TestCase):
    def test_only_three_titles_and_summaries_are_published(self):
        result = sync.render_ideas([idea(str(i)) for i in range(4)])
        self.assertEqual(result.count("<img "), 3)
        self.assertNotIn("never-export", result)
        self.assertNotIn('alt="3:', result)

    def test_note_html_and_region_markers_are_escaped(self):
        result = sync.render_ideas([idea("</strong><img src=x>", sync.END)])
        self.assertIn("&lt;img", result)
        self.assertNotIn("<img src=x>", result)
        self.assertNotIn(sync.END, result)

    def test_real_cards_have_equal_heights_and_stable_file_names(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = [idea("Short", "Brief"), idea("A longer title " * 5, "Long summary " * 12)]
            first = render_cards(sync.public_ideas(rows), directory)
            second = render_cards(sync.public_ideas(rows), directory)
            self.assertEqual(first, second)
            sizes = []
            for path in first:
                with Image.open(path) as image:
                    sizes.append(image.size)
                    self.assertEqual(image.getpixel((0, 0))[3], 0)
            self.assertEqual(sizes[0], sizes[1])

    def test_long_words_wrap_without_overflow(self):
        face = font(28)
        lines = wrap("x" * 200, face, 580)
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(face.getlength(line) <= 580 for line in lines))

    def test_empty_and_archived_results_hide_the_section(self):
        self.assertEqual(sync.render_ideas([]), "")
        self.assertEqual(sync.render_ideas([idea(archived=True)]), "")
        self.assertEqual(sync.render_ideas([idea(in_trash=True)]), "")

    def test_missing_schema_does_not_silently_publish_wrong_content(self):
        with self.assertRaises(ValueError):
            sync.render_ideas([{"properties": {"Name": {}}}])

    def test_region_replacement_preserves_rest_and_is_repeatable(self):
        original = f"before\n{sync.START}\nold\n{sync.END}\nafter"
        updated = sync.replace_region(original, sync.render_ideas([idea()]))
        self.assertTrue(updated.startswith("before\n"))
        self.assertTrue(updated.endswith("\nafter"))
        self.assertEqual(sync.replace_region(updated, sync.render_ideas([idea()])), updated)
        self.assertNotIn("old", updated)
        self.assertNotIn("<details>", sync.replace_region(updated, ""))

    def test_invalid_markers_fail(self):
        for text in ["", sync.END + sync.START, sync.START * 2 + sync.END]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                sync.replace_region(text, "")

    def test_full_sync_updates_readme_and_preserves_generated_images(self):
        with tempfile.TemporaryDirectory() as directory:
            old_cwd = Path.cwd()
            try:
                os.chdir(directory)
                Path("README.md").write_text(
                    f"before\n{sync.START}\nold\n{sync.END}\nafter", encoding="utf-8")
                with patch.dict(os.environ, {"NOTION_TOKEN": "test-only-token"}):
                    with patch.object(sync, "fetch_ideas", return_value=[idea(str(i)) for i in range(3)]):
                        sync.main()
                        first = Path("README.md").read_text(encoding="utf-8")
                        sync.main()
                self.assertEqual(first, Path("README.md").read_text(encoding="utf-8"))
                self.assertEqual(first.count("<img "), 3)
                self.assertEqual(len(list(Path("assets/ideas").glob("idea-*.webp"))), 3)
                self.assertTrue(first.startswith("before\n"))
                self.assertTrue(first.endswith("\nafter"))
            finally:
                os.chdir(old_cwd)

    def test_query_requests_newest_three_without_page_bodies(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({"results": []}).encode()
        with patch.object(sync, "urlopen", return_value=response) as opened:
            self.assertEqual(sync.fetch_ideas("test-only-token"), [])
        request = opened.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["page_size"], 3)
        self.assertEqual(payload["sorts"], [{"timestamp": "created_time", "direction": "descending"}])

    def test_auth_failure_leaves_readme_unchanged_and_does_not_log_token(self):
        with tempfile.TemporaryDirectory() as directory:
            old_cwd = Path.cwd()
            try:
                os.chdir(directory)
                Path("README.md").write_text("unchanged", encoding="utf-8")
                error = HTTPError("https://api.notion.com", 401, "Unauthorized", {}, None)
                with patch.dict(os.environ, {"NOTION_TOKEN": "test-only-token"}):
                    with patch.object(sync, "urlopen", side_effect=error):
                        with self.assertRaises(RuntimeError) as caught:
                            sync.main()
                self.assertNotIn("test-only-token", str(caught.exception))
                self.assertEqual(Path("README.md").read_text(), "unchanged")
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
