"""Table definitions and seed data for the internal business database.

The table and column names deliberately follow the Northwind sample database's
shape and casing. The rows seeded into them are synthetic pharmaceutical
commercial data. Nothing here is real business data of any kind.
"""

import random
import sqlite3
from datetime import date, timedelta

TABLES = (
    "Categories",
    "Region",
    "Territories",
    "Employees",
    "EmployeeTerritories",
    "Customers",
    "Products",
    "Orders",
    "OrderDetails",
)

DDL = """
CREATE TABLE Categories (
    CategoryID   INTEGER PRIMARY KEY,
    CategoryName TEXT NOT NULL,
    Description  TEXT
);

CREATE TABLE Region (
    RegionID          INTEGER PRIMARY KEY,
    RegionDescription TEXT NOT NULL
);

CREATE TABLE Territories (
    TerritoryID          TEXT PRIMARY KEY,
    TerritoryDescription TEXT NOT NULL,
    RegionID             INTEGER NOT NULL REFERENCES Region(RegionID)
);

CREATE TABLE Employees (
    EmployeeID INTEGER PRIMARY KEY,
    LastName   TEXT NOT NULL,
    FirstName  TEXT NOT NULL,
    Title      TEXT,
    HireDate   TEXT
);

CREATE TABLE EmployeeTerritories (
    EmployeeID  INTEGER NOT NULL REFERENCES Employees(EmployeeID),
    TerritoryID TEXT NOT NULL REFERENCES Territories(TerritoryID),
    PRIMARY KEY (EmployeeID, TerritoryID)
);

CREATE TABLE Customers (
    CustomerID   TEXT PRIMARY KEY,
    CompanyName  TEXT NOT NULL,
    ContactName  TEXT,
    ContactTitle TEXT,
    City         TEXT,
    TerritoryID  TEXT REFERENCES Territories(TerritoryID),
    Country      TEXT
);

CREATE TABLE Products (
    ProductID    INTEGER PRIMARY KEY,
    ProductName  TEXT NOT NULL,
    CategoryID   INTEGER NOT NULL REFERENCES Categories(CategoryID),
    UnitPrice    REAL NOT NULL,
    Discontinued INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE Orders (
    OrderID     INTEGER PRIMARY KEY,
    CustomerID  TEXT NOT NULL REFERENCES Customers(CustomerID),
    EmployeeID  INTEGER NOT NULL REFERENCES Employees(EmployeeID),
    OrderDate   TEXT NOT NULL,
    TerritoryID TEXT NOT NULL REFERENCES Territories(TerritoryID)
);

CREATE TABLE OrderDetails (
    OrderID   INTEGER NOT NULL REFERENCES Orders(OrderID),
    ProductID INTEGER NOT NULL REFERENCES Products(ProductID),
    UnitPrice REAL NOT NULL,
    Quantity  INTEGER NOT NULL,
    Discount  REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (OrderID, ProductID)
);
"""

SEED = 42

CATEGORIES = [
    ("Weight Management", "Treatments that support weight loss and obesity care"),
    ("Diabetes Care", "Treatments for blood sugar control"),
    ("Heart Health", "Treatments for blood pressure and cholesterol"),
    ("Cancer Care", "Treatments used in cancer therapy"),
    ("Respiratory", "Treatments for asthma and lung conditions"),
    ("Mental Health", "Treatments for mood, anxiety and sleep"),
    ("Pain Relief", "Treatments for short and long term pain"),
    ("Infection Control", "Antibiotic and antiviral treatments"),
    ("Bone and Joint", "Treatments for arthritis and bone density"),
    ("Skin Care", "Treatments for skin conditions"),
]

REGIONS = ["North", "South", "East", "West"]

# Territories are assigned to regions five at a time, in list order.
TERRITORY_NAMES = [
    "Boston", "Hartford", "Buffalo", "Pittsburgh", "Cleveland",
    "Atlanta", "Orlando", "Nashville", "Charlotte", "New Orleans",
    "New York", "Philadelphia", "Baltimore", "Newark", "Richmond",
    "Denver", "Phoenix", "Seattle", "San Diego", "Portland",
]

_PREFIXES = ["Ava", "Cardi", "Dermi", "Gluco", "Neuro", "Onco", "Pulmo", "Rheu", "Somni", "Vaso"]
_SUFFIXES = ["dex", "lex", "min", "nix", "prin", "sar", "tide", "vir", "zan", "zole"]

_CLINIC_KINDS = ["Clinic", "Medical Group", "Health Center", "Hospital", "Care Partners"]
_CITY_ADJECTIVES = ["Riverside", "Lakeview", "Summit", "Fairview", "Northgate", "Oakwood",
                    "Brookside", "Highland", "Parkway", "Westfield"]

