# Security Policy

## Supported versions

Security fixes are applied to the latest `0.2.x` release and the `main` branch.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use
[GitHub Security Advisories](https://github.com/Riceal28/AxiomPy/security/advisories/new)
and include:

- affected version and Windows version,
- reproduction steps or a minimal command,
- expected and observed impact,
- any relevant logs with paths and secrets redacted.

Please allow time for confirmation and a coordinated fix before public disclosure.

## Scope

AxiomPy builds shell commands and launches FFmpeg-family executables. Users are
responsible for the FFmpeg binaries they install or bundle and for reviewing commands
before running untrusted input. Report command-injection, unsafe path handling,
credential exposure or dependency issues through the private advisory flow.
