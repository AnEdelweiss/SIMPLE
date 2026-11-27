"""Qt-free text helpers shared by the GUI modules."""

import re

RICH_TAGS = re.compile(
    r"\[/?(?:bold\s)?(?:green|red|cyan|yellow|blue|magenta|white)\]"
)


def clean_rich(text):
    """Strip the Rich markup the CLI-oriented backend adds to its messages."""
    return RICH_TAGS.sub("", str(text))
