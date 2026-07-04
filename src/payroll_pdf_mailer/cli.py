from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .core import (
    ConfigurationError,
    SmtpConfig,
    build_delivery_plan,
    format_plan_preview,
    send_delivery_plan,
)


def load_env_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Env file not found: {path}")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan payroll PDF e-mails and optionally send them via SMTP.",
    )
    parser.add_argument("--pdf-dir", type=Path, default=Path("beispiele/payslips"))
    parser.add_argument("--contacts", type=Path, default=Path("beispiele/contacts.csv"))
    parser.add_argument("--env-file", type=Path, help="Optional .env file with SMTP settings.")
    parser.add_argument("--send", action="store_true", help="Send real e-mails. Default is dry-run only.")
    parser.add_argument("--override-to", help="Send every group to one test recipient.")
    parser.add_argument("--bcc", help="Optional Bcc recipient for live sends.")
    parser.add_argument("--sleep", type=float, default=1.0, help="Seconds between live e-mails.")
    parser.add_argument("--log", type=Path, help="CSV log path for successful live sends.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.env_file:
            load_env_file(args.env_file)

        plan = build_delivery_plan(args.pdf_dir, args.contacts)
        print(format_plan_preview(plan, override_to=args.override_to))

        if not args.send:
            print("\nDRY RUN: Es wurden keine E-Mails versendet.")
            return 0

        smtp = SmtpConfig.from_env()
        result = send_delivery_plan(
            plan,
            smtp=smtp,
            override_to=args.override_to,
            bcc=args.bcc,
            sleep_seconds=args.sleep,
            log_path=args.log,
        )

        print(f"\nGesendete Dokumente: {len(result.sent)}")
        if result.errors:
            print("Fehler:")
            for error in result.errors:
                print(f"- {error.name} -> {error.email}: {error.message}")
            return 2
        return 0
    except (ConfigurationError, FileNotFoundError, OSError, ValueError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
