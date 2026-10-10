# Handover notes for Claude Code

The scaffold is deliberately partial. Auth, config, errors, the HTTP client,
date handling, the request builder, output shaping and the test harness are
written and tested. The tool layer is one working example plus TODOs.

## Read first

The full requirements and feasibility spec lives in the Claude project
"GSC MCP Server" as `claude/gsc-mcp-server-spec.md`. Section numbers below
refer to it.

## What is done

| Area | File | State |
|---|---|---|
| Config and mode inference | `config.py` | Done, tested |
| Mode-aware errors | `errors.py` | Done, tested |
| Auth protocol | `auth/provider.py` | Done |
| OAuth provider | `auth/oauth_user.py` | Done, needs a live run |
| Service account provider | `auth/service_account.py` | Done, needs a live run |
| Read-only scope assertion | `auth/factory.py` | Done, tested |
| Token storage (keyring) | `auth/token_store.py` | Done |
| REST client, retry, status mapping | `gsc/client.py` | Done, tested |
| Request builder and trap guards | `gsc/request.py` | Done, tested |
| Date resolution, lag, 16-month clamp | `analysis/periods.py` | Done, tested |
| Output contract | `analysis/shaping.py` | Done, tested |
| Log redaction | `logging_setup.py` | Done, tested |
| Doctor diagnostic | `doctor.py` | Done |
| CLI (auth, doctor, serve) | `cli.py` | Done |
| `list_properties` tool | `tools/properties.py` | Done, the pattern to copy |
| Guardrails, CI, docs | various | Done |

## What is left

1. **Verify the MCP SDK surface.** `server.py` assumes
   `from mcp.server import MCPServer` and a `@server.tool(...)` decorator,
   per the v2 SDK notes. Confirm against the installed version before
   building on it; v1 used `FastMCP` from `mcp.server.fastmcp`.

2. **The remaining eight tools**, in `tools/`, grouped as
   `performance.py`, `urls.py`, `sitemaps.py`. Follow
   `tools/properties.py`: read-only annotations, `ok` plus `reason` on
   failure, `context.config.allows(site_url)` before any property call.

3. **Pagination helper** in `gsc/pagination.py`: loop `startRow` for
   `export_query` only. Inline tools stay at one page.

4. **`export_query`**: write CSV to disk, return the path, never the rows.

5. **URL Inspection quota guard**: a local daily counter, refuse at
   `URL_INSPECTION_SOFT_CAP`. Persist the count in `cfg.state_dir`.

6. **PII redaction filter**: honour `cfg.redact_pii` in the shaping layer.

7. **`get_data_freshness`**: query the last 10 days grouped by `date` with
   `dataState: "final"`, return the maximum. Tools that do date maths should
   call it rather than assuming the lag.

## Rules that are not negotiable

- Never request a scope wider than `webmasters.readonly`.
- `siteUrl` is passed verbatim, percent-encoded for the path, never
  normalised.
- Flat `filters` are always wrapped in `dimensionFilterGroups`. A top-level
  `filters` key is silently ignored by Google and returns unfiltered data.
- `searchAppearance` is rejected when combined with another dimension.
- A half-specified date range is rejected, never defaulted.
- `position` is absent for `discover` and `googleNews`. Absent, not zero.
- Inline row cap stays at 1,000. Bigger pulls go to `export_query`.
- Nothing in `tools/` imports `googleapiclient` or calls Google directly.
- No real domain, query string or property name enters the repository.
  `scripts/check_no_real_domains.py` enforces it in CI and pre-commit.
- Logs carry tool name, property, date range, row count, duration. Never
  rows, query text or token material.

## Before the repo goes public

- `gitleaks detect --source . --log-opts="--all"` over the full history.
- Replace `OWNER` in `pyproject.toml` and `README.md` with the GitHub owner.
- Confirm the 9-day OAuth token test result, then make the surviving mode the
  one the README leads with.
