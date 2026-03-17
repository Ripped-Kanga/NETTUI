from nettui.widgets.interface_detail import (
    _GRAPH_HEIGHT,
    _area_sparkline,
    _braille_line_graph,
    _fmt_rate,
)


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
    assert _fmt_rate(125, "bits") == "1.0 Kb/s"
    assert _fmt_rate(125_000, "bits") == "1.0 Mb/s"
    assert _fmt_rate(125_000_000, "bits") == "1.0 Gb/s"


def test_fmt_rate_bits_sub_kilo():
    assert _fmt_rate(10, "bits") == "80 b/s"


def test_braille_empty():
    rows = _braille_line_graph([], 10, 3)
    assert len(rows) == 3
    assert all(r == " " * 10 for r in rows)


def test_braille_row_count():
    rows = _braille_line_graph([1.0, 2.0, 3.0], 10, _GRAPH_HEIGHT)
    assert len(rows) == _GRAPH_HEIGHT


def test_braille_row_width():
    rows = _braille_line_graph([1.0, 2.0, 3.0], 10, 3)
    assert all(len(r) == 10 for r in rows)


def test_braille_all_zeros():
    rows = _braille_line_graph([0, 0, 0], 5, 3)
    # All values are 0 → dots at bottom row only (row 0 in dot space)
    # Bottom-left dots are still set since all map to dot position 0
    flat = "".join(rows)
    # At minimum the braille base (empty) should be present
    assert all(ord(c) >= 0x2800 or c == " " for c in flat)


def test_braille_max_value_at_top():
    # Single max value should place a dot in the top character row
    rows = _braille_line_graph([1.0], 5, 3)
    # The dot should be in the top row (row index 0), not just spaces
    top_row = rows[0]
    assert any(ord(c) > 0x2800 for c in top_row)


def test_braille_truncates_to_width():
    # Each char holds 2 data points, so 100 values need 50 chars → truncated to 20
    values = list(range(100))
    rows = _braille_line_graph(values, 20, 3)
    assert all(len(r) == 20 for r in rows)


def test_braille_ascending_values():
    # Ascending values: dots should trend upward (bottom-left to top-right)
    values = [float(i) for i in range(20)]
    rows = _braille_line_graph(values, 10, 3)
    # Bottom row should have dots on left side, top row on right side
    bottom = rows[-1]
    top = rows[0]
    # Left chars of bottom row should have dots
    assert any(ord(c) > 0x2800 for c in bottom[:5])
    # Right chars of top row should have dots
    assert any(ord(c) > 0x2800 for c in top[5:])


# ── Area sparkline tests ──


def test_area_empty():
    rows = _area_sparkline([], 10, 3)
    assert len(rows) == 3
    assert all(r == " " * 10 for r in rows)


def test_area_row_count():
    rows = _area_sparkline([1.0, 2.0, 3.0], 10, _GRAPH_HEIGHT)
    assert len(rows) == _GRAPH_HEIGHT


def test_area_row_width():
    rows = _area_sparkline([1.0, 2.0, 3.0], 10, 3)
    assert all(len(r) == 10 for r in rows)


def test_area_max_value_fills_all_rows():
    rows = _area_sparkline([0.0, 1.0, 0.0], 3, 3)
    assert rows[0][1] == "█"
    assert rows[1][1] == "█"
    assert rows[2][1] == "█"


def test_area_truncates_to_width():
    values = list(range(100))
    rows = _area_sparkline(values, 20, 3)
    assert all(len(r) == 20 for r in rows)
