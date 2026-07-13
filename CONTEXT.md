# Context

This is the domain glossary for udm-common. Implementation details belong in code and ADRs, not here.

AI coding agents should read this glossary together with [`CLAUDE.md`](CLAUDE.md) or [`AGENTS.md`](AGENTS.md). The guidance is shared across Claude Code, OpenAI Codex, and other agents; the filename used to load the instructions does not change the project rules.

## Terms

### AI Agent
An AI-assisted coding tool that reads repository instructions, inspects the codebase, and proposes or applies changes. This repository supports Claude Code, OpenAI Codex, and other agents that honor `AGENTS.md` or `CLAUDE.md`.

### Repository Instructions
The checked-in guidance that agents must follow while working here. `CLAUDE.md` contains the shared repository instructions for compatibility with Claude Code; `AGENTS.md` is the OpenAI Codex and agent entrypoint. Both point agents to this glossary.

### Consumer (ISV)
A team or organization of engineers building an application to be onboarded into the DSOP. In CAT, consumers are called **ISVs** (Independent Software Vendors). Maps one-to-one with an **Organization** in CAT. CI/CD provider (GitHub Actions, GitLab, other) is irrelevant — consumers use these tasks regardless of provider.

### Organization
The administrative unit in CAT that groups a consumer's packages. Supplied as `olm_org` when running tasks. A consumer may have multiple packages within one organization. Each package is identified in the CAT UI by `metadata.name` and `metadata.version` from its `zarf.yaml`.

**Required onboarding steps (must complete before pipeline can vouch and publish):**
1. Provide org name to Defense Unicorns for provisioning in CAT
2. Provide email addresses of team members who need CAT access
3. Team members sign up for accounts at `sso.uds-mil.us` — the shared Keycloak instance used by both CAT and the Registry
4. In the CAT UI, configure an allowlist of repos/projects permitted for Fulcio OIDC token exchange — currently supports `github.com` and `gitlab.com` (self-hosted GitLab in progress)
5. Visit `registry.uds-mil.us`, log in with the SSO account from step 3, and create an **Organization Access Token**. Store credentials in a password manager and add to CI as a secret (GitHub Actions) or masked variable (GitLab CI). These map to `registry_user_id` and `registry_password` on `publish:zarf-package`.

### DSOP (DevSecOps Pipeline)
The mechanism that software must pass through to be evaluated for deployment into a DoD ATO'd environment. CAT + Chainloop + OLM together implement the DSOP as a continuous, cryptographically-anchored pipeline. Running the udm-common pipeline tasks does not require a running Kubernetes cluster — cluster knowledge is only needed for Zarf package development and testing, which is separate.

### ATO (Authority to Operate)
A pre-existing DoD accreditation for a deployment environment. CAT does not issue ATOs — it produces per-artifact approvals to run inside an already ATO'd environment.

### CAT (Compliance Assessment Tool)
The UDS Army compliance dashboard. Sits in front of Chainloop as the authorization and review layer. Receives signed attestations via OLM/Chainloop, surfaces policy findings to ISSM reviewers, and records AO approvals. CAT does not evaluate Rego policies itself — it renders Chainloop's results.

### OLM
Internal UDS Army CLI tool (acronym not formally defined). The ISV-side on-ramp to Chainloop. Invoked by `vouch:package` to submit a Zarf package's evidence via a three-phase auth flow: (1) CI identity token → CAT bearer JWT; (2) bearer → Chainloop project token; (3) bearer → Fulcio signing token. CAT provides environment discovery so consumers don't configure Chainloop endpoints manually. Also provides `olm tools generate-fulcio-token` — used by the `olm:generate-fulcio-token` task to mint a **Fulcio Token** before Witness-attested pipeline steps run.

### Chainloop
Open-source supply chain evidence store and attestation control plane. Receives attestations and SARIF files from `olm vouch` as **materials**, evaluates OPA policies at push/view time, and stores evidence immutably. Consumers don't call Chainloop directly — OLM handles the API interaction.

### Material
Chainloop's term for a unit of supply chain evidence. In udm-common's pipeline, materials are the Witness attestation JSON files (`*-witness.json`) and SARIF reports submitted during `vouch:package`.

### Vouch
The act of submitting a package's signed attestations and SARIF materials to Chainloop via OLM. **Non-blocking:** policy failures do not hard-fail the pipeline — they surface as **Findings** in CAT for human review. A vouched package has evidence recorded in Chainloop/CAT and is eligible for publish regardless of policy state. Publishing without vouching first is technically possible but not advised — there is no registry-level enforcement.

### Finding
A policy evaluation failure surfaced in CAT after vouching. Must be remediated or justified by the ISSM reviewer before AO approval.

### Customer Run
The Chainloop workflow run produced by the ISV's pipeline (via udm-common tasks). Paired in CAT with a **Unicorn Run** to form a complete compliance record.

