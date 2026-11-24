"""Experimental dashboard GUI for SIMPLE, launched with ``simple --gui2``.

This is an additive, opt-in interface: the original GUI (``simple --gui``) is
untouched. Both drive the same UI-free import service.
"""


def main():
    from simple.gui2.app import run

    return run()
