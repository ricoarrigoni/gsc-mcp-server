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

## What was left, now done

1. **MCP SDK surface verified** against `mcp` 2.3.0. `MCPServer` and
   `@server.tool(...)` are as assumed. A bare `-> dict` return produces no
   structured content, so tools return `dict[str, Any]` or a
   `CallToolResult` (text table plus `structured_content`). Tool arguments
   are camelCase because the SDK does not honour pydantic aliases.
2. **All nine tools**: `properties.py`, `performance.py`
   (`get_data_freshness`, `query_performance`, `top_queries`, `top_pages`,
   `compare_periods`, `export_query`), `urls.py` (`inspect_url`),
   `sitemaps.py` (`list_sitemaps`). Shared pieces in `tools/_common.py`.
3. **Pagination** in `gsc/pagination.py`, used by `export_query` only.
4. **`export_query`** writes an owner-only CSV to `GSC_EXPORT_DIR`.
5. **URL Inspection quota guard** in `gsc/quota.py`, persisted in
   `state_dir`, Pacific-time day.
6. **PII redaction** in `analysis/shaping.py`, applied by every tool.
7. **`get_data_freshness`** in `gsc/freshness.py`; `compare_periods`
   anchors named ranges on it and compares final data only.

Still needs a live run against a real property: both auth modes, and one
call of each tool.

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
