from concrete_pmm_pro.ui.crossbeam_pages import _joint_continuity_summary_rows


def test_ptqa1_joint_summary_compacts_passed_joint_rows() -> None:
    rows = [
        {
            "Joint s (m)": 3.0,
            "Segment": "S1",
            "Section ID": "CB-S01",
            "Tendon ID": "T1",
            "Continuity status": "PASS",
            "Issue": "OK",
        },
        {
            "Joint s (m)": 3.0,
            "Segment": "S2",
            "Section ID": "CB-H01",
            "Tendon ID": "T1",
            "Continuity status": "PASS",
            "Issue": "OK",
        },
        {
            "Joint s (m)": 3.0,
            "Segment": "S1",
            "Section ID": "CB-S01",
            "Tendon ID": "T2",
            "Continuity status": "PASS",
            "Issue": "OK",
        },
    ]

    assert _joint_continuity_summary_rows(rows) == [
        {
            "Joint s (m)": 3.0,
            "Adjacent segments": "S1 / S2",
            "Section IDs": "CB-H01 / CB-S01",
            "Tendons checked": 2,
            "Review rows": 0,
            "Status": "PASS",
            "Issue summary": "OK",
        }
    ]


def test_ptqa1_joint_summary_flags_any_review_required_rows() -> None:
    rows = [
        {
            "Joint s (m)": 7.0,
            "Segment": "S2",
            "Section ID": "CB-H01",
            "Tendon ID": "T1",
            "Continuity status": "PASS",
            "Issue": "OK",
        },
        {
            "Joint s (m)": 7.0,
            "Segment": "S3",
            "Section ID": "CB-H01",
            "Tendon ID": "T1",
            "Continuity status": "REVIEW REQUIRED",
            "Issue": "Internal tendon outside concrete",
        },
    ]

    summary = _joint_continuity_summary_rows(rows)

    assert summary[0]["Review rows"] == 1
    assert summary[0]["Status"] == "REVIEW REQUIRED"
    assert summary[0]["Issue summary"] == "Internal tendon outside concrete"
