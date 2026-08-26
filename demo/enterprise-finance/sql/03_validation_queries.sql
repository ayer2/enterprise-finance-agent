USE enterprise_demo;

CREATE OR REPLACE VIEW anomaly_a01_sales_decline AS
WITH monthly_sales AS (
    SELECT
        department_id,
        SUM(CASE WHEN order_date >= '2025-10-01' AND order_date < '2025-11-01' THEN total_amount ELSE 0 END) AS sales_2025_10,
        SUM(CASE WHEN order_date >= '2025-11-01' AND order_date < '2025-12-01' THEN total_amount ELSE 0 END) AS sales_2025_11,
        SUM(CASE WHEN order_date >= '2025-12-01' AND order_date < '2026-01-01' THEN total_amount ELSE 0 END) AS sales_2025_12
    FROM sales_order
    WHERE status = 'APPROVED'
      AND order_date >= '2025-10-01'
      AND order_date < '2026-01-01'
    GROUP BY department_id
)
SELECT d.id AS department_id, d.name AS department_name,
       m.sales_2025_10, m.sales_2025_11, m.sales_2025_12
FROM monthly_sales m
JOIN org_department d ON d.id = m.department_id
WHERE m.sales_2025_10 > m.sales_2025_11
  AND m.sales_2025_11 > m.sales_2025_12;

CREATE OR REPLACE VIEW anomaly_a02_budget_overrun AS
SELECT b.department_id, d.name AS department_name, b.period, b.category,
       b.budget_amount, SUM(e.amount) AS approved_expense_amount,
       ROUND(SUM(e.amount) / b.budget_amount, 4) AS execution_ratio
FROM budget b
JOIN org_department d ON d.id = b.department_id
JOIN expense e
  ON e.department_id = b.department_id
 AND DATE_FORMAT(e.expense_date, '%Y-%m') = b.period
 AND e.category = b.category
 AND e.status = 'APPROVED'
WHERE b.period = '2025-12'
  AND b.category = 'MARKETING'
GROUP BY b.department_id, d.name, b.period, b.category, b.budget_amount
HAVING SUM(e.amount) > b.budget_amount;

CREATE OR REPLACE VIEW anomaly_a03_missing_receivable AS
SELECT o.id AS order_id, o.order_no, o.customer_id, o.department_id,
       o.order_date, o.total_amount
FROM sales_order o
LEFT JOIN receivable r ON r.order_id = o.id
WHERE o.status = 'APPROVED'
  AND r.id IS NULL;

CREATE OR REPLACE VIEW anomaly_a04_long_overdue AS
SELECT r.id AS receivable_id, r.receivable_no, r.order_id, o.customer_id,
       r.due_date, r.receivable_amount, r.received_amount,
       r.receivable_amount - r.received_amount AS outstanding_amount,
       DATEDIFF('2025-12-31', r.due_date) AS overdue_days
FROM receivable r
JOIN sales_order o ON o.id = r.order_id
WHERE DATEDIFF('2025-12-31', r.due_date) >= 60
  AND r.received_amount < r.receivable_amount;

CREATE OR REPLACE VIEW anomaly_a05_kpi_under_target AS
SELECT t.department_id, d.name AS department_name, t.kpi_id, k.code AS kpi_code,
       COUNT(*) AS consecutive_periods,
       MIN(v.actual_value / NULLIF(t.target_value, 0)) AS minimum_completion_ratio
FROM kpi_target t
JOIN kpi_value v
  ON v.kpi_id = t.kpi_id
 AND v.department_id = t.department_id
 AND v.period = t.period
JOIN org_department d ON d.id = t.department_id
JOIN kpi_definition k ON k.id = t.kpi_id
WHERE t.period IN ('2025Q3', '2025Q4')
GROUP BY t.department_id, d.name, t.kpi_id, k.code
HAVING COUNT(*) = 2
   AND SUM(CASE WHEN v.actual_value < t.target_value THEN 1 ELSE 0 END) = 2;

CREATE OR REPLACE VIEW anomaly_a06_amount_mismatch AS
SELECT o.id AS order_id, o.order_no, o.total_amount AS order_amount,
       r.id AS receivable_id, r.receivable_amount,
       r.receivable_amount - o.total_amount AS difference_amount
FROM sales_order o
JOIN receivable r ON r.order_id = o.id
WHERE r.receivable_amount <> o.total_amount;

