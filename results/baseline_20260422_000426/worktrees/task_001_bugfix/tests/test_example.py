from src.example import collect_enabled_flags, route_support_ticket, sanitize_filename


def test_collect_enabled_flags_filters_disabled_and_preserves_order():
    items = [
        {"name": "beta_mode", "enabled": True},
        {"name": "dark_launch", "enabled": False},
        {"name": "fast_path", "enabled": True},
    ]
    assert collect_enabled_flags(items) == ["beta_mode", "fast_path"]


def test_collect_enabled_flags_ignores_blank_names():
    items = [
        {"name": "alpha", "enabled": True},
        {"name": "   ", "enabled": True},
        {"name": "", "enabled": True},
    ]
    assert collect_enabled_flags(items) == ["alpha"]


def test_route_support_ticket_escalates_outage_language():
    ticket = {"message": "Login outage across customer accounts, urgent"}
    assert route_support_ticket(ticket) == "priority"


def test_route_support_ticket_refund_stays_billing():
    ticket = {"message": "Need a refund for duplicate charge"}
    assert route_support_ticket(ticket) == "billing"


def test_sanitize_filename_normalizes_spaces_and_separators():
    assert sanitize_filename("Quarterly Report Final.pdf") == "quarterly-report-final.pdf"


def test_sanitize_filename_collapses_mixed_separators():
    assert sanitize_filename("Team__Roadmap   v2 .md") == "team-roadmap-v2.md"