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

## Quickstart

Include task namespaces from this repo in your `tasks.yaml`:

```yaml
includes:
  - attest: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/attest.yaml
  - build: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/build.yaml
  - olm: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/olm.yaml
  - publish: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/publish.yaml
  - scan: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/scan.yaml
  - setup: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/setup.yaml
  - vouch: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/vouch.yaml

```

See [`examples/tasks.yaml`](examples/tasks.yaml) for a full starting point.

### Minimal CI workflow (GitHub Actions)

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
      - uses: defenseunicorns-udm/udm-common/.github/actions/uds-cli-setup@9aaad66b21c7637b5be3d6aafdb21c9e7ff1df2a # v0.10.3
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

The custom command runs under Witness attestation — the resulting `zarf-create-witness.json` is identical in structure to a standard build. Scripts with complex quoting should be placed in a file and called by path rather than passed inline.

## Run Locally

| Lint with Witness attestation | Run SAST scans with Witness attestation | Build Zarf package with Witness attestation | Vouch for package and push attestations to CAT | Publish package to registry ||
|---|---|---|---|---|---|
| `attest-lint` | → `scan:security` | → `build:zarf-package` | → `vouch:package` | → `publish:zarf-package` |  |
|

The full local flow needs a Witness key pair for task attestations. `setup:witness` will download
the required CLIs and place them on your `PATH`.

```shell
uds run setup:witness
openssl genpkey -algorithm ed25519 -outform PEM -out witness-key.pem
openssl pkey -in witness-key.pem -pubout > witness-pub.pem
```

Wrap your repo's `lint` task with Witness:

```shell
uds run attest:lint \
  --with witness_key_path="$(pwd)/witness-key.pem"
```

Run Gitleaks and OpenGrep SAST under Witness attestation:

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

## CI Provider Configuration

By default, Sigstore signing uses `https://token.actions.githubusercontent.com` as the Fulcio OIDC issuer, which is correct for GitHub Actions. To use Sigstore attestation from another CI provider, pass `fulcio_oidc_issuer` with the provider's OIDC issuer URL.

Supported by: `attest:lint`, `scan:security`, `scan:gitleaks`, `scan:opengrep`, `build:zarf-package`, `vouch:package`.

### Configuring Sigstore for GitLab CI

The snippets below show only the Sigstore-relevant configuration — they are not a complete GitLab CI pipeline. GitLab requires OIDC tokens to be explicitly requested via `id_tokens`; without this, Sigstore signing will fail.

```yaml
# .gitlab-ci.yml — Sigstore OIDC token request (add to any job that signs with Witness)
id_tokens:
  SIGSTORE_ID_TOKEN:
    aud: sigstore

scan:
  script:
    - uds run scan:security \
        --with fulcio_oidc_issuer="$CI_SERVER_URL"
```

```yaml
# tasks.yaml — build then vouch as separate steps
- task: build:zarf-package
  with:
    fulcio_oidc_issuer: "$CI_SERVER_URL"
- task: vouch:package
  with:
    olm_identity_token: "$OLM_ID_TOKEN"
    olm_cat: <cat-domain>
    olm_org: <your-org-name>
    attestations: lint-witness.json,gitleaks-witness.json,opengrep-witness.json,zarf-create-witness.json
    sarif_files: gitleaks.sarif.json,opengrep.sarif.json
```

`$CI_SERVER_URL` is a built-in GitLab variable that resolves to the GitLab instance URL, which is the OIDC issuer for GitLab's Sigstore integration. `OLM_ID_TOKEN` is a variable you define in GitLab that requests an OIDC token for your OLM registry — pass it to `vouch:package` as `olm_identity_token`.

See [`examples/.gitlab-ci.yml`](examples/.gitlab-ci.yml) for a complete annotated pipeline.

## Required Secrets

| Secret | Used By | Description |
|--------|---------|-------------|
| `REGISTRY_USER_ID` | `publish:zarf-package` | Username for publishing to `registry.uds-mil.us` |
| `REGISTRY_PASSWORD` | `publish:zarf-package` | Password for publishing to `registry.uds-mil.us` |

## Lint Task

`attest:lint` wraps your repo's `lint` task with Witness attestation. **You
must define a `lint` task in your repo's `tasks.yaml`** — `attest:lint` calls
it. See [`examples/tasks.yaml`](examples/tasks.yaml) for patterns covering
Python, Go, TypeScript, and monorepos.

Include all task namespaces in your repo's `tasks.yaml`:

```yaml
includes:
  - attest: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/attest.yaml
  - build: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/build.yaml
  - olm: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/olm.yaml
  - publish: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/publish.yaml
  - scan: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/scan.yaml
  - setup: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/setup.yaml
  - vouch: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/vouch.yaml
```

## Examples

See the [`examples/`](examples/) directory for copy-paste starting points:

| File | Purpose |
|------|---------|
| [`examples/ci-example.yaml`](examples/ci-example.yaml) | Full annotated GitHub Actions workflow |
| [`examples/.gitlab-ci.yml`](examples/.gitlab-ci.yml) | Full annotated GitLab CI pipeline |
| [`examples/tasks.yaml`](examples/tasks.yaml) | Starter `tasks.yaml` with common lint patterns |
