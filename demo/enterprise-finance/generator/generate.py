#!/usr/bin/env python3
"""Generate deterministic synthetic enterprise operating and finance data."""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Sequence


CENT = Decimal("0.01")


@dataclass
class Dataset:
    employees: list[tuple[Any, ...]]
    customers: list[tuple[Any, ...]]
    contracts: list[tuple[Any, ...]]
    orders: list[tuple[Any, ...]]
    order_items: list[tuple[Any, ...]]
    receivables: list[tuple[Any, ...]]
    payments: list[tuple[Any, ...]]
    budgets: list[tuple[Any, ...]]
    expenses: list[tuple[Any, ...]]
    kpi_targets: list[tuple[Any, ...]]
    kpi_values: list[tuple[Any, ...]]
    expectations: list[tuple[Any, ...]]


def money(value: Decimal | str | int) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def cents(value: Decimal | str | int) -> int:
    return int(money(value) * 100)


def from_cents(value: int) -> Decimal:
    return (Decimal(value) / 100).quantize(CENT)


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def quarter_keys(start: date, months: int) -> list[str]:
    keys: list[str] = []
    for offset in range(0, months, 3):
        current = add_months(start, offset)
        key = f"{current.year}Q{((current.month - 1) // 3) + 1}"
        if key not in keys:
            keys.append(key)
    return keys


