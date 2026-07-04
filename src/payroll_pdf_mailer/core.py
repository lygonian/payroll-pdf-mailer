from __future__ import annotations

import csv
import datetime as dt
import io
import mimetypes
import os
import re
import smtplib
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import Iterable, Mapping

MONTHS_DE = {
    "01": "Januar",
    "02": "Februar",
    "03": "M\u00e4rz",
    "04": "April",
    "05": "Mai",
    "06": "Juni",
    "07": "Juli",
    "08": "August",
    "09": "September",
    "10": "Oktober",
    "11": "November",
    "12": "Dezember",
}

FILENAME_RE = re.compile(
    r"^(?P<mm>\d{2}) (?P<yyyy>\d{4}) Lohnabrechnung (?P<name>.+?)(?: - Korrektur)?\.pdf$",
    re.IGNORECASE,
)
RE_CORR_SUFFIX = re.compile(r" - Korrektur$", re.IGNORECASE)
RE_WS = re.compile(r"\s+")


class ConfigurationError(RuntimeError):
    """Raised when required live-mail configuration is missing."""


@dataclass(frozen=True)
class Contact:
    name: str
    email: str
    norm: str
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class PayrollDocument:
    path: Path
    employee_name: str
    month: str
    year: str
    is_correction: bool
    email: str | None = None

    @property
    def filename(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class DeliveryGroup:
    display_name: str
    email: str
    items: tuple[PayrollDocument, ...]


@dataclass(frozen=True)
class DeliveryPlan:
    groups: tuple[DeliveryGroup, ...]
    missing_contacts: tuple[PayrollDocument, ...]
    ignored_files: tuple[Path, ...]
    contacts_count: int
    file_count: int


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    sender: str
    sender_name: str = "Payroll Team"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "SmtpConfig":
        values = env or os.environ
        host = values.get("PAYROLL_SMTP_HOST", "").strip()
        user = values.get("PAYROLL_SMTP_USER", "").strip()
        password = values.get("PAYROLL_SMTP_PASS", "")
        sender = values.get("PAYROLL_SMTP_FROM", "").strip() or user
        sender_name = values.get("PAYROLL_SENDER_NAME", "Payroll Team").strip() or "Payroll Team"
        port_raw = values.get("PAYROLL_SMTP_PORT", "587").strip()

        missing = [
            name
            for name, value in (
                ("PAYROLL_SMTP_HOST", host),
                ("PAYROLL_SMTP_USER", user),
                ("PAYROLL_SMTP_PASS", password),
                ("PAYROLL_SMTP_FROM", sender),
            )
            if not value
        ]
        if missing:
            raise ConfigurationError("Missing SMTP configuration: " + ", ".join(missing))

        try:
            port = int(port_raw)
        except ValueError as exc:
            raise ConfigurationError("PAYROLL_SMTP_PORT must be an integer") from exc

        return cls(
            host=host,
            port=port,
            user=user,
            password=password,
            sender=sender,
            sender_name=sender_name,
        )


@dataclass(frozen=True)
class SendRecord:
    timestamp: str
    name: str
    email: str
    month: str
    year: str
    kind: str
    filename: str
    mode: str


@dataclass(frozen=True)
class SendError:
    name: str
    email: str
    message: str


@dataclass(frozen=True)
class SendResult:
    sent: tuple[SendRecord, ...]
    errors: tuple[SendError, ...]


def german_transliterate(value: str | None) -> str:
    if value is None:
        return ""
    replacements = {
        "\u00c4": "Ae",
        "\u00d6": "Oe",
        "\u00dc": "Ue",
        "\u00e4": "ae",
        "\u00f6": "oe",
        "\u00fc": "ue",
        "\u00df": "ss",
    }
    text = value
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def norm(value: str | None) -> str:
    return RE_WS.sub(" ", german_transliterate((value or "").strip()).lower()).strip()


def read_text_robust(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        lines: list[str] = []
        for line in raw.split(b"\n"):
            try:
                lines.append(line.decode("utf-8"))
            except UnicodeDecodeError:
                lines.append(line.decode("cp1252"))
        return "\n".join(lines)


def _pick(row: Mapping[str, str], *names: str) -> str:
    lowered = {key.strip().lower(): value for key, value in row.items() if key is not None}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            return value
    return ""


def load_contacts(path: Path) -> list[Contact]:
    if not path.exists():
        return []

    text = read_text_robust(path)
    contacts: list[Contact] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        name = _pick(row, "Name").strip()
        email = _pick(row, "Email", "E-Mail", "Mail").strip()
        if not name or not email:
            continue

        name_norm = norm(name)
        tokens = tuple(token for token in name_norm.split() if len(token) > 1)
        contacts.append(Contact(name=name, email=email, norm=name_norm, tokens=tokens))
    return contacts


def find_email_for_name(name: str, contacts: Iterable[Contact], threshold: float = 0.5) -> str | None:
    name_norm = norm(name)
    best_email: str | None = None
    best_score = 0.0

    for contact in contacts:
        if not contact.tokens:
            continue
        hits = sum(1 for token in contact.tokens if token in name_norm)
        score = hits / len(contact.tokens)
        if score > best_score:
            best_score = score
            best_email = contact.email

    return best_email if best_score >= threshold else None


def parse_file_info(path: Path, contacts: Iterable[Contact]) -> PayrollDocument | None:
    match = FILENAME_RE.match(path.name)
    if not match:
        return None

    name = match.group("name").strip()
    month = match.group("mm")
    year = match.group("yyyy")
    is_correction = bool(RE_CORR_SUFFIX.search(path.stem))
    email = find_email_for_name(name, contacts)
    return PayrollDocument(
        path=path,
        employee_name=name,
        month=month,
        year=year,
        is_correction=is_correction,
        email=email,
    )


def _document_sort_key(document: PayrollDocument) -> tuple[int, int, str]:
    return (int(document.year), int(document.month), document.path.name)


def build_delivery_plan(pdf_dir: Path, contacts_path: Path) -> DeliveryPlan:
    contacts = load_contacts(contacts_path)
    files = sorted(pdf_dir.glob("*.pdf")) if pdf_dir.exists() else []

    ignored_files: list[Path] = []
    missing_contacts: list[PayrollDocument] = []
    groups_by_email: dict[str, list[PayrollDocument]] = {}
    name_for_email: dict[str, str] = {}

    for path in files:
        info = parse_file_info(path, contacts)
        if info is None:
            ignored_files.append(path)
            continue
        if info.email is None:
            missing_contacts.append(info)
            continue
        groups_by_email.setdefault(info.email, []).append(info)
        name_for_email.setdefault(info.email, info.employee_name)

    groups = [
        DeliveryGroup(
            display_name=name_for_email[email],
            email=email,
            items=tuple(sorted(items, key=_document_sort_key)),
        )
        for email, items in groups_by_email.items()
    ]
    groups.sort(key=lambda group: (norm(group.display_name), group.email))

    return DeliveryPlan(
        groups=tuple(groups),
        missing_contacts=tuple(sorted(missing_contacts, key=_document_sort_key)),
        ignored_files=tuple(sorted(ignored_files)),
        contacts_count=len(contacts),
        file_count=len(files),
    )


def month_year_label(month: str, year: str) -> str:
    return f"{MONTHS_DE.get(month, month)} {year}"


def subject_for_group(items: Iterable[PayrollDocument]) -> str:
    documents = tuple(items)
    if not documents:
        return "Lohnabrechnung"

    newest = max(documents, key=_document_sort_key)
    label = month_year_label(newest.month, newest.year)
    has_correction = any(document.is_correction for document in documents)

    if len(documents) == 1 and not has_correction:
        return f"Lohnabrechnung {label}"
    if has_correction:
        return f"Lohnabrechnung {label} und Korrekturausdrucke"
    return f"Lohnabrechnungen bis {label}"


def body_for_group(name: str, items: Iterable[PayrollDocument], sender_name: str = "Payroll Team") -> str:
    first_name = (name or "").split()[0] if name else ""
    salutation = f"Hallo {first_name}" if first_name else "Hallo"
    lines: list[str] = []

    for document in sorted(items, key=_document_sort_key):
        label = month_year_label(document.month, document.year)
        if document.is_correction:
            label += " (Korrektur)"
        lines.append(f"- {label}")

    return (
        f"{salutation},\n\n"
        "anbei deine Lohnabrechnung(en):\n"
        f"{chr(10).join(lines)}\n\n"
        "Viele Gruesse\n"
        f"{sender_name}\n"
    )


def attach_pdf(message: EmailMessage, path: Path) -> None:
    content_type, _ = mimetypes.guess_type(str(path))
    if not content_type:
        content_type = "application/pdf"
    maintype, subtype = content_type.split("/", 1)
    message.add_attachment(
        path.read_bytes(),
        maintype=maintype,
        subtype=subtype,
        filename=path.name,
    )


def build_email_message(
    group: DeliveryGroup,
    smtp_from: str,
    sender_name: str = "Payroll Team",
    override_to: str | None = None,
    bcc: str | None = None,
    smtp_host: str | None = None,
) -> EmailMessage:
    if not group.items:
        raise ValueError("Delivery group has no documents")

    to_addr = override_to or group.email
    domain = smtp_host or (smtp_from.split("@", 1)[1] if "@" in smtp_from else "localhost")

    message = EmailMessage()
    message["Subject"] = subject_for_group(group.items)
    message["From"] = formataddr((sender_name, smtp_from))
    message["To"] = to_addr
    if bcc:
        message["Bcc"] = bcc
    message["Message-ID"] = make_msgid(domain=domain)
    message["Date"] = formatdate(localtime=True)
    message.set_content(body_for_group(group.display_name, group.items, sender_name))

    for document in sorted(group.items, key=_document_sort_key):
        attach_pdf(message, document.path)
    return message


def format_plan_preview(plan: DeliveryPlan, override_to: str | None = None) -> str:
    lines = [
        f"Gefundene PDF-Dateien: {plan.file_count}",
        f"Kontakt-Datensaetze: {plan.contacts_count}",
        f"Versand-Gruppen: {len(plan.groups)}",
    ]

    if plan.groups:
        lines.append("")
        lines.append("Vorschau:")
        for group in plan.groups:
            to_addr = override_to or group.email
            attachments = ", ".join(document.filename for document in group.items)
            lines.append(f"TO: {to_addr} | SUBJ: {subject_for_group(group.items)} | ATTACH: {attachments}")

    if plan.missing_contacts:
        lines.append("")
        lines.append("Ohne Kontaktzuordnung, wird uebersprungen:")
        for document in plan.missing_contacts:
            lines.append(f"- {document.filename} -> {document.employee_name}")

    if plan.ignored_files:
        lines.append("")
        lines.append("Ignorierte PDF-Dateien mit unerwartetem Namen:")
        for path in plan.ignored_files:
            lines.append(f"- {path.name}")

    return "\n".join(lines)


def send_delivery_plan(
    plan: DeliveryPlan,
    smtp: SmtpConfig,
    override_to: str | None = None,
    bcc: str | None = None,
    sleep_seconds: float = 1.0,
    log_path: Path | None = None,
) -> SendResult:
    context = ssl.create_default_context()
    sent_records: list[SendRecord] = []
    errors: list[SendError] = []

    with smtplib.SMTP(smtp.host, smtp.port, timeout=90) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(smtp.user, smtp.password)

        for group in plan.groups:
            to_addr = override_to or group.email
            try:
                message = build_email_message(
                    group,
                    smtp_from=smtp.sender,
                    sender_name=smtp.sender_name,
                    override_to=override_to,
                    bcc=bcc,
                    smtp_host=smtp.host,
                )
                refused = server.send_message(message)
                if refused:
                    errors.append(SendError(group.display_name, to_addr, f"Refused: {refused}"))
                    continue

                timestamp = dt.datetime.now().isoformat(timespec="seconds")
                for document in group.items:
                    sent_records.append(
                        SendRecord(
                            timestamp=timestamp,
                            name=document.employee_name,
                            email=document.email or "",
                            month=document.month,
                            year=document.year,
                            kind="Korrektur" if document.is_correction else "Normal",
                            filename=document.filename,
                            mode="Sammelmail",
                        )
                    )
            except Exception as exc:  # pragma: no cover - depends on live SMTP state
                errors.append(SendError(group.display_name, to_addr, str(exc)))

            time.sleep(max(sleep_seconds, 0.0))

    result = SendResult(sent=tuple(sent_records), errors=tuple(errors))
    if log_path and sent_records:
        write_send_log(log_path, sent_records)
    return result


def write_send_log(path: Path, records: Iterable[SendRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if new_file:
            writer.writerow(["timestamp", "name", "email", "mm", "yyyy", "typ", "datei", "modus"])
        for record in records:
            writer.writerow(
                [
                    record.timestamp,
                    record.name,
                    record.email,
                    record.month,
                    record.year,
                    record.kind,
                    record.filename,
                    record.mode,
                ]
            )
