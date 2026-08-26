# Enterprise Finance Synthetic Dataset

本目录提供完全合成、可公开、可重复生成的企业经营与财务演示数据。所有部门、员工、客户、合同、编号、金额和业务关系均由固定种子生成，与任何真实公司或个人无关。

## 数据范围

- 固定种子：`20260824`
- 固定统计日期：`2025-12-31`
- 数据期间：`2024-01-01` 至 `2025-12-31`，共 24 个月
- 8 个部门、80 名员工、500 个客户、800 份合同
- 20,000 笔订单、50,000 条订单明细
- 18,050 条应收、约 25,000 条回款
- 8 个部门 × 24 个月 × 4 类预算和费用
- 10 个 KPI、8 个季度的目标与实际值

金额统一使用 MySQL `DECIMAL(18, 2)`。订单、应收、回款、预算和 KPI 均建立主外键、唯一约束及查询索引。

## 预设异常

| 编号 | 场景 | 稳定结果 |
|---|---|---:|
| A01 | 华东一部最近 3 个月销售额连续下降 | 1 个部门 |
| A02 | 指定部门 2025-12 市场费用达到预算的 125% | 1 个部门 |
| A03 | 5% 已审核订单未生成应收 | 950 笔 |
| A04 | 到期 60 天后仍未结清 | 120 笔 |
| A05 | 两个部门的 10 个 KPI 连续两个季度未达标 | 20 个部门-KPI 组合 |
| A06 | 应收金额与订单金额不一致 | 50 笔 |

异常规则集中维护在 [`config.json`](config.json)，生成器不会从当前时间或外部数据取值。

## 一条命令重建

Windows PowerShell：

```powershell
.\demo\enterprise-finance\rebuild.ps1
```

Linux/macOS：

```bash
bash demo/enterprise-finance/rebuild.sh
```

命令会依次：

1. 生成 `generated/04_generated_data.sql` 和 `manifest.json`。
2. 运行确定性、唯一性和业务关系测试。
3. 仅重建本目录 Compose 创建的 MySQL 数据卷。
4. 导入 Schema、参考数据和生成数据。
5. 在真实 MySQL 8.4 中运行金额闭合、回款上限、合同有效期及 A01-A06 SQL 断言。
6. 创建业务只读账号，验证 `SELECT` 成功且 `DELETE` 被数据库权限拒绝。

只生成并验证文件、不启动 Docker：

```powershell
.\demo\enterprise-finance\rebuild.ps1 -SkipDocker
```

`generated/` 已加入忽略规则，不提交大体量 SQL。相同种子重复生成必须得到相同 SHA-256。

## 本地连接

- Host：`127.0.0.1`
- Port：`3307`
- Database：`enterprise_demo`
- User：`enterprise_agent_ro`（Agent 运行时使用，仅授予 `enterprise_demo.*` 的 `SELECT`）

数据库密码不写入仓库。若未设置环境变量，重建脚本会为本次验证生成临时随机密码。需要在重建后手动连接时，请先在当前终端设置：

```powershell
$env:ENTERPRISE_DEMO_ROOT_PASSWORD = '<your-local-password>'
$env:ENTERPRISE_DEMO_READONLY_PASSWORD = '<your-local-readonly-password>'
.\demo\enterprise-finance\rebuild.ps1
```

`root` 仅用于重建和验证演示数据，不应配置为 Agent 的业务数据源账号。

## SQL 验证入口

[`sql/03_validation_queries.sql`](sql/03_validation_queries.sql) 会创建以下可查询视图并执行断言：

- `anomaly_a01_sales_decline`
- `anomaly_a02_budget_overrun`
- `anomaly_a03_missing_receivable`
- `anomaly_a04_long_overdue`
- `anomaly_a05_kpi_under_target`
- `anomaly_a06_amount_mismatch`

示例：

```sql
SELECT * FROM anomaly_a01_sales_decline;
SELECT * FROM anomaly_a04_long_overdue ORDER BY overdue_days DESC;
```

## M2 语义模型与知识库

[`knowledge/`](knowledge/) 提供可版本管理、可重复导入的业务语义资产：

- `指标口径.md`：销售额、回款率、预算执行率、逾期应收和 KPI 完成率的公式、时间/组织口径、排除条件和标准 SQL。
- `数据库设计.md`：13 张业务表的粒度、关系和防重复汇总规则。
- `semantic-models.json`：63 个关键字段的业务名称、同义词和字段说明。
- `business-knowledge.json`：14 条指标及时间、组织、客户口径知识。
- `标准问答.json`：18 组不要求用户说出物理表名的自然语言问题与已验证 SQL。

