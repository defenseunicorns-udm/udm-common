# udm-common

Shared UDS tasks for UDS Proving Ground customers. Provides a supply-chain-security
pipeline that lints, scans, builds, vouches, and publishes Zarf packages to
the UDS Proving Ground registry.

## Available Task Namespaces

| Namespace | Tasks | Description |
|-----------|-------|-------------|
| `udm-setup` | `uds-cli`, `cosign`, `witness` | Installs pipeline tooling |
| `udm-attest` | `lint` | Wraps your `lint` task with Witness attestation |
| `udm-scan` | `security`, `gitleaks`, `opengrep` | Runs Gitleaks secrets scanning and OpenGrep SAST |
| `udm-build` | `zarf-package` | Builds a Zarf package under Witness attestation |
| `udm-vouch` | `package` | Vouches for a signed Zarf package via OLM, pushing attestations to CAT |
| `udm-publish` | `zarf-package` | Publishes a vouched Zarf package to the UDS registry |
| `udm-olm` | `setup` | OLM CLI setup |

## Pipeline Overview

Every package goes through these stages in order:

1. **Lint** — `udm-attest:lint` runs your repo's `lint` task and signs the result
2. **Scan** — `udm-scan:security` runs Gitleaks (secrets) and OpenGrep (SAST) and signs each result
3. **Build + Vouch** — `udm-build:zarf-package` builds the Zarf package; `udm-vouch:package` submits signed attestations to OLM/CAT
4. **Publish** — `udm-publish:zarf-package` pushes the package to the UDS Proving Ground registry

> **Tooling glossary**
> - **Witness** — signs each pipeline step, producing `.json` attestation files as evidence
> - **CAT / Fulcio** — CAT-brokered keyless signing; `udm-olm:generate-fulcio-token` mints a short-lived token from `fulcio.uds-mil.us` before any Witness-attested step. No stored key needed in CI.
> - **OLM / CAT** — UDS Proving Ground compliance tracking; receives signed attestations during `vouch`

## Prerequisites

### UDS CLI

