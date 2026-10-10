# Setup: service account (a key, no browser)

Use this path if you read a fixed set of properties and want it to never
break. There is no consent screen, no publishing status and no token expiry.

The trade: access does not follow any human account. Every property needs the
service account email added as a user, one at a time. A property you can see
in the Search Console UI stays invisible to the server until you do that.

> **You are about to put a private key on disk.** It is a standing credential:
> anyone who copies that file can read your Search Console data until you
> revoke the key. Use a dedicated Google Cloud project, keep the file outside
> this repository, and `chmod 600` it.

## 1. Create a project

<https://console.cloud.google.com/projectcreate>

Dedicated, with no other permissions. Nothing else should live in it.

## 2. Enable the Search Console API

APIs & Services, Library, **Google Search Console API**, Enable.

## 3. Create the service account

IAM & Admin, Service Accounts, **Create service account**.

- Name: `gsc-reader`
- Grant it **no** project roles. It needs none. Its access comes from Search
  Console, not from Google Cloud IAM.

## 4. Create a key

Open the service account, **Keys**, Add key, Create new key, **JSON**.

Save it outside this repository and lock it down:

```sh
mkdir -p ~/.config/gsc-mcp
mv ~/Downloads/gsc-*.json ~/.config/gsc-mcp/gsc-reader-key.json
chmod 600 ~/.config/gsc-mcp/gsc-reader-key.json
```

## 5. Find the email

```sh
export GSC_AUTH_MODE=service_account
export GSC_SERVICE_ACCOUNT_KEY="$HOME/.config/gsc-mcp/gsc-reader-key.json"
uv run gsc-mcp-server auth
```

That prints the service account email, which looks like:

```
gsc-reader@your-project-id.iam.gserviceaccount.com
```

## 6. Add it to each property

This is the step people miss.

In Search Console, for **every** property you want to read:

1. Open the property.
2. Settings, **Users and permissions**.
3. Add user.
4. Paste the service account email.
5. Permission: **Full** or **Restricted**. Restricted is enough for reading.

You need owner permission on the property to do this. For a property you do
not own, the owner has to add it for you.

## 7. Verify

```sh
uv run gsc-mcp-server doctor
```

If `properties` reports zero, step 6 has not taken effect for any property.
That is the expected message, not a bug.

## Revoking

Delete the key in Google Cloud Console (service account, Keys), or remove the
email from the property in Search Console. The key never expires on its own,
so revoking is the only way it stops working.

## Client configuration

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
