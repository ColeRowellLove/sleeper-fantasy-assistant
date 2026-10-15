# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's private reporting:
**Security tab -> Report a vulnerability**. You'll get an acknowledgement within a few days.

## Scope notes

- The app only reads Sleeper's public, unauthenticated API; it never asks for Sleeper passwords.
- Secrets (API keys for email, SMS, LLM and data providers) are supplied through environment
  variables and must never be committed. Secret scanning and push protection are enabled on this repo.

If you find a committed secret, report it privately so it can be rotated.
