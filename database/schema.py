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

# North, South, East and West are US regions. India is a market of its own.
REGIONS = ["North", "South", "East", "West", "India"]

# US territories are assigned to the first four regions five at a time, in
# list order.
TERRITORY_NAMES = [
    "Boston", "Hartford", "Buffalo", "Pittsburgh", "Cleveland",
    "Atlanta", "Orlando", "Nashville", "Charlotte", "New Orleans",
    "New York", "Philadelphia", "Baltimore", "Newark", "Richmond",
    "Denver", "Phoenix", "Seattle", "San Diego", "Portland",
]

# India is generated after all the US data, from the same random stream, so
# adding it left every US figure unchanged.
INDIA_REGION_ID = REGIONS.index("India") + 1
INDIA_TERRITORY_NAMES = ["Mumbai", "Pune", "Delhi", "Bengaluru", "Chennai", "Hyderabad"]
INDIA_REPS = [("Sharma", "Ananya"), ("Iyer", "Karthik"), ("Reddy", "Vikram")]
INDIA_CUSTOMERS = 30
INDIA_ORDERS = 600
# Diabetes Care and Heart Health products are ordered more often in India.
INDIA_FOCUS = {"Diabetes Care": 3, "Heart Health": 2}

_IN_FIRST_NAMES = ["Aarav", "Kavya", "Rohan", "Isha", "Arjun", "Meera", "Karan", "Diya",
                   "Nikhil", "Sneha"]
_IN_LAST_NAMES = ["Sharma", "Iyer", "Mehta", "Reddy", "Nair", "Gupta", "Rao", "Kapoor",
                  "Das", "Joshi"]
_IN_CLINIC_NAMES = ["Lotus", "Sunrise", "Banyan", "Neem", "Lakeshore", "Greenfield",
                    "Crescent", "Silverline", "Harbour", "Meadow"]

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
    india_territories = [
        (f"T{len(territories) + i + 1:03d}", name, INDIA_REGION_ID)
        for i, name in enumerate(INDIA_TERRITORY_NAMES)
    ]
    conn.executemany(
        "INSERT INTO Territories (TerritoryID, TerritoryDescription, RegionID) "
        "VALUES (?, ?, ?)",
        territories + india_territories,
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
    india_reps = [
        (
            len(employees) + i + 1,
            last,
            first,
            "Sales Representative",
            (date(2023, 4, 3) + timedelta(days=61 * i)).isoformat(),
        )
        for i, (last, first) in enumerate(INDIA_REPS)
    ]
    conn.executemany(
        "INSERT INTO Employees (EmployeeID, LastName, FirstName, Title, HireDate) "
        "VALUES (?, ?, ?, ?, ?)",
        employees + india_reps,
    )

    # Each rep covers two territories; every territory has exactly one rep.
    emp_territories = [((i % 10) + 1, t[0]) for i, t in enumerate(territories)]
    emp_territories += [
        (india_reps[i % len(india_reps)][0], t[0]) for i, t in enumerate(india_territories)
    ]
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

    # India comes last so the random draws above, and every US figure, are
    # the same as before it was added.
    india_customers = []
    for i in range(INDIA_CUSTOMERS):
        territory_id, city, _ = india_territories[i % len(india_territories)]
        india_customers.append((
            f"C{len(customers) + i + 1:04d}",
            f"{rng.choice(_IN_CLINIC_NAMES)} {rng.choice(_CLINIC_KINDS)}",
            f"{rng.choice(_IN_FIRST_NAMES)} {rng.choice(_IN_LAST_NAMES)}",
            rng.choice(["Physician", "Pharmacy Lead", "Procurement Manager",
                        "Clinical Director"]),
            city,
            territory_id,
            "India",
        ))

    product_ids = [p[0] for p in products]
    weights = [INDIA_FOCUS.get(CATEGORIES[p[2] - 1][0], 1) for p in products]
    for order_id in range(len(orders) + 1, len(orders) + INDIA_ORDERS + 1):
        customer = india_customers[rng.randrange(len(india_customers))]
        customer_id, territory_id = customer[0], customer[5]
        order_date = start + timedelta(days=rng.randrange(730))
        orders.append((
            order_id,
            customer_id,
            territory_rep[territory_id],
            order_date.isoformat(),
            territory_id,
        ))
        line_count = rng.randint(1, 4)
        chosen: list[int] = []
        while len(chosen) < line_count:
            product_id = rng.choices(product_ids, weights)[0]
            if product_id not in chosen:
                chosen.append(product_id)
        for product_id in chosen:
            details.append((
                order_id,
                product_id,
                products[product_id - 1][3],
                rng.randint(1, 40),
                rng.choice([0.0, 0.0, 0.0, 0.05, 0.10]),
            ))

    conn.executemany(
        "INSERT INTO Customers (CustomerID, CompanyName, ContactName, ContactTitle, "
        "City, TerritoryID, Country) VALUES (?, ?, ?, ?, ?, ?, ?)",
        customers + india_customers,
    )
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
