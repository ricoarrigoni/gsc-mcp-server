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

`GSC_REDACT_PII=true` drops rows whose query looks like an email, phone number
or long digit string. A blunt filter, not a guarantee.

## Install

```sh
uvx gsc-mcp-server --help
```

Or from source:

```sh
git clone https://github.com/OWNER/gsc-mcp-server
cd gsc-mcp-server
uv sync --extra dev
```

## Set up

Pick one path. You only need to read one.

**Do the properties you read change over time, or do you manage many of them?**
→ [OAuth setup](docs/setup-oauth.md). Access follows your Google account.

**Do you read a fixed set of properties and want it to never break?**
→ [Service account setup](docs/setup-service-account.md). No consent screen,
no token expiry, one manual grant per property.

If you are not sure, use OAuth.

Then:

```sh
gsc-mcp-server auth     # set up whichever mode is configured
gsc-mcp-server doctor   # verify it, with a named fix on any failure
```

## Tools

| Tool | What it does |
|---|---|
| `list_properties` | Properties this server can read, with permission level |
| `get_data_freshness` | The latest date with complete data |
| `query_performance` | Full Search Analytics query, typed and validated |
| `top_queries` | Opinionated wrapper, last 28 days, top 50 |
| `top_pages` | Same, by page |
| `compare_periods` | Two windows diffed server-side, deltas not raw sets |
| `inspect_url` | URL Inspection for 1 to 10 URLs |
| `list_sitemaps` | Sitemaps with error and warning counts |
| `export_query` | Large pulls written to CSV, returns a path |

Row counts are capped at 1,000 per call on purpose, below the API maximum of
25,000, so returned counts stay honest and the model's context survives.
Responses carry `hasMore` and `nextStartRow` for pagination. Larger pulls go
through `export_query`.

## Troubleshooting

[docs/troubleshooting.md](docs/troubleshooting.md). Start with
`gsc-mcp-server doctor`.

## Contributing

Pull requests welcome. Maintained as time allows.

Before you commit: `uv run pre-commit install`. The hooks block credentials
and any real domain name from entering the repository. Fixtures and examples
use `example.com` only.

Security reports: see [SECURITY.md](SECURITY.md). Please do not open a public
issue for a vulnerability.

## License

MIT. See [LICENSE](LICENSE).
