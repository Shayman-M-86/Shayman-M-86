"""Publish only the three newest Notion idea titles and summaries to README.md."""
import html
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

START = "<!-- FLOWFORM_IDEAS:START -->"
END = "<!-- FLOWFORM_IDEAS:END -->"
DATA_SOURCE_ID = "4221cb8e-6238-8136-a907-000b64767dc0"


def fetch_ideas(token, data_source_id=DATA_SOURCE_ID):
    """Read properties only; never request page bodies or follow links."""
    payload = {
        "page_size": 3,
        "sorts": [{"timestamp": "created_time", "direction": "descending"}],
    }
    request = Request(
        f"https://api.notion.com/v1/data_sources/{data_source_id}/query",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2026-03-11",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    for attempt in range(3):
        try:
            with urlopen(request, timeout=20) as response:
                data = json.load(response)
            rows = data.get("results")
            if not isinstance(rows, list):
                raise ValueError("Notion returned an unexpected response.")
            return rows[:3]
        except HTTPError as exc:
            if (exc.code == 429 or exc.code >= 500) and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            # Do not log response bodies, request headers, or credentials.
            raise RuntimeError(
                f"Notion request failed (HTTP {exc.code}). Check the token and data-source access."
            ) from None
        except (URLError, TimeoutError):
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError("Notion could not be reached; README was left unchanged.") from None


def plain_text(prop, kind):
    if prop.get("type") != kind or not isinstance(prop.get(kind), list):
        raise ValueError(f"Expected a Notion {kind} property.")
    return "".join(part.get("plain_text", "") for part in prop[kind])


def safe_text(value):
    """Render literal text inside HTML paragraphs; never interpret note markup."""
    value = " ".join(value.split())
    return html.escape(value, quote=True)


def render_ideas(rows):
    paragraphs = []
    for row in rows[:3]:
        if row.get("archived") or row.get("in_trash"):
            continue
        props = row.get("properties", {})
        title = plain_text(props.get("Title", {}), "title").strip()
        summary = plain_text(props.get("Summary", {}), "rich_text").strip()
        if not title:
            continue
        title = safe_text(title)
        summary = safe_text(summary)
        paragraphs.append(
            f"<p><strong>{title}</strong>" +
            (f"<br/>{summary}" if summary else "") + "</p>"
        )
    if not paragraphs:
        return ""
    return (
        '<details>\n<summary><strong>💡 Current FlowForm ideas</strong></summary>\n\n'
        + "\n\n".join(paragraphs)
        + "\n\n</details>\n"
    )


def replace_region(readme, content):
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError("Expected exactly one pair of FlowForm ideas markers.")
    start = readme.index(START) + len(START)
    end = readme.index(END)
    if end < start:
        raise ValueError("FlowForm ideas markers are out of order.")
    return readme[:start] + "\n" + content + readme[end:]


def main():
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Add the NOTION_TOKEN repository secret to enable the Notion sync.")
    path = Path("README.md")
    original = path.read_text(encoding="utf-8")
    # All network, parsing and rendering must succeed before writing anything.
    content = render_ideas(fetch_ideas(token))
    updated = replace_region(original, content)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        print("Updated the FlowForm ideas section.")
    else:
        print("FlowForm ideas have not changed.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Notion sync failed: {exc}", file=sys.stderr)
        sys.exit(1)
