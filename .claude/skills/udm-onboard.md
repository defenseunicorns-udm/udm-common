# udm-onboard

Onboard an ISV codebase into the UDS Army pipeline by generating a `tasks.yaml` and CI workflow file. Invoke with `/udm-onboard`.

## What this skill does

1. Notes onboarding prerequisites (informational — does not block file generation)
2. Asks upfront questions; offers to autodiscover language and CI provider from the repo
3. Generates `tasks.yaml` and CI workflow file (new files written directly; existing files get a diff/snippet with instructions)
4. Points to a sample `zarf.yaml` and explains it is a required prerequisite

## Step 1 — Prerequisites notice

Always display this block first, before asking any questions:

```
⚠️  Before this pipeline will work, you must complete onboarding with Defense Unicorns.

Full onboarding steps and explanations are in the udm-common README and CONTEXT.md:
  https://github.com/defenseunicorns-udm/udm-common#prerequisites
  https://github.com/defenseunicorns-udm/udm-common/blob/main/CONTEXT.md (see "Organization")

Files will be generated regardless — complete onboarding when ready.
```

## Step 2 — Ask upfront questions

Ask these questions before exploring the repo. Offer to autodiscover #1 and #2 by scanning the codebase.

1. **CI provider** — GitHub Actions, GitLab (cloud), or GitLab (self-hosted)?
2. **Primary language/runtime** — Python, Go, TypeScript/JavaScript, other? (offer to detect from package.json / go.mod / requirements.txt / pyproject.toml)
3. **Monorepo?** — If yes: how many services and what are their paths?
4. **`olm_org`** — What is your CAT organization name? (provided by DU during onboarding)
5. **Existing files?** — Does a `tasks.yaml` or CI workflow file already exist? (offer to check)

If the user says "detect" or "discover" for #1/#2, scan the repo and confirm findings before proceeding.

## Step 3 — Check for a zarf.yaml

Before generating files, check whether a `zarf.yaml` exists in the repo root (or at relevant service paths for monorepos).

If **no `zarf.yaml` found**, display:

```
⚠️  No zarf.yaml found. A zarf.yaml is required before your package can be built and published.

A minimal starting point looks like this — adapt to your application:

  kind: ZarfPackageConfig
  metadata:
    name: my-app           # must match what you pass as olm_org package name in CAT
    version: "0.1.0"
    description: My application

  components:
    - name: my-app
      required: true
      # Add your charts, manifests, or images here.
      # See https://docs.zarf.dev/ref/components/ for all options.

Defense Unicorns is preparing additional Zarf onboarding docs. For now, see:
https://docs.zarf.dev/getting-started/
```

Continue generating `tasks.yaml` and CI files regardless.

## Step 4 — Generate tasks.yaml

### For a new tasks.yaml

Write the file. Use the correct `lint` task for the detected language (see templates below). Always pin udm-common at the latest release tag.

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/defenseunicorns/maru-runner/refs/heads/main/tasks.schema.json
#
# UDS CLI is required to run these tasks.
# GitHub Actions: use defenseunicorns-udm/udm-common/.github/actions/uds-cli-setup
# Other CI/local: see https://github.com/defenseunicorns/udm-common#prerequisites
#
# renovate: datasource=github-releases depName=defenseunicorns-udm/udm-common
# Pin version below. Use Renovate to keep it current.

includes:
  # renovate: datasource=github-releases depName=defenseunicorns-udm/udm-common
  - setup:   https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/setup.yaml
  - attest:  https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/attest.yaml
  - scan:    https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/scan.yaml
  - build:   https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/build.yaml
  - vouch:   https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/vouch.yaml
  - publish: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/publish.yaml
  - olm:     https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/olm.yaml

tasks:

  - name: lint
    description: <FILL IN — see lint templates below>
    actions:
      - cmd: <FILL IN>
```

### Lint task templates by language

**Python (Ruff)**
```yaml
  - name: lint
    description: Lint Python source with Ruff
    actions:
      - cmd: ruff check .
```

**Go (golangci-lint)**
```yaml
  - name: lint
    description: Lint Go source with golangci-lint
    actions:
      - cmd: golangci-lint run ./...
