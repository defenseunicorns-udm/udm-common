# Context

This is the domain glossary for udm-common. Implementation details belong in code and ADRs, not here.

## Terms

### Consumer (ISV)
A team or organization of engineers building an application to be onboarded into the DSOP. In CAT, consumers are called **ISVs** (Independent Software Vendors). Maps one-to-one with an **Organization** in CAT. CI/CD provider (GitHub Actions, GitLab, other) is irrelevant — consumers use these tasks regardless of provider.

### Organization
The administrative unit in CAT that groups a consumer's packages. Supplied as `olm_org` when running tasks. A consumer may have multiple packages within one organization. Each package is identified in the CAT UI by `metadata.name` and `metadata.version` from its `zarf.yaml`.

**Required onboarding steps (must complete before pipeline can vouch):**
1. Provide org name to Defense Unicorns for provisioning in CAT
2. Provide email addresses of team members who need CAT access
3. Team members sign up for accounts at `sso.uds-mil.us`
4. In the CAT UI, configure an allowlist of repos/projects permitted for Fulcio OIDC token exchange — currently supports `github.com` and `gitlab.com` (self-hosted GitLab in progress)

### DSOP (DevSecOps Pipeline)
The mechanism that software must pass through to be evaluated for deployment into a DoD ATO'd environment. CAT + Chainloop + OLM together implement the DSOP as a continuous, cryptographically-anchored pipeline. Running the udm-common pipeline tasks does not require a running Kubernetes cluster — cluster knowledge is only needed for Zarf package development and testing, which is separate.

### ATO (Authority to Operate)
A pre-existing DoD accreditation for a deployment environment. CAT does not issue ATOs — it produces per-artifact approvals to run inside an already ATO'd environment.

### CAT (Compliance Assessment Tool)
The UDS Army compliance dashboard. Sits in front of Chainloop as the authorization and review layer. Receives signed attestations via OLM/Chainloop, surfaces policy findings to ISSM reviewers, and records AO approvals. CAT does not evaluate Rego policies itself — it renders Chainloop's results.

### OLM
Internal UDS Army CLI tool (acronym not formally defined). The ISV-side on-ramp to Chainloop. Invoked by `vouch:package` to submit a Zarf package's evidence via a three-phase auth flow: (1) CI identity token → CAT bearer JWT; (2) bearer → Chainloop project token; (3) bearer → Fulcio signing token. CAT provides environment discovery so consumers don't configure Chainloop endpoints manually.

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
The CLI tool that wraps pipeline steps and produces attestations. Supports local ED25519 key signing (for local runs) and keyless Sigstore/Fulcio OIDC signing (for CI).

### Version Pinning
Consumers pin udm-common at a specific release tag in their `includes:` block. Recommended: use Renovate to keep pins current. Breaking changes are documented in release notes with migration guidance where possible. No strong backwards-compatibility guarantee at this stage of the project.

### github_token (task input)
Optional parameter on `vouch:package` and `olm:setup`. Used solely to authenticate to `ghcr.io` when downloading the OLM binary, avoiding anonymous pull rate limits. Has no role in OIDC, CAT auth, or Chainloop. Recommended for GitHub Actions CI but not required.

### Zarf Package
The deployable artifact a consumer builds. Published to the UDS Army registry after vouching.

### Registry
`registry.uds-mil.us` — the UDS Army OCI registry where vouched Zarf packages are published. Consumers self-serve credentials via the registry UI.