先在管理页面创建或选择一个 Agent，绑定本目录的 `enterprise_demo` 数据源并初始化 13 张业务表，然后执行：

```powershell
python .\demo\enterprise-finance\knowledge\import_knowledge.py --agent-id <agent-id>
python .\demo\enterprise-finance\knowledge\verify_recall.py --agent-id <agent-id>
```

导入程序按字段、业务术语和标准问题做更新或新增，可安全重复执行。它会等待业务知识和标准问答的向量化状态全部变为 `COMPLETED`；召回验证使用 5 个不含物理字段名的业务词和同义词，失败时返回非零退出码。

无需后端服务即可先做资产一致性检查：

```powershell
python -m unittest discover -s .\demo\enterprise-finance\knowledge -p "test_*.py" -v
```

## M3 Agent 查询闭环验收

[`m3/`](m3/) 提供 20 道核心问题、3 道多轮下钻、4 道意图问题，以及保留节点、SQL、结果集、报告、图表和重试信息的真实流式评测程序。

```powershell
python .\demo\enterprise-finance\m3\evaluate.py --agent-id <agent-id> --workers 2
python -m unittest discover -s .\demo\enterprise-finance\m3 -p "test_*.py" -v
```

每个核心查询只有同时完成工作流、生成并执行 SQL、返回结果集、生成报告且报告包含 `## 数据口径与查询依据` 时才通过。ECharts 是整套能力要求，不强制每道单值查询绘图。评测中途发生外部额度错误时，可用 `--ids` 只重跑失败项，并通过 `--merge-base` 合并；合并逻辑会保留每道题最完整的真实轨迹，避免早期失败覆盖既有成功证据。

2026-08-24 最终证据为 [`m3/evidence/final-accepted.json`](m3/evidence/final-accepted.json)：核心问题 `20/20`、多轮下钻 `3/3`、意图识别 `4/4`、图表运行 10 次、HTML 导出通过，`summary.passed=true`。

## M4 SQL 安全测试集

[`m4/security-cases.json`](m4/security-cases.json) 保存了 12 个危险查询样例和 2 个正常查询样例，覆盖 DML、DDL、存储过程、危险函数、多语句、越权表字段、锁定查询、集合分支绕过和高成本查询。应用层以 SQL AST、白名单、数据范围、脱敏和审计形成第一道边界，MySQL 只读账号形成独立的数据库权限边界。

```powershell
python -m unittest discover -s .\demo\enterprise-finance\m4 -p "test_*.py" -v
```

M4 的实施边界和验收状态见 [`../../docs/M4SQL安全权限与审计验证记录.md`](../../docs/M4SQL安全权限与审计验证记录.md)。

## M6 自动评测

[`m6/cases.json`](m6/cases.json) 固定了 8 道单表、10 道多表、8 道指标口径、6 道趋势异常和 4 道多轮追问题。评测程序在同一固定种子数据库实时执行标准 SQL，以结果而非 SQL 字符串作为正确性标准，并合并 M4 的 12 条安全攻击结果。

先验证标准答案和离线判定逻辑：

```powershell
python .\demo\enterprise-finance\m6\evaluate.py --agent-id <agent-id> --references-only `
  --output .\demo\enterprise-finance\m6\evidence\reference-results.json
python -m unittest discover -s .\demo\enterprise-finance\m6 -p "test_*.py" -v
```

完整真实模型评测：

```powershell
python .\demo\enterprise-finance\m6\evaluate.py --agent-id <agent-id> --workers 2
```

输出同时包含机器可读 JSON 和 Markdown 报告，记录 SQL 可执行率、查询结果正确率、指标口径正确率、危险请求拦截率、逐题耗时和独立的失败类型。`--ids` 仅用于小范围诊断，其结果不能替代完整验收。

2026-08-26 最终真实模型评测已通过：SQL 可执行率 `94.44%`、查询结果正确率 `94.44%`、指标口径正确率 `87.50%`、危险请求拦截率 `100%`。机器可读证据见 [`m6/evidence/final-accepted.json`](m6/evidence/final-accepted.json)，可读报告见 [`m6/evidence/final-accepted.md`](m6/evidence/final-accepted.md)。两道未通过题均被当前字段白名单阻断，具体边界记录在 [`../../docs/M6自动评测验证记录.md`](../../docs/M6自动评测验证记录.md)。

停止容器但保留数据：

```powershell
docker compose -f .\demo\enterprise-finance\docker-compose.yml down
```

删除并重建数据卷属于有意的演示数据重置，由 `rebuild.ps1`/`rebuild.sh` 限定在本目录 Compose 项目中执行。
