import argparse

from simple.cli import main as cli_main


def main():
    parser = argparse.ArgumentParser(description="SIMPLE - Scientific data import tool")
    parser.add_argument(
        "--gui", 
        action="store_true", 
        help="Launch the graphical user interface"
    )

    parser.add_argument(
        "--gui2",
        action="store_true",
        help="Launch the experimental dashboard interface (preview)",
    )
    
    parser.add_argument(
        "--dry-run",
        metavar="FOLDER",
        help="Validate an experiment folder offline (no login, nothing uploaded)",
    )

    # Parse known args in case uv passes extra arguments
    args, unknown = parser.parse_known_args()

    if args.dry_run:
        from simple.dry_run import dry_run
        from simple.errors import SimpleBaseException

        try:
            lines, ok = dry_run(args.dry_run)
        except SimpleBaseException as e:
            raise SystemExit(f"Dry run failed: {e}")
        print("\n".join(lines))
        raise SystemExit(0 if ok else 1)
    if args.gui:
        from simple.gui import main as gui_main
        gui_main()
    elif args.gui2:
        from simple.gui2 import main as gui2_main
        raise SystemExit(gui2_main())
    else:
        cli_main()

if __name__ == "__main__":
    main()