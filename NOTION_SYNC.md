# Notion ideas on the GitHub profile

The profile displays the three newest cards from the FlowForm Ideas data source, ordered by Notion's page creation time. Editing an older card updates its text if it is still among the newest three; it does not make that card newer.

The gallery publishes each card's **cover image**, **Title** and **Summary** as a rounded image card. Page bodies, chat links, related-page links, category, dates and Notion URLs are not exported. Future cards enter this public feed automatically. Published content also becomes part of the public Git commit history.

## One-time connection

1. Create an internal connection in [Notion's developer portal](https://www.notion.so/profile/integrations), with **Read content** capability. Give it access to the [FlowForm Ideas page](https://www.notion.so/4221cb8e623881b8bbb8f9cc4fec2c62) and its inline Ideas database. Keep the page itself private.
2. Copy the connection's secret and add it directly to [GitHub repository Actions secrets](https://github.com/Shayman-M-86/Shayman-M-86/settings/secrets/actions/new), named **NOTION_TOKEN**. Never put the token into a commit or a chat.
3. Open [Sync FlowForm ideas from Notion](https://github.com/Shayman-M-86/Shayman-M-86/actions/workflows/notion-ideas.yml) and choose **Run workflow** on main.
4. Check that the **Refresh idea gallery** step actually reads Notion and does not report that the secret is missing.

A Notion personal access token with access to this database also works, but a dedicated connection allows narrower access. This chat's Notion connection is separate from GitHub Actions.

## Behaviour

- Scheduled daily at 03:41 UTC (14:41 Melbourne during daylight saving; 13:41 during standard time). GitHub can delay scheduled runs.
- Can also be run manually; updates to the workflow or script trigger a run.
- Uses Python and pinned Pillow to compose consistent cards. Run `python -m pip install -r requirements-profile.txt` before running locally.
- Only changes content between the FLOWFORM_IDEAS markers in README.md.
- Downloads cover images during each sync and commits stable WebP cards to `assets/ideas`; signed Notion URLs never appear in the public README.
- Cards share a height, preserve complete titles and summaries, and wrap onto new rows on narrower displays.
- Cards with no cover use a geometric fallback. A broken existing cover fails the sync and preserves the previous gallery.
- Commits only when the rendered gallery changes, removing only obsolete generated card files.
- Missing credentials leave the existing section unchanged and add an Actions notice.
- API or schema errors fail the run before the README is written.
- An empty or entirely archived result removes the ideas section.
- Does not modify Notion or require its pages to be publicly shared.

The initial snapshot was populated through the connected Notion plugin. It is not evidence that GitHub Actions has authenticated to Notion.

## Validation

Run `python -m unittest discover -s scripts -p 'test_sync_notion_ideas.py' -v`.

The tests cover public-field selection, the three-item limit, HTML escaping, archived/empty results, marker validation, idempotence, API query ordering and preserving the README when authentication fails.

[Notion API documentation](https://developers.notion.com/reference/query-a-data-source)
