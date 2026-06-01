# udm-common

Shared UDS tasks for UDS Army customers. Provides a supply-chain-security
pipeline that lints, scans, builds, vouches, and publishes Zarf packages to
the UDS Army registry.

## Available Task Namespaces

| Namespace | Tasks | Description |
|-----------|-------|-------------|
| `setup` | `uds-cli`, `cosign`, `witness` | Installs pipeline tooling |
| `attest` | `lint` | Wraps your `lint` task with Witness attestation |
| `scan` | `security`, `gitleaks`, `opengrep` | Runs Gitleaks secrets scanning and OpenGrep SAST |
| `build` | `zarf-package` | Builds a Zarf package under Witness attestation |
| `vouch` | `package` | Vouches for a signed Zarf package via OLM, pushing attestations to CAT |
| `publish` | `zarf-package` | Publishes a vouched Zarf package to the UDS registry |
| `olm` | `setup` | OLM CLI setup |

## Pipeline Overview

Every package goes through these stages in order:

1. **Lint** — `attest:lint` runs your repo's `lint` task and signs the result
2. **Scan** — `scan:security` runs Gitleaks (secrets) and OpenGrep (SAST) and signs each result
3. **Build + Vouch** — `vouch:package` builds the Zarf package, then submits all signed attestations to OLM/CAT
4. **Publish** — `publish:zarf-package` pushes the package to the UDS Army registry

> **Tooling glossary**
> - **Witness** — signs each pipeline step, producing `.json` attestation files as evidence
> - **Sigstore / Fulcio** — keyless signing via OIDC (e.g. GitHub Actions token — no stored key needed in CI)
> - **OLM / CAT** — UDS Army compliance tracking; receives signed attestations during `vouch`

## Prerequisites

### UDS CLI