def allocate_cents(total: int, size: int, rng: random.Random) -> list[int]:
    if size <= 0:
        return []
    weights = [rng.randint(70, 130) for _ in range(size)]
    weight_sum = sum(weights)
    values = [(total * weight) // weight_sum for weight in weights]
    remainder = total - sum(values)
    for index in range(remainder):
        values[index % size] += 1
    return values


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def build_reference_data(config: dict[str, Any], rng: random.Random) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    counts = config["counts"]
    departments = counts["departments"]
    employees: list[tuple[Any, ...]] = []
    for employee_id in range(1, counts["employees"] + 1):
        department_id = ((employee_id - 1) % departments) + 1
        employees.append(
            (
                employee_id,
                department_id,
                f"演示员工{employee_id:03d}",
                f"employee{employee_id:03d}@example.invalid",
            )
        )

    industries = ["SOFTWARE", "MANUFACTURING", "RETAIL", "HEALTHCARE", "LOGISTICS"]
    regions = ["EAST", "SOUTH", "NORTH", "WEST"]
    credit_levels = ["A", "B", "C"]
    customers: list[tuple[Any, ...]] = []
    for customer_id in range(1, counts["customers"] + 1):
        customers.append(
            (
                customer_id,
                f"演示客户{customer_id:04d}",
                industries[(customer_id - 1) % len(industries)],
                regions[(customer_id - 1) % len(regions)],
                credit_levels[(customer_id - 1) % len(credit_levels)],
            )
        )

    start = parse_date(config["period_start"])
    as_of = parse_date(config["as_of_date"])
    contracts: list[tuple[Any, ...]] = []
    for contract_id in range(1, counts["contracts"] + 1):
        customer_id = ((contract_id - 1) % counts["customers"]) + 1
        start_date = start - timedelta(days=30 + rng.randrange(335))
        end_date = as_of + timedelta(days=30 + rng.randrange(335))
        amount = money(rng.randint(80_000, 3_000_000))
        status = "ACTIVE"
        contracts.append(
            (
                contract_id,
                f"DEMO-CTR-{contract_id:06d}",
                customer_id,
                amount,
                start_date,
                end_date,
                status,
            )
        )
    return employees, customers, contracts


def build_orders(config: dict[str, Any], rng: random.Random) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    counts = config["counts"]
    order_count = counts["orders"]
    department_count = counts["departments"]
    month_count = config["months"]
    start = parse_date(config["period_start"])
    approved_count = int(Decimal(order_count) * Decimal(config["rules"]["approved_order_ratio"]))
    non_approved_count = order_count - approved_count
    non_approved_ids = set(rng.sample(range(1, order_count + 1), non_approved_count))

    cell_count = department_count * month_count
    base_orders, extra_orders = divmod(order_count, cell_count)
    skeletons: list[dict[str, Any]] = []
    order_id = 1
    for month_offset in range(month_count):
        month_start = add_months(start, month_offset)
        for department_id in range(1, department_count + 1):
            current_cell = month_offset * department_count + department_id - 1
            orders_in_cell = base_orders + (1 if current_cell < extra_orders else 0)
            for _ in range(orders_in_cell):
                contract_id = ((order_id * 37 - 1) % counts["contracts"]) + 1
                customer_id = ((contract_id - 1) % counts["customers"]) + 1
                salesperson_id = (department_id - 1) * (counts["employees"] // department_count)
                salesperson_id += rng.randrange(counts["employees"] // department_count) + 1
                order_date = month_start + timedelta(days=rng.randrange(28))
                if order_id in non_approved_ids:
                    status = "DRAFT" if order_id % 2 else "CANCELLED"
                else:
                    status = "APPROVED"
                skeletons.append(
                    {
                        "id": order_id,
                        "contract_id": contract_id,
                        "customer_id": customer_id,
                        "department_id": department_id,
                        "salesperson_id": salesperson_id,
                        "order_date": order_date,
                        "status": status,
                    }
                )
                order_id += 1

    by_cell: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for skeleton in skeletons:
        by_cell[(month_key(skeleton["order_date"]), skeleton["department_id"])].append(skeleton)

    a01 = config["anomalies"]["A01"]
    controlled_periods = a01["periods"]
    normal_base = cents(config["rules"]["normal_recent_sales_base"])
    normal_growth = cents(config["rules"]["normal_recent_sales_monthly_growth"])
    department_step = cents(config["rules"]["normal_department_sales_step"])
    controlled_totals: dict[tuple[str, int], int] = {}
    for department_id in range(1, department_count + 1):
        for period_index, period in enumerate(controlled_periods):
            if department_id == a01["department_id"]:
                target = cents(a01["monthly_sales"][period_index])
            else:
                target = normal_base + department_id * department_step + period_index * normal_growth
            controlled_totals[(period, department_id)] = target

    for cell, target in controlled_totals.items():
        approved = [item for item in by_cell[cell] if item["status"] == "APPROVED"]
        allocations = allocate_cents(target, len(approved), rng)
        for skeleton, total in zip(approved, allocations, strict=True):
            skeleton["total_cents"] = total

    for skeleton in skeletons:
        if "total_cents" not in skeleton:
            skeleton["total_cents"] = rng.randint(120_000, 1_800_000)

    orders: list[tuple[Any, ...]] = []
    items: list[tuple[Any, ...]] = []
    item_id = 1
    product_names = ["分析服务", "实施服务", "订阅服务", "培训服务", "运维服务"]
    for skeleton in skeletons:
        current_order_id = skeleton["id"]
        total = skeleton["total_cents"]
        orders.append(
            (
                current_order_id,
                f"DEMO-SO-{current_order_id:07d}",
                skeleton["contract_id"],
                skeleton["customer_id"],
                skeleton["department_id"],
                skeleton["salesperson_id"],
                skeleton["order_date"],
                from_cents(total),
                skeleton["status"],
            )
        )
        item_count = 2 + (current_order_id % 2)
        item_amounts = allocate_cents(total, item_count, rng)
        for item_index, item_amount in enumerate(item_amounts):
            items.append(
                (
                    item_id,
                    current_order_id,
                    product_names[(current_order_id + item_index) % len(product_names)],
                    1,
                    from_cents(item_amount),
                    from_cents(item_amount),
                )
            )
            item_id += 1
    return orders, items


def build_receivables(
    config: dict[str, Any], orders: Sequence[tuple[Any, ...]], rng: random.Random
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]], dict[str, int]]:
    approved_orders = [order for order in orders if order[8] == "APPROVED"]
    missing_count = int(
        (Decimal(len(approved_orders)) * Decimal(config["anomalies"]["A03"]["ratio"])).to_integral_value(
            rounding=ROUND_HALF_UP
        )
    )
    missing_order_ids = set(rng.sample([order[0] for order in approved_orders], missing_count))
    receivable_orders = [order for order in approved_orders if order[0] not in missing_order_ids]

    due_days = config["rules"]["receivable_due_days"]
    as_of = parse_date(config["as_of_date"])
    overdue_cutoff = as_of - timedelta(days=config["rules"]["long_overdue_days"])
    eligible_overdue = [order for order in receivable_orders if order[6] + timedelta(days=due_days) <= overdue_cutoff]
    overdue_count = config["anomalies"]["A04"]["count"]
    overdue_order_ids = set(rng.sample([order[0] for order in eligible_overdue], overdue_count))
    mismatch_count = config["anomalies"]["A06"]["count"]
    mismatch_order_ids = {order[0] for order in receivable_orders[:mismatch_count]}
    mismatch_difference = money(config["anomalies"]["A06"]["difference_amount"])
    split_ratio = Decimal(config["rules"]["payment_split_ratio"])

    receivables: list[tuple[Any, ...]] = []
    payments: list[tuple[Any, ...]] = []
    payment_id = 1
    channels = ["BANK_TRANSFER", "ONLINE", "BILL"]
    for receivable_id, order in enumerate(receivable_orders, start=1):
        order_id = order[0]
        order_date = order[6]
        due_date = order_date + timedelta(days=due_days)
        receivable_amount = order[7]
        if order_id in mismatch_order_ids:
            receivable_amount += mismatch_difference

        payment_amounts: list[Decimal] = []
        if order_id in overdue_order_ids:
            if receivable_id % 2 == 0:
                payment_amounts = [money(receivable_amount * Decimal("0.30"))]
            status = "OVERDUE"
        elif due_date <= overdue_cutoff:
            if receivable_id % 2 == 0:
                first = money(receivable_amount * split_ratio)
                payment_amounts = [first, receivable_amount - first]
            else:
                payment_amounts = [receivable_amount]
            status = "PAID"
        elif due_date <= as_of:
            if receivable_id % 4 == 0:
                payment_amounts = [money(receivable_amount * Decimal("0.50"))]
                status = "PARTIAL"
            else:
                payment_amounts = [receivable_amount]
                status = "PAID"
        else:
            status = "OPEN"

        received_amount = sum(payment_amounts, Decimal("0.00"))
        receivables.append(
            (
                receivable_id,
                f"DEMO-AR-{receivable_id:07d}",
                order_id,
                due_date,
                receivable_amount,
                received_amount,
                status,
            )
        )
        for payment_index, payment_amount in enumerate(payment_amounts):
            payment_date = order_date + timedelta(days=10 + payment_index * 10)
            payments.append(
                (
                    payment_id,
                    f"DEMO-PAY-{payment_id:07d}",
                    receivable_id,
                    payment_date,
                    payment_amount,
                    channels[payment_id % len(channels)],
                )
            )
            payment_id += 1

    return receivables, payments, {"A03": missing_count, "A04": overdue_count, "A06": mismatch_count}


def build_budgets_and_expenses(config: dict[str, Any], rng: random.Random) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    start = parse_date(config["period_start"])
    departments = config["counts"]["departments"]
    categories = config["rules"]["expense_categories"]
    minimum_ratio = Decimal(config["rules"]["normal_expense_min_ratio"])
    maximum_ratio = Decimal(config["rules"]["normal_expense_max_ratio"])
    a02 = config["anomalies"]["A02"]
    budgets: list[tuple[Any, ...]] = []
    expenses: list[tuple[Any, ...]] = []
    budget_id = 1
    expense_id = 1
    for month_offset in range(config["months"]):
        current = add_months(start, month_offset)
        period = month_key(current)
        for department_id in range(1, departments + 1):
            for category_index, category in enumerate(categories):
                budget_amount = money(100_000 + department_id * 5_000 + category_index * 10_000 + month_offset * 1_000)
                if (
                    department_id == a02["department_id"]
                    and period == a02["period"]
                    and category == a02["category"]
                ):
                    ratio = Decimal(a02["execution_ratio"])
                else:
                    ratio_span = maximum_ratio - minimum_ratio
                    ratio = minimum_ratio + ratio_span * Decimal(rng.randrange(1000)) / Decimal(999)
                expense_amount = money(budget_amount * ratio)
                budgets.append((budget_id, department_id, period, category, budget_amount))
                expenses.append(
                    (
                        expense_id,
                        department_id,
                        current + timedelta(days=14),
                        category,
                        expense_amount,
                        "APPROVED",
                    )
                )
                budget_id += 1
                expense_id += 1
    return budgets, expenses


def build_kpis(config: dict[str, Any], rng: random.Random) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    periods = quarter_keys(parse_date(config["period_start"]), config["months"])
    departments = config["counts"]["departments"]
    kpis = config["counts"]["kpis"]
    anomalous_departments = set(config["anomalies"]["A05"]["department_ids"])
    anomalous_periods = set(config["anomalies"]["A05"]["periods"])
    anomaly_ratio = Decimal(config["anomalies"]["A05"]["actual_to_target_ratio"])
    base_targets = [
        Decimal("1000000"),
        Decimal("90"),
        Decimal("200000"),
        Decimal("85"),
        Decimal("500"),
        Decimal("5000"),
        Decimal("200"),
        Decimal("2000000"),
        Decimal("5"),
        Decimal("25"),
    ]
    targets: list[tuple[Any, ...]] = []
    values: list[tuple[Any, ...]] = []
    target_id = 1
    value_id = 1
    for period_index, period in enumerate(periods):
        for department_id in range(1, departments + 1):
            for kpi_id in range(1, kpis + 1):
                target = money(base_targets[kpi_id - 1] * (Decimal("1") + Decimal(department_id) / 100 + Decimal(period_index) / 50))
                if department_id in anomalous_departments and period in anomalous_periods:
                    ratio = anomaly_ratio
                else:
                    ratio = Decimal("1.02") + Decimal(rng.randrange(190)) / Decimal(1000)
                actual = money(target * ratio)
                targets.append((target_id, kpi_id, department_id, period, target))
                values.append((value_id, kpi_id, department_id, period, actual))
                target_id += 1
                value_id += 1
    return targets, values


def validate_dataset(config: dict[str, Any], dataset: Dataset) -> dict[str, int]:
    counts = config["counts"]
    if len(dataset.employees) != counts["employees"]:
        raise ValueError("employee count mismatch")
    if len(dataset.customers) != counts["customers"]:
        raise ValueError("customer count mismatch")
    if len(dataset.contracts) != counts["contracts"]:
        raise ValueError("contract count mismatch")
    if len(dataset.orders) != counts["orders"]:
        raise ValueError("order count mismatch")
    if len(dataset.order_items) != 50_000:
        raise ValueError("order item count mismatch")

    contract_by_id = {contract[0]: contract for contract in dataset.contracts}
    for order in dataset.orders:
        contract = contract_by_id[order[2]]
        if contract[2] != order[3]:
            raise ValueError(f"order customer does not match contract: order_id={order[0]}")
        if not contract[4] <= order[6] <= contract[5]:
            raise ValueError(f"order date is outside contract period: order_id={order[0]}")

    item_totals: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for _, order_id, _, quantity, unit_price, amount in dataset.order_items:
        if amount != money(Decimal(quantity) * unit_price):
            raise ValueError(f"order item amount mismatch: order_id={order_id}")
        item_totals[order_id] += amount
    for order in dataset.orders:
        if item_totals[order[0]] != order[7]:
            raise ValueError(f"order total mismatch: order_id={order[0]}")

    payment_totals: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for _, _, receivable_id, _, amount, _ in dataset.payments:
        payment_totals[receivable_id] += amount
    for receivable in dataset.receivables:
        if payment_totals[receivable[0]] != receivable[5]:
            raise ValueError(f"received amount mismatch: receivable_id={receivable[0]}")
        if receivable[5] > receivable[4]:
            raise ValueError(f"payment exceeds receivable: receivable_id={receivable[0]}")

    expectations = {row[0]: row[1] for row in dataset.expectations}
    order_by_id = {order[0]: order for order in dataset.orders}
    receivable_order_ids = {row[2] for row in dataset.receivables}
    approved_order_ids = {row[0] for row in dataset.orders if row[8] == "APPROVED"}
    anomaly_counts: dict[str, int] = {}
    anomaly_counts["A03"] = len(approved_order_ids - receivable_order_ids)
    anomaly_counts["A04"] = sum(
        1
        for row in dataset.receivables
        if row[3] <= parse_date(config["as_of_date"]) - timedelta(days=config["rules"]["long_overdue_days"])
        and row[5] < row[4]
    )
    anomaly_counts["A06"] = sum(
        1 for row in dataset.receivables if row[4] != order_by_id[row[2]][7]
    )

    a01 = config["anomalies"]["A01"]
    monthly_sales: dict[tuple[int, str], Decimal] = defaultdict(lambda: Decimal("0.00"))
    for order in dataset.orders:
        if order[8] == "APPROVED" and month_key(order[6]) in a01["periods"]:
            monthly_sales[(order[4], month_key(order[6]))] += order[7]
    anomaly_counts["A01"] = sum(
        1
        for department_id in range(1, counts["departments"] + 1)
        if monthly_sales[(department_id, a01["periods"][0])]
        > monthly_sales[(department_id, a01["periods"][1])]
        > monthly_sales[(department_id, a01["periods"][2])]
    )

    a02 = config["anomalies"]["A02"]
    budget_by_key = {(row[1], row[2], row[3]): row[4] for row in dataset.budgets}
    expense_by_key: dict[tuple[int, str, str], Decimal] = defaultdict(lambda: Decimal("0.00"))
    for row in dataset.expenses:
        if row[5] == "APPROVED":
            expense_by_key[(row[1], month_key(row[2]), row[3])] += row[4]
    anomaly_counts["A02"] = sum(
        1
        for key, budget_amount in budget_by_key.items()
        if key[1] == a02["period"] and key[2] == a02["category"] and expense_by_key[key] > budget_amount
    )

    target_by_key = {(row[1], row[2], row[3]): row[4] for row in dataset.kpi_targets}
    value_by_key = {(row[1], row[2], row[3]): row[4] for row in dataset.kpi_values}
    a05_periods = config["anomalies"]["A05"]["periods"]
    anomaly_counts["A05"] = sum(
        1
        for department_id in range(1, counts["departments"] + 1)
        for kpi_id in range(1, counts["kpis"] + 1)
        if all(
            value_by_key[(kpi_id, department_id, period)] < target_by_key[(kpi_id, department_id, period)]
            for period in a05_periods
        )
    )

    for code, actual_count in anomaly_counts.items():
        if actual_count != expectations[code]:
            raise ValueError(f"{code} count mismatch: expected={expectations[code]}, actual={actual_count}")
    return anomaly_counts


def generate_dataset(config: dict[str, Any]) -> Dataset:
    rng = random.Random(config["seed"])
    employees, customers, contracts = build_reference_data(config, rng)
    orders, order_items = build_orders(config, rng)
    receivables, payments, calculated = build_receivables(config, orders, rng)
    budgets, expenses = build_budgets_and_expenses(config, rng)
    kpi_targets, kpi_values = build_kpis(config, rng)
    expected_a05 = len(config["anomalies"]["A05"]["department_ids"]) * config["counts"]["kpis"]
    expectations = [
        ("A01", config["anomalies"]["A01"]["expected_count"], "最近三个月已审核销售额连续下降的部门数"),
        ("A02", config["anomalies"]["A02"]["expected_count"], "指定月份市场费用超过预算的部门数"),
        ("A03", calculated["A03"], "已审核但未生成应收单的订单数"),
        ("A04", calculated["A04"], "超过六十天仍未结清的应收单数"),
        ("A05", expected_a05, "连续两个季度低于目标的部门与KPI组合数"),
        ("A06", calculated["A06"], "应收金额与订单金额不一致的记录数"),
    ]
    dataset = Dataset(
        employees=employees,
        customers=customers,
        contracts=contracts,
        orders=orders,
        order_items=order_items,
        receivables=receivables,
        payments=payments,
        budgets=budgets,
        expenses=expenses,
        kpi_targets=kpi_targets,
        kpi_values=kpi_values,
        expectations=expectations,
    )
    validate_dataset(config, dataset)
    return dataset


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (Decimal, int)):
        return str(value)
    if isinstance(value, date):
        return f"'{value.isoformat()}'"
    text = str(value).replace("\\", "\\\\").replace("'", "''")
    return f"'{text}'"


