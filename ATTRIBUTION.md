# AI快站公开推广资产 UTM 规范

此规范用于 GitHub、CSDN、知乎、掘金、NodeSeek 与 Dev.to 的公开入口。API Base URL、代码请求地址、机器调用端点、Canonical、JSON-LD、`llms.txt` 和品牌事实 JSON 不得添加 UTM。

## 参数定义

| 参数 | 允许值或格式 | 示例 |
|:---|:---|:---|
| `utm_source` | `github`、`csdn`、`zhihu`、`juejin`、`nodeseek`、`devto` | `github` |
| `utm_medium` | `profile`、`repository`、`pages`、`article`、`answer`、`release`、`third-party` | `repository` |
| `utm_campaign` | `developer_acquisition`、`integration-guide`、`api-doctor`、`model-check` | `model-check` |
| `utm_content` | `{资产}-{语言}-{位置}`，使用小写短横线 | `guide-cn-hero-register` |

## 四个 Campaign 的边界

- `developer_acquisition`：`/start/` 任务分流页及首次调用、接口检测、工具迁移、企业接入等跨场景入口。
- `integration-guide`：品牌主页、模型价格、注册、客户端配置与接入教程。
- `api-doctor`：401、429、5xx、超时、鉴权、Base URL 与生产排错。
- `model-check`：模型声明、Token、动态题、SSE、工具调用、降智与套壳风险筛查。

## 漏斗口径

1. `registration_landing`：用户通过带 UTM 的链接进入注册页，可由前端来源参数确认。
2. `signup_completed`：用户完成注册，必须由主站后端把首次归因写入用户记录。
3. `first_topup_completed`：用户首次充值，必须由主站支付或订单后端关联用户归因。

在主站后端没有回传之前，只能报告进入注册页的访问，不能把 CTA 点击写成完成注册，也不能推测首次充值。

## 示例

```text
https://www.aifast.club/register?channel=c_uoqg7aoy&utm_source=github&utm_medium=repository&utm_campaign=integration-guide&utm_content=guide-cn-hero-register
```

新增公开链接时必须填写 `utm_content`，同一位置不得在不同仓库复用相同值。

机器可读文件中的官网、价格和注册链接属于事实标识，不计入 CTA 的 UTM 覆盖率。归因审计应只统计 README、文章正文和可点击页面中的推广入口。

## 自动审计

在当前仓库运行：

```bash
node scripts/audit-utm.mjs .
```

本地同时克隆推广矩阵仓库时，可一次检查多个目录：

```bash
node scripts/audit-utm.mjs \
  . \
  ../github-profile \
  ../api-status \
  ../ai-api-proxy-china-guide \
  ../llm-api-proxy-china \
  ../aifast-model-check-kit
```

脚本会拒绝旧或未知 Campaign、缺少四个必要参数的追踪链接、带 UTM 的 API 调用地址，以及机器可读事实文件中的追踪参数。它不会把代码里的 Base URL 或纯事实链接算作 CTA。
