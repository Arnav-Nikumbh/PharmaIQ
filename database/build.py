"""Create the local database file. Run: uv run python -m database.build"""

import config
from database.db_manager import DBManager, build_database


def main() -> None:
    build_database(config.DB_PATH)
    db = DBManager(config.DB_PATH)
    rows = db.execute_select(
        "SELECT c.CategoryName, "
        "ROUND(SUM(d.UnitPrice * d.Quantity * (1 - d.Discount)), 2) AS TotalSales "
        "FROM OrderDetails d "
        "JOIN Products p ON p.ProductID = d.ProductID "
        "JOIN Categories c ON c.CategoryID = p.CategoryID "
        "GROUP BY c.CategoryName ORDER BY TotalSales DESC"
    )
    print(f"Database built at {config.DB_PATH}")
    print("Total sales by therapy area:")
    for row in rows:
        print(f"  {row['CategoryName']:<20} {row['TotalSales']:>14,.2f}")


if __name__ == "__main__":
    main()
