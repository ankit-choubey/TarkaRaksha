# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Financial & Operational Safety Guarantees

TarkaRaksha enforces strict transaction integrity and safety principles:

1. **Deterministic Verification is Authoritative**: AI and LLM inferences are advisory only and never possess authority to approve payments, alter money values, or override deterministic integrity rules.
2. **Untrusted LLM Output**: Natural language outputs and AI agent actions are never granted execution permission without passing schema validation, limit checks, and state machine verification.
3. **No Secrets in Source Control**: Live API credentials, Razorpay secret keys, and webhook signing secrets must never be committed to Git. All secrets are loaded via environment variables defined in `.env.example`.
4. **Integer Minor Units**: Floating-point arithmetic for currency calculations is strictly prohibited to prevent financial rounding errors.

## Reporting a Vulnerability

If you discover a security vulnerability or financial integrity bypass within TarkaRaksha, please report it responsibly:

- **Email**: ankit.choubey@example.com (or via repository maintainer contact)
- Please do not disclose vulnerabilities in public issues or discussions.
- Include a detailed description of the flaw, reproduction steps or payload, and potential financial impact.