All tasks require the [UDS CLI](https://github.com/defenseunicorns/uds-cli). Install it before running any `uds run` command.

**GitHub Actions** — use the bundled setup action (already included in [`examples/ci-example.yaml`](examples/ci-example.yaml)):

```yaml
- uses: defenseunicorns-udm/udm-common/.github/actions/uds-cli-setup@560fc17745c6b3817d5c1d7c449081be19c59f3a # v0.12.0
```

**Other CI / local** — download the binary directly:

```shell
# renovate: datasource=github-releases depName=defenseunicorns/uds-cli
UDS_VERSION=v0.31.0
curl --retry-all-errors --retry 5 -fSL \
  "https://github.com/defenseunicorns/uds-cli/releases/download/${UDS_VERSION}/uds-cli_${UDS_VERSION}_Linux_amd64" \
  -o uds
chmod +x uds
sudo mv uds /usr/local/bin/uds
```

See [`examples/.gitlab-ci.yml`](examples/.gitlab-ci.yml) for a complete GitLab install snippet with caching.

> **Keep versions current:** use [Renovate](https://docs.renovatebot.com/) to auto-update both the UDS CLI version pin above and your `udm-common` task include URLs. The inline `# renovate:` comments in the snippets above and in `examples/` are already wired for Renovate's GitHub Releases datasource.

### Lint task

**You must define a `lint` task** in your repo's `tasks.yaml` before using `attest:lint` — `attest:lint`
calls it. See [`examples/tasks.yaml`](examples/tasks.yaml) for patterns covering Python, Go, TypeScript,
and monorepos.

## Quickstart

Include task namespaces from this repo in your `tasks.yaml`:

```yaml
includes:
  - attest: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.12.0/tasks/attest.yaml
  - build: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.12.0/tasks/build.yaml
  - olm: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.12.0/tasks/olm.yaml
  - publish: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.12.0/tasks/publish.yaml
  - scan: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.12.0/tasks/scan.yaml
  - setup: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.12.0/tasks/setup.yaml
  - vouch: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.12.0/tasks/vouch.yaml

```

See [`examples/tasks.yaml`](examples/tasks.yaml) for a full starting point.

### Minimal CI workflow (GitHub Actions)

> **Note:** `vouch:package` calls `build:zarf-package` automatically.

```yaml
jobs:
  ci:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
      - uses: defenseunicorns-udm/udm-common/.github/actions/uds-cli-setup@560fc17745c6b3817d5c1d7c449081be19c59f3a # v0.12.0
      - run: |
          uds run olm:generate-fulcio-token \
            --with olm_cat="cat-api.uds-mil.us" \
            --with olm_org="<your-org-name>" \
            --with github_token="${{ secrets.GITHUB_TOKEN }}"
      - run: uds run attest:lint
      - run: |
          uds run scan:security \
            --with gitleaks_scan_path="." \
            --with opengrep_scan_path="."
      - run: uds run build:zarf-package
      - run: |
          uds run vouch:package \
            --with attestations="lint-witness.json,gitleaks-witness.json,opengrep-witness.json,zarf-create-witness.json" \
            --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json" \
            --with olm_cat="cat-api.uds-mil.us" \
            --with olm_org="<your-org-name>"
      - run: |
          uds run publish:zarf-package \
            --with registry_org="<your-org-name>" \
            --with registry_user_id="${{ secrets.REGISTRY_USER_ID }}" \
            --with registry_password="${{ secrets.REGISTRY_PASSWORD }}"
```

See [`examples/ci-example.yaml`](examples/ci-example.yaml) for a full annotated workflow.

### Monorepo

Use `zarf_path` in a matrix to build and publish multiple services:

```yaml
jobs:
  scan-vouch-publish:
    strategy:
      matrix:
        service: [api, worker, frontend]
    steps:
      - run: |
          uds run scan:security \
            --with gitleaks_scan_path="services/${{ matrix.service }}" \
            --with opengrep_scan_path="services/${{ matrix.service }}"
      - run: |
          uds run build:zarf-package \
            --with zarf_path="services/${{ matrix.service }}"
      - run: |
          uds run vouch:package \
            --with attestations="gitleaks-witness.json,opengrep-witness.json,zarf-create-witness.json" \
            --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json" \
            --with olm_cat="cat-api.uds-mil.us" \
            --with olm_org="<your-org-name>"
      - run: |
          uds run publish:zarf-package \
            --with registry_org="<your-org-name>" \
            --with registry_user_id="${{ secrets.REGISTRY_USER_ID }}" \
            --with registry_password="${{ secrets.REGISTRY_PASSWORD }}"
```

### Security Scan Scope

`scan:gitleaks` scans tracked Git commits in the current package iteration, not
the live working directory. It compares `HEAD` to the local `origin/main` or
`origin/master` default branch ref and scopes the scan to `gitleaks_scan_path`.
This keeps local-only files such as `.env` files, generated SARIF reports, and
Witness attestations out of the scan while still letting monorepos scan only the
service that is being packaged.

For monorepos, pass the same service path to `gitleaks_scan_path`,
`opengrep_scan_path`, and `zarf_path` so the evidence matches the package being
cut.

## Custom Build Commands

By default `build:zarf-package` runs `uds zarf package create .`.
If your build requires a custom script (pre-processing, non-standard flags, multi-step build), pass `build_command`:

```shell
uds run build:zarf-package \
    --with build_command="scripts/build.sh"
```
## Required Secrets

| Secret | Used By | Description |
|--------|---------|-------------|
| `REGISTRY_USER_ID` | `publish:zarf-package` | Username for publishing to `registry.uds-mil.us` |
| `REGISTRY_PASSWORD` | `publish:zarf-package` | Password for publishing to `registry.uds-mil.us` |

## Run Locally

| Lint with Witness attestation | Run SAST scans with Witness attestation | Build Zarf package with Witness attestation | Vouch for package and push attestations to CAT | Publish package to registry ||
|---|---|---|---|---|---|
| `attest-lint` | → `scan:security` | → `build:zarf-package` | → `vouch:package` | → `publish:zarf-package` |  |
|

The full local flow needs a Witness key pair for task attestations. `setup:witness` will download
the required CLIs and place them on your `PATH`.

Use the UDS CLI to execute tasks locally before you push or run CI.
The full local flow needs a Witness key pair for task attestations. `setup:witness` will download the required CLIs and place them on your PATH.

```shell
uds run setup:witness
openssl genpkey -algorithm ed25519 -outform PEM -out witness-key.pem
openssl pkey -in witness-key.pem -pubout > witness-pub.pem
```

**Wrap your repo's `lint` task with Witness:**

```shell
uds run attest:lint \
  --with witness_key_path="$(pwd)/witness-key.pem"
```

**Run Gitleaks and OpenGrep SAST under Witness attestation:**

```shell
uds run scan:security \
  --with witness_key_path="$(pwd)/witness-key.pem" \
  --with gitleaks_scan_path="." \
  --with opengrep_scan_path="."
```

Build the Zarf package with Witness attestation:

```shell
uds run build:zarf-package \
  --with witness_key_path="$(pwd)/witness-key.pem"
```

Vouch for the package and push attestations to CAT:

```shell
uds run vouch:package \
  --with olm_cat="<cat-domain>" \
  --with olm_org="<org>" \
  --with attestations="lint-witness.json,gitleaks-witness.json,opengrep-witness.json,zarf-create-witness.json" \
  --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json"
```

When `zarf_package` is unset, `vouch:package` uses the most recent `zarf-package-*.tar.zst` in the current directory. Pass `--with zarf_package=<path>` explicitly for local runs where old artifacts may be present, or when a repo produces multiple packages.

Publish the Zarf package to the registry:

```shell
uds run publish:zarf-package \
  --with registry_org="<org>" \
  --with registry_user_id="<registry-user-id>" \
  --with registry_password="<registry-password>" \
  --with zarf_package="zarf-package-<name>-<architecture>-<version>.tar.zst"
```

In CI, `publish:zarf-package` can usually rely on the workspace containing only
the package produced by the current job. When `zarf_package` is unset, the task
publishes the most recent `zarf-package-*.tar.zst` in the current directory. For
local runs, pass `zarf_package` explicitly when old package artifacts may still
be present.

## Security Scan Scope

`scan:gitleaks` scans tracked Git commits in the current package iteration, not
the live working directory. It compares `HEAD` to the local `origin/main` or
`origin/master` default branch ref and scopes the scan to `gitleaks_scan_path`.
This keeps local-only files such as `.env` files, generated SARIF reports, and
Witness attestations out of the scan while still letting monorepos scan only the
service that is being packaged.

For monorepos, pass the same service path to `gitleaks_scan_path`,
`opengrep_scan_path`, and `zarf_path` so the evidence matches the package being
cut.

## CI Provider Configuration

All Witness attestation signing uses `fulcio.uds-mil.us` via a CAT-brokered token. Before any Witness-attested step, call `olm:generate-fulcio-token` to mint a short-lived JWT and write it to `.fulcio-token`. The attestation tasks (`attest:lint`, `scan:security`, `scan:gitleaks`, `scan:opengrep`, `build:zarf-package`) read `.fulcio-token` automatically when it is present.

On **GitHub Actions**, OLM auto-detects the GitHub OIDC token — no extra configuration needed beyond `id-token: write` on the job.

### Configuring Fulcio signing for GitLab CI

GitLab requires OIDC tokens to be explicitly requested via `id_tokens`. Request a token with audience `cat` and pass it to `olm:generate-fulcio-token` as `olm_identity_token`. Each job that runs Witness-attested steps must generate its own token — `.fulcio-token` is gitignored and is not shared between jobs.

```yaml
# .gitlab-ci.yml — CAT token request (add to every job that signs with Witness)
id_tokens:
  OLM_ID_TOKEN:
    aud: cat

ci:
  script:
    # Generate Fulcio token before any Witness-attested step
    - |
      uds run olm:generate-fulcio-token \
        --with olm_cat="cat-api.uds-mil.us" \
        --with olm_org="<your-org>" \
        --with olm_identity_token="$OLM_ID_TOKEN"
    - uds run attest:lint
    - uds run scan:security
```

```yaml
# publish job — refresh token before build (builds can exceed token lifetime)
publish:
  id_tokens:
    OLM_ID_TOKEN:
      aud: cat
  script:
    - |
      uds run olm:generate-fulcio-token \
        --with olm_cat="cat-api.uds-mil.us" \
        --with olm_org="<your-org>" \
        --with olm_identity_token="$OLM_ID_TOKEN"
    - uds run build:zarf-package
    - |
      uds run vouch:package \
        --with olm_cat="cat-api.uds-mil.us" \
        --with olm_org="<your-org>" \
        --with olm_identity_token="$OLM_ID_TOKEN" \
        --with attestations="lint-witness.json,gitleaks-witness.json,opengrep-witness.json,zarf-create-witness.json" \
        --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json"
```

See [`examples/.gitlab-ci.yml`](examples/.gitlab-ci.yml) for a complete annotated pipeline.

## Lint Task

`attest:lint` wraps your repo's `lint` task with Witness attestation. **You
must define a `lint` task in your repo's `tasks.yaml`** — `attest:lint` calls
it. See [`examples/tasks.yaml`](examples/tasks.yaml) for patterns covering
Python, Go, TypeScript, and monorepos.

Include all task namespaces in your repo's `tasks.yaml`:

```yaml
includes:
  - attest: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.12.0/tasks/attest.yaml
  - build: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.12.0/tasks/build.yaml
  - olm: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.12.0/tasks/olm.yaml
  - publish: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.12.0/tasks/publish.yaml
  - scan: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.12.0/tasks/scan.yaml
  - setup: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.12.0/tasks/setup.yaml
  - vouch: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.12.0/tasks/vouch.yaml
```

## Migrating from v0.11.x to v0.12.x

v0.12 replaces direct Sigstore OIDC signing (`fulcio.sigstore.dev`) with CAT-brokered signing (`fulcio.uds-mil.us`). All Witness attestations now use a single trust root managed by CAT.

### Required changes for all consumers

**1. Add `olm:` to your `tasks.yaml` includes** (if not already present):

```yaml
includes:
  - olm: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.12.0/tasks/olm.yaml
```

**2. Remove `fulcio_oidc_issuer` from all task calls.** The parameter no longer exists. Remove any `--with fulcio_oidc_issuer=...` from `attest:lint`, `scan:security`, `scan:gitleaks`, `scan:opengrep`, and `build:zarf-package` calls.

**3. Call `olm:generate-fulcio-token` before the first Witness-attested step in each CI job.** The token is short-lived — for long jobs (builds > 30 min), call it again before `build:zarf-package`.

### GitHub Actions

No provider-specific changes needed. `id-token: write` on the job is sufficient — OLM auto-detects the GitHub OIDC token.

```yaml
# Before first attested step
- run: |
    uds run olm:generate-fulcio-token \
      --with olm_cat="cat-api.uds-mil.us" \
      --with olm_org="<your-org>" \
      --with github_token="${{ secrets.GITHUB_TOKEN }}"
```

### GitLab CI

Replace the `SIGSTORE_ID_TOKEN` block with `OLM_ID_TOKEN`:

```yaml
# Before (v0.11.x)
id_tokens:
  SIGSTORE_ID_TOKEN:
    aud: sigstore

# After (v0.12.x)
id_tokens:
  OLM_ID_TOKEN:
    aud: cat
```

Then generate the Fulcio token before attested steps in each job:

```yaml
- |
  uds run olm:generate-fulcio-token \
    --with olm_cat="cat-api.uds-mil.us" \
    --with olm_org="<your-org>" \
    --with olm_identity_token="$OLM_ID_TOKEN"
```

See [`examples/.gitlab-ci.yml`](examples/.gitlab-ci.yml) for a complete annotated pipeline.

## Examples

See the [`examples/`](examples/) directory for copy-paste starting points:

| File | Purpose |
|------|---------|
| [`examples/ci-example.yaml`](examples/ci-example.yaml) | Full annotated GitHub Actions workflow |
| [`examples/.gitlab-ci.yml`](examples/.gitlab-ci.yml) | Full annotated GitLab CI pipeline |
| [`examples/tasks.yaml`](examples/tasks.yaml) | Starter `tasks.yaml` with common lint patterns |
