# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

Shared task library for ISV's onboarding into the UDS Army platform. Provides reusable Maru/UDS task namespaces that teams include in their own `tasks.yaml` to get a complete supply-chain-security pipeline: lint → scan → build → vouch → publish.

All automation uses **UDS CLI** (task runner). No npm, go, or traditional build systems.

## Commands

```bash
# Lint
uds run lint          # all linting (YAML + shell + tasks dry-run)
uds run yaml          # YAML lint only (yamllint)
uds run shell         # shell script lint only (shellcheck)
uds run tasks         # dry-run all tasks

# Test
uds run test          # integration tests

# Full local pipeline (requires witness key + OLM credentials)
uds run scan-and-vouch
uds run pipeline
```

### Tool setup (first time)
```bash
uds run setup:uds-cli
uds run setup:witness
uds run setup:cosign

# Generate local ED25519 signing key for local runs
openssl genpkey -algorithm ed25519 -out witness-key.pem
openssl pkey -in witness-key.pem -pubout -out witness-pub-key.pem
```

## Architecture

### Pipeline Flow
```
attest:lint  →  scan:security  →  build:zarf-package  →  vouch:package  →  publish:zarf-package
     ↓                ↓                   ↓                    ↓
lint-witness.json  *.sarif.json   zarf-create-witness.json  (submitted to OLM/CAT)
```

Each step produces a signed **in-toto attestation** (`*-witness.json`). In CI, signing uses Sigstore/Fulcio OIDC (keyless). Locally, signing uses an ED25519 key (`--with witness_key_path=...`).

### Task Namespace Design

`tasks.yaml` at root orchestrates and re-exports. All reusable task files live in `tasks/`:

| File | Namespace | Purpose |
|------|-----------|---------|
| `tasks/setup.yaml` | `setup:` | Install UDS CLI, Cosign, Witness, Gitleaks, OpenGrep, OLM |
| `tasks/attest.yaml` | `attest:` | Wrap consumer's `lint` task with Witness attestation |
| `tasks/scan.yaml` | `scan:` | Gitleaks (secrets) + OpenGrep (SAST), produces SARIF |
| `tasks/scorecard.yaml` | `scorecard:` | OpenSSF Scorecard repo-posture analysis, produces SARIF |
| `tasks/ossinsight.yaml` | `ossinsight:` | OSSInsight community-health data (stargazer geography/orgs), produces one JSON evidence file |
| `tasks/build.yaml` | `build:` | Build Zarf package with Witness attestation |
| `tasks/vouch.yaml` | `vouch:` | Build + attest + submit to OLM/CAT |
| `tasks/publish.yaml` | `publish:` | OCI registry publish via Zarf |
| `tasks/olm.yaml` | `olm:` | OLM CLI setup |

### How Teams Consume This

Teams add to their own `tasks.yaml`:
```yaml
includes:
  - attest: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/attest.yaml
  - scan: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/scan.yaml
  - build: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/build.yaml
  - vouch: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/vouch.yaml
  - publish: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/publish.yaml
```

Consumers **must** define a `lint` task — `attest:lint` calls it internally.

### Key Design Patterns

- Tasks use `--with` parameters for customization (paths, versions, flags)
- Tools install to `$HOME/.local/bin` with idempotency checks
- Local vs CI signing: ED25519 key path param vs Sigstore OIDC (auto-detected)
- The `src/nginx/` and `chart/` directories are an **example Zarf package** (nginx), not the core library
- `examples/` contains copy-paste CI workflow templates for consumers

### Version Tracking

Tool versions live as inline comments in `tasks/` files (e.g., `# renovate: datasource=github-releases`). Renovate auto-opens PRs to bump them. Do not hardcode versions without the Renovate comment.

### Release Process

Release Please automates versioning. Merge to main → release-please tags + creates GitHub release. No manual version bumps needed.
