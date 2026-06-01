# ADR 0003: CAT-Brokered Fulcio Signing via UDS Fulcio Instance

Witness attestations are signed using `fulcio.uds-mil.us` (UDS-hosted Fulcio) with a token minted by CAT, replacing the previous direct OIDC flow against `fulcio.sigstore.dev`.

## Context

The original signing approach used `fulcio.sigstore.dev` with a CI OIDC token: Witness would exchange the token directly with Sigstore's public Fulcio instance. This required Chainloop to trust the public Sigstore trust root, and required consumers to configure a `fulcio_oidc_issuer` override for non-GitHub CI providers (e.g. `https://gitlab.com`). Defense Unicorns had to manually configure OIDC trust in Fulcio for each provider.

OLM gained a `tools generate-fulcio-token` subcommand that calls CAT as a broker: CAT authenticates the CI identity, checks the Organization's configured project allowlist (GitHub or GitLab), and issues a short-lived JWT. That token is passed to Witness as `--signer-fulcio-token` against `fulcio.uds-mil.us`. Consumers self-serve provider configuration in the CAT UI — no manual trust configuration per provider required.

## Decision

Replace direct Sigstore OIDC signing with CAT-brokered Fulcio signing:

- A new `olm:generate-fulcio-token` task calls `olm tools generate-fulcio-token` and writes the result to `.fulcio-token`
- Witness tasks (`attest:lint`, scan tasks, `build:zarf-package`) read `.fulcio-token` when present; fall back to browser OIDC against `fulcio.uds-mil.us` locally
- The `fulcio_oidc_issuer` task input is removed — provider trust is now CAT's responsibility. `enable_sigstore` remains and controls whether Witness attestation runs at all.
- CI workflows call `olm:generate-fulcio-token` explicitly before Witness-attested steps, and again before `build:zarf-package` as a token refresh (Fulcio tokens expire; builds can exceed 30 minutes)

## Considered Options

**Pass `olm_cat`/`olm_org`/`olm_identity_token` to every Witness task** — rejected. Would have proliferated OLM-specific inputs onto tasks (`attest:lint`, scan tasks) that currently need zero OLM knowledge, coupling attestation signing to the vouch infrastructure at every callsite.

**Keep `fulcio.sigstore.dev` as fallback** — rejected. Two trust roots in play means Chainloop must trust both; mixed pipelines (some steps via sigstore.dev, others via uds-mil.us) produce confusing policy failures. The fallback would silently undermine the new approach for consumers who haven't migrated.

## Consequences

- All attestations in a pipeline run share a single trust root (`fulcio.uds-mil.us`)
- CI workflows must call `olm:generate-fulcio-token` before any Witness-attested step — this is a breaking change for existing consumers
- Token expiry during long builds is managed by explicit refresh calls in CI, not by internal task logic
- Local dev without a signing key triggers a browser OIDC flow against `fulcio.uds-mil.us` — behavior subject to change as the UDS Fulcio OIDC configuration stabilizes
