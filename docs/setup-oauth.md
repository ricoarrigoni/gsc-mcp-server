# Setup: OAuth (sign in as yourself)

Use this path if the properties you read change over time, or you manage many
of them. Access follows your Google account automatically.

> **Read this first.** A Google OAuth app left in **Testing** status expires
> every refresh token after **7 days**. The server works for a week, then
> fails with `invalid_grant`. Step 5 is what prevents it. Do not skip it.

Google calls this area the **Google Auth Platform**. The old "OAuth consent
screen" page was split into Branding, Audience, Clients and Data Access.

## 1. Create a project

<https://console.cloud.google.com/projectcreate>

Use a dedicated project with no other permissions in it. Name it something
like `gsc-mcp`.

## 2. Enable the Search Console API

APIs & Services, Library, search for **Google Search Console API**, Enable.

## 3. Configure the app

Google Auth Platform, **Get started**.

- App name: anything that does not resemble a Google product.
- User support email: your own.
- Audience: **External**. (Internal exists only for Google Workspace
  organisations.)
- Contact email: your own.

## 4. Add the scope

Google Auth Platform, **Data Access**, Add or remove scopes.

Add exactly one:

```
https://www.googleapis.com/auth/webmasters.readonly
```

Do not add `.../auth/webmasters`. The server refuses to start with the
read-write scope, by design.

## 5. Publish the app (this is the important step)

Google Auth Platform, **Audience**, Publishing status, **Publish app**.

Your app moves from Testing to In production. It stays *unverified*, which is
fine for personal use:

- You will see a "Google hasn't verified this app" screen once. Click
  Advanced, then continue.
- Unverified apps are capped at 100 users in total. Irrelevant for one person.
- Verification is only needed if you intend to let strangers sign in to *your*
  Google Cloud project, which this server does not do. Each self-hoster brings
  their own.

Leaving the app in Testing is the single most common cause of
"it worked last week".

## 6. Create the OAuth client

Google Auth Platform, **Clients**, Create client.

- Application type: **Desktop app**
- Name: `gsc-mcp-server`

Download the JSON. Save it **outside this repository**, for example:

```sh
mkdir -p ~/.config/gsc-mcp
mv ~/Downloads/client_secret_*.json ~/.config/gsc-mcp/client_secret.json
chmod 600 ~/.config/gsc-mcp/client_secret.json
```

## 7. Point the server at it

```sh
export GSC_AUTH_MODE=oauth
export GSC_OAUTH_CLIENT_SECRET="$HOME/.config/gsc-mcp/client_secret.json"
```

## 8. Sign in

```sh
uv run gsc-mcp-server auth
```

A browser opens. Choose the Google account that has access to your Search
Console properties. The refresh token is stored in your OS keyring.

## 9. Verify

```sh
uv run gsc-mcp-server doctor
```

All checks should pass and your properties should be listed.

## 10. Confirm the 7-day trap is gone

Write down today's date. In **9 days**, run `doctor` again without
re-authorising. If it still passes, publishing worked. If it fails with
`invalid_grant`, the expiry applies to unverified production apps too, and
you should switch to [the service account path](setup-service-account.md).

## Client configuration

Claude Code or Claude Desktop, in `claude_desktop_config.json` or your MCP
config:

```json
{
  "mcpServers": {
    "gsc": {
      "command": "uvx",
      "args": ["gsc-mcp-server"],
      "env": {
        "GSC_AUTH_MODE": "oauth",
        "GSC_OAUTH_CLIENT_SECRET": "/absolute/path/to/client_secret.json"
      }
    }
  }
}
```
