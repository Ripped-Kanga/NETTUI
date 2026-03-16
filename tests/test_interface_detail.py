from nettui.widgets.interface_detail import _GRAPH_HEIGHT, _fmt_rate, _multirow_sparkline


def test_fmt_rate_bytes():
    assert _fmt_rate(0) == "0 B/s"
    assert _fmt_rate(512) == "512 B/s"
    assert _fmt_rate(1023) == "1023 B/s"


def test_fmt_rate_kilobytes():
    assert _fmt_rate(1024) == "1.0 KB/s"
    assert _fmt_rate(1536) == "1.5 KB/s"
    assert _fmt_rate(1_047_552) == "1023.0 KB/s"


def test_fmt_rate_megabytes():
    assert _fmt_rate(1_048_576) == "1.0 MB/s"
    assert _fmt_rate(10_485_760) == "10.0 MB/s"
    assert _fmt_rate(125_000_000) == "119.2 MB/s"


def test_fmt_rate_gigabytes():
    assert _fmt_rate(1_073_741_824) == "1.0 GB/s"
    assert _fmt_rate(1_073_741_824 * 10) == "10.0 GB/s"


def test_fmt_rate_bits_mode():
    # 1000 b/s boundary
    assert _fmt_rate(125, "bits") == "1.0 Kb/s"       # 125 B/s × 8 = 1000 b/s
    assert _fmt_rate(125_000, "bits") == "1.0 Mb/s"   # 125 KB/s × 8 = 1 Mb/s
    assert _fmt_rate(125_000_000, "bits") == "1.0 Gb/s"

def test_fmt_rate_bits_sub_kilo():
    assert _fmt_rate(10, "bits") == "80 b/s"           # 10 B/s × 8 = 80 b/s


def test_multirow_empty():
    rows = _multirow_sparkline([], 10, 3)
    assert len(rows) == 3
    assert all(r == " " * 10 for r in rows)


def test_multirow_row_count():
    rows = _multirow_sparkline([1.0, 2.0, 3.0], 10, _GRAPH_HEIGHT)
    assert len(rows) == _GRAPH_HEIGHT


def test_multirow_row_width():
    rows = _multirow_sparkline([1.0, 2.0, 3.0], 10, 3)
    assert all(len(r) == 10 for r in rows)


def test_multirow_all_zeros():
    rows = _multirow_sparkline([0, 0, 0], 5, 3)
    # max_val falls back to 1.0 → all sub_heights = 0 → every cell is a space
    assert all(c == " " for r in rows for c in r)


def test_multirow_full_value_fills_all_rows():
    # Max value should produce a full block in every row for that column.
    # data=[0,1,0] → no padding, chars at index 0/1/2 in each row.
    rows = _multirow_sparkline([0.0, 1.0, 0.0], 3, 3)
    assert rows[0][1] == "█"   # top row, centre column: full
    assert rows[1][1] == "█"   # middle row, centre column: full
    assert rows[2][1] == "█"   # bottom row, centre column: full
    assert rows[0][0] == " "   # neighbouring zero is empty
    assert rows[0][2] == " "


def test_multirow_half_value_fills_bottom_row_only():
    # values=[1.0, 2.0], max=2.0 → first sample maps to sub_height=8 (exactly half of 16)
    # row_floor=8 (top row): sh(8) <= 8 → empty
    # row_floor=0 (bottom row): sh(8) >= 8 → full block
    rows = _multirow_sparkline([1.0, 2.0], 2, 2)
    assert rows[0][0] == " "   # top row: half-value sample is empty
    assert rows[1][0] == "█"   # bottom row: half-value sample is full


def test_multirow_truncates_to_width():
    values = list(range(100))
    rows = _multirow_sparkline(values, 20, 3)
    assert all(len(r) == 20 for r in rows)
