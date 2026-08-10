from tether.__main__ import _build_parser


CORE_COMMANDS = ("send", "resolve", "inbox", "delivery", "dashboard")
INTERNAL_COMMANDS = (
    "collapse",
    "metadata",
    "tables",
    "delete",
    "reap",
    "serve",
    "mux",
    "agents",
    "konsole",
    "board",
)


def test_default_help_only_bills_the_small_public_surface():
    help_text = _build_parser().format_help()

    for command in CORE_COMMANDS:
        assert command in help_text
    for command in INTERNAL_COMMANDS:
        assert f"    {command:<19}" not in help_text
    assert "==SUPPRESS==" not in help_text


def test_extended_help_exposes_compatibility_and_operator_commands():
    help_text = _build_parser(show_internal=True).format_help()

    for command in CORE_COMMANDS + INTERNAL_COMMANDS:
        assert command in help_text


def test_hidden_commands_remain_parseable_for_compatibility():
    args = _build_parser().parse_args(["metadata", "h&l_messages_example"])

    assert args.command == "metadata"
    assert args.handle == "h&l_messages_example"


def test_dashboard_is_explicit():
    args = _build_parser().parse_args(["dashboard"])

    assert args.command == "dashboard"
