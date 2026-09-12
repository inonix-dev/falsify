# Security Policy

## Supported versions

The latest release on PyPI (`falsify-backtest`) is the only supported version.
Fixes ship forward; there are no backported patch branches.

## Threat model

falsify is a local CLI. It reads a CSV you point it at, computes, and writes to
stdout. It makes no network calls, holds no credentials, and writes no state or
config files. So the realistic risks are narrow:

- Malicious CSV input causing arbitrary code execution, or a crash a caller
  can turn into something worse.
- Path handling that reads or writes outside what the user asked for.
- A supply-chain problem in the published PyPI package.

**Not a vulnerability:** a wrong verdict on a backtest. A check that passes a
bad strategy is a correctness bug — please report it as a
[false negative issue](https://github.com/kire21b/falsify/issues/new/choose),
in public, where it's most useful to everyone.

## Reporting

Report privately via
[GitHub Security Advisories](https://github.com/kire21b/falsify/security/advisories/new).
Please don't open a public issue for a suspected vulnerability.

Include: version (`falsify --version`), Python version, OS, a minimal input
that reproduces it, and what you observed.

Expect a first response within 7 days. This is a small unfunded project —
there is no bounty, and no guaranteed fix timeline, but credible reports get
credited in the release notes unless you'd rather not be.