def write_insert(
    stream: Any, table: str, columns: Sequence[str], rows: Sequence[tuple[Any, ...]], batch_size: int = 500
) -> None:
    column_sql = ", ".join(columns)
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        stream.write(f"INSERT INTO {table} ({column_sql}) VALUES\n")
        for index, row in enumerate(batch):
            suffix = ",\n" if index < len(batch) - 1 else ";\n\n"
            stream.write("    (" + ", ".join(sql_literal(value) for value in row) + ")" + suffix)


def write_sql(output: Path, dataset: Dataset) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("-- Generated synthetic demo data. Do not edit manually.\n")
        stream.write("SET NAMES utf8mb4;\n")
        stream.write("USE enterprise_demo;\n\n")
        write_insert(stream, "employee", ["id", "department_id", "name", "email"], dataset.employees)
        write_insert(stream, "customer", ["id", "name", "industry", "region", "credit_level"], dataset.customers)
        write_insert(
            stream,
            "contract",
            ["id", "contract_no", "customer_id", "contract_amount", "start_date", "end_date", "status"],
            dataset.contracts,
        )
        write_insert(
            stream,
            "sales_order",
            [
                "id",
                "order_no",
                "contract_id",
                "customer_id",
                "department_id",
                "salesperson_id",
                "order_date",
                "total_amount",
                "status",
            ],
            dataset.orders,
        )
        write_insert(
            stream,
            "sales_order_item",
            ["id", "order_id", "product_name", "quantity", "unit_price", "amount"],
            dataset.order_items,
        )
        write_insert(
            stream,
            "receivable",
            [
                "id",
                "receivable_no",
                "order_id",
                "due_date",
                "receivable_amount",
                "received_amount",
                "status",
            ],
            dataset.receivables,
        )
        write_insert(
            stream,
            "payment",
            ["id", "payment_no", "receivable_id", "payment_date", "amount", "channel"],
            dataset.payments,
        )
        write_insert(
            stream,
            "budget",
            ["id", "department_id", "period", "category", "budget_amount"],
            dataset.budgets,
        )
        write_insert(
            stream,
            "expense",
            ["id", "department_id", "expense_date", "category", "amount", "status"],
            dataset.expenses,
        )
        write_insert(
            stream,
            "kpi_target",
            ["id", "kpi_id", "department_id", "period", "target_value"],
            dataset.kpi_targets,
        )
        write_insert(
            stream,
            "kpi_value",
            ["id", "kpi_id", "department_id", "period", "actual_value"],
            dataset.kpi_values,
        )
        write_insert(
            stream,
            "demo_anomaly_expectation",
            ["anomaly_code", "expected_count", "description"],
            dataset.expectations,
        )
    return hashlib.sha256(output.read_bytes()).hexdigest()


