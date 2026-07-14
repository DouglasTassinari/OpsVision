"""Populate the Sistema TAZZIN with a coherent, multi-year synthetic dataset.

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
import unicodedata
from datetime import date, datetime, time, timedelta
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
from app.database.models.machining import (
    Appointment,
    Machine,
    OccurrenceCategory,
    OccurrenceType,
    Operator,
)
from app.database.models.scrap import ScrapPart, ScrapRecord
from app.database.models.adjustments import TimeAdjustment
from app.database.models.compensation import (
    Placement,
    Position,
    PositionLevel,
    SeniorityBand,
    UnionFloor,
)

# Bump whenever the generated dataset changes shape (volumes, salaries,
# accounting rules...): deployments with a database seeded by an older
# version reseed automatically on boot (see app/core/bootstrap.py).
DATASET_VERSION = 6

DATASET_START = date(2023, 1, 1)
DATASET_END = date.today()
HIRE_WINDOW_START = date(2018, 1, 1)


# Vocabulário pt-BR para entidades que o Faker não cobre bem em português.
PRODUCT_NAME_POOLS = {
    ProductCategory.RAW_MATERIAL: (
        ["Chapa de Aço", "Bobina de Alumínio", "Resina ABS", "Polietileno Granulado", "Barra de Latão",
         "Tubo de Cobre", "Chapa Galvanizada", "Vergalhão CA-50", "Tinta Epóxi", "Borracha Nitrílica"],
        ["1mm", "3mm", "6mm", "10kg", "25kg", "50kg", "Tipo A", "Tipo B", "Premium", "Industrial"],
    ),
    ProductCategory.COMPONENT: (
        ["Rolamento", "Engrenagem", "Motor Elétrico", "Válvula Solenoide", "Sensor Indutivo",
         "Correia Dentada", "Painel de Comando", "Bomba Hidráulica", "Cilindro Pneumático", "Fonte Chaveada"],
        ["6204", "8210", "2CV", "5CV", "12V", "24V", "220V", "Série X", "Série K", "Compacto"],
    ),
    ProductCategory.FINISHED_GOOD: (
        ["Compressor", "Furadeira Industrial", "Esteira Transportadora", "Painel Modular", "Bancada de Trabalho",
         "Exaustor Industrial", "Talha Elétrica", "Serra de Bancada", "Prensa Manual", "Gerador Portátil"],
        ["Pro 200", "Max 350", "Slim", "Heavy Duty", "Standard", "Plus", "Ultra", "Eco", "Turbo", "HD 500"],
    ),
    ProductCategory.PACKAGING: (
        ["Caixa de Papelão", "Filme Stretch", "Palete PBR", "Fita Adesiva", "Saco Plástico",
         "Cinta de Arquear", "Etiqueta Térmica", "Manta de Proteção", "Cantoneira", "Plástico Bolha"],
        ["30x30", "40x60", "Rolo 500m", "Reforçado", "Standard", "Industrial", "Kit 100", "Rolo 50m", "Branco", "Pardo"],
    ),
}

ASSET_NAMES = [
    "Prensa Hidráulica", "Torno CNC", "Compressor de Ar", "Empilhadeira", "Ponte Rolante",
    "Injetora Plástica", "Caldeira", "Chiller Industrial", "Gerador Diesel", "Esteira Transportadora",
    "Robô de Solda", "Fresadora", "Dobradeira", "Serra Fita", "Câmara Fria",
]

PROJECT_PREFIXES = [
    "Expansão", "Automação", "Modernização", "Implantação", "Otimização",
    "Integração", "Digitalização", "Reestruturação",
]
PROJECT_TARGETS = [
    "da Linha de Montagem", "do Armazém Central", "da Planta 2", "do ERP",
    "da Frota", "de Embalagens", "do Controle de Qualidade", "da Malha Logística",
    "do Centro de Distribuição", "da Célula de Solda",
]
TASK_TITLES = [
    "Levantar requisitos", "Aprovar orçamento", "Contratar fornecedor", "Elaborar cronograma",
    "Executar testes", "Treinar equipe", "Homologar processo", "Revisar documentação",
    "Instalar equipamentos", "Validar protótipo", "Mapear riscos", "Auditar entregas",
    "Configurar sistema", "Migrar dados", "Realizar piloto", "Aprovar layout",
]
MILESTONE_NAMES = [
    "Kickoff concluído", "Requisitos aprovados", "Fase 1 entregue", "Homologação concluída",
    "Go-live", "Treinamento finalizado", "Encerramento do projeto",
]
MAINTENANCE_NOTES = [
    "Troca de rolamento e lubrificação geral.", "Substituição de correia desgastada.",
    "Ajuste de alinhamento e calibração.", "Reparo no painel elétrico.",
    "Limpeza técnica e inspeção preventiva.", "Substituição de vedação com vazamento.",
    "Atualização de firmware do controlador.", "Troca de filtros e óleo hidráulico.",
]
NONCONFORMANCE_DESCRIPTIONS = [
    "Dimensão fora da tolerância especificada.", "Acabamento superficial com riscos.",
    "Falha de solda identificada na inspeção.", "Cor divergente do padrão aprovado.",
    "Embalagem danificada no manuseio.", "Componente com folga acima do limite.",
    "Etiqueta com informação incorreta.", "Contaminação detectada no lote.",
]
AUDIT_ACTIONS = ["criação", "atualização", "exclusão", "aprovação", "exportação"]
AUDIT_ENTITIES = [
    "Pedido de Venda", "Pedido de Compra", "Ordem de Produção",
    "Fatura", "Projeto", "Solicitação de Manutenção",
]
AUDIT_DETAILS = [
    "Registro revisado pelo responsável do módulo.", "Alteração aprovada pelo gestor da área.",
    "Operação executada em lote pela rotina mensal.", "Ajuste manual após conferência física.",
    "Documento exportado para auditoria externa.", "Atualização de status após integração.",
]

# ── Machining (Usinagem) vocabulary ──
MACHINE_NAMES = [
    "Torno CNC Romi", "Torno CNC Mazak", "Centro de Usinagem Haas", "Centro de Usinagem DMG",
    "Fresadora CNC", "Furadeira Radial", "Retífica Cilíndrica", "Retífica Plana",
    "Mandrilhadora", "Torno Convencional", "Centro de Torneamento", "Eletroerosão",
]
OCCURRENCE_TYPES_SEED = [
    ("PRODUCAO", "Produção", OccurrenceCategory.PRODUCTIVE, True, True, 1.0),
    ("SETUP_30MIN", "Setup 30min", OccurrenceCategory.SEMI_PRODUCTIVE, False, True, 0.8),
    ("SETUP_1H", "Setup 1h", OccurrenceCategory.SEMI_PRODUCTIVE, False, True, 0.8),
    ("SETUP_1H30", "Setup 1h30", OccurrenceCategory.SEMI_PRODUCTIVE, False, True, 0.8),
    ("SETUP_2H", "Setup 2h", OccurrenceCategory.SEMI_PRODUCTIVE, False, True, 0.8),
    ("MANUTENCAO", "Manutenção", OccurrenceCategory.UNPRODUCTIVE, False, True, 0.0),
    ("SEM_PECA", "Sem Peça", OccurrenceCategory.UNPRODUCTIVE, False, False, 0.0),
    ("ESPERANDO_PECA", "Esperando Peça", OccurrenceCategory.UNPRODUCTIVE, False, False, 0.0),
    ("REUNIAO", "Reunião", OccurrenceCategory.UNPRODUCTIVE, False, False, 0.0),
    ("LIMPEZA", "Limpeza", OccurrenceCategory.UNPRODUCTIVE, False, False, 0.0),
    ("TROCA_OP", "Troca de OP", OccurrenceCategory.UNPRODUCTIVE, False, False, 0.0),
    ("RETRABALHO", "Retrabalho", OccurrenceCategory.UNPRODUCTIVE, True, True, 0.5),
    ("PROGRAMA", "Programa CNC", OccurrenceCategory.UNPRODUCTIVE, False, False, 0.0),
    ("TREINAMENTO", "Treinamento", OccurrenceCategory.UNPRODUCTIVE, False, False, 0.0),
]
OPERATOR_NAMES = [
    "Adriano da Silva", "Arthur Gonçalves", "Marco Antonio", "Guilherme Costa",
    "Ricardo Pereira", "Alcioni Donato", "Aliff Fernandes", "Eduardo Santos",
    "Felipe Oliveira", "Lucas Mendes", "Rafael Souza", "Bruno Martins",
    "Thiago Ribeiro", "Carlos Alberto",
]
SCRAP_REASONS = [
    "Dimensional Errado Usinagem", "Trinca na Fundição", "Porosidade",
    "Rechupe", "Empenamento", "Dureza Fora", "Defeito de Superfície",
    "Outros",
]
SCRAP_SUPPLIERS = [
    "Fundição Criciúma", "Fundição Tubarão", "Aços Especiais Sul",
    "MetalBrut Ltda", "Fundiminas", "Aço Forte",
]
MACHINING_OPERATIONS = [
    "Lado 1", "Lado 2", "Furação", "Rosqueamento", "Acabamento",
    "Desbaste", "Chanfro", "Retífica",
]
ADJUSTMENT_JUSTIFICATIONS = [
    "Troca de ferramenta por modelo mais eficiente.",
    "Revisão de parâmetros de corte após teste.",
    "Ajuste de fixação reduziu tempo de setup.",
    "Material mais duro que o especificado.",
    "Desgaste prematuro da ferramenta.",
    "Otimização do programa CNC.",
    "Mudança de estratégia de usinagem.",
    "Ferramenta com vida útil abaixo do esperado.",
]


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


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
    type_labels = {
        LocationType.PLANT: "Planta",
        LocationType.WAREHOUSE: "Armazém",
        LocationType.OFFICE: "Escritório",
    }
    locations = [
        Location(
            code=code, name=f"{type_labels[loc_type]} {fake.city()}", city=fake.city(),
            state=fake.state(), country="Brasil", location_type=loc_type,
        )
        for code, loc_type in blueprint
    ]
    session.add_all(locations)
    session.flush()
    return locations


def generate_departments(session) -> list[Department]:
    names = [
        ("SALES", "Vendas", "CC-100"), ("MFG", "Produção", "CC-200"),
        ("LOG", "Logística", "CC-210"), ("PROC", "Suprimentos", "CC-300"),
        ("FIN", "Financeiro", "CC-400"), ("HR", "Recursos Humanos", "CC-500"),
        ("PMO", "Escritório de Projetos", "CC-600"), ("FAC", "Manutenção e Instalações", "CC-700"),
        ("QA", "Qualidade", "CC-800"), ("IT", "TI e Administração", "CC-900"),
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
            base_salary=round(random.uniform(2600, 15000), 2),
        )
        for i in range(1, count + 1)
    ]
    session.add_all(employees)
    session.flush()
    return employees


def generate_warehouses(session, locations, count: int = 5) -> list[Warehouse]:
    candidates = [loc for loc in locations if loc.location_type in (LocationType.WAREHOUSE, LocationType.PLANT)]
    warehouses = [
        Warehouse(code=f"WH-{i:02d}", name=f"Armazém {i}", location_id=random.choice(candidates).id, capacity_units=random.randint(5000, 50000))
        for i in range(1, count + 1)
    ]
    session.add_all(warehouses)
    session.flush()
    return warehouses


def generate_products(session, fake: Faker, count: int = 130) -> list[Product]:
    products, used_names = [], set()
    for i in range(1, count + 1):
        category = weighted_choice(
            {ProductCategory.RAW_MATERIAL: 0.25, ProductCategory.COMPONENT: 0.3, ProductCategory.FINISHED_GOOD: 0.35, ProductCategory.PACKAGING: 0.1}
        )
        bases, variants = PRODUCT_NAME_POOLS[category]
        name = f"{random.choice(bases)} {random.choice(variants)}"
        while name in used_names:
            name = f"{random.choice(bases)} {random.choice(variants)}"
        used_names.add(name)
        unit_cost = round(random.uniform(4, 480), 2)
        products.append(
            Product(
                sku=f"SKU-{i:05d}",
                name=name,
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
        ProductionLine(code=f"LINE-{i:02d}", name=f"Linha {i}", location_id=random.choice(plants).id, capacity_units_per_hour=round(random.uniform(50, 520), 2))
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
        ("ADMIN", "Administrador", "Acesso total ao sistema"), ("MANAGER", "Gestor", "Supervisão do departamento"),
        ("ANALYST", "Analista", "Relatórios e análises"), ("OPERATOR", "Operador", "Operações do dia a dia"),
        ("VIEWER", "Leitor", "Acesso somente leitura"),
    ]
    roles = [Role(code=c, name=n, description=d) for c, n, d in role_defs]
    session.add_all(roles)
    session.flush()

    staff = random.sample(employees, k=min(count, len(employees)))
    users = []
    for i, employee in enumerate(staff, start=1):
        username = f"{strip_accents(employee.full_name.split()[0].lower())}.{i}"
        users.append(
            User(
                username=username,
                email=f"{username}@tazzin.example",
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
        status = weighted_choice(status_weights)
        # Propostas em aberto (rascunho/confirmada) são naturalmente recentes —
        # uma proposta muito antiga já teria sido faturada ou cancelada. Datá-las
        # nos últimos ~40 dias dá ao Radar de Oportunidades uma distribuição de
        # temperatura realista (Quente/Morna/Fria/Vencida) em vez de tudo vencido.
        if status in (OrderStatus.DRAFT, OrderStatus.CONFIRMED):
            order_date = random_date(DATASET_END - timedelta(days=40), DATASET_END)
        else:
            order_date = random_date()
        order = SalesOrder(
            order_number=f"SO-{i:06d}", customer_id=random.choice(active_customers).id,
            location_id=random.choice(locations).id, status=status,
            order_date=order_date, discount_pct=round(random.uniform(0, 20), 2),
        )
        session.add(order)
        session.flush()
        for product in random.sample(products, k=random.randint(1, 5)):
            unit_price = round(float(product.unit_price) * random.uniform(0.92, 1.08), 2)
            items.append(
                SalesOrderItem(order_id=order.id, product_id=product.id, quantity=random.randint(1, 220), unit_price=unit_price)
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
                PurchaseOrderItem(purchase_order_id=order.id, product_id=product.id, quantity=random.randint(10, 360), unit_cost=unit_cost)
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
                    quantity=item.quantity, movement_date=order.order_date, reference_note=f"Expedição do pedido {order.order_number}",
                )
            )
    for order in purchase_orders:
        if order.status == PurchaseOrderStatus.CANCELLED:
            continue
        for item in order.items:
            movements.append(
                StockMovement(
                    product_id=item.product_id, warehouse_id=random.choice(warehouses).id, movement_type=MovementType.INBOUND,
                    quantity=item.quantity, movement_date=order.order_date, reference_note=f"Recebimento do pedido {order.order_number}",
                )
            )
    for _ in range(1200):
        movement_type = weighted_choice({MovementType.ADJUSTMENT: 0.6, MovementType.TRANSFER: 0.4})
        quantity = random.randint(1, 200)
        movements.append(
            StockMovement(
                product_id=random.choice(products).id, warehouse_id=random.choice(warehouses).id, movement_type=movement_type,
                quantity=quantity if random.random() > 0.3 else -quantity, movement_date=random_date(), reference_note="Ajuste de inventário cíclico",
            )
        )
    for batch_start in range(0, len(movements), 1000):
        session.add_all(movements[batch_start : batch_start + 1000])
        session.flush()
    return movements


def generate_finance(session, sales_orders, purchase_orders, employees):
    account_defs = [
        ("1000", "Caixa", AccountType.ASSET), ("1100", "Contas a Receber", AccountType.ASSET),
        ("2000", "Contas a Pagar", AccountType.LIABILITY), ("3000", "Patrimônio Líquido", AccountType.EQUITY),
        ("4000", "Receita de Vendas", AccountType.REVENUE), ("5000", "Custo da Mercadoria Vendida", AccountType.EXPENSE),
        ("5100", "Despesa de Folha", AccountType.EXPENSE), ("5200", "Despesa Operacional", AccountType.EXPENSE),
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
            invoice_number=f"INV-R-{i:06d}", direction=InvoiceDirection.RECEIVABLE, counterparty_name=f"Cliente #{order.customer_id}",
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
            invoice_number=f"INV-P-{i:06d}", direction=InvoiceDirection.PAYABLE, counterparty_name=f"Fornecedor #{order.supplier_id}",
            amount=amount, issue_date=issue, due_date=due, status=status, source_purchase_order_id=order.id,
        )
        invoices.append(invoice)

    for batch_start in range(0, len(invoices), 1000):
        session.add_all(invoices[batch_start : batch_start + 1000])
        session.flush()

    for invoice in invoices:
        if invoice.status != InvoiceStatus.PAID:
            continue
        # Only the cash leg is recorded here: net_cashflow_by_month sums every
        # Transaction in range, so a paired revenue/COGS recognition entry
        # would always net to zero and silently erase sales and purchases
        # from the cash flow, leaving only payroll visible.
        cash_type = TransactionType.CREDIT if invoice.direction == InvoiceDirection.RECEIVABLE else TransactionType.DEBIT
        transactions.append(
            Transaction(
                account_id=by_code["1000"].id, invoice_id=invoice.id, transaction_type=cash_type,
                amount=invoice.amount, transaction_date=invoice.due_date,
                description=f"Liquidação da fatura {invoice.invoice_number}",
            )
        )

    active_employees = [e for e in employees if e.employment_status == EmploymentStatus.ACTIVE]
    monthly_payroll = round(sum(float(e.base_salary) for e in active_employees), 2)
    for month in months_between(DATASET_START, DATASET_END):
        transactions.append(
            Transaction(
                account_id=by_code["5100"].id, transaction_type=TransactionType.DEBIT, amount=monthly_payroll,
                transaction_date=month, description=f"Folha de pagamento {month.strftime('%Y-%m')}",
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


# Grade sintética de cargos: um cargo por departamento. Os VALORES são fictícios
# (premissa do TAZZIN: nenhum dado salarial real no repositório); as REGRAS,
# faixas e o corte 01/05 do dissídio são idênticos ao módulo de origem.
_POSITION_BLUEPRINT = {
    "SALES": ("Vendas", True), "MFG": ("Produção", True), "LOG": ("Logística", False),
    "PROC": ("Suprimentos", False), "FIN": ("Financeiro", False), "HR": ("Recursos Humanos", False),
    "PMO": ("Projetos", True), "FAC": ("Manutenção", False), "QA": ("Qualidade", True),
    "IT": ("TI e Administração", False),
}
# Piso do sindicato por ano (fictício, ~6%/ano). Cobre os aniversários possíveis
# (janela de admissão desde 2018). O corte 01/05 é aplicado pela regra pura.
_SYNTHETIC_FLOORS = {
    2019: 1700.00, 2020: 1800.00, 2021: 1908.00, 2022: 2022.00,
    2023: 2140.00, 2024: 2270.00, 2025: 2405.00, 2026: 2549.00,
}
_SENIORITY_BANDS = [(2, 5), (5, 7), (10, 10), (15, 12), (20, 15)]  # (anos, % sobre o piso)


def generate_compensation(session, departments, employees):
    """Seed do módulo Cargos e Salários: pisos, faixas de tempo de casa, cargos/níveis
    e o enquadramento decomposto de cada colaborador ativo.

    Deriva a grade dos próprios funcionários sintéticos: por departamento, os ativos
    são divididos em três níveis por faixa salarial; a base de cada nível é fixada
    abaixo dos ocupantes para que ``base + avaliação + tempo de casa`` reconstrua o
    salário atual (adicional de avaliação sempre positivo).
    """
    from decimal import ROUND_HALF_UP, Decimal

    from app.domain import compensation_rules as rules

    def _r2(value) -> Decimal:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    floors_dec = {year: Decimal(str(value)) for year, value in _SYNTHETIC_FLOORS.items()}
    bands_tuple = tuple((anos, Decimal(str(pct))) for anos, pct in _SENIORITY_BANDS)
    today = DATASET_END

    session.add_all(
        [UnionFloor(year=y, value=v, note="Piso sindical (sintético)") for y, v in _SYNTHETIC_FLOORS.items()]
    )
    session.add_all(
        [
            SeniorityBand(position_id=None, min_months=anos * 12, percent=pct, note="Tempo de casa")
            for anos, pct in _SENIORITY_BANDS
        ]
    )

    active_by_dept: dict[int, list] = {}
    for emp in employees:
        if emp.employment_status == EmploymentStatus.ACTIVE:
            active_by_dept.setdefault(emp.department_id, []).append(emp)

    placements: list[Placement] = []
    for dept in departments:
        name, has_leadership = _POSITION_BLUEPRINT.get(dept.code, (dept.name, False))
        position = Position(
            name=name, area=dept.name, code=f"CG-{dept.code}",
            has_leadership=has_leadership, has_levels=True, status="active",
        )
        session.add(position)
        session.flush()  # id

        roster = sorted(active_by_dept.get(dept.id, []), key=lambda e: float(e.base_salary))
        # três níveis por faixa salarial (terços); níveis sem ocupante ficam "a definir".
        n = len(roster)
        cut1, cut2 = n // 3, (2 * n) // 3
        tiers = [roster[:cut1], roster[cut1:cut2], roster[cut2:]]

        for order, tier in enumerate(tiers, start=1):
            base = None
            if tier:
                adjusted = []
                seniorities = {}
                for emp in tier:
                    sen = rules.seniority_addon(emp.hire_date, today, floors_dec, bands_tuple)
                    seniorities[emp.id] = sen
                    adjusted.append(Decimal(str(emp.base_salary)) - sen)
                base = _r2(Decimal("0.90") * min(adjusted))

            level = PositionLevel(
                position_id=position.id, name=f"Nível {order}",
                description=None, base_salary=base, display_order=order, status="active",
            )
            session.add(level)
            session.flush()  # id

            for emp in tier:
                sen = seniorities[emp.id]
                evaluation = max(Decimal("0.00"), _r2(Decimal(str(emp.base_salary)) - base - sen))
                placements.append(
                    Placement(
                        employee_id=emp.id, position_id=position.id, level_id=level.id,
                        evaluation_addon=evaluation, comment=None,
                    )
                )

    session.add_all(placements)
    session.flush()
    return placements


def generate_projects(session, fake: Faker, departments, employees, count: int = 42):
    status_weights = {ProjectStatus.PLANNING: 0.15, ProjectStatus.ACTIVE: 0.35, ProjectStatus.ON_HOLD: 0.1, ProjectStatus.COMPLETED: 0.35, ProjectStatus.CANCELLED: 0.05}
    task_status_weights = {TaskStatus.TODO: 0.2, TaskStatus.IN_PROGRESS: 0.2, TaskStatus.BLOCKED: 0.1, TaskStatus.DONE: 0.5}
    projects, tasks, milestones = [], [], []
    for i in range(1, count + 1):
        start = random_date(DATASET_START, DATASET_END - timedelta(days=30))
        target_end = start + timedelta(days=random.randint(60, 400))
        project = Project(
            code=f"PRJ-{i:04d}",
            name=f"{random.choice(PROJECT_PREFIXES)} {random.choice(PROJECT_TARGETS)}",
            sponsor_department_id=random.choice(departments).id,
            status=weighted_choice(status_weights), start_date=start, target_end_date=target_end,
            budget=round(random.uniform(20000, 2_000_000), 2),
        )
        session.add(project)
        session.flush()
        for _ in range(random.randint(6, 18)):
            tasks.append(
                Task(
                    project_id=project.id, title=random.choice(TASK_TITLES), assignee_employee_id=random.choice(employees).id,
                    status=weighted_choice(task_status_weights), due_date=random_date(start, target_end),
                    estimated_hours=round(random.uniform(2, 80), 2),
                )
            )
        for _ in range(random.randint(2, 5)):
            due = random_date(start, target_end)
            achieved = due < DATASET_END and random.random() > 0.3
            milestones.append(
                Milestone(project_id=project.id, name=random.choice(MILESTONE_NAMES), due_date=due, achieved=achieved, achieved_date=due if achieved else None)
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
            asset_tag=f"AST-{i:05d}", name=f"{random.choice(ASSET_NAMES)} {i:02d}", location_id=random.choice(locations).id,
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
                        notes=random.choice(MAINTENANCE_NOTES) if random.random() > 0.5 else None,
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
                    inspection_id=inspection.id, severity=severity,
                    description=random.choice(NONCONFORMANCE_DESCRIPTIONS), status=status,
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
    logs = [
        AuditLog(
            actor_user_id=random.choice(users).id if users and random.random() > 0.1 else None,
            action=random.choice(AUDIT_ACTIONS), entity_name=random.choice(AUDIT_ENTITIES), entity_id=random.randint(1, 2000),
            occurred_at=random_datetime(random_date()),
            detail=random.choice(AUDIT_DETAILS) if random.random() > 0.4 else None,
        )
        for _ in range(count)
    ]
    session.add_all(logs)
    session.flush()
    return logs


def generate_machining(session, production_lines, employees, work_orders, count_appointments: int = 4500):
    """Generate machines, operators, occurrence types and appointments for the Usinagem module."""
    # Occurrence types (seed catalog)
    occ_types = [
        OccurrenceType(
            code=code, description=desc, category=cat,
            impacts_efficiency=eff, impacts_oee=oee, weight=w,
        )
        for code, desc, cat, eff, oee, w in OCCURRENCE_TYPES_SEED
    ]
    session.add_all(occ_types)
    session.flush()
    prod_type = [o for o in occ_types if o.category == OccurrenceCategory.PRODUCTIVE][0]
    setup_types = [o for o in occ_types if o.category == OccurrenceCategory.SEMI_PRODUCTIVE]
    unprod_types = [o for o in occ_types if o.category == OccurrenceCategory.UNPRODUCTIVE]

    # Machines
    machines = [
        Machine(
            code=f"CNC-{i:02d}", name=f"{MACHINE_NAMES[i % len(MACHINE_NAMES)]} {i:02d}",
            production_line_id=random.choice(production_lines).id, active=True,
        )
        for i in range(1, 13)
    ]
    session.add_all(machines)
    session.flush()

    # Operators (linked to employees)
    active_employees = [e for e in employees if e.employment_status.value == "active"]
    operator_employees = random.sample(active_employees, k=min(len(OPERATOR_NAMES), len(active_employees)))
    operators = [
        Operator(
            employee_id=emp.id, code=f"OP-{i:02d}", name=OPERATOR_NAMES[i],
            shift=1 if i < 7 else 2, active=True,
        )
        for i, emp in enumerate(operator_employees)
    ]
    session.add_all(operators)
    session.flush()

    # Appointments
    wo_numbers = [wo.order_number for wo in work_orders if wo.status != WorkOrderStatus.CANCELLED]
    appointments = []
    for _ in range(count_appointments):
        day = random_date()
        operator = random.choice(operators)
        machine = random.choice(machines)
        # 65% production, 15% setup, 20% unproductive
        roll = random.random()
        if roll < 0.65:
            occ = prod_type
            qty = random.randint(5, 120)
            eff = round(random.gauss(92, 18), 2)
            eff = max(20, min(eff, 250))
        elif roll < 0.80:
            occ = random.choice(setup_types)
            qty = random.randint(0, 1)
            eff = 0
        else:
            occ = random.choice(unprod_types)
            qty = 0
            eff = 0

        duration = round(random.uniform(10, 180), 2)
        start_hour = random.randint(6, 20)
        start_min = random.randint(0, 59)
        start_t = time(start_hour, start_min)
        end_min_total = start_hour * 60 + start_min + int(duration)
        end_h = min(end_min_total // 60, 23)
        end_m = end_min_total % 60
        end_t = time(end_h, end_m)

        total_prod_day = random.randint(max(qty, 1), max(qty * 3, 10))
        appointments.append(Appointment(
            appointment_date=day, machine_id=machine.id, operator_id=operator.id,
            work_order_number=random.choice(wo_numbers) if wo_numbers and random.random() > 0.1 else None,
            operation=random.choice(MACHINING_OPERATIONS) if random.random() > 0.3 else None,
            occurrence_type_id=occ.id,
            start_time=start_t, end_time=end_t, duration_minutes=duration,
            quantity=qty, efficiency_pct=eff, standard_time=round(duration * random.uniform(0.8, 1.2), 2),
            total_production=total_prod_day,
            lot_code=f"L-{random.randint(1000, 9999)}" if random.random() > 0.4 else None,
        ))
        if len(appointments) % 1000 == 0:
            session.add_all(appointments)
            session.flush()
            appointments = []
    session.add_all(appointments)
    session.flush()
    return machines, operators, occ_types


def generate_scrap(session, operators, machines, work_orders, count: int = 380):
    """Generate scrap parts and scrap records for the Refugo module."""
    # Scrap parts catalog
    parts = []
    for i in range(1, 51):
        supplier = random.choice(SCRAP_SUPPLIERS)
        parts.append(ScrapPart(
            supplier=supplier, part_code=f"PC-{i:04d}",
            item_code=f"BRT-PC-{i:04d}", active=True,
        ))
    session.add_all(parts)
    session.flush()

    wo_numbers = [wo.order_number for wo in work_orders if wo.status != WorkOrderStatus.CANCELLED]
    records = []
    for _ in range(count):
        day = random_date()
        operator = random.choice(operators)
        machine = random.choice(machines)
        part = random.choice(parts)
        reason_1 = random.choice(SCRAP_REASONS)
        q1 = random.randint(1, 8)
        reason_2 = random.choice(SCRAP_REASONS) if random.random() > 0.6 else None
        q2 = random.randint(1, 4) if reason_2 else None
        reason_3 = random.choice(SCRAP_REASONS) if random.random() > 0.85 else None
        q3 = random.randint(1, 3) if reason_3 else None
        total = q1 + (q2 or 0) + (q3 or 0)
        records.append(ScrapRecord(
            record_date=day, operator_id=operator.id, machine_id=machine.id,
            work_order_number=random.choice(wo_numbers) if wo_numbers and random.random() > 0.2 else None,
            part_code=part.part_code, part_description=f"Peça {part.part_code}",
            supplier=part.supplier,
            reason_1=reason_1, quantity_1=q1, notes_1=None,
            reason_2=reason_2, quantity_2=q2, notes_2=None,
            reason_3=reason_3, quantity_3=q3, notes_3=None,
            total_quantity=total, pending=random.random() > 0.9, active=True,
        ))
    session.add_all(records)
    session.flush()
    return records


def generate_adjustments(session, operators, machines, work_orders, count: int = 220):
    """Generate time adjustments for the Ajustes module."""
    wo_numbers = [wo.order_number for wo in work_orders if wo.status != WorkOrderStatus.CANCELLED]
    adjustments = []
    for _ in range(count):
        day = random_date()
        operator = random.choice(operators)
        machine = random.choice(machines)
        prev = round(random.uniform(30, 600), 2)
        # 60% improvements, 40% worsenings
        if random.random() < 0.6:
            curr = round(prev * random.uniform(0.5, 0.95), 2)
        else:
            curr = round(prev * random.uniform(1.05, 1.5), 2)
        adjustments.append(TimeAdjustment(
            record_date=random_datetime(day),
            work_order_number=random.choice(wo_numbers) if wo_numbers and random.random() > 0.2 else None,
            operator_id=operator.id, machine_id=machine.id,
            part_code=f"PC-{random.randint(1, 50):04d}",
            part_description=f"Peça PC-{random.randint(1, 50):04d}",
            quantity=round(random.uniform(10, 500), 2),
            operation=random.choice(MACHINING_OPERATIONS),
            previous_time_seconds=prev, current_time_seconds=curr,
            justification=random.choice(ADJUSTMENT_JUSTIFICATIONS),
            active=True,
        ))
    session.add_all(adjustments)
    session.flush()
    return adjustments


def _write_dataset_version(session) -> None:
    """Record DATASET_VERSION so the bootstrap can detect stale datasets."""
    from sqlalchemy import text

    session.execute(
        text("CREATE TABLE IF NOT EXISTS dataset_meta (key VARCHAR PRIMARY KEY, value VARCHAR)")
    )
    session.execute(text("DELETE FROM dataset_meta WHERE key = 'dataset_version'"))
    session.execute(
        text("INSERT INTO dataset_meta (key, value) VALUES ('dataset_version', :v)"),
        {"v": str(DATASET_VERSION)},
    )


def run(seed: int = 42, reset: bool = False) -> None:
    """Generate the full dataset. Callable from code (e.g. the app bootstrap)."""
    random.seed(seed)
    fake = Faker("pt_BR")
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
        print("Generating compensation (cargos e salários) data...")
        generate_compensation(session, departments, employees)
        print("Generating projects...")
        generate_projects(session, fake, departments, employees)
        print("Generating maintenance activity...")
        generate_maintenance(session, fake, locations, employees)
        print("Generating quality activity...")
        generate_quality(session, fake, products, work_orders, employees, locations)
        print("Generating machining (usinagem) data...")
        machines, operators, occ_types = generate_machining(session, production_lines, employees, work_orders)
        print("Generating scrap (refugo) data...")
        generate_scrap(session, operators, machines, work_orders)
        print("Generating time adjustments (ajustes) data...")
        generate_adjustments(session, operators, machines, work_orders)
        print("Generating audit trail...")
        generate_audit_logs(session, fake, users)

        _write_dataset_version(session)
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
