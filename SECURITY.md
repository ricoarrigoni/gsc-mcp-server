# Security

## Reporting a vulnerability

Please do not open a public issue for a security problem. Open a private
security advisory on this repository instead, via the Security tab.

Expect an initial reply within a week. This project is maintained as time
allows.

## What this server does and does not protect

This server holds a credential that can read your Google Search Console data.
It requests the read-only scope only, so it cannot change anything in your
Search Console account.

It cannot protect the data it returns. Every row a tool returns is sent to
whichever model provider you point it at (Anthropic, OpenAI, or another). That
is the purpose of the server. Search queries sometimes contain personal data,
because people search for their own names, email addresses and phone numbers.
If you query a property you do not own, the owner's data processing agreement
decides whether sending that data to a model provider is allowed. Check first.

Set `GSC_REDACT_PII=true` to drop rows whose query matches email, phone or
long-digit patterns. It is a blunt filter, not a guarantee.

## Credential handling

  - Never commit a credential. `.gitignore` and the gitleaks pre-commit hook
    are there to stop you, but they are a backstop, not a substitute for care.
  - Keep the OAuth client file and any service account key outside this
    repository.
  - `chmod 600` any service account key.
  - Use a dedicated Google Cloud project with no other permissions.
  - OAuth tokens are stored in the OS keyring by default.
