"""Step 02 existing-panel rectangle check (offline): the 7 rectangles found on the Institut, 27 Nov 2026."""
from step02_pv_capacity import existing_panels as ep


def _rect(cx, cy, panels, ripple, raised, half=1.0):
    corners = [[cx - half, cy - half], [cx + half, cy - half], [cx + half, cy + half], [cx - half, cy + half], [cx - half, cy - half]]
    return {"corners": corners, "panels_estimate": panels, "lidar_ripple_m": ripple, "raised_share": raised}


# panels, LiDAR ripple (m) and share of cells raised > 0.1 m, as measured on the Institut (step 02 README)
INSTITUT = {1: (60, 0.068, 0.0), 2: (16, 0.067, 0.0), 3: (10, 0.065, 0.0),
            4: (8, 0.142, 0.12), 5: (5, 0.042, 0.0), 6: (4, 0.167, 0.27), 7: (2, 0.117, 0.31)}


def test_rule_keeps_the_3_real_rectangles_and_drops_the_4_false_ones():
    kept = {i for i, (n, rip, up) in INSTITUT.items() if ep.rectangle_rejected(_rect(0, 0, n, rip, up)) is None}
    assert kept == {1, 2, 3}                               # Breno checked by eye, 27 Nov 2026
    assert "rough" in ep.rectangle_rejected(_rect(0, 0, *INSTITUT[4]))
    assert "fewer than" in ep.rectangle_rejected(_rect(0, 0, *INSTITUT[5]))


def test_rule_keeps_steep_and_flat_real_blocks_on_the_red_roof():
    # Escola Pere IV: a 75-panel block with steep rows (ripple 0.26 m, nothing raised) and a flat 18-panel block
    assert ep.rectangle_rejected(_rect(0, 0, 75, 0.260, 0.0)) is None
    assert ep.rectangle_rejected(_rect(0, 0, 18, 0.013, 0.0)) is None


def test_not_panels_csv_matches_one_rectangle_not_its_neighbour():
    listed = [(10.0, 0.0, 2.0, "not panels: checked by eye")]
    look_alike = _rect(10.0, 0.0, 20, 0.07, 0.0)           # big and smooth, but listed by hand
    neighbour = _rect(4.0, 0.0, 20, 0.07, 0.0, half=2.5)   # its edge is 3.5 m from the listed point, centre 6 m
    assert ep.rectangle_rejected(look_alike, listed).startswith("not_panels.csv")
    assert ep.rectangle_rejected(neighbour, listed) is None


def test_institut_is_listed_in_not_panels_csv():
    rows = ep.load_not_panels("3241428DF3834A")
    assert len(rows) == 4 and all("checked by eye, Breno 27 Nov 2026" in w for *_, w in rows)
