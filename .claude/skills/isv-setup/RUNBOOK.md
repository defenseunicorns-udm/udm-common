# ISV CI Setup Runbook

Walk an ISV through wiring up UDM CI from zero to a validated CI config.

This runbook works with any AI coding assistant. Claude Code users: invoke via `/isv-setup`.
GitHub Copilot / Codex users: ask your assistant to "follow the ISV CI setup runbook".

---

## Phase 0 — Read the repo

Before asking anything, read the repo:

- Check for existing `.github/workflows/*.yaml` files — if present, note them. Option B applies.
- Check for existing `.gitlab-ci.yml` — if present, note it. Option B applies.
- Check for a `tasks.yaml` at the repo root — confirm a `lint` task is defined (required by `attest:lint`).
- Note the repo name and any existing Zarf-related files (`zarf.yaml`, `zarf-config.yaml`).

---

## Phase 1 — Detect platform

Ask exactly one question:

> "Which CI platform are you using?"
> 1. GitHub Actions
> 2. GitLab CI

Map the answer to `platform=github` or `platform=gitlab`.

---

## Phase 2 — Run setup:generate

Run the generator:

```bash
uds run setup:generate --with platform=<platform>
```

Tell the user what file was written:
- GitHub → `.github/workflows/udm.yaml`
- GitLab → `.gitlab-ci.yml`

Then read the generated file so you have its exact content.

---

## Phase 3 — Walk REPLACE_ME values

The generated file contains `REPLACE_ME` placeholders. Ask for each one in order — one at a time:

### GitHub Actions

1. **CAT organization name** (`REPLACE_ME: your CAT organization name`)
   - Ask: "What's your CAT organization name? This is provided to you by Defense Unicorns when your CAT account is created."
   - Replace all occurrences in the file (appears in both Generate Fulcio Token and Vouch steps).

2. **Registry organization** (`REPLACE_ME: your registry organization`)
   - Ask: "What's your registry organization on registry.uds-mil.us? Defense Unicorns provides this when your registry account is provisioned."
   - Replace in the Publish step.

3. **Secrets reminder** — don't ask for values, just remind:
   > "You'll need to add two GitHub Actions secrets. Both are provided by Defense Unicorns with your registry credentials:
   > - `REGISTRY_USER_ID` — your registry.uds-mil.us username
   > - `REGISTRY_PASSWORD` — your registry.uds-mil.us password or token
   >
   > Add them at: Settings > Secrets and variables > Actions"

### GitLab CI

1. **CAT organization name** (`REPLACE_ME: your CAT organization name`)
   - Ask: "What's your CAT organization name? This is provided to you by Defense Unicorns when your CAT account is created."
   - Replace in the `OLM_ORG` variable.

2. **Registry organization** (`REPLACE_ME: your registry organization`)
   - Ask: "What's your registry organization on registry.uds-mil.us? Defense Unicorns provides this when your registry account is provisioned."
   - Replace in the `publish:` script.

3. **Variables reminder** — don't ask for values, just remind:
   > "You'll need to add two masked CI/CD variables. Both are provided by Defense Unicorns with your registry credentials:
   > - `REGISTRY_USER_ID` — your registry.uds-mil.us username
   > - `REGISTRY_PASSWORD` — your registry.uds-mil.us password or token
   >
   > Add them at: Settings > CI/CD > Variables (mark both as Masked)"

After collecting values, edit the generated file to substitute them.

---

## Phase 4 — Check lint task

Check whether a `lint` task is defined in `tasks.yaml`:

```bash
grep -A2 'name: lint' tasks.yaml 2>/dev/null || true
```

If **missing**, warn:
> "`attest:lint` calls a `lint` task that must be defined in your `tasks.yaml`. Add something like:
> ```yaml
> tasks:
>   - name: lint
>     actions:
>       - cmd: echo "no-op lint — replace with your actual linting command"
> ```"

If **present**, confirm: "Your `lint` task is defined — `attest:lint` will call it."

---

## Phase 5 — Option A vs B guidance

If the user has an **existing workflow/pipeline file** (detected in Phase 0):

GitHub:
> "You're on Option B. Copy the entire `jobs:` block from `.github/workflows/udm.yaml` into your existing workflow file, then delete `.github/workflows/udm.yaml`. Make sure your existing `on:` block covers the branches you want."

GitLab:
> "You're on Option B. Follow these steps:
> 1. Add `ci` and `publish` to your `stages:` list
> 2. Merge the `variables:` block into your existing variables
> 3. Copy the `.uds-cache` and `.install-deps` anchors (skip if you have equivalent ones)
> 4. Copy the `ci:` and `publish:` job definitions
> 5. If `ci` or `publish` conflict with existing job names, rename them (e.g. `udm-ci`, `udm-publish`) and update `needs:` in `publish:`"

If **no existing CI** (Option A):
> "You're on Option A — the generated file is ready to commit as-is."

---

## Phase 6 — Run setup:validate

Run validation:

```bash
uds run setup:validate
```

Report the result. If it fails:
- If it mentions `REPLACE_ME`: a placeholder was missed — help them find and fix it.
- If it mentions a missing tool (witness, cosign): suggest `uds run setup:witness` or `uds run setup:cosign`.
- Other failures: show the output and diagnose.

---

## Phase 7 — Install pre-commit hook (optional)

Offer:
> "Want to install a pre-commit hook that blocks commits with unfilled `REPLACE_ME` values? Run `uds run setup:install-hooks` to set it up."

Don't run it automatically — just offer.

---

## Phase 8 — Done

Give the ISV a concrete checklist of what's left:

```
[ ] Fill in REPLACE_ME values (if any remain)
[ ] Add REGISTRY_USER_ID and REGISTRY_PASSWORD secrets/variables to your CI platform
[ ] Ensure a lint task is defined in tasks.yaml
[ ] Commit the CI file (Option A) or merge into existing workflow (Option B)
[ ] Push and watch the first pipeline run
```

---

## Key Rules

- Never ask for secret values (passwords, tokens) — only remind where to set them in the CI platform.
- Walk values one at a time, not as a list dump.
- CAT org name, registry org, registry credentials are all **provided by Defense Unicorns** — never imply the ISV creates or chooses these.
- If the user already has a CI file, default to Option B guidance.
- If setup:validate passes, you're done — don't add extra steps.