def build_manifest(config: dict[str, Any], dataset: Dataset, sql_sha256: str) -> dict[str, Any]:
    anomaly_counts = validate_dataset(config, dataset)
    return {
        "seed": config["seed"],
        "period_start": config["period_start"],
        "months": config["months"],
        "as_of_date": config["as_of_date"],
        "sql_sha256": sql_sha256,
        "row_counts": {
            "employee": len(dataset.employees),
            "customer": len(dataset.customers),
            "contract": len(dataset.contracts),
            "sales_order": len(dataset.orders),
            "sales_order_item": len(dataset.order_items),
            "receivable": len(dataset.receivables),
            "payment": len(dataset.payments),
            "budget": len(dataset.budgets),
            "expense": len(dataset.expenses),
            "kpi_target": len(dataset.kpi_targets),
            "kpi_value": len(dataset.kpi_values),
        },
        "anomaly_counts": anomaly_counts,
    }


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    demo_dir = script_dir.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=demo_dir / "config.json")
    parser.add_argument("--output", type=Path, default=demo_dir / "generated" / "04_generated_data.sql")
    parser.add_argument("--manifest", type=Path, default=demo_dir / "generated" / "manifest.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    dataset = generate_dataset(config)
    sql_sha256 = write_sql(args.output, dataset)
    manifest = build_manifest(config, dataset, sql_sha256)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
