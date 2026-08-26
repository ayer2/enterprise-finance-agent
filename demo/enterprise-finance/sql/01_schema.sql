DROP DATABASE IF EXISTS enterprise_demo;
CREATE DATABASE enterprise_demo CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE enterprise_demo;

CREATE TABLE org_department (
    id BIGINT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    region VARCHAR(32) NOT NULL,
    parent_id BIGINT NULL,
    UNIQUE KEY uk_department_name (name),
    CONSTRAINT fk_department_parent FOREIGN KEY (parent_id) REFERENCES org_department (id)
) COMMENT='Synthetic organization departments';

CREATE TABLE employee (
    id BIGINT PRIMARY KEY,
    department_id BIGINT NOT NULL,
    name VARCHAR(64) NOT NULL,
    email VARCHAR(128) NOT NULL,
    UNIQUE KEY uk_employee_email (email),
    KEY idx_employee_department (department_id),
    CONSTRAINT fk_employee_department FOREIGN KEY (department_id) REFERENCES org_department (id)
) COMMENT='Synthetic employees';

CREATE TABLE customer (
    id BIGINT PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    industry VARCHAR(64) NOT NULL,
    region VARCHAR(32) NOT NULL,
    credit_level VARCHAR(16) NOT NULL,
    UNIQUE KEY uk_customer_name (name),
    KEY idx_customer_region_industry (region, industry)
) COMMENT='Synthetic customers';

CREATE TABLE contract (
    id BIGINT PRIMARY KEY,
    contract_no VARCHAR(32) NOT NULL,
    customer_id BIGINT NOT NULL,
    contract_amount DECIMAL(18, 2) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(16) NOT NULL,
    UNIQUE KEY uk_contract_no (contract_no),
    KEY idx_contract_customer (customer_id),
    KEY idx_contract_period (start_date, end_date),
    CONSTRAINT fk_contract_customer FOREIGN KEY (customer_id) REFERENCES customer (id),
    CONSTRAINT ck_contract_amount CHECK (contract_amount >= 0),
    CONSTRAINT ck_contract_period CHECK (end_date >= start_date)
) COMMENT='Synthetic contracts';

CREATE TABLE sales_order (
    id BIGINT PRIMARY KEY,
    order_no VARCHAR(32) NOT NULL,
    contract_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    department_id BIGINT NOT NULL,
    salesperson_id BIGINT NOT NULL,
    order_date DATE NOT NULL,
    total_amount DECIMAL(18, 2) NOT NULL,
    status VARCHAR(16) NOT NULL,
    UNIQUE KEY uk_sales_order_no (order_no),
    KEY idx_order_date_status (order_date, status),
    KEY idx_order_department_date (department_id, order_date),
    KEY idx_order_customer (customer_id),
    CONSTRAINT fk_order_contract FOREIGN KEY (contract_id) REFERENCES contract (id),
    CONSTRAINT fk_order_customer FOREIGN KEY (customer_id) REFERENCES customer (id),
    CONSTRAINT fk_order_department FOREIGN KEY (department_id) REFERENCES org_department (id),
    CONSTRAINT fk_order_salesperson FOREIGN KEY (salesperson_id) REFERENCES employee (id),
    CONSTRAINT ck_order_amount CHECK (total_amount >= 0)
) COMMENT='Synthetic sales orders';

CREATE TABLE sales_order_item (
    id BIGINT PRIMARY KEY,
    order_id BIGINT NOT NULL,
    product_name VARCHAR(128) NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(18, 2) NOT NULL,
    amount DECIMAL(18, 2) NOT NULL,
    KEY idx_order_item_order (order_id),
    CONSTRAINT fk_order_item_order FOREIGN KEY (order_id) REFERENCES sales_order (id),
    CONSTRAINT ck_order_item_quantity CHECK (quantity > 0),
    CONSTRAINT ck_order_item_amount CHECK (amount = quantity * unit_price)
) COMMENT='Synthetic sales order items';

CREATE TABLE receivable (
    id BIGINT PRIMARY KEY,
    receivable_no VARCHAR(32) NOT NULL,
    order_id BIGINT NOT NULL,
    due_date DATE NOT NULL,
    receivable_amount DECIMAL(18, 2) NOT NULL,
    received_amount DECIMAL(18, 2) NOT NULL,
    status VARCHAR(16) NOT NULL,
    UNIQUE KEY uk_receivable_no (receivable_no),
    UNIQUE KEY uk_receivable_order (order_id),
    KEY idx_receivable_due_status (due_date, status),
    CONSTRAINT fk_receivable_order FOREIGN KEY (order_id) REFERENCES sales_order (id),
    CONSTRAINT ck_receivable_amount CHECK (receivable_amount >= 0),
    CONSTRAINT ck_received_amount CHECK (received_amount >= 0 AND received_amount <= receivable_amount)
) COMMENT='Synthetic accounts receivable';