_FIRST_NAMES = ["Alex", "Priya", "Jordan", "Mei", "Sam", "Ana", "Chris", "Nadia", "Ravi", "Elena"]
_LAST_NAMES = ["Reyes", "Patel", "Okafor", "Nguyen", "Silva", "Haddad", "Kim", "Novak",
               "Ibrahim", "Costa"]


def create_tables(conn: sqlite3.Connection) -> None:
    """Drop and recreate every table. Safe to call repeatedly."""
    for table in reversed(TABLES):
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.executescript(DDL)
    conn.commit()


def seed(conn: sqlite3.Connection) -> None:
    """Populate every table with deterministic synthetic data."""
    rng = random.Random(SEED)

    conn.executemany(
        "INSERT INTO Categories (CategoryID, CategoryName, Description) VALUES (?, ?, ?)",
        [(i + 1, name, desc) for i, (name, desc) in enumerate(CATEGORIES)],
    )

    conn.executemany(
        "INSERT INTO Region (RegionID, RegionDescription) VALUES (?, ?)",
        [(i + 1, name) for i, name in enumerate(REGIONS)],
    )

    territories = []
    for i, name in enumerate(TERRITORY_NAMES):
        territories.append((f"T{i + 1:03d}", name, (i // 5) + 1))
    conn.executemany(
        "INSERT INTO Territories (TerritoryID, TerritoryDescription, RegionID) "
        "VALUES (?, ?, ?)",
        territories,
    )

    employees = [
        (
            i + 1,
            _LAST_NAMES[i],
            _FIRST_NAMES[i],
            "Sales Representative",
            (date(2020, 1, 6) + timedelta(days=97 * i)).isoformat(),
        )
        for i in range(10)
    ]
    conn.executemany(
        "INSERT INTO Employees (EmployeeID, LastName, FirstName, Title, HireDate) "
        "VALUES (?, ?, ?, ?, ?)",
        employees,
    )

    # Each rep covers two territories; every territory has exactly one rep.
    emp_territories = [((i % 10) + 1, t[0]) for i, t in enumerate(territories)]
    conn.executemany(
        "INSERT INTO EmployeeTerritories (EmployeeID, TerritoryID) VALUES (?, ?)",
        emp_territories,
    )

    products = []
    used_names = set()
    for i in range(60):
        while True:
            name = (
                f"{rng.choice(_PREFIXES)}{rng.choice(_SUFFIXES)} "
                f"{rng.choice([5, 10, 25, 50, 100, 250])}mg"
            )
            if name not in used_names:
                used_names.add(name)
                break
        products.append((
            i + 1,
            name,
            (i % 10) + 1,
            round(rng.uniform(12.0, 480.0), 2),
            1 if rng.random() < 0.05 else 0,
        ))
    conn.executemany(
        "INSERT INTO Products (ProductID, ProductName, CategoryID, UnitPrice, Discontinued) "
        "VALUES (?, ?, ?, ?, ?)",
        products,
    )

    customers = []
    for i in range(90):
        territory_id, city, _ = territories[i % len(territories)]
        customers.append((
            f"C{i + 1:04d}",
            f"{rng.choice(_CITY_ADJECTIVES)} {rng.choice(_CLINIC_KINDS)}",
            f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}",
            rng.choice(["Physician", "Pharmacy Lead", "Procurement Manager",
                        "Clinical Director"]),
            city,
            territory_id,
            "USA",
        ))
    conn.executemany(
        "INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, "
        "City, TerritoryID, Country) VALUES (?, ?, ?, ?, ?, ?, ?)",
        customers,
    )

    territory_rep = {t_id: emp_id for emp_id, t_id in emp_territories}
    start = date(2024, 10, 1)
    orders = []
    details = []
    for order_id in range(1, 3001):
        customer = customers[rng.randrange(len(customers))]
        customer_id, territory_id = customer[0], customer[5]
        order_date = start + timedelta(days=rng.randrange(730))
        orders.append((
            order_id,
            customer_id,
            territory_rep[territory_id],
            order_date.isoformat(),
            territory_id,
        ))
        for product_id in rng.sample(range(1, 61), rng.randint(1, 4)):
            details.append((
                order_id,
                product_id,
                products[product_id - 1][3],
                rng.randint(1, 40),
                rng.choice([0.0, 0.0, 0.0, 0.05, 0.10]),
            ))
    conn.executemany(
        "INSERT INTO Orders (OrderID, CustomerID, EmployeeID, OrderDate, TerritoryID) "
        "VALUES (?, ?, ?, ?, ?)",
        orders,
    )
    conn.executemany(
        "INSERT INTO OrderDetails (OrderID, ProductID, UnitPrice, Quantity, Discount) "
        "VALUES (?, ?, ?, ?, ?)",
        details,
    )

    conn.commit()
