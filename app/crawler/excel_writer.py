import xlsxwriter
from io import BytesIO
import anyio


def _write_workbook_bytes(records, headers):
    """
    Writes Excel workbook with conditional formatting and a Legend sheet.
    Uses in-memory streaming for performance.
    """
    out = BytesIO()
    wb = xlsxwriter.Workbook(out, {'in_memory': True})

    # ========== Legend Sheet ==========
    legend_ws = wb.add_worksheet("Legend")

    title_fmt = wb.add_format({'bold': True, 'font_size': 14, 'align': 'left'})
    header_fmt = wb.add_format({'bold': True, 'bg_color': '#D9E1F2'})
    text_fmt = wb.add_format({'valign': 'vcenter', 'text_wrap': True})

    legend_ws.write("A1", "Validation Color Legend", title_fmt)

    legend_data = [
        ("✅ Success", "Light Green", "Row passed all validations."),
        ("⚠️ Warning", "Yellow", "Field type/regex/required validation failed."),
        ("❌ Duplicate", "Red", "Duplicate based on unique constraints."),
    ]

    # Table header
    legend_headers = ["Status", "Color", "Meaning"]
    for col_idx, header in enumerate(legend_headers):
        legend_ws.write(2, col_idx, header, header_fmt)

    color_formats = {
        "Light Green": wb.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'}),
        "Yellow": wb.add_format({'bg_color': '#FFF2CC', 'font_color': '#9C6500'}),
        "Red": wb.add_format({'bg_color': '#F4CCCC', 'font_color': '#9C0006'}),
    }

    # Fill rows
    for i, (status, color_name, meaning) in enumerate(legend_data, start=3):
        legend_ws.write(i, 0, status, text_fmt)
        legend_ws.write(i, 1, color_name, color_formats[color_name])
        legend_ws.write(i, 2, meaning, text_fmt)

    # Adjust Legend layout
    legend_ws.set_column("A:A", 20)
    legend_ws.set_column("B:B", 15)
    legend_ws.set_column("C:C", 60)

    # ========== Data Sheet ==========
    ws = wb.add_worksheet("ValidatedData")
    header_fmt = wb.add_format({'bold': True, 'bg_color': '#D9E1F2'})
    ws.freeze_panes(1, 0)

    # Write headers
    for c, h in enumerate(headers):
        ws.write(0, c, h, header_fmt)

    # Write data
    for r, rec in enumerate(records, start=1):
        for c, h in enumerate(headers):
            ws.write(r, c, rec.get(h))

    # ========== Conditional Formatting ==========
    last_row = len(records)
    last_col = len(headers) - 1
    col_letters = [xlsxwriter.utility.xl_col_to_name(c) for c in range(len(headers))]

    if "Valid" in headers and "Remarks" in headers:
        valid_col = headers.index("Valid")
        remarks_col = headers.index("Remarks")
        valid_letter = col_letters[valid_col]
        remarks_letter = col_letters[remarks_col]
        full_range = f"A2:{col_letters[last_col]}{last_row + 1}"

        # ✅ Green = Success
        ws.conditional_format(
            full_range,
            {
                "type": "formula",
                "criteria": f'=${valid_letter}2="Success"',
                "format": wb.add_format({"bg_color": "#C6EFCE", "font_color": "#006100"}),
            },
        )

        # ⚠️ Yellow = Fail (not duplicate)
        ws.conditional_format(
            full_range,
            {
                "type": "formula",
                "criteria": f'=AND(${valid_letter}2="Fail", ISERROR(SEARCH("duplicate", LOWER(${remarks_letter}2))))',
                "format": wb.add_format({"bg_color": "#FFF2CC", "font_color": "#9C6500"}),
            },
        )

        # ❌ Red = Duplicate
        ws.conditional_format(
            full_range,
            {
                "type": "formula",
                "criteria": f'=SEARCH("duplicate", LOWER(${remarks_letter}2))',
                "format": wb.add_format({"bg_color": "#F4CCCC", "font_color": "#9C0006"}),
            },
        )

    # Auto-fit columns
    for c, h in enumerate(headers):
        max_len = max(len(str(r.get(h, ""))) for r in records)
        ws.set_column(c, c, min(max_len + 2, 50))

    wb.close()
    out.seek(0)
    return out.getvalue()


async def write_validated_excel_stream(validated_records):
    """
    validated_records: list[dict]
    Returns: BytesIO (Excel file with conditional formatting + legend)
    """
    records = list(validated_records)
    if not records:
        return None
    headers = list(records[0].keys())

    # Run in a thread to keep async I/O non-blocking
    data = await anyio.to_thread.run_sync(_write_workbook_bytes, records, headers)
    return BytesIO(data)
