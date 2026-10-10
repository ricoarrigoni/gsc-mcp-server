# Connecting an MCP client

The server speaks stdio. The client launches it as a subprocess, so the
credential path goes in the client's `env` block, not your shell. Use
**absolute paths**: `~` is not expanded there.

Run `gsc-mcp-server doctor` first. If it does not pass in a terminal, it will
not pass through a client either, and the client gives you a worse error.

## Claude Code, desktop app

Put a `.mcp.json` in the project folder, then open that folder in the Code
tab. Replace the credential path with your own.

```json
{
  "mcpServers": {
    "gsc": {
      "command": "uvx",
      "args": ["gsc-mcp-server"],
      "env": {
        "GSC_AUTH_MODE": "service_account",
        "GSC_SERVICE_ACCOUNT_KEY": "/absolute/path/to/gsc-reader-key.json"
      }
    }
  }
}
```

`uvx` runs the latest release from PyPI. To pin one, use
`"args": ["gsc-mcp-server@0.1.0"]`. Some clients do not inherit your shell's
`PATH`; if the client cannot find `uvx`, give its absolute path (`which uvx`).

Running from a clone instead? Use `"command": "uv"` with
`"args": ["run", "--directory", "/absolute/path/to/gsc-mcp-server", "gsc-mcp-server"]`.

## Claude Code, terminal CLI

Same file works. Or register it globally:

```sh
claude mcp add-json gsc -s user '{ ...the server object above... }'
```

Note that `add-json` takes only the inner server object, without the
`mcpServers` wrapper.

## Claude Desktop, Chat tab

Merge the full block, `mcpServers` wrapper included, into:

```
~/Library/Application Support/Claude/claude_desktop_config.json
```

Restart the app afterwards.

## Checking it worked

Ask the client to list your Search Console properties. A correct answer names
each property and its permission level. If it returns none, the credential
reached Google but has no property access yet: see the setup guide for your
auth mode.

## A note on `.mcp.json` in a shared repo

`.mcp.json` normally gets committed so a team shares one config. This repo
gitignores it, because the file names an absolute path to a credential on one
machine. Keep it local.
