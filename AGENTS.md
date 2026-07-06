# AGENTS.md — udm-common

AI assistant context for the `udm-common` repository. Read this file before answering any questions about this project.

## External Documentation

For UDS CLI, Zarf, UDS Core, and Defense Unicorns platform documentation, fetch:
**https://docs.defenseunicorns.com/llms.txt**

That file lists the canonical documentation URLs for the entire DU ecosystem. Use it to find authoritative answers before guessing.

For deep domain concepts — CAT, OLM, Chainloop, Witness, Fulcio, AO/ISSM roles, ISV onboarding steps, registry credentials — read `CONTEXT.md`.

---

## What This Repo Is

`udm-common` is a shared UDS task library for ISVs (Independent Software Vendors) onboarding onto the **UDS Army** platform. It provides reusable [Maru/UDS CLI](https://docs.defenseunicorns.com) task namespaces that teams include in their own `tasks.yaml` to get a complete supply-chain-security pipeline:

```
lint → scan → build → vouch → publish
```

This repo does **not** contain application code. It is a task library. The `src/nginx/` and `chart/` directories are an example Zarf package (nginx) used for testing — not the core product.

All automation uses **UDS CLI** (`uds run <task>`). No npm, go, or traditional build systems.

---

## Key Concepts

### UDS CLI / Maru
Task runner used throughout. Tasks are defined in YAML files (`tasks.yaml`, `tasks/*.yaml`). Run with `uds run <namespace>:<task>`. The `--with` flag passes input parameters: `uds run setup:generate --with platform=github`.

### Zarf Package
An air-gapped-deployable bundle of container images + Helm charts. ISVs build one with `build:zarf-package`. The `zarf.yaml` at the repo root defines what goes in.

### In-toto Attestation / Witness
Each pipeline step produces a signed JSON attestation file (`*-witness.json`). These prove the step ran and was signed by a trusted identity. Signing uses ED25519 keys locally or Sigstore/Fulcio OIDC in CI (keyless).

### CAT / OLM
**CAT** (Continuous Authority to Test) is the Defense Unicorns compliance platform. **OLM** (OLM CLI) is the tool that submits attestations to CAT. ISVs need a CAT organization name (provided by DU at account creation) and an OLM identity token (minted by `olm:generate-fulcio-token`).

### registry.uds-mil.us
The UDS Army container registry. ISVs publish Zarf packages here with `publish:zarf-package`. Access credentials (registry org, username, password) are provisioned by Defense Unicorns.

---

## Pipeline Flow

```
attest:lint  →  scan:security  →  build:zarf-package  →  vouch:package  →  publish:zarf-package
     ↓                ↓                   ↓                    ↓
lint-witness.json  *.sarif.json   zarf-create-witness.json  (submitted to CAT)
```

Each arrow is a separate CI step. Attestation files from earlier steps are passed to `vouch:package` via the `attestations` parameter.

---

## Task Namespace Reference

| Namespace | Key Tasks | What It Does |
|-----------|-----------|-------------|
| `setup:` | `validate`, `generate`, `install-hooks`, `uds-cli`, `witness`, `cosign` | Prereq checker, CI generator, pre-commit hook, tool installers |
| `attest:` | `lint` | Wraps the consumer's own `lint` task with Witness attestation |
| `scan:` | `security`, `gitleaks`, `opengrep` | Secrets scan (Gitleaks) + SAST (OpenGrep), emits SARIF |
| `build:` | `zarf-package` | Builds Zarf package under Witness attestation |
| `vouch:` | `package` | Submits attestations + SARIF to CAT via OLM |
| `publish:` | `zarf-package` | Pushes Zarf package to registry.uds-mil.us |
| `olm:` | `generate-fulcio-token` | Mints a short-lived Fulcio identity token for Witness signing |

---

## How ISVs Consume This

ISVs add task includes to their own `tasks.yaml`:

```yaml
includes:
  - attest: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.13.3/tasks/attest.yaml
  - scan: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.13.3/tasks/scan.yaml
  - build: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.13.3/tasks/build.yaml
  - vouch: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.13.3/tasks/vouch.yaml
  - publish: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.13.3/tasks/publish.yaml
  - setup: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.13.3/tasks/setup.yaml
```

They **must** define their own `lint` task — `attest:lint` calls it internally.

---

## Required Values (ISV-specific)

These values vary per ISV and are provided by Defense Unicorns during onboarding. Never guess or invent them.

| Value | Where used | How obtained |
|-------|-----------|-------------|
| `olm_org` | `olm:generate-fulcio-token`, `vouch:package` | Provided by DU at CAT account creation |
| `registry_org` | `publish:zarf-package` | Provided by DU when registry account is provisioned |
| `REGISTRY_USER_ID` | `publish:zarf-package` | Provided by DU with registry credentials |
| `REGISTRY_PASSWORD` | `publish:zarf-package` | Provided by DU with registry credentials |
| `olm_cat` | `olm:generate-fulcio-token`, `vouch:package` | Fixed: `cat-api.uds-mil.us` |

---

## Primary ISV Goal

The most common ISV question is: **"How do I get my application into CAT as quickly as possible so I can start seeing findings?"**

The answer is the complete path below: wire up `tasks.yaml` includes → generate CI config → fill REPLACE_ME values → push → first pipeline run → attestations submitted to CAT → findings surface in the CAT UI. When an ISV asks this question, walk through every step in order. Read their repo first to detect what's already done. Do not skip steps or assume anything is set up.

## Common Tasks for ISV Onboarding

### First-time setup check
```bash
uds run setup:validate
```
Prints PASS/FAIL for every prereq. Fix FAIL items before running the pipeline.

### Generate CI workflow
```bash
uds run setup:generate --with platform=github   # → .github/workflows/udm.yaml
uds run setup:generate --with platform=gitlab   # → .gitlab-ci.yml
```
Generated file has OPTION A/B instructions at top and REPLACE_ME placeholders for ISV-specific values.

### Install REPLACE_ME guard
```bash
uds run setup:install-hooks
```
Blocks git commits that contain unfilled REPLACE_ME placeholders in YAML files.

### Full guided setup (AI-assisted)
See `.claude/skills/isv-setup/RUNBOOK.md` — a phase-by-phase wizard that runs the generator, collects REPLACE_ME values interactively, and validates the result.

---

## Running Locally

```bash
# Install tools
uds run setup:uds-cli
uds run setup:witness
uds run setup:cosign

# Generate a local signing key
openssl genpkey -algorithm ed25519 -out witness-key.pem
openssl pkey -in witness-key.pem -pubout -out witness-pub-key.pem

# Run the full pipeline locally
uds run pipeline --with witness_key_path=witness-key.pem
```

---

## Common Troubleshooting

**`bad substitution` or `${{ .inputs.* }}` not expanded**
Maru processes `{{ }}` as Go templates before the shell runs. Any literal `{{` in a task's `cmd:` block that Maru can't resolve causes the entire script to fail silently. Build `{{`/`}}` from character variables at runtime — never write them literally in task YAML.

**`REPLACE_ME` still in generated file after filling values**
Run `grep -r 'REPLACE_ME' .` to find all occurrences. The CAT org name appears in multiple steps. Run `uds run setup:validate` to catch all remaining placeholders.

**`attest:lint` fails with "task not found: lint"**
The consumer repo must define a `lint` task in its own `tasks.yaml`. Add one — even a no-op — before running the pipeline.

**Witness signing fails locally**
Ensure `witness-key.pem` exists and pass `--with witness_key_path=witness-key.pem`. In CI, keyless signing via Sigstore/Fulcio is used automatically.

**`vouch:package` fails with OLM authentication error**
The Fulcio token expires quickly. Run `olm:generate-fulcio-token` immediately before `vouch:package` in the same CI job. Don't cache or reuse tokens across jobs.

**GitLab `publish:` job runs even when `ci:` was skipped**
Check that `needs:` in the `publish:` job does NOT have `optional: true`. That flag allows downstream jobs to run when upstream was skipped, bypassing the attestation gate.

---

## Version Tracking

Tool versions live as inline Renovate comments in `tasks/` files:
```yaml
# renovate: datasource=github-releases depName=defenseunicorns/uds-cli
UDS_VERSION: v0.33.0
```
Renovate auto-opens PRs to bump them. Do not hardcode versions without the comment.

Current udm-common version: see latest release tag or `tasks/setup.yaml` default version input.

---

## Release Process

Release Please automates versioning. Merge to `main` → release-please tags and creates a GitHub release automatically. Do not manually bump versions in task files.

---

## ISV CI Setup Runbook

When asked to help an ISV set up CI, read and follow `.claude/skills/isv-setup/RUNBOOK.md` phase by phase. Do not summarize or skip phases.
