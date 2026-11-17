# SPDX-License-Identifier: AGPL-3.0-or-later
"""Small admin CLI.

python -m app.cli make-admin user@example.com
python -m app.cli gen-key            # prints a fresh BYOK_ENCRYPTION_KEY
"""

import asyncio
import sys

from cryptography.fernet import Fernet
from sqlalchemy import select

from app import db
from app.models import User


async def make_admin(email: str) -> int:
    async with db.session_factory()() as session:
        user = (
            await session.execute(select(User).where(User.email == email.lower()))
        ).scalar_one_or_none()
        if user is None:
            print("no such user")
            return 1
        user.is_admin = True
        await session.commit()
    print("ok")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "make-admin":
        return asyncio.run(make_admin(argv[1]))
    if argv == ["gen-key"]:
        print(Fernet.generate_key().decode())
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
