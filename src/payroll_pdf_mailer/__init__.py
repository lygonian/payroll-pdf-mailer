"""Payroll PDF mail planning and dry-run-first delivery helpers."""

from .core import (
    Contact,
    DeliveryGroup,
    DeliveryPlan,
    PayrollDocument,
    SmtpConfig,
    build_delivery_plan,
    build_email_message,
    body_for_group,
    find_email_for_name,
    format_plan_preview,
    load_contacts,
    month_year_label,
    parse_file_info,
    send_delivery_plan,
    subject_for_group,
)

__all__ = [
    "Contact",
    "DeliveryGroup",
    "DeliveryPlan",
    "PayrollDocument",
    "SmtpConfig",
    "build_delivery_plan",
    "build_email_message",
    "body_for_group",
    "find_email_for_name",
    "format_plan_preview",
    "load_contacts",
    "month_year_label",
    "parse_file_info",
    "send_delivery_plan",
    "subject_for_group",
]
