# Troubleshooting

## Run this first

```sh
uv run gsc-mcp-server doctor
```

It checks auth mode, credential, scope, token refresh and property access, and
names the next action on the first failure. Paste its output into any issue
you open. Redact the property names if you prefer.

## It worked last week and now fails with `invalid_grant`

**OAuth mode.** Your app is still in Testing status, where Google expires
every refresh token after 7 days.

Fix: Google Auth Platform, Audience, Publishing status, **Publish app**. Then
`gsc-mcp-server auth` again. See [setup-oauth.md](setup-oauth.md) step 5.

**Service account mode.** The key was revoked or deleted. Create a new one.

## `access_denied` during sign-in

Your app is in Testing and your Google account is not on the test user list.
Either publish the app (preferred) or add the account under Google Auth
Platform, Audience, Test users.

## `doctor` says zero properties

**Service account mode.** The email has not been added to any property. See
[setup-service-account.md](setup-service-account.md) step 6. Properties
visible in the Search Console UI are not visible to a service account until
it is added as a user on each one.

**OAuth mode.** You signed in with a Google account that has no Search Console
properties. Run `gsc-mcp-server auth` again and pick the right account.

## 403 on one property but others work

The credential has no permission on that property. In OAuth mode, check the
account's access in Search Console. In service account mode, add the email to
that property.

## 404 property not found

`siteUrl` must be passed exactly as `list_properties` returned it. Search
Console matches it byte for byte:

- `sc-domain:example.com` is a Domain property
- `https://example.com/` is a URL-prefix property, trailing slash included

These are different properties. Never normalise, strip or add a slash.

## Numbers do not match the Search Console UI

Expected. The API and the UI are both right.

- Query rows exclude anonymised queries, so they never sum to the property
  total.
- Grouping by page or query makes Google drop rows to keep the query fast.
- `byPage` and `byProperty` aggregation give different clicks, impressions and
  position for the same period.
- The last 2 to 3 days are incomplete. `dataState: "final"` excludes them.

## `reason: quota_guard` from `inspect_url`

The server refuses URL Inspection locally at 1,900 calls per property per day,
just under Google's limit of 2,000. The count resets at midnight Pacific time,
matching Google. It is stored in `GSC_STATE_DIR`.

## `reason: io_error` from `export_query`

The CSV could not be written. Point `GSC_EXPORT_DIR` at a directory the MCP
client's user can write to, with free space. A failed export leaves no partial
file behind.

## `compare_periods` ends earlier than I expected

It compares final data only, so a named range such as `last_28_days` ends on
the latest final day reported by `get_data_freshness`, not on today minus a
fixed lag. Partial recent days would otherwise read as a drop.

## `position` is missing from rows

Google does not report position for the `discover` and `googleNews` search
types. The other metrics are present. This is not an error.

## Server refuses to start: scope too wide

The credential grants `.../auth/webmasters`, the read-write scope. This server
is read-only by design and will not run with a write credential. Re-authorise
with `webmasters.readonly` only.

## `uvx gsc-mcp-server` cannot find the credential

The MCP client launches the server with its own environment, not your shell's.
Put the variables in the `env` block of your MCP config, with **absolute**
paths. `~` is not expanded there.
