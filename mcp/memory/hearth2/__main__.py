"""Offline commands; never fetch auth, contact a model, or overwrite a target."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path
from .backup import export_record, restore_record
from .schema import Schema, SchemaError
from .store import RecordError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ['init', 'export', 'restore', 'migrate']:
        command = commands.add_parser(name)
        command.add_argument('--database', type=Path, required=True)
        if name in {'export', 'restore'}:
            command.add_argument('--bundle', type=Path, required=True)
        if name == 'restore':
            command.add_argument('--controller-stopped', action='store_true')
        if name == 'migrate':
            command.add_argument('--target', type=int, choices=[0, 1], required=True)
            command.add_argument('--backup', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'init':
            Schema.initialize(args.database, enabled=True)
            result = {'initialized': True, 'schema_version': 1}
        elif args.command == 'export':
            result = export_record(args.database, args.bundle)
        elif args.command == 'restore':
            result = restore_record(args.bundle, args.database, controller_stopped=args.controller_stopped)
        else:
            Schema.migrate(args.database, args.target, backup_path=args.backup)
            result = {'schema_version': args.target, 'backup_preserved': True}
        print(json.dumps(result))
        return 0
    except (RecordError, SchemaError, OSError, sqlite3.DatabaseError):
        # Do not echo unexpected raw database/credential content from an import.
        print('Operation refused or failed; original data retained. Check paths, version and controller state.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
