"""Local operator entry point for synthetic transactions."""

import argparse
import re
from uuid import UUID

from sqlalchemy import select

from app.core.config import Settings
from app.db.session import Database
from app.models.exam_access import PaymentTransaction
from app.services.exam_access import AccessError, settle_mock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payment", help="Payment UUID or displayed MOCK reference")
    parser.add_argument("outcome", choices=["SUCCESSFUL", "FAILED", "CANCELLED"])
    args = parser.parse_args()
    settings = Settings()
    if not settings.mock_allowed:
        parser.exit(1, "MOCK_DISABLED\n")
    db = Database(settings)
    try:
        try:
            identifier = UUID(args.payment)
        except ValueError:
            if not re.fullmatch(r"MOCK-[0-9a-f]{32}", args.payment):
                parser.exit(1, "INVALID_PAYMENT_REFERENCE\n")
            with db.session_factory() as lookup:
                identifier = lookup.scalar(
                    select(PaymentTransaction.id).where(
                        PaymentTransaction.reference == args.payment
                    )
                )
            if identifier is None:
                parser.exit(1, "PAYMENT_NOT_FOUND\n")
        with db.session_factory() as session:
            result = settle_mock(session, settings, identifier, args.outcome)
        if isinstance(result, AccessError):
            parser.exit(1, result.code + "\n")
        print(f"Mock transaction {result['id']} is {result['status']}. No funds moved.")
    except AccessError as error:
        parser.exit(1, error.code + "\n")
    finally:
        db.dispose()


if __name__ == "__main__":
    main()
