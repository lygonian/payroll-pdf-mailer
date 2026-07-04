from pathlib import Path

from payroll_pdf_mailer.core import (
    Contact,
    DeliveryGroup,
    PayrollDocument,
    build_delivery_plan,
    build_email_message,
    find_email_for_name,
    format_plan_preview,
    subject_for_group,
)


PDF_BYTES = b"%PDF-1.4\n% synthetic test pdf\n%%EOF\n"


def write_pdf(path: Path) -> None:
    path.write_bytes(PDF_BYTES)


def test_build_delivery_plan_groups_by_email_and_keeps_newest_subject(tmp_path: Path) -> None:
    contacts = tmp_path / "contacts.csv"
    contacts.write_text(
        "Name,Email\n"
        "Mitarbeiter Alpha,mitarbeiter-alpha@example.test\n"
        "Mitarbeiter Beta,mitarbeiter-beta@example.test\n",
        encoding="utf-8",
    )
    pdf_dir = tmp_path / "payslips"
    pdf_dir.mkdir()
    write_pdf(pdf_dir / "06 2026 Lohnabrechnung Mitarbeiter Alpha.pdf")
    write_pdf(pdf_dir / "05 2026 Lohnabrechnung Mitarbeiter Alpha - Korrektur.pdf")
    write_pdf(pdf_dir / "06 2026 Lohnabrechnung Mitarbeiter Beta.pdf")
    write_pdf(pdf_dir / "sonstiges.pdf")

    plan = build_delivery_plan(pdf_dir, contacts)

    assert plan.file_count == 4
    assert len(plan.groups) == 2
    assert len(plan.ignored_files) == 1
    employee_group = next(group for group in plan.groups if group.email == "mitarbeiter-alpha@example.test")
    assert len(employee_group.items) == 2
    assert subject_for_group(employee_group.items) == "Lohnabrechnung Juni 2026 und Korrekturausdrucke"


def test_missing_contact_is_reported_and_not_grouped(tmp_path: Path) -> None:
    contacts = tmp_path / "contacts.csv"
    contacts.write_text("Name,Email\nMitarbeiter Alpha,mitarbeiter-alpha@example.test\n", encoding="utf-8")
    pdf_dir = tmp_path / "payslips"
    pdf_dir.mkdir()
    write_pdf(pdf_dir / "06 2026 Lohnabrechnung Kontakt Ohne Zuordnung.pdf")

    plan = build_delivery_plan(pdf_dir, contacts)

    assert not plan.groups
    assert [doc.employee_name for doc in plan.missing_contacts] == ["Kontakt Ohne Zuordnung"]
    preview = format_plan_preview(plan)
    assert "Ohne Kontaktzuordnung" in preview


def test_name_matching_transliterates_german_names() -> None:
    contacts = [
        Contact(
            name="Kontakt Ueber",
            email="kontakt-ueber@example.test",
            norm="kontakt ueber",
            tokens=("kontakt", "ueber"),
        )
    ]

    assert find_email_for_name("Kontakt \u00dcber", contacts) == "kontakt-ueber@example.test"


def test_build_email_message_adds_grouped_pdf_attachments(tmp_path: Path) -> None:
    first_pdf = tmp_path / "06 2026 Lohnabrechnung Mitarbeiter Alpha.pdf"
    correction_pdf = tmp_path / "05 2026 Lohnabrechnung Mitarbeiter Alpha - Korrektur.pdf"
    write_pdf(first_pdf)
    write_pdf(correction_pdf)
    group = DeliveryGroup(
        display_name="Mitarbeiter Alpha",
        email="mitarbeiter-alpha@example.test",
        items=(
            PayrollDocument(first_pdf, "Mitarbeiter Alpha", "06", "2026", False, "mitarbeiter-alpha@example.test"),
            PayrollDocument(correction_pdf, "Mitarbeiter Alpha", "05", "2026", True, "mitarbeiter-alpha@example.test"),
        ),
    )

    message = build_email_message(
        group,
        smtp_from="payroll@example.test",
        sender_name="Payroll Demo Team",
        override_to="audit@example.test",
        smtp_host="smtp.example.test",
    )

    assert message["To"] == "audit@example.test"
    assert message["Subject"] == "Lohnabrechnung Juni 2026 und Korrekturausdrucke"
    assert len(list(message.iter_attachments())) == 2
