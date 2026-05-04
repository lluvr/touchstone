# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability in the `clarethium-touchstone` library, please do NOT open a public GitHub issue. Instead, contact the editor body privately.

**Contact:** open a GitHub Security Advisory at <https://github.com/Clarethium/touchstone/security/advisories/new>

You can expect:

- Acknowledgement within 7 days
- Initial assessment within 14 days
- Coordinated disclosure timeline based on severity

## Scope

In scope:

- The `clarethium-touchstone` library code
- The library's dependency declarations (`pyproject.toml`)
- The CI/CD workflows that build and (eventually) publish releases
- The Touchstone Standard's threshold values and reference test cases (a security issue here would be: a threshold or test case that would allow malicious content to evade detection)

Out of scope:

- Library behavior on adversarial AI outputs designed to evade structural detection. The Standard documents known gaming vectors (Section 9 of the methodology); evasion of structural detection by design is a research problem, not a security vulnerability.
- Third-party LLM clients the user supplies via the
  ``BaselineGenerator`` callable for Layer 1a. The library imports no
  specific provider SDK; security of the user-supplied client is the
  user's responsibility.
- Misuse of the library for purposes outside its intended scope

## Supported versions

Pre-1.0: only the latest 0.x release is supported.

Post-1.0: the latest minor version on each supported major version is supported. Older versions receive critical security fixes for 12 months after a new major version ships.

## Security model

The library is designed to operate offline. All eleven measurement layers
in v0.1 run without making any network requests EXCEPT Layer 1a (heading
defaultness), which only runs when the caller supplies both a ``topic``
argument AND a ``BaselineGenerator`` callable. The library imports no
specific provider SDK; the network call (if any) happens inside the
caller-supplied callable.

The library does not handle authentication, secrets, or persistent storage. Users are responsible for securing API keys and managing data the library processes.

The Standard explicitly notes (Section 9 of methodology) gaming vectors that humans aware of the implementation can exploit. Treat substrate output as one input to a quality decision, not the only input.

## Disclosure

Vulnerabilities are disclosed via GitHub Security Advisories. Patches ship as point releases.

Credit is given to reporters who choose to be acknowledged.
