import csv
from io import StringIO

def stream_csv_records(csv_bytes: bytes):
    """
    CSV row generator auto-detect delimiter (comma, tab, pipe, semicolon etc).
    Returns normalized dict per row (lowercase headers).
    """

    text = csv_bytes.decode("utf-8", errors="ignore")
    sio = StringIO(text)

    # auto detect delimiter
    sample = text[:5000]  # read first few KB is enough
    dialect = csv.Sniffer().sniff(sample, delimiters=[",", "\t", ";", "|"])

    reader = csv.reader(sio, dialect)

    rows = list(reader)
    if not rows:
        return

    headers = [str(h).strip().lower() for h in rows[0]]

    for row in rows[1:]:
        yield {headers[i]: row[i] if i < len(row) else None for i in range(len(headers))}
