"""Populate OpsVision with a coherent, multi-year synthetic dataset.

Every entity is fictional (generated with Faker). Relationships are built
in dependency order (locations -> departments -> employees -> ... ->
audit logs) so foreign keys always point at rows that already exist, and
downstream activity (stock movements, invoices) is derived from upstream
activity (sales/purchase orders) rather than generated independently —
that's what makes the dashboards show a company that hangs together
instead of disconnected random tables.

Usage:
    python scripts/generate_synthetic_data.py [--reset] [--seed 42]
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from faker import Faker

from app.database.base import Base, SessionLocal, engine
from app.database.models.administration import AuditLog, Role, User
from app.database.models.core import Location, LocationType
from app.database.models.finance import (
    Account,
    AccountType,
    Invoice,
    InvoiceDirection,
    InvoiceStatus,
    Transaction,
    TransactionType,
)
from app.database.models.inventory import MovementType, Product, ProductCategory, StockMovement, Warehouse
from app.database.models.maintenance import (
    Asset,
    AssetCategory,
    AssetCriticality,
    MaintenanceLog,
    MaintenancePriority,
    MaintenanceRequest,
    MaintenanceRequestType,
    MaintenanceStatus,
)
from app.database.models.people import (
    Department,
    Employee,
    EmploymentStatus,
    TimeOffRequest,
    TimeOffStatus,
    TimeOffType,
)
from app.database.models.production import (
    ProductionEvent,
    ProductionEventType,
    ProductionLine,
    WorkOrder,
    WorkOrderStatus,
)
from app.database.models.projects import Milestone, Project, ProjectStatus, Task, TaskStatus
from app.database.models.purchasing import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    Supplier,
    SupplierCategory,
)
from app.database.models.quality import (
    Inspection,
    InspectionResult,
    NonConformance,
    NonConformanceSeverity,
    NonConformanceStatus,
    QualityMetric,
)
from app.database.models.sales import Customer, CustomerSegment, OrderStatus, SalesOrder, SalesOrderItem

DATASET_START = date(2023, 1, 1)
DATASET_END = date.today()
HIRE_WINDOW_START = date(2018, 1, 1)


def random_date(start: date = DATASET_START, end: date = DATASET_END) -> date:
    span = (end - start).days
    return start + timedelta(days=random.randint(0, max(span, 0)))


def random_datetime(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time()) + timedelta(
        hours=random.randint(6, 20), minutes=random.randint(0, 59)
    )


def weighted_choice(options: dict) -> object:
    return random.choices(list(options.keys()), weights=list(options.values()), k=1)[0]


def months_between(start: date, end: date) -> list[date]:
    months, cursor = [], date(start.year, start.month, 1)
    while cursor <= end:
        months.append(cursor)
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    return months


def generate_locations(session, fake: Faker) -> list[Location]:
    blueprint = [
        ("PLT1", LocationType.PLANT), ("PLT2", LocationType.PLANT), ("PLT3", LocationType.PLANT),
        ("WH1", LocationType.WAREHOUSE), ("WH2", LocationType.WAREHOUSE),
        ("HQ1", LocationType.OFFICE), ("OFF2", LocationType.OFFICE), ("OFF3", LocationType.OFFICE),
    ]
    locations = [
        Location(
            code=code, name=f"{fake.city()} {loc_type.value.title()}", city=fake.city(),
            state=fake.state(), country="Brazil", location_type=loc_type,
        )
        for code, loc_type in blueprint
    ]
    session.add_all(locations)
    session.flush()
    return locations


def generate_departments(session) -> list[Department]:
    names = [
        ("SALES", "Sales", "CC-100"), ("MFG", "Manufacturing", "CC-200"),
        ("LOG", "Logistics", "CC-210"), ("PROC", "Procurement", "CC-300"),
        ("FIN", "Finance", "CC-400"), ("HR", "Human Resources", "CC-500"),
        ("PMO", "Program Management", "CC-600"), ("FAC", "Facilities & Maintenance", "CC-700"),
        ("QA", "Quality Assurance", "CC-800"), ("IT", "IT & Administration", "CC-900"),
    ]
    departments = [Department(code=c, name=n, cost_center=cc) for c, n, cc in names]
    session.add_all(departments)
    session.flush()
    return departments


def generate_employees(session, fake: Faker, departments, locations, count: int = 260) -> list[Employee]:
    status_weights = {EmploymentStatus.ACTIVE: 0.90, EmploymentStatus.ON_LEAVE: 0.05, EmploymentStatus.TERMINATED: 0.05}
    employees = [
        Employee(
            employee_code=f"EMP-{i:05d}",
            full_name=fake.name(),
            department_id=random.choice(departments).id,
            location_id=random.choice(locations).id,
            job_title=fake.job(),
            hire_date=random_date(HIRE_WINDOW_START, DATASET_END),
            employment_status=weighted_choice(status_weights),
            base_salary=round(random.uniform(3200, 24000), 2),
        )
        for i in range(1, count + 1)
    ]
    session.add_all(employees)
    session.flush()
    return employees


def generate_warehouses(session, locations, count: int = 5) -> list[Warehouse]:
    candidates = [loc for loc in locations if loc.location_type in (LocationType.WAREHOUSE, LocationType.PLANT)]
    warehouses = [
        Warehouse(code=f"WH-{i:02d}", name=f"Warehouse {i}", location_id=random.choice(candidates).id, capacity_units=random.randint(5000, 50000))
        for i in range(1, count + 1)
    ]
    session.add_all(warehouses)
    session.flush()
    return warehouses


def generate_products(session, fake: Faker, count: int = 130) -> list[Product]:
    products = []
    for i in range(1, count + 1):
        category = weighted_choice(
            {ProductCategory.RAW_MATERIAL: 0.25, ProductCategory.COMPONENT: 0.3, ProductCategory.FINISHED_GOOD: 0.35, ProductCategory.PACKAGING: 0.1}
        )
        unit_cost = round(random.uniform(4, 480), 2)
        products.append(
            Product(
                sku=f"SKU-{i:05d}",
                name=f"{fake.word().title()} {fake.word().title()}",
                category=category,
                unit_cost=unit_cost,
                unit_price=round(unit_cost * random.uniform(1.3, 2.6), 2),
                reorder_point=random.randint(20, 220),
                active=random.random() > 0.05,
            )
        )
    session.add_all(products)
    session.flush()
    return products


def generate_production_lines(session, locations, count: int = 12) -> list[ProductionLine]:
    plants = [loc for loc in locations if loc.location_type == LocationType.PLANT]
    lines = [
        ProductionLine(code=f"LINE-{i:02d}", name=f"Line {i}", location_id=random.choice(plants).id, capacity_units_per_hour=round(random.uniform(50, 520), 2))
        for i in range(1, count + 1)
    ]
    session.add_all(lines)
    session.flush()
    return lines


def generate_customers(session, fake: Faker, count: int = 240) -> list[Customer]:
    segment_weights = {CustomerSegment.RETAIL: 0.5, CustomerSegment.WHOLESALE: 0.35, CustomerSegment.ENTERPRISE: 0.15}
    customers = [
        Customer(
            code=f"CUST-{i:05d}", name=fake.company(), segment=weighted_choice(segment_weights),
            city=fake.city(), state=fake.state(), active=random.random() > 0.08,
        )
        for i in range(1, count + 1)
    ]
    session.add_all(customers)
    session.flush()
    return customers


def generate_suppliers(session, fake: Faker, count: int = 95) -> list[Supplier]:
    category_weights = {SupplierCategory.RAW_MATERIAL: 0.35, SupplierCategory.SERVICES: 0.25, SupplierCategory.EQUIPMENT: 0.2, SupplierCategory.PACKAGING: 0.2}
    suppliers = [
        Supplier(
            code=f"SUP-{i:05d}", name=fake.company(), category=weighted_choice(category_weights),
            city=fake.city(), state=fake.state(), rating=round(random.uniform(2.5, 5.0), 2),
        )
        for i in range(1, count + 1)
    ]
    session.add_all(suppliers)
    session.flush()
    return suppliers


def generate_roles_and_users(session, fake: Faker, employees, count: int = 70) -> tuple[list[Role], list[User]]:
    role_defs = [
        ("ADMIN", "Administrator", "Full system access"), ("MANAGER", "Manager", "Departmental oversight"),
        ("ANALYST", "Analyst", "Reporting and analytics"), ("OPERATOR", "Operator", "Day-to-day operations"),
        ("VIEWER", "Viewer", "Read-only access"),
    ]
    roles = [Role(code=c, name=n, description=d) for c, n, d in role_defs]
    session.add_all(roles)
    session.flush()

    staff = random.sample(employees, k=min(count, len(employees)))
    users = []
    for i, employee in enumerate(staff, start=1):
        username = f"{employee.full_name.split()[0].lower()}.{i}"
        users.append(
            User(
                username=username,
                email=f"{username}@opsvision.example",
                employee_id=employee.id,
                role_id=random.choice(roles).id,
                is_active=random.random() > 0.1,
                last_login_at=random_datetime(random_date(date(2026, 1, 1), DATASET_END)) if random.random() > 0.2 else None,
            )
        )
    session.add_all(users)
    session.flush()
    return roles, users


def generate_sales(session, customers, products, locations, count: int = 2200):
    status_weights = {OrderStatus.DRAFT: 0.05, OrderStatus.CONFIRMED: 0.15, OrderStatus.SHIPPED: 0.15, OrderStatus.INVOICED: 0.6, OrderStatus.CANCELLED: 0.05}
    active_customers = [c for c in customers if c.active]
    orders, items = [], []
    for i in range(1, count + 1):
        order_date = random_date()
        order = SalesOrder(
            order_number=f"SO-{i:06d}", customer_id=random.choice(active_customers).id,
            location_id=random.choice(locations).id, status=weighted_choice(status_weights),
            order_date=order_date, discount_pct=round(random.uniform(0, 20), 2),
        )
        session.add(order)
        session.flush()
        for product in random.sample(products, k=random.randint(1, 5)):
            unit_price = round(float(product.unit_price) * random.uniform(0.92, 1.08), 2)
            items.append(
                SalesOrderItem(order_id=order.id, product_id=product.id, quantity=random.randint(1, 50), unit_price=unit_price)
            )
        orders.append(order)
        if i % 500 == 0:
            session.add_all(items)
            session.flush()
            items = []
    session.add_all(items)
    session.flush()
    return orders


def generate_purchasing(session, suppliers, products, locations, count: int = 950):
    status_weights = {PurchaseOrderStatus.DRAFT: 0.05, PurchaseOrderStatus.SENT: 0.1, PurchaseOrderStatus.CONFIRMED: 0.15, PurchaseOrderStatus.RECEIVED: 0.65, PurchaseOrderStatus.CANCELLED: 0.05}
    orders, items = [], []
    for i in range(1, count + 1):
        order_date = random_date()
        order = PurchaseOrder(
            order_number=f"PO-{i:06d}", supplier_id=random.choice(suppliers).id, location_id=random.choice(locations).id,
            status=weighted_choice(status_weights), order_date=order_date,
            expected_date=order_date + timedelta(days=random.randint(7, 30)),
        )
        session.add(order)
        session.flush()
        for product in random.sample(products, k=random.randint(1, 6)):
            unit_cost = round(float(product.unit_cost) * random.uniform(0.9, 1.15), 2)
            items.append(
                PurchaseOrderItem(purchase_order_id=order.id, product_id=product.id, quantity=random.randint(10, 500), unit_cost=unit_cost)
            )
        orders.append(order)
        if i % 500 == 0:
            session.add_all(items)
            session.flush()
            items = []
    session.add_all(items)
    session.flush()
    return orders


def generate_production(session, products, production_lines, count: int = 1700):
    status_weights = {WorkOrderStatus.PLANNED: 0.08, WorkOrderStatus.IN_PROGRESS: 0.1, WorkOrderStatus.COMPLETED: 0.77, WorkOrderStatus.CANCELLED: 0.05}
    orders, events = [], []
    for i in range(1, count + 1):
        scheduled = random_date()
        status = weighted_choice(status_weights)
        planned = random.randint(100, 5000)
        produced = scrap = 0
        completed_at = None
        if status == WorkOrderStatus.COMPLETED:
            produced = int(planned * random.uniform(0.9, 1.02))
            scrap = int(planned * random.uniform(0, 0.08))
            completed_at = random_datetime(scheduled)
        elif status == WorkOrderStatus.IN_PROGRESS:
            produced = int(planned * random.uniform(0.1, 0.6))
        order = WorkOrder(
            order_number=f"WO-{i:06d}", product_id=random.choice(products).id, production_line_id=random.choice(production_lines).id,
            status=status, planned_quantity=planned, produced_quantity=produced, scrap_quantity=scrap,
            scheduled_date=scheduled, completed_at=completed_at,
        )
        session.add(order)
        session.flush()
        event_time = random_datetime(scheduled)
        events.append(ProductionEvent(work_order_id=order.id, event_type=ProductionEventType.START, event_time=event_time))
        if status in (WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED):
            events.append(
                ProductionEvent(
                    work_order_id=order.id, event_type=ProductionEventType.STOP,
                    event_time=event_time + timedelta(hours=random.randint(1, 12)),
                )
            )
        orders.append(order)
        if i % 500 == 0:
            session.add_all(events)
            session.flush()
            events = []
    session.add_all(events)
    session.flush()
    return orders


def generate_stock_movements(session, sales_orders, purchase_orders, products, warehouses):
    movements = []
    for order in sales_orders:
        if order.status == OrderStatus.CANCELLED:
            continue
        for item in order.items:
            movements.append(
                StockMovement(
                    product_id=item.product_id, warehouse_id=random.choice(warehouses).id, movement_type=MovementType.OUTBOUND,
                    quantity=item.quantity, movement_date=order.order_date, reference_note=f"Shipment for {order.order_number}",
                )
            )
    for order in purchase_orders:
        if order.status == PurchaseOrderStatus.CANCELLED:
            continue
        for item in order.items:
            movements.append(
                StockMovement(
                    product_id=item.product_id, warehouse_id=random.choice(warehouses).id, movement_type=MovementType.INBOUND,
                    quantity=item.quantity, movement_date=order.order_date, reference_note=f"Receipt for {order.order_number}",
                )
            )
    for _ in range(1200):
        movement_type = weighted_choice({MovementType.ADJUSTMENT: 0.6, MovementType.TRANSFER: 0.4})
        quantity = random.randint(1, 200)
        movements.append(
            StockMovement(
                product_id=random.choice(products).id, warehouse_id=random.choice(warehouses).id, movement_type=movement_type,
                quantity=quantity if random.random() > 0.3 else -quantity, movement_date=random_date(), reference_note="Cycle count adjustment",
            )
        )
    for batch_start in range(0, len(movements), 1000):
        session.add_all(movements[batch_start : batch_start + 1000])
        session.flush()
    return movements


def generate_finance(session, sales_orders, purchase_orders, employees):
    account_defs = [
        ("1000", "Cash", AccountType.ASSET), ("1100", "Accounts Receivable", AccountType.ASSET),
        ("2000", "Accounts Payable", AccountType.LIABILITY), ("3000", "Equity", AccountType.EQUITY),
        ("4000", "Sales Revenue", AccountType.REVENUE), ("5000", "Cost of Goods Sold", AccountType.EXPENSE),
        ("5100", "Payroll Expense", AccountType.EXPENSE), ("5200", "Operating Expense", AccountType.EXPENSE),
    ]
    accounts = [Account(code=c, name=n, account_type=t) for c, n, t in account_defs]
    session.add_all(accounts)
    session.flush()
    by_code = {a.code: a for a in accounts}

    invoices, transactions = [], []
    invoiced_sales = [o for o in sales_orders if o.status in (OrderStatus.SHIPPED, OrderStatus.INVOICED)]
    for i, order in enumerate(random.sample(invoiced_sales, k=int(len(invoiced_sales) * 0.85)), start=1):
        amount = round(order.net_amount, 2)
        if amount <= 0:
            continue
        issue = order.order_date
        due = issue + timedelta(days=30)
        status = InvoiceStatus.PAID if due < DATASET_END - timedelta(days=45) else weighted_choice({InvoiceStatus.OPEN: 0.6, InvoiceStatus.OVERDUE: 0.3, InvoiceStatus.PAID: 0.1})
        invoice = Invoice(
            invoice_number=f"INV-R-{i:06d}", direction=InvoiceDirection.RECEIVABLE, counterparty_name=f"Customer #{order.customer_id}",
            amount=amount, issue_date=issue, due_date=due, status=status, source_sales_order_id=order.id,
        )
        invoices.append(invoice)

    received_purchases = [o for o in purchase_orders if o.status == PurchaseOrderStatus.RECEIVED]
    for i, order in enumerate(random.sample(received_purchases, k=int(len(received_purchases) * 0.85)), start=1):
        amount = round(order.total_cost, 2)
        if amount <= 0:
            continue
        issue = order.order_date
        due = issue + timedelta(days=30)
        status = InvoiceStatus.PAID if due < DATASET_END - timedelta(days=45) else weighted_choice({InvoiceStatus.OPEN: 0.6, InvoiceStatus.OVERDUE: 0.3, InvoiceStatus.PAID: 0.1})
        invoice = Invoice(
            invoice_number=f"INV-P-{i:06d}", direction=InvoiceDirection.PAYABLE, counterparty_name=f"Supplier #{order.supplier_id}",
            amount=amount, issue_date=issue, due_date=due, status=status, source_purchase_order_id=order.id,
        )
        invoices.append(invoice)

    for batch_start in range(0, len(invoices), 1000):
        session.add_all(invoices[batch_start : batch_start + 1000])
        session.flush()

    for invoice in invoices:
        if invoice.status != InvoiceStatus.PAID:
            continue
        revenue_side = by_code["4000"] if invoice.direction == InvoiceDirection.RECEIVABLE else by_code["5000"]
        cash_type = TransactionType.CREDIT if invoice.direction == InvoiceDirection.RECEIVABLE else TransactionType.DEBIT
        transactions.append(
            Transaction(
                account_id=by_code["1000"].id, invoice_id=invoice.id, transaction_type=cash_type,
                amount=invoice.amount, transaction_date=invoice.due_date,
                description=f"Settlement of {invoice.invoice_number}",
            )
        )
        transactions.append(
            Transaction(
                account_id=revenue_side.id, invoice_id=invoice.id,
                transaction_type=TransactionType.DEBIT if cash_type == TransactionType.CREDIT else TransactionType.CREDIT,
                amount=invoice.amount, transaction_date=invoice.due_date, description=f"Recognize {invoice.invoice_number}",
            )
        )

    active_employees = [e for e in employees if e.employment_status == EmploymentStatus.ACTIVE]
    monthly_payroll = round(sum(float(e.base_salary) for e in active_employees), 2)
    for month in months_between(DATASET_START, DATASET_END):
        transactions.append(
            Transaction(
                account_id=by_code["5100"].id, transaction_type=TransactionType.DEBIT, amount=monthly_payroll,
                transaction_date=month, description=f"Payroll run {month.strftime('%Y-%m')}",
            )
        )

    for batch_start in range(0, len(transactions), 1000):
        session.add_all(transactions[batch_start : batch_start + 1000])
        session.flush()
    return accounts, invoices, transactions


def generate_time_off(session, fake: Faker, employees, count: int = 650):
    type_weights = {TimeOffType.VACATION: 0.55, TimeOffType.SICK: 0.25, TimeOffType.PERSONAL: 0.15, TimeOffType.UNPAID: 0.05}
    status_weights = {TimeOffStatus.APPROVED: 0.75, TimeOffStatus.PENDING: 0.15, TimeOffStatus.REJECTED: 0.1}
    requests = []
    for _ in range(count):
        employee = random.choice(employees)
        window_start = max(employee.hire_date, DATASET_START)
        start = random_date(window_start, DATASET_END)
        end = start + timedelta(days=random.randint(1, 14))
        requests.append(
            TimeOffRequest(employee_id=employee.id, request_type=weighted_choice(type_weights), start_date=start, end_date=end, status=weighted_choice(status_weights))
        )
    session.add_all(requests)
    session.flush()
    return requests


def generate_projects(session, fake: Faker, departments, employees, count: int = 42):
    status_weights = {ProjectStatus.PLANNING: 0.15, ProjectStatus.ACTIVE: 0.35, ProjectStatus.ON_HOLD: 0.1, ProjectStatus.COMPLETED: 0.35, ProjectStatus.CANCELLED: 0.05}
    task_status_weights = {TaskStatus.TODO: 0.2, TaskStatus.IN_PROGRESS: 0.2, TaskStatus.BLOCKED: 0.1, TaskStatus.DONE: 0.5}
    projects, tasks, milestones = [], [], []
    for i in range(1, count + 1):
        start = random_date(DATASET_START, DATASET_END - timedelta(days=30))
        target_end = start + timedelta(days=random.randint(60, 400))
        project = Project(
            code=f"PRJ-{i:04d}", name=fake.catch_phrase(), sponsor_department_id=random.choice(departments).id,
            status=weighted_choice(status_weights), start_date=start, target_end_date=target_end,
            budget=round(random.uniform(20000, 2_000_000), 2),
        )
        session.add(project)
        session.flush()
        for _ in range(random.randint(6, 18)):
            tasks.append(
                Task(
                    project_id=project.id, title=fake.bs().title(), assignee_employee_id=random.choice(employees).id,
                    status=weighted_choice(task_status_weights), due_date=random_date(start, target_end),
                    estimated_hours=round(random.uniform(2, 80), 2),
                )
            )
        for _ in range(random.randint(2, 5)):
            due = random_date(start, target_end)
            achieved = due < DATASET_END and random.random() > 0.3
            milestones.append(
                Milestone(project_id=project.id, name=fake.bs().title(), due_date=due, achieved=achieved, achieved_date=due if achieved else None)
            )
        projects.append(project)
    session.add_all(tasks)
    session.add_all(milestones)
    session.flush()
    return projects


def generate_maintenance(session, fake: Faker, locations, employees, count_assets: int = 210, count_requests: int = 850):
    category_weights = {AssetCategory.MACHINE: 0.4, AssetCategory.VEHICLE: 0.2, AssetCategory.FACILITY: 0.2, AssetCategory.IT_EQUIPMENT: 0.2}
    criticality_weights = {AssetCriticality.LOW: 0.3, AssetCriticality.MEDIUM: 0.35, AssetCriticality.HIGH: 0.25, AssetCriticality.CRITICAL: 0.1}
    assets = [
        Asset(
            asset_tag=f"AST-{i:05d}", name=f"{fake.word().title()} Unit {i}", location_id=random.choice(locations).id,
            category=weighted_choice(category_weights), install_date=random_date(date(2016, 1, 1), DATASET_END),
            criticality=weighted_choice(criticality_weights),
        )
        for i in range(1, count_assets + 1)
    ]
    session.add_all(assets)
    session.flush()

    type_weights = {MaintenanceRequestType.PREVENTIVE: 0.5, MaintenanceRequestType.CORRECTIVE: 0.4, MaintenanceRequestType.PREDICTIVE: 0.1}
    priority_weights = {MaintenancePriority.LOW: 0.3, MaintenancePriority.MEDIUM: 0.35, MaintenancePriority.HIGH: 0.25, MaintenancePriority.URGENT: 0.1}
    status_weights = {MaintenanceStatus.OPEN: 0.1, MaintenanceStatus.SCHEDULED: 0.1, MaintenanceStatus.IN_PROGRESS: 0.05, MaintenanceStatus.COMPLETED: 0.7, MaintenanceStatus.CANCELLED: 0.05}
    requests, logs = [], []
    for i in range(1, count_requests + 1):
        opened = random_date()
        status = weighted_choice(status_weights)
        request = MaintenanceRequest(
            asset_id=random.choice(assets).id, request_type=weighted_choice(type_weights), priority=weighted_choice(priority_weights),
            status=status, opened_date=opened, requested_by_employee_id=random.choice(employees).id if random.random() > 0.3 else None,
        )
        session.add(request)
        session.flush()
        if status in (MaintenanceStatus.COMPLETED, MaintenanceStatus.IN_PROGRESS):
            for _ in range(random.randint(1, 3)):
                logs.append(
                    MaintenanceLog(
                        request_id=request.id, log_date=opened + timedelta(days=random.randint(0, 10)),
                        hours_spent=round(random.uniform(0.5, 40), 2), cost=round(random.uniform(50, 5000), 2),
                        notes=fake.sentence() if random.random() > 0.5 else None,
                    )
                )
        requests.append(request)
        if i % 500 == 0:
            session.add_all(logs)
            session.flush()
            logs = []
    session.add_all(logs)
    session.flush()
    return assets, requests


def generate_quality(session, fake: Faker, products, work_orders, employees, locations, count: int = 2400):
    inspections, nonconformances = [], []
    for i in range(1, count + 1):
        sample_size = random.randint(10, 500)
        defect_rate = random.betavariate(0.5, 45)  # heavily skewed toward low defect rates, rare spikes
        defect_count = min(sample_size, int(sample_size * defect_rate))
        result = InspectionResult.PASS if defect_rate < 0.02 else (InspectionResult.REWORK if defect_rate < 0.08 else InspectionResult.FAIL)
        inspection_date = random_date()
        inspection = Inspection(
            work_order_id=random.choice(work_orders).id if random.random() > 0.3 else None,
            product_id=random.choice(products).id, inspector_employee_id=random.choice(employees).id,
            inspection_date=inspection_date, result=result, sample_size=sample_size, defect_count=defect_count,
        )
        session.add(inspection)
        session.flush()
        if result != InspectionResult.PASS:
            severity = weighted_choice({NonConformanceSeverity.MINOR: 0.5, NonConformanceSeverity.MAJOR: 0.35, NonConformanceSeverity.CRITICAL: 0.15})
            status = weighted_choice({NonConformanceStatus.OPEN: 0.15, NonConformanceStatus.UNDER_REVIEW: 0.1, NonConformanceStatus.RESOLVED: 0.15, NonConformanceStatus.CLOSED: 0.6})
            closed_date = inspection_date + timedelta(days=random.randint(1, 30)) if status == NonConformanceStatus.CLOSED else None
            nonconformances.append(
                NonConformance(
                    inspection_id=inspection.id, severity=severity, description=fake.sentence(), status=status,
                    opened_date=inspection_date, closed_date=closed_date,
                )
            )
        inspections.append(inspection)
        if i % 500 == 0:
            session.add_all(nonconformances)
            session.flush()
            nonconformances = []
    session.add_all(nonconformances)
    session.flush()

    metrics = []
    for location in locations:
        for month in months_between(DATASET_START, DATASET_END):
            metrics.append(
                QualityMetric(location_id=location.id, metric_date=month, metric_name="on_time_delivery_rate", metric_value=round(random.uniform(85, 99.5), 2))
            )
            metrics.append(
                QualityMetric(location_id=location.id, metric_date=month, metric_name="customer_complaints", metric_value=float(random.randint(0, 12)))
            )
    session.add_all(metrics)
    session.flush()
    return inspections


def generate_audit_logs(session, fake: Faker, users, count: int = 350):
    actions = ["create", "update", "delete", "approve", "export"]
    entities = ["SalesOrder", "PurchaseOrder", "WorkOrder", "Invoice", "Project", "MaintenanceRequest"]
    logs = [
        AuditLog(
            actor_user_id=random.choice(users).id if users and random.random() > 0.1 else None,
            action=random.choice(actions), entity_name=random.choice(entities), entity_id=random.randint(1, 2000),
            occurred_at=random_datetime(random_date()), detail=fake.sentence() if random.random() > 0.4 else None,
        )
        for _ in range(count)
    ]
    session.add_all(logs)
    session.flush()
    return logs


def run(seed: int = 42, reset: bool = False) -> None:
    """Generate the full dataset. Callable from code (e.g. the app bootstrap)."""
    random.seed(seed)
    fake = Faker()
    Faker.seed(seed)

    import app.database.models  # noqa: F401 — registers every model on Base.metadata

    if reset:
        print("Dropping and recreating schema...")
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        print("Generating core reference data...")
        locations = generate_locations(session, fake)
        departments = generate_departments(session)
        employees = generate_employees(session, fake, departments, locations)
        warehouses = generate_warehouses(session, locations)
        products = generate_products(session, fake)
        production_lines = generate_production_lines(session, locations)
        customers = generate_customers(session, fake)
        suppliers = generate_suppliers(session, fake)
        roles, users = generate_roles_and_users(session, fake, employees)

        print("Generating sales orders...")
        sales_orders = generate_sales(session, customers, products, locations)
        print("Generating purchase orders...")
        purchase_orders = generate_purchasing(session, suppliers, products, locations)
        print("Generating production work orders...")
        work_orders = generate_production(session, products, production_lines)
        print("Deriving stock movements...")
        generate_stock_movements(session, sales_orders, purchase_orders, products, warehouses)
        print("Deriving finance ledger...")
        generate_finance(session, sales_orders, purchase_orders, employees)
        print("Generating HR activity...")
        generate_time_off(session, fake, employees)
        print("Generating projects...")
        generate_projects(session, fake, departments, employees)
        print("Generating maintenance activity...")
        generate_maintenance(session, fake, locations, employees)
        print("Generating quality activity...")
        generate_quality(session, fake, products, work_orders, employees, locations)
        print("Generating audit trail...")
        generate_audit_logs(session, fake, users)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(f"Done. Dataset spans {DATASET_START} to {DATASET_END}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Drop and recreate the schema before seeding")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible datasets")
    args = parser.parse_args()
    run(seed=args.seed, reset=args.reset)


if __name__ == "__main__":
    main()
