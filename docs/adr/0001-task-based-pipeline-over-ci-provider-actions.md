# ADR 0001: Task-Based Pipeline Over CI-Provider-Specific Actions

## Status
Accepted

## Context

The udm-common pipeline (lint, scan, build, vouch, publish) needs to be usable by ISVs on any CI/CD platform — GitHub Actions, GitLab CI (cloud and self-hosted), and others. The obvious implementation path for a supply-chain security pipeline is to build reusable GitHub Actions workflows, since most tooling in this space is GitHub-native.

The alternative was to use UDS/Maru tasks: a declarative task runner that executes identically regardless of CI provider, requiring only the UDS CLI to be present in the runner environment.

This repo was designed to mirror the conventions of [`github.com/defenseunicorns/uds-common`](https://github.com/defenseunicorns/uds-common), which uses the same task-based pattern for UDS packaging workflows. The naming similarity (`uds-common` vs `udm-common`) causes confusion: `uds-common` is strictly about UDS packaging; `udm-common` is about the UDS Army supply-chain compliance pipeline. The shared pattern was deliberate — teams familiar with `uds-common` should find `udm-common` recognizable.

## Decision

Implement the pipeline as UDS task namespaces (`.yaml` task files) that consumers include by URL into their own `tasks.yaml`. CI pipelines call `uds run <task>` — the same command on every provider.

## Consequences

**Benefits:**
- Consumers on GitHub Actions, GitLab CI, self-hosted runners, or any other provider use identical task invocations
- Pipeline behavior is fully reproducible locally with the same commands used in CI
- No per-provider fork of pipeline logic to maintain

**Trade-offs:**
- Consumers must install the UDS CLI in their CI runner (an extra bootstrap step not needed with native Actions/GitLab templates)
- Consumers unfamiliar with UDS must learn the `tasks.yaml` include syntax and `uds run` invocation pattern before they can use the pipeline
- Cannot leverage CI-provider-native features (e.g., GitHub Actions marketplace, GitLab CI `include` templates) directly
