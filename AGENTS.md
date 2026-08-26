# AGENTS.md

## 项目定位

本仓库基于 Apache License 2.0 的 Spring AI Alibaba DataAgent 二次开发，目标是完成一个可公开运行、可验证、可用于面试展示的“企业经营与财务数据分析 Agent”。

本项目是个人开源项目，只使用合成业务数据。不得复制、导入或影射任何任职公司的源码、表结构、账号、日志和业务数据，也不得将演示结果描述为真实生产成果。

## 开始工作前必读

按顺序阅读：

1. `docs/CODEX_START_HERE.md`
2. `docs/企业经营与财务数据分析Agent开发路线图.md`
3. `docs/模拟业务数据设计.md`
4. `docs/QUICK_START.md`
5. `docs/ARCHITECTURE.md`
6. `docs/DEVELOPER_GUIDE.md`

## 当前阶段

当前只执行 M0“上游基线验证”。在后端、前端、管理数据库、示例数据源和一次完整问答没有跑通之前，不开始修改 Agent 工作流、业务数据模型或页面。

每完成一个里程碑，都要同步更新 `docs/CODEX_START_HERE.md` 中的状态和验证证据。

## MVP 范围

第一版只实现：

- 合成的经营、财务和 KPI 数据。
- 自然语言查询、指标口径检索、NL2SQL、多轮下钻、表格和报告。
- 数据库只读访问、SQL 安全校验、查询限制、权限范围和审计日志。
- 可重复执行的评测集、Docker 部署和公开演示材料。

第一版不实现：

- 真实企业系统接入或真实财务数据。
- 自动记账、付款、审批等写操作。
- 为了展示概念而增加的多 Agent、A2A 或复杂 Python 分析。
- 与 MVP 无关的整站换肤或上游大规模重构。

## 技术基线

- Java 17
- Spring Boot 3.4.8
- Spring AI 1.1.2
- Spring AI Alibaba 1.1.2.2
- Maven Wrapper
- MySQL 8
- Nuxt 4、Vue 3、TypeScript、Pinia、Vuetify
- Docker Compose

除非路线图中的里程碑明确需要，否则沿用上游版本和现有模块边界，不主动升级依赖。

## 实现原则

- 优先复用现有 StateGraph 节点和管理能力，再做小范围扩展。
- 先运行和验证现有行为，再修改代码。
- 业务数据生成必须可重复，使用固定种子并保留异常注入规则。
- SQL 安全采用纵深防御：只读数据库账号、AST 解析、单语句限制、`SELECT` 白名单、表字段白名单、超时、行数限制和审计。
- 不使用正则表达式作为唯一 SQL 安全边界。
- 金额使用 `DECIMAL` 和 Java `BigDecimal`，禁止使用浮点数表示财务金额。
- 所有模型密钥、数据库密码和外部服务密钥只能通过环境变量或未纳入 Git 的本地配置提供。
- README 和简历必须明确写明“基于 DataAgent 二次开发”和“使用合成数据”。

## 开发流程

1. 阅读相关模块、测试和上游文档。
2. 确认当前里程碑和验收条件。
3. 先补充或调整测试，再进行最小范围实现。
4. 运行与改动范围匹配的后端、前端和数据验证。
5. 检查差异，不提交密钥、生成文件或无关格式化。
6. 更新项目状态、验证证据和必要文档。

## 验证命令

Windows 后端基础验证：

```powershell
.\mvnw.cmd -pl data-agent-management test
.\mvnw.cmd checkstyle:check
```

前端验证：

```powershell
cd data-agent-frontend-nuxt
pnpm test:unit
pnpm build
```

支持 GNU Make 的环境可以执行：

```bash
make format-check
make checkstyle-check
make test
```

测试通过不等于端到端可用。涉及 Agent 工作流时，还必须保存一次真实问答的输入、生成 SQL、查询结果、最终报告和错误日志作为验收证据。

## 完成标准

只有同时满足以下条件，里程碑才能标记完成：

- 约定功能已经实现。
- 自动化测试通过。
- 对应的端到端场景已实际运行。
- 安全边界和失败路径已验证。
- 文档、状态和评测结果已更新。
- 没有把目标值、合成数据或个人推测写成真实生产成果。