### Unicorn Run
A secondary pipeline run by Defense Unicorns against the ISV's published artifacts. Triggered automatically when a package is published to the registry. Paired with the Customer Run in CAT. Consumers do not control or trigger this run. Built-in Chainloop policies are evaluated but do not block the run.

### AO (Authorizing Official)
CAT role. Approves specific software artifacts for deployment into an ATO'd environment after ISSM review.

### ISSM (Information System Security Manager)
CAT role. Reviews findings surfaced from the paired Customer Run + Unicorn Run and vets evidence before AO approval.

### Attestation
A signed JSON file (in-toto v1 statement, DSSE-wrapped) that proves a pipeline step ran and what it produced. Each pipeline step produces one file (e.g. `lint-witness.json`, `gitleaks-witness.json`).

### Witness
The CLI tool that wraps pipeline steps and produces attestations. Supports local ED25519 key signing (for local runs) and keyless signing via `fulcio.uds-mil.us` (for CI). In CI, signing uses a **Fulcio Token** written to `.fulcio-token` by the `olm:generate-fulcio-token` task. Locally, if no key is set, Witness triggers a browser OIDC flow against `fulcio.uds-mil.us` directly.

### Fulcio Token
A short-lived JWT issued by CAT that authorizes Witness to obtain a signing certificate from the UDS Fulcio instance (`fulcio.uds-mil.us`). Generated by `olm tools generate-fulcio-token` and stored in `.fulcio-token`. CAT acts as broker: it authenticates the CI identity, checks the configured GitHub or GitLab project allowlist for the **Organization**, and mints the token — eliminating the need to manually configure per-provider OIDC trust in Fulcio directly.
_Avoid_: OIDC token, Sigstore token (those refer to different things)

### Version Pinning
Consumers pin udm-common at a specific release tag in their `includes:` block. Recommended: use Renovate to keep pins current. Breaking changes are documented in release notes with migration guidance where possible. No strong backwards-compatibility guarantee at this stage of the project.

### github_token (task input)
Optional parameter on `vouch:package` and `olm:setup`. Used solely to authenticate to `ghcr.io` when downloading the OLM binary, avoiding anonymous pull rate limits. Has no role in OIDC, CAT auth, or Chainloop. Recommended for GitHub Actions CI but not required.

### Zarf Package
The deployable artifact a consumer builds. Should contain **all components of the ISV's application** (e.g. API server, worker, frontend) in a single package — not split across multiple packages. Think of it as your app, not its infrastructure. Databases, message queues, and other backing services belong in the **UDS Bundle**, not here: your application code should treat them as attached resources, reading connection details from environment variables rather than bundling the services themselves. Published to the UDS Army registry after vouching.

### UDS Bundle
General UDS concept ([docs](https://docs.defenseunicorns.com/core/concepts/configuration--packaging/bundles/)). Defined in a `uds-bundle.yaml` manifest, a bundle specifies which Zarf packages to deploy, in what order, and which Helm values or Zarf variables are configurable. Think of it as the blueprint: built once, deployed to multiple environments by pairing it with a **UDS Config** that fills in environment-specific values.

In udm-common's pipeline, when `uds_bundle` is passed to `vouch:package`, the `uds-bundle.yaml` is submitted as a **Material** to Chainloop. CAT retrieves this material and uses it to submit a **Customer Deployment** CR, enabling sandbox preview of the ISV's application.

ISVs may pass the same bundle they use for local testing — the platform detects and strips infrastructure dependencies (e.g. postgres-operator, minio) that are not needed in the UDS Army environment.

### UDS Config
General UDS concept ([docs](https://docs.defenseunicorns.com/cli/how-to-guides/use-bundle-overrides/)). A `uds-config.yaml` file that supplies deployment-time values for a **UDS Bundle** — environment-specific secrets, hostnames, cluster endpoints, and other concrete values for variables the bundle exposes. Separate from the bundle itself so the same bundle artifact can be deployed to multiple environments without modification. The ISV authors the bundle; the UDS Army platform provides the config for the sandbox environment at deploy time. ISVs do not need to supply a `uds-config.yaml` to the pipeline.

### Customer Deployment
A Kubernetes custom resource (CR) submitted by CAT to an IL2 sandbox environment, enabling a preview/demo deploy of an ISV's application. Requires a **UDS Bundle** to be submitted as material during `vouch:package`. The sandbox module reads the CR and orchestrates the actual deployment. Distinct from a **Customer Run** (Chainloop evidence record) — a Customer Deployment is the live running instance, not the compliance record.

### Registry
`registry.uds-mil.us` — the UDS Army OCI registry where vouched Zarf packages are published. Login uses the same SSO account from `sso.uds-mil.us`. Consumers self-serve registry credentials via the registry UI as either an **Organization Access Token** (recommended for CI — created by an org admin, shared via password manager, added as a CI secret or masked variable) or a **Personal Access Token** (per-user, recommended for local testing). Despite the "token" label, both types are dynamically generated username/password credential pairs, not API keys. Creating either type produces a ready-to-run `zarf tools registry login` command.
