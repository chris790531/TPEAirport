from __future__ import annotations

from pathlib import Path

from python_calamine import CalamineWorkbook


def main() -> int:
    path = Path("data/sample.xls")
    wb = CalamineWorkbook.from_path(str(path))
    print("sheets:", wb.sheet_names)
    sheet = wb.get_sheet_by_index(0)
    rows = sheet.to_python()
    print("rows:", len(rows))
    for r in rows[:30]:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