All tasks require the [UDS CLI](https://docs.defenseunicorns.com/cli/getting-started/installation/). Install it before running any `uds run` command.

**GitHub Actions** — use the bundled setup action (already included in [`examples/ci-example.yaml`](examples/ci-example.yaml)):

```yaml
- uses: defenseunicorns-udm/udm-common/.github/actions/uds-cli-setup@v0.14.0
```

**Other CI / local** — download the binary directly:

```shell
# renovate: datasource=github-releases depName=defenseunicorns/uds-cli
UDS_VERSION=v0.36.0
curl --retry-all-errors --retry 5 -fSL \
  "https://github.com/defenseunicorns/uds-cli/releases/download/${UDS_VERSION}/uds-cli_${UDS_VERSION}_Linux_amd64" \
  -o uds
chmod +x uds
sudo mv uds /usr/local/bin/uds
```

See [`examples/.gitlab-ci.yml`](examples/.gitlab-ci.yml) for a complete GitLab install snippet with caching.

> **Keep versions current:** use [Renovate](https://docs.renovatebot.com/) to auto-update both the UDS CLI version pin above and your `udm-common` task include URLs. The inline `# renovate:` comments in the snippets above and in `examples/` are already wired for Renovate's GitHub Releases datasource.

### OLM CLI

OLM is managed in the [CAT repository](https://github.com/defenseunicorns-udm/cat).
The setup task and bundled GitHub action pin a complete CAT upstream release tag;
Renovate keeps both pins current. `olm:setup` installs to `./olm`, reuses an exact
version match, and replaces older, newer, or unrecognized binaries. Override the
pin with `uds run olm:setup --with version=<CAT-upstream-release-tag>` (or the
action's `version` input), including when downgrading. Published installers support
Linux amd64/arm64 and macOS arm64.

### Lint task

**You must define a `lint` task** in your repo's `tasks.yaml` before using `udm-attest:lint` — `udm-attest:lint`
calls it. See [`examples/tasks.yaml`](examples/tasks.yaml) for patterns covering Python, Go, TypeScript,
and monorepos. For an overview of the UDS task runner format, see [Use UDS Runner](https://docs.defenseunicorns.com/cli/how-to-guides/use-uds-runner/).

## Quickstart

All reusable task namespaces use the `udm-` prefix so they can coexist with
`uds-common` includes such as `setup` and `publish`. Keep the include aliases
shown below: internal task calls depend on `udm-setup` and `udm-olm`. Task filenames
and task names within each namespace are unchanged. The consumer still defines
its own root `lint` task, which `udm-attest:lint` invokes.

The examples below are pinned to `v0.14.0`; Renovate will update the pins
after the next release is cut. To try this checkout locally, use paths such as `./tasks/setup.yaml`
with the `udm-setup` alias instead of remote URLs.

Include task namespaces from this repo in your `tasks.yaml`:

```yaml
includes:
  - udm-attest: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.14.0/tasks/attest.yaml
  - udm-build: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.14.0/tasks/build.yaml
  - udm-olm: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.14.0/tasks/olm.yaml
  - udm-publish: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.14.0/tasks/publish.yaml
  - udm-scan: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.14.0/tasks/scan.yaml
  - udm-setup: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.14.0/tasks/setup.yaml
  - udm-vouch: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.14.0/tasks/vouch.yaml

```

See [`examples/tasks.yaml`](examples/tasks.yaml) for a full starting point.

### Minimal CI workflow (GitHub Actions)

> **Note:** `udm-build:zarf-package` and `udm-vouch:package` are separate steps. Run build first, then vouch.

```yaml
jobs:
  ci:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: defenseunicorns-udm/udm-common/.github/actions/uds-cli-setup@v0.14.0
      - run: |
          uds run udm-olm:generate-fulcio-token \
            --with olm_cat="cat-api.uds-mil.us" \
            --with olm_org="<your-org-name>" \
            --with github_token="${{ secrets.GITHUB_TOKEN }}"
      - run: uds run udm-attest:lint
      - run: |
          uds run udm-scan:security \
            --with gitleaks_scan_path="." \
            --with opengrep_scan_path="."
      - run: uds run udm-build:zarf-package
      - run: |
          uds run udm-vouch:package \
            --with attestations="lint-witness.json,gitleaks-witness.json,opengrep-witness.json,zarf-create-witness.json" \
            --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json" \
            --with olm_cat="cat-api.uds-mil.us" \
            --with olm_org="<your-org-name>" \
            --with uds_bundle="<path-to-uds-bundle.yaml>"

      - run: |
          uds run udm-publish:zarf-package \
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
          uds run udm-scan:security \
            --with gitleaks_scan_path="services/${{ matrix.service }}" \
            --with opengrep_scan_path="services/${{ matrix.service }}"
      - run: |
          uds run udm-build:zarf-package \
            --with zarf_path="services/${{ matrix.service }}"
      - run: |
          uds run udm-vouch:package \
            --with attestations="gitleaks-witness.json,opengrep-witness.json,zarf-create-witness.json" \
            --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json" \
            --with olm_cat="cat-api.uds-mil.us" \
            --with olm_org="<your-org-name>" \
            --with uds_bundle="<path-to-uds-bundle.yaml>"
      - run: |
          uds run udm-publish:zarf-package \
            --with registry_org="<your-org-name>" \
            --with registry_user_id="${{ secrets.REGISTRY_USER_ID }}" \
            --with registry_password="${{ secrets.REGISTRY_PASSWORD }}"
```

### Security Scan Scope

`udm-scan:gitleaks` scans tracked Git commits in the current package iteration, not
the live working directory. It compares `HEAD` to the local `origin/main` or
`origin/master` default branch ref and scopes the scan to `gitleaks_scan_path`.
This keeps local-only files such as `.env` files, generated SARIF reports, and
Witness attestations out of the scan while still letting monorepos scan only the
service that is being packaged.

For monorepos, pass the same service path to `gitleaks_scan_path`,
`opengrep_scan_path`, and `zarf_path` so the evidence matches the package being
cut.

## Customer Deployment (Sandbox Preview)

Passing a `uds-bundle.yaml` to `udm-vouch:package` submits material UDS Proving Ground can use for an optional **Customer Deployment** in its IL2 sandbox. Submitting the bundle does not itself create a sandbox deployment or complete validation. Without it, vouching still succeeds and your package is eligible for publish.

### What goes where

| Artifact | Contains | Examples |
|----------|----------|---------|
| **Zarf package** | Your application — all services in one package | API server, worker, frontend |
| **[UDS Bundle](https://docs.defenseunicorns.com/core/concepts/configuration--packaging/bundles/)** | Your app's Zarf package + any infrastructure it depends on | postgres-operator, minio, redis |

Think of the Zarf package as your app and the bundle as the environment it runs in. Your application code should read backing-service connection details from environment variables — not bundle the services themselves into the package. This keeps your app portable across environments (local, staging, IL2).

You can submit the same `uds-bundle.yaml` you use for local development; UDS Proving Ground may apply supported sandbox transformations to infrastructure dependencies. You do not need to provide a [`uds-config.yaml`](https://docs.defenseunicorns.com/cli/how-to-guides/use-bundle-overrides/) — the platform supplies environment-specific configuration at deploy time.

### Passing your bundle to vouch

Add `--with uds_bundle="uds-bundle.yaml"` to your existing `udm-vouch:package` call. The path should point to the `uds-bundle.yaml` in your repo.

**GitHub Actions:**

```shell
uds run udm-vouch:package \
  --with attestations="lint-witness.json,gitleaks-witness.json,opengrep-witness.json,zarf-create-witness.json" \
  --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json" \
  --with olm_cat="cat-api.uds-mil.us" \
  --with olm_org="<your-org-name>" \
  --with uds_bundle="uds-bundle.yaml"
```

**GitLab CI** — also pass `olm_identity_token`:

```shell
uds run udm-vouch:package \
  --with attestations="lint-witness.json,gitleaks-witness.json,opengrep-witness.json,zarf-create-witness.json" \
  --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json" \
  --with olm_cat="cat-api.uds-mil.us" \
  --with olm_org="<your-org-name>" \
  --with olm_identity_token="$OLM_ID_TOKEN" \
  --with uds_bundle="uds-bundle.yaml"
```

### Creating a bundle (if you don't have one yet)

If you have not created a UDS Bundle for your application, see the [UDS CLI bundle documentation](https://docs.defenseunicorns.com/core/concepts/configuration--packaging/bundles/). A minimal bundle references your Zarf package from the registry and lists any infrastructure packages your app needs to run:

```yaml
kind: UDSBundle
metadata:
  name: my-app
  description: My application bundle
  version: 0.1.0

packages:
  - name: my-app
    ref: 0.1.0
    path: ./my-app
  - name: postgres-operator
    repository: ghcr.io/defenseunicorns/packages/uds/postgres-operator
    ref: <version>
```

## Custom Build Commands

By default `udm-build:zarf-package` runs `uds zarf package create .`.
If your build requires a custom script (pre-processing, non-standard flags, multi-step build), pass `build_command`:

```shell
uds run udm-build:zarf-package \
    --with build_command="scripts/build.sh"
```
## Required Secrets

| Secret | Used By | Description |
|--------|---------|-------------|
| `REGISTRY_USER_ID` | `udm-publish:zarf-package` | Username for publishing to `registry.uds-mil.us` |
| `REGISTRY_PASSWORD` | `udm-publish:zarf-package` | Password for publishing to `registry.uds-mil.us` |

## Run Locally

| Lint with Witness attestation | Run SAST scans with Witness attestation | Build Zarf package with Witness attestation | Vouch for package and push attestations to CAT | Publish package to registry ||
|---|---|---|---|---|---|
| `udm-attest:lint` | → `udm-scan:security` | → `udm-build:zarf-package` | → `udm-vouch:package` | → `udm-publish:zarf-package` |  |
|

The full local flow needs a Witness key pair for task attestations. `udm-setup:witness` will download
the required CLIs and place them on your `PATH`.

Use the UDS CLI to execute tasks locally before you push or run CI.
The full local flow needs a Witness key pair for task attestations. `udm-setup:witness` will download the required CLIs and place them on your PATH.

```shell
uds run udm-setup:witness
openssl genpkey -algorithm ed25519 -outform PEM -out witness-key.pem
openssl pkey -in witness-key.pem -pubout > witness-pub.pem
```

**Wrap your repo's `lint` task with Witness:**

```shell
uds run udm-attest:lint \
  --with witness_key_path="$(pwd)/witness-key.pem"
```

**Run Gitleaks and OpenGrep SAST under Witness attestation:**

```shell
uds run udm-scan:security \
  --with witness_key_path="$(pwd)/witness-key.pem" \
  --with gitleaks_scan_path="." \
  --with opengrep_scan_path="."
```

Build the Zarf package with Witness attestation:

```shell
uds run udm-build:zarf-package \
  --with witness_key_path="$(pwd)/witness-key.pem"
```

Vouch for the package and push attestations to CAT:

```shell
uds run udm-vouch:package \
  --with olm_cat="<cat-domain>" \
  --with olm_org="<org>" \
  --with attestations="lint-witness.json,gitleaks-witness.json,opengrep-witness.json,zarf-create-witness.json" \
  --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json"
```

When `zarf_package` is unset, `udm-vouch:package` uses the most recent `zarf-package-*.tar.zst` in the current directory. Pass `--with zarf_package=<path>` explicitly for local runs where old artifacts may be present, or when a repo produces multiple packages.

Publish the Zarf package to the registry:

```shell
uds run udm-publish:zarf-package \
  --with registry_org="<org>" \
  --with registry_user_id="<registry-user-id>" \
  --with registry_password="<registry-password>" \
  --with zarf_package="zarf-package-<name>-<architecture>-<version>.tar.zst"
```

In CI, `udm-publish:zarf-package` can usually rely on the workspace containing only
the package produced by the current job. When `zarf_package` is unset, the task
publishes the most recent `zarf-package-*.tar.zst` in the current directory. For
local runs, pass `zarf_package` explicitly when old package artifacts may still
be present.

## CI Provider Configuration

All Witness attestation signing uses `fulcio.uds-mil.us` via a CAT-brokered token. Before any Witness-attested step, call `udm-olm:generate-fulcio-token` to mint a short-lived JWT and write it to `.fulcio-token`. The attestation tasks (`udm-attest:lint`, `udm-scan:security`, `udm-scan:gitleaks`, `udm-scan:opengrep`, `udm-build:zarf-package`) read `.fulcio-token` automatically when it is present.

On **GitHub Actions**, OLM auto-detects the GitHub OIDC token — no extra configuration needed beyond `id-token: write` on the job.

### Configuring Fulcio signing for GitLab CI

GitLab requires OIDC tokens to be explicitly requested via `id_tokens`. Request a token with audience `cat` and pass it to `udm-olm:generate-fulcio-token` as `olm_identity_token`. Each job that runs Witness-attested steps must generate its own token — `.fulcio-token` is gitignored and is not shared between jobs.

```yaml
# .gitlab-ci.yml — CAT token request (add to every job that signs with Witness)
id_tokens:
  OLM_ID_TOKEN:
    aud: cat

ci:
  script:
    # Generate Fulcio token before any Witness-attested step
    - |
      uds run udm-olm:generate-fulcio-token \
        --with olm_cat="cat-api.uds-mil.us" \
        --with olm_org="<your-org>" \
        --with olm_identity_token="$OLM_ID_TOKEN"
    - uds run udm-attest:lint
    - uds run udm-scan:security
```

```yaml
# publish job — refresh token before build (builds can exceed token lifetime)
publish:
  id_tokens:
    OLM_ID_TOKEN:
      aud: cat
  script:
    - |
      uds run udm-olm:generate-fulcio-token \
        --with olm_cat="cat-api.uds-mil.us" \
        --with olm_org="<your-org>" \
        --with olm_identity_token="$OLM_ID_TOKEN"
    - uds run udm-build:zarf-package
    - |
      uds run udm-vouch:package \
        --with olm_cat="cat-api.uds-mil.us" \
        --with olm_org="<your-org>" \
        --with olm_identity_token="$OLM_ID_TOKEN" \
        --with attestations="lint-witness.json,gitleaks-witness.json,opengrep-witness.json,zarf-create-witness.json" \
        --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json" \
        --with uds_bundle="<path-to-uds-bundle.yaml>"
```

See [`examples/.gitlab-ci.yml`](examples/.gitlab-ci.yml) for a complete annotated pipeline.

## Lint Task

`udm-attest:lint` wraps your repo's `lint` task with Witness attestation. **You
must define a `lint` task in your repo's `tasks.yaml`** — `udm-attest:lint` calls
it. See [`examples/tasks.yaml`](examples/tasks.yaml) for patterns covering
Python, Go, TypeScript, and monorepos.

Include all task namespaces in your repo's `tasks.yaml`:

```yaml
includes:
  - udm-attest: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.14.0/tasks/attest.yaml
  - udm-build: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.14.0/tasks/build.yaml
  - udm-olm: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.14.0/tasks/olm.yaml
  - udm-publish: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.14.0/tasks/publish.yaml
  - udm-scan: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.14.0/tasks/scan.yaml
  - udm-setup: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.14.0/tasks/setup.yaml
  - udm-vouch: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.14.0/tasks/vouch.yaml
```

## Migrating to the prefixed namespaces

This is a breaking change. Update all seven include aliases and their calls in
`tasks.yaml`, CI workflows, and scripts:

| Previous namespace | New namespace |
|--------------------|---------------|
| `setup` | `udm-setup` |
| `attest` | `udm-attest` |
| `scan` | `udm-scan` |
| `build` | `udm-build` |
| `olm` | `udm-olm` |
| `vouch` | `udm-vouch` |
| `publish` | `udm-publish` |

For example, `uds run setup:witness` becomes `uds run udm-setup:witness`, and
`task: build:zarf-package` becomes `task: udm-build:zarf-package`. Update the
include URL pins to the release containing this change at the same time; changing
only aliases against older releases leaves their internal calls incompatible.
Do not rename the consumer's root `lint` task or the repository's root
orchestration tasks (`test`, `scan-and-vouch`, and `pipeline`).

## Migrating from v0.11.x to v0.12.x

v0.12 replaces direct Sigstore OIDC signing (`fulcio.sigstore.dev`) with CAT-brokered signing (`fulcio.uds-mil.us`). All Witness attestations now use a single trust root managed by CAT.

### Required changes for all consumers

**1. Add `olm:` to your `tasks.yaml` includes** (if not already present):

```yaml
includes:
  - olm: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.14.0/tasks/olm.yaml
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

## Contributor and AI Agent Guidance

Repository instructions are shared across Claude Code, OpenAI Codex, and other AI coding agents:

- [`AGENTS.md`](AGENTS.md) — OpenAI Codex and agent entrypoint
- [`CLAUDE.md`](CLAUDE.md) — shared commands, architecture, and development guidance
- [`CONTEXT.md`](CONTEXT.md) — domain glossary and terminology