```

**TypeScript / JavaScript (ESLint)**
```yaml
  - name: lint
    description: Lint TypeScript/JavaScript with ESLint
    actions:
      - cmd: npx eslint .
```

**Monorepo (adapt paths)**
```yaml
  - name: lint
    description: Lint all services
    actions:
      - cmd: ruff check services/api          # adapt per service
      - cmd: golangci-lint run ./services/worker/...
      - cmd: npx eslint services/frontend
```

**Unknown language**
```yaml
  - name: lint
    description: Lint source code
    actions:
      - cmd: <YOUR LINT COMMAND HERE>
```

### For an existing tasks.yaml

Do **not** overwrite. Show the user exactly what to add:

```
tasks.yaml already exists. Add these two blocks:

1. Merge into your existing `includes:` section:

  # renovate: datasource=github-releases depName=defenseunicorns-udm/udm-common
  - setup:   https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/setup.yaml
  - attest:  https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/attest.yaml
  - scan:    https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/scan.yaml
  - build:   https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/build.yaml
  - vouch:   https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/vouch.yaml
  - publish: https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/publish.yaml
  - olm:     https://raw.githubusercontent.com/defenseunicorns-udm/udm-common/v0.10.3/tasks/olm.yaml

2. Add a `lint` task (if you don't have one already):

  <use appropriate template from above>
```

## Step 5 — Generate CI workflow file

### GitHub Actions (new file: .github/workflows/udm-pipeline.yaml)

```yaml
name: UDM Pipeline

on:
  workflow_dispatch:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write        # required for Sigstore keyless signing

    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2

      # renovate: datasource=github-releases depName=defenseunicorns-udm/udm-common
      - uses: defenseunicorns-udm/udm-common/.github/actions/uds-cli-setup@9aaad66b21c7637b5be3d6aafdb21c9e7ff1df2a # v0.10.3

      # attest:lint wraps your repo's `lint` task with Witness attestation.
      # You must define a `lint` task in tasks.yaml — see examples/tasks.yaml in udm-common.
      - name: Lint
        run: uds run attest:lint

      - name: Security Scan
        run: |
          uds run scan:security \
            --with opengrep_scan_path=.    # narrow to your source directory if needed

      - name: Vouch
        run: |
          uds run vouch:package \
            --with github_token="${{ secrets.GITHUB_TOKEN }}" \
            --with attestations="lint-witness.json,gitleaks-witness.json,opengrep-witness.json" \
            --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json" \
            --with olm_cat=cat-api.uds-mil.us \
            --with olm_org="<YOUR_ORG_NAME>"    # replace with your CAT org name

      - name: Publish
        run: |
          uds run publish:zarf-package \
            --with registry_org="<YOUR_ORG_NAME>" \
            --with registry_user_id="${{ secrets.REGISTRY_USER_ID }}" \
            --with registry_password="${{ secrets.REGISTRY_PASSWORD }}"
```

Substitute `<YOUR_ORG_NAME>` with the `olm_org` value provided by the user.

For **monorepos**, wrap Vouch + Publish in a matrix strategy:

```yaml
  scan-vouch-publish:
    strategy:
      matrix:
        service: [api, worker, frontend]   # replace with actual service names
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
            --with olm_org="<YOUR_ORG_NAME>"
      - run: |
          uds run publish:zarf-package \
            --with registry_org="<YOUR_ORG_NAME>" \
            --with registry_user_id="${{ secrets.REGISTRY_USER_ID }}" \
            --with registry_password="${{ secrets.REGISTRY_PASSWORD }}"
```

### GitLab CI (new file: .gitlab-ci.yml)

```yaml
stages:
  - ci
  - publish

variables:
  # renovate: datasource=github-releases depName=defenseunicorns/uds-cli
  UDS_VERSION: v0.31.0
  DOCKER_HOST: tcp://docker:2375
  DOCKER_TLS_CERTDIR: ""
  OLM_CAT: cat-api.uds-mil.us
  OLM_ORG: <YOUR_ORG_NAME>    # replace with your CAT org name

.uds-cache: &uds-cache
  cache:
    key: uds-${UDS_VERSION}
    paths:
      - .cache/uds-bin/

.install-uds: &install-uds
  - mkdir -p .cache/uds-bin
  - |
    if [ ! -f ".cache/uds-bin/uds" ]; then
      curl --retry-all-errors --retry 5 -fSL \
        "https://github.com/defenseunicorns/uds-cli/releases/download/${UDS_VERSION}/uds-cli_${UDS_VERSION}_Linux_amd64" \
        -o .cache/uds-bin/uds
      chmod +x .cache/uds-bin/uds
    fi
    cp .cache/uds-bin/uds /usr/local/bin/uds

ci:
  stage: ci
  <<: *uds-cache
  image: <YOUR_BUILD_IMAGE>    # e.g. node:24, python:3.12, golang:1.22
  id_tokens:
    SIGSTORE_ID_TOKEN:
      aud: sigstore
  services:
    - name: docker:24-dind
      command: --tls=false
  before_script:
    - apt-get update -qq && apt-get install -y -qq curl docker.io
    - *install-uds
  script:
    - uds run attest:lint --with enable_sigstore=true --with fulcio_oidc_issuer="$CI_SERVER_URL"
    - |
      uds run scan:security \
        --with opengrep_scan_path=. \
        --with enable_sigstore=true \
        --with fulcio_oidc_issuer="$CI_SERVER_URL"
  artifacts:
    paths:
      - lint-witness.json
      - gitleaks-witness.json
      - opengrep-witness.json
      - gitleaks.sarif.json
      - opengrep.sarif.json
    when: always
    expire_in: 1 day

publish:
  stage: publish
  <<: *uds-cache
  image: <YOUR_BUILD_IMAGE>
  id_tokens:
    OLM_ID_TOKEN:
      aud: cat
    SIGSTORE_ID_TOKEN:
      aud: sigstore
  services:
    - name: docker:24-dind
      command: --tls=false
  needs:
    - job: ci
      artifacts: true
      optional: true
  before_script:
    - apt-get update -qq && apt-get install -y -qq curl docker.io
    - *install-uds
  script:
    - |
      uds run vouch:package \
        --with olm_cat="$OLM_CAT" \
        --with olm_org="$OLM_ORG" \
        --with enable_sigstore=true \
        --with fulcio_oidc_issuer="$CI_SERVER_URL" \
        --with olm_identity_token="$OLM_ID_TOKEN" \
        --with attestations="lint-witness.json,gitleaks-witness.json,opengrep-witness.json" \
        --with sarif_files="gitleaks.sarif.json,opengrep.sarif.json"
    - |
      uds run publish:zarf-package \
        --with registry="registry.uds-mil.us" \
        --with registry_org="$OLM_ORG" \
        --with registry_user_id="$REGISTRY_USER_ID" \
        --with registry_password="$REGISTRY_PASSWORD"
```

Substitute `<YOUR_ORG_NAME>` and `<YOUR_BUILD_IMAGE>` with the user's values.

### For an existing CI file

Do **not** overwrite. Show the diff as a code block and explain what to add and where.

## Step 6 — Final output summary

After generating or showing all files, display:

```
Done. Here's what was generated/shown:

  ✓ tasks.yaml         — includes udm-common task namespaces + lint task
  ✓ <ci-file>          — pipeline with lint, scan, vouch, publish steps
  ⚠  zarf.yaml         — not generated; required prerequisite (see note above)

Next steps:
  1. Complete DU onboarding if you haven't (see prerequisites above)
  2. Add REGISTRY_USER_ID and REGISTRY_PASSWORD to your CI secrets/variables
     (self-serve at registry.uds-mil.us after completing onboarding)
  3. Replace any <PLACEHOLDER> values in the generated files
  4. Add Renovate to your repo to keep udm-common and UDS CLI version pins current
  5. Commit and push — your first pipeline run will produce evidence in CAT

For full docs: https://github.com/defenseunicorns-udm/udm-common
```

## How to install this skill

ISVs copy this file to `.claude/skills/udm-onboard.md` in their own repo, then invoke it with `/udm-onboard`.

To keep it current with udm-common releases, add a Renovate comment in the copied file pointing at this repo.
