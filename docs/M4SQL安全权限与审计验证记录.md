# M4 SQL 安全、权限与审计验证记录

## 结论

M4 状态为 `completed`。应用安全边界、数据库只读账号、安全攻击集、审计持久化和自动化测试均已完成；重新配置 Chat/Embedding 模型并恢复语义知识后，真实模型正常查询回归通过。预设危险 SQL 由应用校验或数据库只读权限阻断，正常查询未受影响，满足路线图退出条件。

本阶段只处理完全合成的 `enterprise_demo` 数据，不包含任何真实企业源码、账号、日志或业务数据。

## 已实现的安全边界

- 基于 Druid SQL AST 解析，严格限制为一条 `SELECT`，不以正则表达式作为唯一边界。
- 拒绝 DML、DDL、存储过程、多语句、危险函数、`SELECT INTO` 和锁定查询。
- 表白名单来自 Agent 当前绑定的数据表；字段白名单来自 `sql-security.allowed-columns`。
- JDBC 默认最多返回 500 行，查询超时为 15 秒。
- 对邮箱、手机号字段以及符合其值形态的结果执行脱敏，包括带别名的结果列。
- `DEPARTMENT` 角色必须提供部门 ID，并在 AST 中注入 `department_id IN (...)`；拒绝可绕过范围的集合查询。
- 敏感或高成本查询必须已有 Human-in-the-loop 确认状态，否则暂停执行。
- `sql_audit_log` 记录 Agent、线程、问题、SQL、用户、角色、部门范围、耗时、结果数、状态和失败原因。
- MySQL 业务账号 `enterprise_agent_ro` 仅有 `enterprise_demo.*` 的 `SELECT` 权限，形成独立的数据库兜底边界。

## 已执行验证

### SQL 安全单元与节点测试

已覆盖正常 `SELECT`、CTE、DML/DDL/CALL、多语句、危险函数、表字段白名单、锁定查询、人工确认、部门条件注入、缺失范围、集合分支绕过、高成本查询和脱敏。SQL 执行节点还验证了安全校验发生在数据库访问之前，以及默认 500 行和 15 秒超时会传递到底层执行器。

最近一次针对性验证结果：`SqlSecurityServiceTest`、`SqlExecuteNodeTest`、`SqlExecutorTest` 共 `45/45` 通过；`SqlAuditLogMapperIntegrationTest` `1/1` 通过；M4 资产测试 `1/1` 通过。最终完整后端测试结果见下方最终验收，Checkstyle 为 0 个违规。

### 真实 MySQL 只读权限

执行 `demo/enterprise-finance/rebuild.ps1` 后：

- 固定种子数据重新生成并通过 3 个生成器测试。
- MySQL 8.4 中的金额、业务关系和 A01-A06 异常断言全部通过。
- 只读账号查询 20,000 笔订单成功。
- 同一只读账号执行 `DELETE` 被数据库权限拒绝。

这项验证证明数据库权限边界有效，但不单独等价于应用端到端验收。

### 安全攻击资产

`demo/enterprise-finance/m4/security-cases.json` 包含 12 个危险样例和 2 个允许样例。危险样例覆盖：

- DML、DDL、存储过程和多语句。
- 危险函数、锁定查询和越权表字段。
- 部门范围集合分支绕过。
- 敏感或高成本查询的人工确认分流。

## 真实模型正常查询回归

重新配置并激活 Chat/Embedding 模型后：

- 模型就绪检查：Chat 与 Embedding 均为 `true`。
- Agent `5` 的 13 张表 Schema 初始化成功。
- 恢复 63 个字段语义、14 条业务知识和 18 条标准问答。
- 5 组真实向量召回全部通过。
- 执行 `M2-Q01`“2025年全年销售额是多少？”，单题 `passed=true`。
- 工作流完整经过 11 个节点，无流式错误和业务错误。
- 生成并执行的 SQL 是 `sales_order` 上的只读 `SUM(total_amount)` 聚合，返回 1 行。
- 报告结果为 `95,165,908.34`，并包含数据口径与查询依据。

原始证据保存在 `demo/enterprise-finance/m4/normal-query.json`。该文件复用 M3 完整评测器；因为本次只选择 1 道核心题，没有运行多轮和意图分组，所以文件中的整套 `summary.passed` 为 `false`，但 `coreRuns[0].passed` 明确为 `true`。这不是查询失败，不能用整套汇总字段替代单题结论。

## 审计持久化验证

`SqlAuditLogMapperIntegrationTest` 使用真实 H2 表完成插入和回读，确认以下字段持久化成功：Agent、线程、用户、角色、问题、SQL、耗时、结果数、状态和生成时间。结合 `SqlExecuteNodeTest` 对成功、阻断和失败三个分支的审计调用验证，覆盖了从 SQL 执行决策到数据库记录的链路。

## 最终运行环境

- 后端：H2 profile，`http://127.0.0.1:8065`。
- Agent：`5`，名称为“企业经营与财务分析 Agent”。
- 数据源：`4`，名称为 `enterprise_demo_readonly`。
- 数据源连接测试：通过。
- Agent 已选择 13 张业务表。
- Chat 模型：已就绪。
- Embedding 模型：已就绪。

H2 管理库属于重启可重建环境，Agent 和数据源 ID 不是持久接口约定。

## 最终验收

- 功能实现：通过。
- 安全攻击与失败路径：通过。
- MySQL 只读权限：通过。
- 审计表真实插入与回读：通过。
- 真实模型正常查询：通过。
- 文档与证据：已更新。
- 完整后端测试：`1731/1731` 通过，Checkstyle 0 个违规。

## 边界说明

`actorId`、`dataRole` 和 `departmentIds` 目前是演示请求上下文，用于验证 SQL 范围控制；生产系统仍需由可信认证层解析身份和角色，不能让外部调用方自行声明权限。M4 不扩展为生产级组织身份目录，也不声称当前实现已经过真实企业数据或生产流量验证。
