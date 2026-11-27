"""Graphical interface for SIMPLE, launched with ``simple --gui``.

The interface drives the same UI-free import service as the CLI.
"""


def main():
    from simple.gui.app import run

    return run()
