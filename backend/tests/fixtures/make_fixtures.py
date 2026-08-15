"""Regenerate the PDF test fixtures.

    python -m tests.fixtures.make_fixtures

The generated PDFs are committed, so the test suite needs neither `fpdf2` nor
this script. Run it when a fixture needs to change.

Four documents, each standing for a real failure mode:

- `clean_table.pdf`   the happy path, ISO dates, one row per meal
- `units_per_100g.pdf` units in the header, per-100g values, a serving column,
                       DD/MM dates where one value proves the order
- `prose_diary.pdf`   no table at all
- `scanned.pdf`       a page with no text layer
"""

from pathlib import Path

from fpdf import FPDF

HERE = Path(__file__).parent


def _pdf() -> FPDF:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    return pdf


def _table(pdf: FPDF, headers: list[str], rows: list[list[str]], widths: list[int]) -> None:
    pdf.set_font("Helvetica", style="B", size=10)
    for header, width in zip(headers, widths, strict=True):
        pdf.cell(width, 7, header, border=1)
    pdf.ln()

    pdf.set_font("Helvetica", size=10)
    for row in rows:
        for cell, width in zip(row, widths, strict=True):
            pdf.cell(width, 6, cell, border=1)
        pdf.ln()


def clean_table() -> None:
    pdf = _pdf()
    pdf.set_font("Helvetica", style="B", size=14)
    pdf.cell(0, 10, "Food Diary", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    _table(
        pdf,
        ["Date", "Meal", "Food", "Calories", "Protein", "Carbs", "Fat"],
        [
            ["2026-06-15", "Breakfast", "Porridge with banana", "320", "11", "54", "6"],
            ["2026-06-15", "Lunch", "Chicken salad", "480", "42", "18", "26"],
            ["2026-06-15", "Dinner", "Salmon and rice", "610", "44", "45", "26"],
            ["2026-06-16", "Breakfast", "Greek yoghurt", "210", "18", "24", "4"],
            ["2026-06-16", "Lunch", "Turkey sandwich", "520", "30", "55", "18"],
            ["2026-06-16", "Dinner", "Dal and rice", "540", "18", "84", "13"],
            ["2026-06-17", "Snack", "Almonds", "170", "6", "6", "15"],
        ],
        [26, 22, 52, 22, 20, 20, 18],
    )
    pdf.output(str(HERE / "clean_table.pdf"))


def units_per_100g() -> None:
    pdf = _pdf()
    pdf.set_font("Helvetica", style="B", size=14)
    pdf.cell(0, 10, "Nutrition Log (per 100g)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    _table(
        pdf,
        # Real nutrition tables label the basis on the columns, not just the
        # title — which is also what makes it detectable.
        ["Day", "Item", "Serving (g)", "Energy (kcal per 100g)", "Protein (g per 100g)"],
        [
            # 15/06 is unambiguous only via 25/06 below, which proves day-first.
            ["15/06/2026", "Cheddar", "30", "410", "25"],
            ["25/06/2026", "Oat flakes", "50", "380", "13"],
            ["25/06/2026", "Peanut butter", "20", "590", "25"],
            ["26/06/2026", "Greek yoghurt", "150", "97", "9"],
        ],
        [30, 38, 26, 48, 44],
    )
    pdf.output(str(HERE / "units_per_100g.pdf"))


def prose_diary() -> None:
    pdf = _pdf()
    pdf.set_font("Helvetica", style="B", size=14)
    pdf.cell(0, 10, "My week of eating", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", size=11)
    for line in [
        "2026-06-15",
        "Breakfast",
        "Porridge with banana - 320 cal",
        "Black coffee - 5 cal",
        "Lunch",
        "Chicken salad - 480 cal",
        "Dinner",
        "Salmon and rice - 610 cal",
        "",
        "2026-06-16",
        "Breakfast",
        "Greek yoghurt with berries - 210 cal",
        "Lunch",
        "Turkey sandwich - 520 cal",
    ]:
        pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(HERE / "prose_diary.pdf"))


def scanned() -> None:
    """A page with no text layer, standing in for a scan."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(210, 210, 210)
    pdf.rect(20, 20, 170, 120, style="F")
    pdf.output(str(HERE / "scanned.pdf"))


if __name__ == "__main__":
    clean_table()
    units_per_100g()
    prose_diary()
    scanned()
    print(f"Wrote fixtures to {HERE}")