DROP PROCEDURE IF EXISTS validate_enterprise_demo;
DELIMITER $$
CREATE PROCEDURE validate_enterprise_demo()
BEGIN
    DECLARE v_actual INT DEFAULT 0;
    DECLARE v_expected INT DEFAULT 0;
    DECLARE v_message VARCHAR(255);

    SELECT COUNT(*) INTO v_actual FROM sales_order;
    IF v_actual <> 20000 THEN
        SET v_message = CONCAT('sales_order count mismatch: ', v_actual);
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    SELECT COUNT(*) INTO v_actual FROM sales_order_item;
    IF v_actual <> 50000 THEN
        SET v_message = CONCAT('sales_order_item count mismatch: ', v_actual);
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    SELECT COUNT(*) INTO v_actual
    FROM org_department
    WHERE id = 1
      AND HEX(name) = 'E58D8EE4B89CE4B880E983A8';
    IF v_actual <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'org_department UTF-8 encoding mismatch';
    END IF;

    SELECT COUNT(*) INTO v_actual
    FROM sales_order o
    JOIN contract c ON c.id = o.contract_id
    WHERE o.customer_id <> c.customer_id
       OR o.order_date < c.start_date
       OR o.order_date > c.end_date;
    IF v_actual <> 0 THEN
        SET v_message = CONCAT('order/contract relationship mismatch count: ', v_actual);
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    SELECT COUNT(*) INTO v_actual
    FROM (
        SELECT o.id
        FROM sales_order o
        JOIN sales_order_item i ON i.order_id = o.id
        GROUP BY o.id, o.total_amount
        HAVING o.total_amount <> SUM(i.amount)
    ) mismatched_orders;
    IF v_actual <> 0 THEN
        SET v_message = CONCAT('order total mismatch count: ', v_actual);
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    SELECT COUNT(*) INTO v_actual
    FROM (
        SELECT r.id
        FROM receivable r
        LEFT JOIN payment p ON p.receivable_id = r.id
        GROUP BY r.id, r.receivable_amount, r.received_amount
        HAVING r.received_amount <> COALESCE(SUM(p.amount), 0)
           OR COALESCE(SUM(p.amount), 0) > r.receivable_amount
    ) invalid_receivables;
    IF v_actual <> 0 THEN
        SET v_message = CONCAT('invalid receivable/payment count: ', v_actual);
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    SELECT COUNT(*) INTO v_actual FROM anomaly_a01_sales_decline;
    SELECT expected_count INTO v_expected FROM demo_anomaly_expectation WHERE anomaly_code = 'A01';
    IF v_actual <> v_expected THEN
        SET v_message = CONCAT('A01 mismatch: expected=', v_expected, ', actual=', v_actual);
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    SELECT COUNT(*) INTO v_actual FROM anomaly_a02_budget_overrun;
    SELECT expected_count INTO v_expected FROM demo_anomaly_expectation WHERE anomaly_code = 'A02';
    IF v_actual <> v_expected THEN
        SET v_message = CONCAT('A02 mismatch: expected=', v_expected, ', actual=', v_actual);
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    SELECT COUNT(*) INTO v_actual FROM anomaly_a03_missing_receivable;
    SELECT expected_count INTO v_expected FROM demo_anomaly_expectation WHERE anomaly_code = 'A03';
    IF v_actual <> v_expected THEN
        SET v_message = CONCAT('A03 mismatch: expected=', v_expected, ', actual=', v_actual);
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    SELECT COUNT(*) INTO v_actual FROM anomaly_a04_long_overdue;
    SELECT expected_count INTO v_expected FROM demo_anomaly_expectation WHERE anomaly_code = 'A04';
    IF v_actual <> v_expected THEN
        SET v_message = CONCAT('A04 mismatch: expected=', v_expected, ', actual=', v_actual);
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    SELECT COUNT(*) INTO v_actual FROM anomaly_a05_kpi_under_target;
    SELECT expected_count INTO v_expected FROM demo_anomaly_expectation WHERE anomaly_code = 'A05';
    IF v_actual <> v_expected THEN
        SET v_message = CONCAT('A05 mismatch: expected=', v_expected, ', actual=', v_actual);
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    SELECT COUNT(*) INTO v_actual FROM anomaly_a06_amount_mismatch;
    SELECT expected_count INTO v_expected FROM demo_anomaly_expectation WHERE anomaly_code = 'A06';
    IF v_actual <> v_expected THEN
        SET v_message = CONCAT('A06 mismatch: expected=', v_expected, ', actual=', v_actual);
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_message;
    END IF;

    SELECT 'M1_VALIDATION_PASSED' AS validation_status,
           (SELECT COUNT(*) FROM sales_order) AS order_count,
           (SELECT COUNT(*) FROM sales_order_item) AS order_item_count,
           (SELECT COUNT(*) FROM receivable) AS receivable_count,
           (SELECT COUNT(*) FROM payment) AS payment_count;

    SELECT e.anomaly_code, e.expected_count,
           CASE e.anomaly_code
               WHEN 'A01' THEN (SELECT COUNT(*) FROM anomaly_a01_sales_decline)
               WHEN 'A02' THEN (SELECT COUNT(*) FROM anomaly_a02_budget_overrun)
               WHEN 'A03' THEN (SELECT COUNT(*) FROM anomaly_a03_missing_receivable)
               WHEN 'A04' THEN (SELECT COUNT(*) FROM anomaly_a04_long_overdue)
               WHEN 'A05' THEN (SELECT COUNT(*) FROM anomaly_a05_kpi_under_target)
               WHEN 'A06' THEN (SELECT COUNT(*) FROM anomaly_a06_amount_mismatch)
           END AS actual_count,
           e.description
    FROM demo_anomaly_expectation e
    ORDER BY e.anomaly_code;
END$$
DELIMITER ;

CALL validate_enterprise_demo();
