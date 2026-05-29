# ADR 0002: Split Build from Vouch in `vouch:package`

## Status
Accepted

## Context

`vouch:package` originally ran `build:zarf-package → olm:setup → ./olm vouch` as a single action, accepting the CAT OIDC identity token (`olm_identity_token`) as a static input minted by the caller before invocation.

For packages with large images, `build:zarf-package` (image pull + SBOM generation) can exceed 30 minutes. GitHub Actions OIDC tokens and GitLab `id_tokens` are minted at job start with short lifetimes. By the time `./olm vouch` reaches the CAT token-exchange, the token has expired and the vouch fails.

The monolithic form also accumulated 9 build-specific inputs (`zarf_path`, `architecture`, `zarf_flavor`, `witness_key_path`, `witness_workingdir`, `enable_sigstore`, `enable_archivista`, `fulcio_oidc_issuer`, `build_command`) alongside the vouch-specific inputs, making the task interface difficult to reason about.

An additive approach (adding a `package_path` escape hatch to skip the build) was considered but rejected: it would increase the already-large input surface, leave the broken monolithic form available, and split maintenance between two code paths.

## Decision

Remove the `build:zarf-package` invocation from `vouch:package`. The task now accepts an optional `zarf_package` input pointing to a pre-built `zarf-package-*.tar.zst` (falls back to auto-detecting the most recent file in the working directory) and performs only the vouch steps (OLM setup + `./olm vouch`).

Consumers call the two tasks as separate CI steps. The CI workflow controls when the OIDC token is minted — immediately before the vouch step, well within token lifetime.

## Consequences

**Benefits:**
- Consumers mint the OIDC token immediately before vouching, eliminating token expiry for long builds
- `vouch:package` sheds 9 build-only inputs; the interface is scoped to vouch concerns only
- Consumers gain explicit control over the build → vouch boundary (e.g., separate CI stages, parallel matrix builds feeding a single vouch)

**Trade-offs:**
- Breaking change: consumers using the monolithic form must add a separate build step to their CI workflows
- Requires a major version bump and migration guidance in release notes
- Consumer CI workflows become slightly more verbose (two task invocations instead of one)
