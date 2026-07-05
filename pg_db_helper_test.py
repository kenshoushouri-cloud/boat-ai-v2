from db_pg import fetch_all, fetch_one, upsert_rows


def main():
    print("=== db_pg helper test ===")

    rows = [
        {
            "venue_code": "99",
            "venue_name": "RailwayPGテスト場",
        }
    ]

    count = upsert_rows(
        table="v2_venues",
        rows=rows,
        conflict_cols=["venue_code"],
    )

    print(f"upsert_rows: OK count={count}")

    one = fetch_one(
        "select venue_code, venue_name from v2_venues where venue_code = %s;",
        ("99",),
    )

    print(f"fetch_one: {one}")

    all_rows = fetch_all(
        "select venue_code, venue_name from v2_venues order by venue_code;"
    )

    print(f"fetch_all rows={len(all_rows)}")
    for row in all_rows:
        print(row)

    print("=== db_pg helper test finished ===")


if __name__ == "__main__":
    main()