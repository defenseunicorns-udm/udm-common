# udm-common

Shared GitHub Actions and reusable workflows for UDS MIL customers. Provides
a supply-chain-security pipeline that lints, scans, builds, vouches, and
publishes Zarf packages to the UDS MIL registry.

## Available Actions

| Action | Description |
|--------|-------------|
| [`uds-cli-setup`](.github/actions/uds-cli-setup/action.yaml) | Installs the UDS CLI |
| [`olm-cli-setup`](.github/actions/olm-cli-setup/action.yaml) | Authenticates with GHCR and installs the OLM CLI |
| [`security-scan`](.github/actions/security-scan/action.yaml) | Runs Gitleaks secrets scanning and OpenGrep SAST; outputs witness JSON and SARIF file lists |
| [`vouch`](.github/actions/vouch/action.yaml) | Builds a Zarf package with Witness attestation and vouches for it via OLM |
| [`publish`](.github/actions/publish/action.yaml) | Publishes a vouched Zarf package to the UDS registry |
| [`verify-permissions`](.github/actions/verify-permissions/action.yaml) | Validates required GitHub Actions OIDC permissions are present |

The GitHub Actions are thin wrappers around the shared UDS tasks in this repo.
Prefer calling tasks directly in workflows when the task file is available; use
the actions when you need a packaged GitHub Actions interface.

## Quickstart

Reference actions or shared task sources from this repo using the full path and a ref:

```yaml
uses: defenseunicorns-udm/udm-common/.github/actions/security-scan@189ad0d6c780416eb929a15fad22e636e0a9f62c # v0.7.1
```

### Minimal CI workflow (GitHub example)

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v6.0.2
      - uses: defenseunicorns-udm/udm-common/.github/actions/uds-cli-setup@189ad0d6c780416eb929a15fad22e636e0a9f62c # v0.7.1
      - uses: testifysec/witness-run-action@7aa15e327829f1f2a523365c564c948d5dde69dd
        with:
          step: lint
          command: uds run lint        # defined in your tasks.yaml
          outfile: lint-witness.json
      - uses: actions/upload-artifact@v7.0.1
        with:
          name: lint-artifacts
          path: lint-witness.json

  scan-vouch-publish:
    needs: lint
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write
    steps:
      - uses: actions/checkout@v6.0.2
      - uses: defenseunicorns-udm/udm-common/.github/actions/uds-cli-setup@189ad0d6c780416eb929a15fad22e636e0a9f62c # v0.7.1
      - uses: actions/download-artifact@v8.0.1
        with:
          name: lint-artifacts
          path: .
      - run: uds run scan:security
      - run: |
          uds run vouch:package \
            --with github_token="${{ secrets.GITHUB_TOKEN }}" \
            --with attestations="gitleaks-witness.json,opengrep-witness.json,lint-witness.json" \
            --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json" \
            --with olm_cat=cat-api.uds-mil.us \
            --with olm_org="<your-org-name>"

      - run: |
          uds run publish:zarf-package \
            --with registry_org="<your-org-name>" \
            --with registry_user_id="${{ secrets.REGISTRY_USER_ID }}" \
            --with registry_password="${{ secrets.REGISTRY_PASSWORD }}"
```

### Monorepo

Use `zarf_path` to build and publish multiple services in a matrix:

```yaml
jobs:
  scan-vouch-publish:
    strategy:
      matrix:
        service: [api, worker, frontend]
    steps:
      - run: |
          uds run scan:security \
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

## Custom Build Commands

By default, the `vouch:package` and `build:zarf-package` tasks run `uds zarf package create`.
If your build requires a custom script (pre-processing, non-standard flags, multi-step build), pass `build_command` to the task.

**UDS task:**
```yaml
- task: vouch:package
  with:
    build_command: ./scripts/my-build.sh
    olm_cat: cat-api.uds-mil.us
    olm_org: <your-org-name>
```

**Build-only task:**
```yaml
- task: build:zarf-package
  with:
    build_command: ./scripts/my-build.sh
```

The custom command runs under Witness attestation — the resulting `zarf-create-witness.json` is identical in structure to a standard build. Scripts with complex quoting should be placed in a file and called by path rather than passed inline.

## Run Locally

Use the UDS CLI to execute tasks locally before you push or run CI.

- Run lint and generate a Witness attestation:

```bash
uds run lint
```

- Build a Zarf package locally with the shared `build:zarf-package` task:

```bash
uds run build:zarf-package --with zarf_path=. --with architecture=amd64
```

- Build a flavored Zarf package locally:

```bash
uds run build:zarf-package \
  --with zarf_path=. \
  --with architecture=amd64 \
  --with zarf_flavor=upstream
```

- Build a Zarf package locally with a custom build command:

```bash
uds run build:zarf-package --with build_command="./scripts/my-build.sh"
```

- Build and vouch locally using the shared `vouch:package` task:

```bash
uds run vouch:package \
  --with zarf_path=. \
  --with olm_cat=cat-api.uds-mil.us \
  --with olm_org="<your-org-name>" \
  --with github_token="$GITHUB_TOKEN"
```

- Build and vouch locally with a custom build command:

```bash
uds run vouch:package \
  --with build_command="./scripts/my-build.sh" \
  --with olm_cat=cat-api.uds-mil.us \
  --with olm_org="<your-org-name>" \
  --with github_token="$GITHUB_TOKEN"
```

- Test publish behavior locally without pushing to a registry:

```bash
uds run publish:zarf-package --with dry_run=true
```

Notes:

- `build_command` replaces the default `uds zarf package create` flow. If you use `--with build_command=...`, `--with zarf_path` and `--with architecture` are ignored by `build:zarf-package`.
- `zarf-flavor` / `zarf_flavor` applies to normal `uds zarf package create` builds. Omit it when your package does not define a flavor. It has no effect when the build is driven by a custom `build_command`.
- In task-based workflows, pass package flavor as `--with zarf_flavor=upstream`; in the `vouch` GitHub Action wrapper, pass `zarf-flavor: upstream`.
- For local runs without Sigstore/OIDC, pass `--with enable_sigstore=false` to `build:zarf-package`, `vouch:package`, `scan-and-vouch`, or `pipeline`. Add `--with witness_key_path=/path/to/key` when you still want local Witness signing.
- `enable_archivista` is available on task-based builds and pipelines and is forwarded to the build attestation step.

## Required Secrets

| Secret | Used By | Description |
|--------|---------|-------------|
| `REGISTRY_USER_ID` | `publish` | Username for publishing to `registry.uds-mil.us` |
| `REGISTRY_PASSWORD` | `publish` | Password for publishing to `registry.uds-mil.us` |

## Lint Task

The example CI workflow calls `uds run lint` — you must define a `lint`
task in your repo's `tasks.yaml`. See [`examples/tasks.yaml`](examples/tasks.yaml)
for patterns covering Python, Go, TypeScript, and monorepos.

## Examples

See the [`examples/`](examples/) directory for copy-paste starting points.