CREATE TABLE payment (
    id BIGINT PRIMARY KEY,
    payment_no VARCHAR(32) NOT NULL,
    receivable_id BIGINT NOT NULL,
    payment_date DATE NOT NULL,
    amount DECIMAL(18, 2) NOT NULL,
    channel VARCHAR(32) NOT NULL,
    UNIQUE KEY uk_payment_no (payment_no),
    KEY idx_payment_receivable (receivable_id),
    KEY idx_payment_date (payment_date),
    CONSTRAINT fk_payment_receivable FOREIGN KEY (receivable_id) REFERENCES receivable (id),
    CONSTRAINT ck_payment_amount CHECK (amount > 0)
) COMMENT='Synthetic receipt records';

CREATE TABLE budget (
    id BIGINT PRIMARY KEY,
    department_id BIGINT NOT NULL,
    period CHAR(7) NOT NULL,
    category VARCHAR(32) NOT NULL,
    budget_amount DECIMAL(18, 2) NOT NULL,
    UNIQUE KEY uk_budget_department_period_category (department_id, period, category),
    KEY idx_budget_period (period),
    CONSTRAINT fk_budget_department FOREIGN KEY (department_id) REFERENCES org_department (id),
    CONSTRAINT ck_budget_amount CHECK (budget_amount > 0)
) COMMENT='Synthetic monthly budgets';

CREATE TABLE expense (
    id BIGINT PRIMARY KEY,
    department_id BIGINT NOT NULL,
    expense_date DATE NOT NULL,
    category VARCHAR(32) NOT NULL,
    amount DECIMAL(18, 2) NOT NULL,
    status VARCHAR(16) NOT NULL,
    KEY idx_expense_department_date (department_id, expense_date),
    KEY idx_expense_category_status (category, status),
    CONSTRAINT fk_expense_department FOREIGN KEY (department_id) REFERENCES org_department (id),
    CONSTRAINT ck_expense_amount CHECK (amount >= 0)
) COMMENT='Synthetic expenses';

CREATE TABLE kpi_definition (
    id BIGINT PRIMARY KEY,
    code VARCHAR(64) NOT NULL,
    name VARCHAR(128) NOT NULL,
    formula_description VARCHAR(512) NOT NULL,
    unit VARCHAR(32) NOT NULL,
    UNIQUE KEY uk_kpi_code (code)
) COMMENT='Synthetic KPI definitions';

CREATE TABLE kpi_target (
    id BIGINT PRIMARY KEY,
    kpi_id BIGINT NOT NULL,
    department_id BIGINT NOT NULL,
    period CHAR(6) NOT NULL,
    target_value DECIMAL(18, 2) NOT NULL,
    UNIQUE KEY uk_kpi_target (kpi_id, department_id, period),
    KEY idx_kpi_target_period (period),
    CONSTRAINT fk_kpi_target_definition FOREIGN KEY (kpi_id) REFERENCES kpi_definition (id),
    CONSTRAINT fk_kpi_target_department FOREIGN KEY (department_id) REFERENCES org_department (id)
) COMMENT='Synthetic KPI targets';

CREATE TABLE kpi_value (
    id BIGINT PRIMARY KEY,
    kpi_id BIGINT NOT NULL,
    department_id BIGINT NOT NULL,
    period CHAR(6) NOT NULL,
    actual_value DECIMAL(18, 2) NOT NULL,
    UNIQUE KEY uk_kpi_value (kpi_id, department_id, period),
    KEY idx_kpi_value_period (period),
    CONSTRAINT fk_kpi_value_definition FOREIGN KEY (kpi_id) REFERENCES kpi_definition (id),
    CONSTRAINT fk_kpi_value_department FOREIGN KEY (department_id) REFERENCES org_department (id)
) COMMENT='Synthetic KPI actual values';

CREATE TABLE demo_anomaly_expectation (
    anomaly_code CHAR(3) PRIMARY KEY,
    expected_count INT NOT NULL,
    description VARCHAR(256) NOT NULL
) COMMENT='Expected counts for deterministic synthetic anomalies';
