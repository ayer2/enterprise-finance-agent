# Codex 开发入口

## 项目快照

- 项目名称：企业经营与财务数据分析 Agent
- 上游项目：`https://github.com/spring-ai-alibaba/DataAgent.git`
- 克隆日期：2026-08-24
- 上游基线提交：`3fb7852 docs: fix broken Star History chart (#606)`
- 当前分支：`codex/enterprise-finance-agent`
- 当前状态：M0 至 M7 已完成，`v1.0.0` 作品交付验收通过

## 项目目标

在保留 DataAgent 核心架构的基础上，使用完全合成的经营、财务和 KPI 数据，完成以下闭环：

```text
自然语言问题
-> 意图识别与任务规划
-> 指标口径和表结构检索
-> SQL 生成
-> SQL 安全校验
-> 只读数据库查询
-> 多轮下钻
-> 表格、图表和分析报告
-> 执行日志与评测
```

## 当前里程碑

| 里程碑 | 状态 | 说明 |
|---|---|---|
| M0 上游基线验证 | completed | 完整 Agent 问答和后端 `1712` 个测试全部通过，证据见基线验证记录 |
| M1 合成业务数据 | completed | 24 个月、2 万订单及 A01-A06 已通过重复生成和 MySQL SQL 验证 |
| M2 语义模型与知识库 | completed | 63 个字段语义、14 条业务知识、18 组标准 SQL 和 5 组真实向量召回均已验证 |
| M3 Agent 查询闭环 | completed | 核心问题 20/20、多轮下钻 3/3、意图识别 4/4，最终证据 `summary.passed=true` |
| M4 SQL 安全与权限 | completed | 预设危险 SQL 均被应用或数据库边界阻断，真实模型正常查询单题通过 |
| M5 页面与交互 | completed | 经营分析首页、执行依据、下钻、导出、反馈和响应式浏览器验收通过 |
| M6 自动评测 | completed | 36 题真实模型评测通过：SQL 94.44%、结果 94.44%、口径 87.50%、危险请求拦截 100% |
| M7 部署与作品包装 | completed | 三镜像 Compose、干净数据卷启动、真实截图、3 分钟视频、回归与合规检查均通过 |

状态只能使用 `pending`、`in_progress`、`blocked`、`completed`。标记完成时必须附上命令、结果或截图路径。

M2 验证证据见 [`M2语义模型与知识库验证记录.md`](M2语义模型与知识库验证记录.md)。知识导入在当前 H2 管理库的 Agent `5`、数据源 `4` 上完成；这些运行时 ID 在后端重启后可能变化，持久证据和重建入口以 `demo/enterprise-finance/knowledge/` 中的文件与脚本为准。

M3 验证证据见 [`M3Agent查询闭环验证记录.md`](M3Agent查询闭环验证记录.md)。重建运行环境并重新导入语义知识后，完整真实模型链路达到核心问题 `20/20`、多轮下钻 `3/3`、意图识别 `4/4`、图表运行 10 次、HTML 导出通过，最终证据为 `demo/enterprise-finance/m3/evidence/final-accepted.json`；完整后端测试 `1716/1716` 通过。

M4 实施与验证证据见 [`M4SQL安全权限与审计验证记录.md`](M4SQL安全权限与审计验证记录.md)。应用层已经使用 SQL AST 限制单条只读查询，并增加表字段白名单、500 行上限、15 秒超时、部门范围注入、敏感字段脱敏、人工确认分流和审计日志；MySQL 只读账号的 `SELECT` 已成功且 `DELETE` 已被数据库权限拒绝。重新配置 Chat/Embedding 模型并恢复语义知识后，真实模型查询 `M2-Q01` 单题 `passed=true`，生成并执行只读聚合 SQL，结果为 `95,165,908.34`，完整证据保存在 `demo/enterprise-finance/m4/normal-query.json`。

M5 实施与验证证据见 [`M5页面与交互验证记录.md`](M5页面与交互验证记录.md)。保留现有 Nuxt 页面结构并增量加入经营分析首页、预设问题、执行依据、执行前确认、失败重试和持久化回答反馈；真实浏览器完成 `2025年全年销售额是多少？` 的 11 节点查询、同会话按月下钻和 Markdown 报告导出。前端 `9/9` 个测试文件、`30/30` 项测试和生产构建通过，375/768/1024/1440 宽度均无横向溢出。

