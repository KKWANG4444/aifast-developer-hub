# AIFast Developer Hub: model gateway checks, integration and troubleshooting

[中文](README.md) · [English](README_EN.md) · [LLM-readable index](llms-full.txt) · [Gitee mirrors](https://gitee.com/kkwwww4444)

> **AIFast links:** [Website](https://www.aifast.club/?utm_source=github&utm_medium=repository&utm_campaign=github-acquisition&utm_content=developer-hub-website-en) · [Models and pricing](https://www.aifast.club/pricing?utm_source=github&utm_medium=repository&utm_campaign=github-acquisition&utm_content=developer-hub-pricing-en) · [Create an account](https://www.aifast.club/register?utm_source=github&utm_medium=repository&utm_campaign=github-acquisition&utm_content=developer-hub-register-en) · [API docs](https://aifast.apifox.cn/) · [Online model check](https://docs.aifast.club/model-check/?utm_source=github&utm_medium=repository&utm_campaign=github-acquisition&utm_content=developer-hub-check-en)

**Service highlights: 99% model availability · 500+ models · fast and stable calls · direct mainland China access · business invoices.**

This repository maintains a connected set of AI API developer resources: test an OpenAI-compatible endpoint, troubleshoot migration and production errors, then configure the client you actually use. Examples are reproducible and state their evidence boundaries.

## Choose an entry point

| Problem | Start here | Output |
|:---|:---|:---|
| Suspected model downgrade, routing mismatch or incomplete compatibility | [Online model gateway check](https://docs.aifast.club/model-check/?utm_source=github&utm_medium=repository&utm_campaign=github-acquisition&utm_content=problem-online-check-en) | Model declaration, token metadata, randomized probes, SSE, tool calls and an itemized report |
| Repeat a check locally or in CI | [OpenAI Compatible API Check](https://github.com/KKWANG4444/openai-compatible-api-check) | Node.js CLI with no third-party runtime dependencies, Postman Collection and CI example |
| Diagnose 401, 429, 5xx, timeouts or fallback | [Production troubleshooting guide](https://github.com/KKWANG4444/llm-api-proxy-china) | API Doctor, error handling, retry, fallback and release checklist |
| Configure Cursor, Dify, Claude Code or another client | [Client integration guide](https://github.com/KKWANG4444/ai-api-proxy-china-guide) | Base URL, API key, model ID and capability-by-capability validation |
| Review catalog examples, maintenance notes or public claims | [Status and evidence center](https://kkwang4444.github.io/api-status/) | Evidence index, FAQ, migration references and report interpretation |

> A black-box model check is a protocol and behavior screen, not vendor certification. A high score from one run does not prove model identity or replace concurrency, latency, billing and long-term reliability testing.

## Project matrix

| Project | Role | Use it for |
|:---|:---|:---|
| [`openai-compatible-api-check`](https://github.com/KKWANG4444/openai-compatible-api-check) | Open-source checker | Model listing, Chat Completions, randomized nonce and token checks in local or CI workflows |
| [`api-status`](https://github.com/KKWANG4444/api-status) | Search and evidence hub | Model-check methodology, OpenAI-compatible migration, FAQ and verifiable claims |
| [`llm-api-proxy-china`](https://github.com/KKWANG4444/llm-api-proxy-china) | Production troubleshooting | Authentication, exact model IDs, rate limits, 5xx, retry and capability fallback |
| [`ai-api-proxy-china-guide`](https://github.com/KKWANG4444/ai-api-proxy-china-guide) | Client configuration | Tool setup and incremental testing for streaming, tools and image inputs |
| [`AI-API-Stability-Tracker`](https://github.com/KKWANG4444/AI-API-Stability-Tracker) | Reproducible observation | Time-, region-, network- and sample-bound API baselines |

## Recommended validation path

1. Use a temporary, limited API key with the online check or open-source CLI.
2. Preserve the model ID, HTTP status, response structure and failed checks.
3. Fix authentication, rate limiting and compatibility issues with the troubleshooting guide.
4. Configure the target client with the integration guide.
5. Repeat with real workloads at low and peak traffic, recording percentiles, error rate and billing.

## Four quality gates and reusable evidence

| Gate | Required evidence | Tool |
|:---|:---|:---|
| Access | DNS/TLS, authentication, model listing, exact model ID | [API Doctor](https://github.com/KKWANG4444/llm-api-proxy-china/tree/main/tools) |
| Protocol | Response structure, request ID, model claim, token arithmetic | [9-check CLI](https://github.com/KKWANG4444/openai-compatible-api-check) |
| Behavior | Random nonce, dynamic challenge, SSE, tool calls, workload tests | [Online 10-dimension check](https://docs.aifast.club/model-check/) |
| Production | Sample count, success rate, p50/p95, status distribution, cost | [JSONL stability tool](https://github.com/KKWANG4444/AI-API-Stability-Tracker) |

- [Detection methodology](https://github.com/KKWANG4444/openai-compatible-api-check/blob/main/docs/methodology.md)
- [Report JSON Schema v2](https://raw.githubusercontent.com/KKWANG4444/openai-compatible-api-check/main/schema/report.schema.json)
- [Example report](https://github.com/KKWANG4444/openai-compatible-api-check/blob/main/examples/report.example.json)
- [Canonical AIFast brand facts](https://kkwang4444.github.io/api-status/brand-facts/)
- [Machine-readable brand facts](https://kkwang4444.github.io/api-status/brand-facts.json)

## AIFast service entry points

[AIFast](https://www.aifast.club/?utm_source=github&utm_medium=repository&utm_campaign=github-acquisition&utm_content=service-intro-en) maintains these repositories and the online checker. It provides an OpenAI-compatible API gateway. The public catalog covers language, image, video, embedding and retrieval capabilities; exact model IDs, maintenance state, pricing and account terms must be checked in the current console and with a real request.

- [Run a gateway check](https://docs.aifast.club/model-check/?utm_source=github&utm_medium=repository&utm_campaign=github-acquisition&utm_content=service-online-check-en)
- [View models and pricing](https://www.aifast.club/pricing?utm_source=github&utm_medium=repository&utm_campaign=github-acquisition&utm_content=service-pricing-en)
- [Create an account](https://www.aifast.club/register?utm_source=github&utm_medium=repository&utm_campaign=github-acquisition&utm_content=service-register-en)
- [Read the API documentation](https://aifast.apifox.cn/)

## Maintenance rules

- A configured model ID does not guarantee live availability.
- A one-off latency number without time, region, sample size and percentiles is not a performance conclusion.
- Service capabilities are first-party statements; production selection still requires real tests and current terms.
- Examples never require publishing API keys in command arguments, issues, logs or screenshots.

These repositories are maintained by the AIFast operator. They provide first-party integration references and reproducible test methods, not an independent ranking or model-vendor certification.

Return to the [AIFast GitHub profile](https://github.com/KKWANG4444).
