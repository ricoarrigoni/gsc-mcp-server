# gsc-mcp-server

A read-only [Model Context Protocol](https://modelcontextprotocol.io) server
for Google Search Console. Point Claude, or any MCP client, at your own search
performance data.

Read-only by design: it requests `webmasters.readonly` and refuses to start
with a wider scope, so no model can change anything in your Search Console
account.

## What it can and cannot read

Google's Search Console API exposes four resources. That is the ceiling for
any MCP server, including this one.

| Search Console report | Available |
|---|---|
| Performance (clicks, impressions, CTR, position) | Yes, fully |
| URL Inspection (index status, canonical, crawl) | Yes, fully |
| Sitemaps | Yes, read only |
| Pages / index coverage rollup | **No API exists** |
| Links (internal and external) | **No API exists** |
| Core Web Vitals / Page Experience | **No API exists** |
| Enhancements and rich result rollups | **No API exists** |
| Crawl stats, manual actions, security issues, removals | **No API exists** |

In short: this is a Performance report tool with URL Inspection attached. If
you expected the whole Search Console UI, the API cannot give it to you.

## Data caveats worth knowing before you analyse anything

- **16 months** of history, no more.
- **Anonymised queries** are stripped, so query rows never sum to property
  totals. The gap is often large.
- Grouping by page or query makes Google **drop rows** to keep the query fast.
- `byPage` and `byProperty` aggregation give **different numbers** for the
  same period. Neither is wrong.
- The last **2 to 3 days** are incomplete.

Every performance response from this server repeats the relevant caveat so the
model does not present partial data as complete.

## Privacy, stated plainly

This server protects your credential. It cannot protect your data.

Every row a tool returns is sent to whichever model provider you use. That is
the point of an MCP server. Search queries sometimes contain personal data,
because people search for their own names, emails and phone numbers. If you
query a property you do not own, the owner's data processing agreement decides
whether that is allowed, not this README.

`GSC_REDACT_PII=true` drops rows whose query contains an email address or a
run of 9 or more digits (phone, account and card numbers). It applies to every
tool, including CSV exports, and each response says how many rows it dropped.
A blunt filter, not a guarantee.

## Install

Requires [uv](https://docs.astral.sh/uv/). `brew install uv`, or `curl -LsSf https://astral.sh/uv/install.sh | sh`.

Run it from PyPI, no clone needed:

```sh
uvx gsc-mcp-server --help
```

`uvx` fetches the latest release and caches it. Pin a version with
`uvx gsc-mcp-server@0.1.0`, or install it permanently with
`uv tool install gsc-mcp-server` (or `pip install gsc-mcp-server`).

Or from source:

```sh
git clone https://github.com/ricoarrigoni/gsc-mcp-server
cd gsc-mcp-server
uv sync
uv run gsc-mcp-server --help
```

Then connect your MCP client: [docs/mcp-client-config.md](https://github.com/ricoarrigoni/gsc-mcp-server/blob/main/docs/mcp-client-config.md).

Once connected, the [user guide](https://github.com/ricoarrigoni/gsc-mcp-server/blob/main/docs/user-guide.md) shows what to ask and how
to read the answers.

## Set up

Pick one path. You only need to read one.

**Do the properties you read change over time, or do you manage many of them?**
→ [OAuth setup](https://github.com/ricoarrigoni/gsc-mcp-server/blob/main/docs/setup-oauth.md). Access follows your Google account.

**Do you read a fixed set of properties and want it to never break?**
→ [Service account setup](https://github.com/ricoarrigoni/gsc-mcp-server/blob/main/docs/setup-service-account.md). No consent screen,
no token expiry, one manual grant per property.

If you are not sure, use OAuth.

Then:

```sh
gsc-mcp-server auth     # set up whichever mode is configured
gsc-mcp-server doctor   # verify it, with a named fix on any failure
```

## Tools

You ask questions in plain language; the client picks the tools. See the
[user guide](https://github.com/ricoarrigoni/gsc-mcp-server/blob/main/docs/user-guide.md) for example questions and workflows.


| Tool | What it does |
|---|---|
| `list_properties` | Properties this server can read, with permission level |
| `get_data_freshness` | The latest date with final data, and with provisional data |
| `query_performance` | Full Search Analytics query, typed and validated. `dimensions: []` gives property totals |
| `top_queries` | Opinionated wrapper, last 28 days, top 50 |
| `top_pages` | Same, by page |
| `compare_periods` | Two windows diffed server-side on final data, deltas not raw sets. Previous period or previous year |
| `inspect_url` | URL Inspection for 1 to 10 URLs |
| `list_sitemaps` | Sitemaps with error and warning counts |
| `export_query` | Large pulls (up to 500,000 rows) written to CSV, returns the path, never the rows |

Row counts are capped at 1,000 per call on purpose, below the API maximum of
25,000, so returned counts stay honest and the model's context survives.
Responses carry `hasMore` and `nextStartRow` for pagination. Larger pulls go
through `export_query`.

Every tool returns a readable table plus structured content. A failure comes
back as `ok: false` with a stable `reason` and a sentence naming the fix.

URL Inspection is capped by Google at 2,000 calls per property per day. The
server counts locally and refuses at 1,900, so you get a clear message rather
than a failed batch.

## Configuration

All settings are environment variables. Put them in the `env` block of your
MCP client config (see [docs/mcp-client-config.md](https://github.com/ricoarrigoni/gsc-mcp-server/blob/main/docs/mcp-client-config.md)),
or export them in your shell for `auth` and `doctor`. No `.env` file is read.

| Variable | Default | Purpose |
|---|---|---|
| `GSC_AUTH_MODE` | inferred | `oauth` or `service_account`. Inferred from which credential path is set |
| `GSC_OAUTH_CLIENT_SECRET` | | OAuth client JSON from Google Cloud Console |
| `GSC_SERVICE_ACCOUNT_KEY` | | Service account JSON key |
| `GSC_PROPERTY_ALLOWLIST` | all | Comma-separated `siteUrl`s. Every other property is refused |
| `GSC_REDACT_PII` | `false` | Drop rows whose query looks like personal data |
| `GSC_STATE_DIR` | `~/.gsc-mcp` | Token cache and the URL Inspection counter |
| `GSC_EXPORT_DIR` | `~/.gsc-mcp/exports` | Where `export_query` writes CSV files |

Keep credential files outside any git repository.

## Troubleshooting

[docs/troubleshooting.md](https://github.com/ricoarrigoni/gsc-mcp-server/blob/main/docs/troubleshooting.md). Start with
`gsc-mcp-server doctor`.

## Contributing

Pull requests welcome. Maintained as time allows.

Set up with `uv sync --extra dev`. Before every commit, run `uv run pytest -q`,
`uv run ruff check .`, `uv run ruff format --check .` and
`uv run python scripts/check_no_real_domains.py`; CI runs the same.

Install the hooks once: `uv run pre-commit install`. The hooks block credentials
and any real domain name from entering the repository. Fixtures and examples
use `example.com` only.

Security reports: see [SECURITY.md](https://github.com/ricoarrigoni/gsc-mcp-server/blob/main/SECURITY.md). Please do not open a public
issue for a vulnerability.

## Author

Built and maintained by Ricardo Arrigoni,
[ricardoarrigoni.com](https://ricardoarrigoni.com). Get in touch there.

## License

MIT. See [LICENSE](https://github.com/ricoarrigoni/gsc-mcp-server/blob/main/LICENSE).
