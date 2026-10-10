# User guide

How to get useful answers out of your Search Console data once the server is
connected. If it is not connected yet, start with the [README](../README.md)
and [docs/mcp-client-config.md](mcp-client-config.md).

You never call the tools yourself. You ask Claude (or another MCP client) a
question in plain language and it picks the tools. This guide shows what to
ask, what each tool does underneath, and the few Search Console quirks that
change how you should read the answers.

## Your first three questions

1. **"List my Search Console properties."**
   Confirms the connection and shows each property's exact name. If you
   have several, name the one you mean in later questions.
2. **"How fresh is the data for sc-domain:example.com?"**
   Tells you the last complete day. Search Console usually trails by 2 to 4
   days, so "yesterday" often has no data yet.
3. **"What were my top queries and top pages over the last 28 days?"**
   A quick picture of where traffic comes from.

## Property names matter

A property name is matched character by character. These are three
different properties:

| Name | What it is |
|---|---|
| `sc-domain:example.com` | Domain property: every subdomain, http and https |
| `https://example.com/` | URL-prefix property, trailing slash included |
| `https://www.example.com/` | A different URL-prefix property |

If a question fails with "property not found", ask Claude to list your
properties and use the name exactly as shown.

## What you can ask

### Overall performance

- "How many clicks and impressions did sc-domain:example.com get in the last
  3 months?"
- "Show daily clicks for the last 28 days."
- "Split last month's traffic by device." / "...by country."

Totals come from a query with no grouping. They are the only figures that
include **anonymised queries** (searches Google hides for privacy), so they
are always higher than the sum of query rows. That gap is normal and often
large on small sites.

### Queries and pages

- "What are my top 20 queries this month?"
- "Which pages get the most impressions but few clicks?"
- "Which queries does /blog/widgets/ rank for?"
- "Find queries in position 8 to 20 with lots of impressions." These are
  quick wins: close to page one, already visible.
- "Which queries have more than one of my pages ranking?" This spots
  cannibalisation, using a query plus page grouping.

The `top_queries` and `top_pages` tools rank by clicks, then impressions.
The general `query_performance` tool returns rows in Google's order (clicks,
then alphabetical), which is what makes paging work. For a ranked shortlist,
ask for "top" queries or pages.

### Comparing periods

- "Compare the last 28 days with the 28 days before."
- "Compare last month with the same month last year."
- "Which pages lost the most clicks compared with the previous period?"
- "Did anything change for mobile traffic in the UK?" Filters apply to both
  periods.

Comparisons use **final data only** and end on the latest complete day, so
a half-finished last day cannot look like a drop. Each row is marked `new`,
`lost` or `changed`, sorted by the biggest change in clicks. The window
totals always come from a separate ungrouped query, so they include
anonymised queries.

### Indexing and URL Inspection

- "Is https://example.com/widgets/ indexed?"
- "Check these five URLs and tell me which are not indexed and why."
- "Does Google pick the canonical I declared for /pricing/?"

You get the verdict, coverage state, last crawl, robots.txt and fetch state,
and whether Google's chosen canonical matches yours. This is the indexed
version, not a live test. Up to 10 URLs per question. Google allows 2,000
inspections per property per day; the server stops at 1,900 and tells you,
and the count resets at midnight Pacific time.

### Sitemaps

- "Are there any problems with my sitemaps?"
- "When did Google last download my sitemap?"

Sitemaps with errors are listed first.

### Large exports

- "Export all queries and pages for the last 16 months to CSV."

Anything over 1,000 rows goes to a CSV file on your computer, up to 500,000
rows. Claude gets the file path and row count, never the rows, so a big
export does not flood the conversation. Files go to `~/.gsc-mcp/exports`
unless you set `GSC_EXPORT_DIR`. Only your user account can read them.

## Dates

- **Named ranges** end 3 days ago, because of the data lag: last 7 days,
  last 28 days, last 3, 6, 12 or 16 months. The default is last 28 days.
- **Exact dates** work too: "from 2026-03-01 to 2026-03-31". Give both a start
  and an end; a start alone is refused instead of guessed.
- **16 months** is all the history Search Console keeps. Older start dates
  are moved up to the earliest available day.
- **Final or provisional.** Most answers include the latest provisional
  days, which can still change. Comparisons use final data only. Ask for
  "final data only" if you need stable numbers.

## Filters

You can narrow any question by query, page, country, device or search
appearance, combining several:

- "...only for pages containing /blog/"
- "...excluding queries that contain my brand name"
- "...for mobile only" (devices: desktop, mobile, tablet)
- "...for the United States" (countries use three-letter codes, e.g. usa,
  gbr, deu; Claude converts names for you)
- "...matching the regex ^how to"

## Search types

Web is the default. You can also ask about image, video, news, Google News
and Discover traffic: "Show Discover clicks by day for the last 3 months."
Google does not report position for Discover and Google News. Those answers
leave position out instead of showing zero.

## Reading the numbers

- **Query rows never add up to the totals.** Anonymised queries are left
  out, and Google drops some rows when grouping by query or page. Each answer
  carries a short note when this applies.
- **Numbers differ slightly from the Search Console UI.** Both are right.
  The UI and API aggregate differently, and recent days are still changing.
- **Position** is the average position, where 1 is the top result. Lower is
  better, so a negative change is an improvement.
- **CTR** is clicks divided by impressions.

## Example workflows

**Investigating a traffic drop.** "Compare the last 28 days with the
previous 28 days by page." Then: "For the three pages that lost the most,
compare by query." Then: "Inspect those three URLs." Then: "Any sitemap
errors?" Then check the dates against "How fresh is the data?" to rule out
the lag.

**Monthly report.** "Give me last month's totals compared with the month
before and the same month last year, the top 10 queries and pages, and
anything new or lost in the top 50."

**Content opportunities.** "Find queries where I rank 5 to 15 with over 100
impressions in the last 3 months, grouped by page." These pages are the
cheapest to improve.

**Indexing audit.** "Export all pages with impressions in the last 3
months." Then compare that list with your sitemap or CMS, and ask Claude to
inspect up to 10 of the missing URLs at a time.

## Privacy

Everything a tool returns is sent to the model provider you use, as with
any MCP server. Search queries sometimes contain personal data, because
people search for their own names, emails and phone numbers. Set
`GSC_REDACT_PII=true` to drop rows whose query contains an email address or
a run of 9 or more digits. Each answer then says how many rows were dropped.
It is a blunt filter, not a guarantee.

To limit which properties the server can read, set
`GSC_PROPERTY_ALLOWLIST=sc-domain:example.com,https://example.org/`. Every
other property is refused.

The server is read-only. It requests the `webmasters.readonly` scope and
refuses to start with anything wider, so it cannot change your Search
Console settings.

## What it cannot do

Google's API does not expose these reports, so no MCP server can provide
them: the Pages (index coverage) report, Links, Core Web Vitals, rich result
and enhancement reports, crawl stats, manual actions, security issues and
removals. See the table in the [README](../README.md#what-it-can-and-cannot-read).

## When something goes wrong

Every failure comes back with a reason and a sentence naming the fix. If
that does not help, run `gsc-mcp-server doctor` in a terminal and see
[troubleshooting](troubleshooting.md).
