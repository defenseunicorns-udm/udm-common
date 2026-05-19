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
| `vouch` | `package` | Builds, attests, and vouches via OLM.  Pushes attestations to CAT |
| `publish` | `zarf-package` | Publishes a vouched Zarf package to the UDS registry |
| `olm` | `setup` | OLM CLI setup |

## Quickstart

Include task namespaces from this repo in your `tasks.yaml`:

```yaml
includes:
  - setup: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/setup.yaml
  - attest: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/attest.yaml
  - build: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/build.yaml
  - scan: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/scan.yaml
  - vouch: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/vouch.yaml
  - publish: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/publish.yaml
  - olm: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/olm.yaml

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
      - run: uds run scan:security
      - run: |
          uds run vouch:package \
            --with github_token="${{ secrets.GITHUB_TOKEN }}" \
            --with attestations="lint-witness.json,gitleaks-witness.json,opengrep-witness.json" \
            --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json" \
            --with olm_cat=cat-api.uds-mil.us \
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
          uds run vouch:package \
            --with github_token="${{ secrets.GITHUB_TOKEN }}" \
            --with attestations="gitleaks-witness.json,opengrep-witness.json" \
            --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json" \
            --with zarf_path="services/${{ matrix.service }}" \
            --with olm_cat=cat-api.uds-mil.us \
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

By default, `vouch:package` and `build:zarf-package` run `uds zarf package create`.
If your build requires a custom script (pre-processing, non-standard flags, multi-step build), pass `build_command`:

**Via vouch:**
```yaml
- task: vouch:package
  with:
    build_command: ./scripts/my-build.sh
    olm_cat: cat-api.uds-mil.us
    olm_org: <your-org-name>
```

**Build only:**
```yaml
- task: build:zarf-package
  with:
    build_command: ./scripts/my-build.sh
```

The custom command runs under Witness attestation — the resulting `zarf-create-witness.json` is identical in structure to a standard build. Scripts with complex quoting should be placed in a file and called by path rather than passed inline.

## Run Locally

Use the UDS CLI to execute tasks locally before you push or run CI.

- Run lint:

```bash
uds run lint
```

- Run lint with Witness attestation (requires a local signing key or Sigstore OIDC):

```bash
uds run attest:lint \
  --with witness_key_path=/path/to/key
```

- Build a Zarf package locally:

# Replace `<ARCH>` with `amd64` or `arm64` 
```bash
uds run build:zarf-package \
  --with zarf_path=. \
  --with architecture=<ARCH>
```

- Build a flavored Zarf package locally:

```bash
uds run build:zarf-package \
  --with zarf_path=. \
  --with architecture=<ARCH> \
  --with zarf_flavor=upstream
```

- Build with a custom build command:

```bash
uds run build:zarf-package --with build_command="./scripts/my-build.sh"
```

- Build and vouch locally:

```bash
uds run vouch:package \
  --with zarf_path=. \
  --with witness_key_path="$(pwd)/witness-key.pem" \
  --with enable_sigstore=true \
  --with olm_cat="cat-api.uds-mil.us" \
  --with olm_org="<your-org>" \
  --with attestations="lint-witness.json,gitleaks-witness.json,opengrep-witness.json" \
  --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json" \
  --with github_token="$GITHUB_TOKEN" \
  --with architecture=<ARCH>
```

- Build and vouch with a custom build command:

```bash
uds run vouch:package \
  --with build_command="./scripts/my-build.sh" \
  --with zarf_path=. \
  --with witness_key_path="$(pwd)/witness-key.pem" \
  --with enable_sigstore=true \
  --with olm_cat="cat-api.uds-mil.us" \
  --with olm_org="<your-org>" \
  --with attestations="lint-witness.json,gitleaks-witness.json,opengrep-witness.json" \
  --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json" \
  --with github_token="$GITHUB_TOKEN" \
  --with architecture=<ARCH>
```

- Test publish without pushing to a registry:

```bash
uds run publish:zarf-package --with dry_run=true
```

Notes:

- `build_command` replaces the default `uds zarf package create` flow. When set, `zarf_path` and `architecture` are ignored by `build:zarf-package`.
- `zarf_flavor` applies to normal `uds zarf package create` builds only. Omit it when your package does not define a flavor.
- For local runs without Sigstore/OIDC, pass `--with enable_sigstore=false`. Add `--with witness_key_path=/path/to/key` when you still want local Witness signing.
- `enable_archivista` is available on task-based builds and pipelines and is forwarded to the build attestation step.

## CI Provider Configuration

By default, Sigstore signing uses `https://token.actions.githubusercontent.com` as the Fulcio OIDC issuer, which is correct for GitHub Actions. To use Sigstore attestation from another CI provider, pass `fulcio_oidc_issuer` with the provider's OIDC issuer URL.

Supported by: `attest:lint`, `scan:security`, `scan:gitleaks`, `scan:opengrep`, `build:zarf-package`, `vouch:package`.

### Configuring Sigstore for GitLab CI

The snippets below show only the Sigstore-relevant configuration — they are not a complete GitLab CI pipeline. GitLab requires OIDC tokens to be explicitly requested via `id_tokens`; without this, `enable_sigstore=true` will fail.

```yaml
# .gitlab-ci.yml — Sigstore OIDC token request (add to any job that signs with Witness)
id_tokens:
  SIGSTORE_ID_TOKEN:
    aud: sigstore

scan:
  script:
    - uds run scan:security \
        --with enable_sigstore=true \
        --with fulcio_oidc_issuer=""$CI_SERVER_URL""
```

```yaml
# tasks.yaml — pass fulcio_oidc_issuer through to vouch
- task: vouch:package
  with:
    enable_sigstore: "true"
    fulcio_oidc_issuer: "$CI_SERVER_URL"
    olm_identity_token: "$OLM_ID_TOKEN"
    olm_cat: cat-api.uds-mil.us
    olm_org: <your-org-name>
    attestations: lint-witness.json,gitleaks-witness.json,opengrep-witness.json
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
  - setup: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/setup.yaml
  - attest: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/attest.yaml
  - scan: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/scan.yaml
  - vouch: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/vouch.yaml
  - publish: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/publish.yaml
  - olm: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/olm.yaml
```

## Examples

See the [`examples/`](examples/) directory for copy-paste starting points:

| File | Purpose |
|------|---------|
| [`examples/ci-example.yaml`](examples/ci-example.yaml) | Full annotated GitHub Actions workflow |
| [`examples/.gitlab-ci.yml`](examples/.gitlab-ci.yml) | Full annotated GitLab CI pipeline |
| [`examples/tasks.yaml`](examples/tasks.yaml) | Starter `tasks.yaml` with common lint patterns |