M6 实施与验证证据见 [`M6自动评测验证记录.md`](M6自动评测验证记录.md)。固定种子 `20260824` 上的 36 题真实模型评测达到 SQL 可执行率 `94.44%`、查询结果正确率 `94.44%`、指标口径正确率 `87.50%`、危险请求拦截率 `100%`，四项均达到验收阈值，最终报告为 `demo/enterprise-finance/m6/evidence/final-accepted.md`。两道未通过题均因当前字段白名单未启用 `receivable.receivable_no` 而被安全边界阻断，已作为已知限制保留；完整后端测试 `1732/1732`、Python 分阶段测试 `17/17` 通过。

M7 实施与验证证据见 [`M7部署与作品包装验证记录.md`](M7部署与作品包装验证记录.md)。三镜像 Compose 在全新隔离数据卷启动后均为 `healthy`，固定数据与 A01-A06 断言、数据库只读权限、非 root 后端和重启恢复均通过；真实页面截图与 180 秒 1080p 演示视频已保存。最终回归为后端 `1732/1732`、前端 `30/30`、Python `17/17`，仓库密钥与真实公司数据检查未发现发布阻塞项。

## Codex 接手后的第一项任务

目标：完成 M0 上游基线验证，不实现任何新业务功能。

执行顺序：

1. 检查 JDK、Maven Wrapper、Docker、Node.js 和 pnpm 是否满足上游要求。
2. 阅读 `docs/QUICK_START.md`，确认管理数据库和模拟数据源的初始化方式。
3. 启动 MySQL 数据源或使用 `docker-file/docker-compose-datasource.yml`。
4. 导入上游 `schema.sql`、`data.sql`、`product_schema.sql`、`product_data.sql`。
5. 启动 `data-agent-management`。
6. 启动 `data-agent-frontend-nuxt`。
7. 访问 `http://localhost:3000`，配置一个模型和 Embedding 模型。
8. 新建 Agent，绑定商品示例数据源并初始化。
9. 完成至少一次 NL2SQL 查询，记录问题、SQL、结果和报告。
10. 新建 `docs/基线验证记录.md`，写入环境版本、命令、结果、错误和未验证项。

M0 验收条件：

- 后端能启动且无阻塞性异常。
- 前端能访问并调用后端。
- 管理数据库和示例业务数据导入成功。
- 模型与 Embedding 模型调用成功。
- 至少一个商品数据问题完成从提问到报告的全链路。
- 后端测试和前端基础检查已运行，未运行项目明确说明原因。

## 已确认的上游事实

- 后端模块为 `data-agent-management`。
- 前端模块为 `data-agent-frontend-nuxt`。
- 工作流基于 StateGraph，已有意图识别、证据召回、计划生成、SQL 生成和报告生成节点。
- 上游提供 MySQL 商品示例表与数据。
- SQL-only 分析不要求启动 Python 沙盒；需要 Python 分析时才依赖 Docker 沙盒。
- 自动数据库初始化默认关闭，不能把配置解析成功当成数据已导入。
- 当前外部 Access API 尚未完整实现，MVP 优先使用内置运行页面。
- 当前结构校验覆盖单语句和未解析占位符，不等于完整的只读 SQL 安全控制。

## 本地密钥规则

- 不在仓库中写入真实 API Key、数据库密码或 Langfuse Secret。
- 新增环境变量时同步维护 `.env.example`，示例值必须无效。
- 不输出包含密钥的完整环境配置或 Docker Compose 展开结果。

## 路线图入口

- 基线验证记录：[`基线验证记录.md`](基线验证记录.md)
- M1 验证记录：[`M1合成业务数据验证记录.md`](M1合成业务数据验证记录.md)
- M2 验证记录：[`M2语义模型与知识库验证记录.md`](M2语义模型与知识库验证记录.md)
- M3 验证记录：[`M3Agent查询闭环验证记录.md`](M3Agent查询闭环验证记录.md)
- M4 验证记录：[`M4SQL安全权限与审计验证记录.md`](M4SQL安全权限与审计验证记录.md)
- M5 验证记录：[`M5页面与交互验证记录.md`](M5页面与交互验证记录.md)
- M6 验证记录：[`M6自动评测验证记录.md`](M6自动评测验证记录.md)
- M7 验证记录：[`M7部署与作品包装验证记录.md`](M7部署与作品包装验证记录.md)
- 完整开发计划：[`企业经营与财务数据分析Agent开发路线图.md`](企业经营与财务数据分析Agent开发路线图.md)
- 合成数据设计：[`模拟业务数据设计.md`](模拟业务数据设计.md)
- 上游快速开始：[`QUICK_START.md`](QUICK_START.md)
- 上游架构说明：[`ARCHITECTURE.md`](ARCHITECTURE.md)
- 上游开发说明：[`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md)
