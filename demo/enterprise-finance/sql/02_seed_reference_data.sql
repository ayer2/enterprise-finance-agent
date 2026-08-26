SET NAMES utf8mb4;
USE enterprise_demo;

INSERT INTO org_department (id, name, region, parent_id) VALUES
    (1, '华东一部', 'EAST', NULL),
    (2, '华东二部', 'EAST', NULL),
    (3, '华南一部', 'SOUTH', NULL),
    (4, '华南二部', 'SOUTH', NULL),
    (5, '华北一部', 'NORTH', NULL),
    (6, '华北二部', 'NORTH', NULL),
    (7, '西部一部', 'WEST', NULL),
    (8, '西部二部', 'WEST', NULL);

INSERT INTO kpi_definition (id, code, name, formula_description, unit) VALUES
    (1, 'SALES_REVENUE', '销售额', '已审核订单 total_amount 合计', 'CNY'),
    (2, 'COLLECTION_RATE', '回款率', '回款金额 / 应收金额', 'PERCENT'),
    (3, 'RECEIVABLE_BALANCE', '应收余额', '应收金额 - 已回款金额', 'CNY'),
    (4, 'BUDGET_EXECUTION', '预算执行率', '已审核费用 / 预算金额', 'PERCENT'),
    (5, 'ORDER_COUNT', '订单数', '已审核订单数量', 'COUNT'),
    (6, 'AVG_ORDER_VALUE', '客单价', '已审核订单金额 / 已审核订单数量', 'CNY'),
    (7, 'CUSTOMER_COUNT', '成交客户数', '已审核订单去重客户数', 'COUNT'),
    (8, 'CONTRACT_AMOUNT', '合同金额', '有效合同金额合计', 'CNY'),
    (9, 'OVERDUE_RATE', '逾期率', '逾期应收余额 / 应收金额', 'PERCENT'),
    (10, 'PROFIT_MARGIN', '利润率', '模拟利润 / 销售额', 'PERCENT');
