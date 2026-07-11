"""
Password hashing, verification, and strength policy utilities using Argon2id and bcrypt.
"""
import re
import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Initialize Argon2id password hasher
ph = PasswordHasher()


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using Argon2id.

    Args:
        password: The plaintext password to hash.

    Returns:
        The Argon2id-hashed password string.
    """
    return ph.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plaintext password against an Argon2id or bcrypt hash.

    Args:
        plain: The plaintext password to verify.
        hashed: The hashed password to compare against.

    Returns:
        True if the password matches, False otherwise.
    """
    if hashed.startswith("$argon2"):
        try:
            return ph.verify(hashed, plain)
        except VerifyMismatchError:
            return False
        except Exception:
            return False
    else:
        # Fallback to legacy bcrypt for existing database users
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False


def validate_password_strength(password: str, user_details: dict) -> list[str]:
    """
    Validate password strength based on corporate security policies:
    - Min 12 characters
    - Must contain uppercase, lowercase, numbers, and special characters
    - Must not contain user's name, email, employee code, etc.
    - Must not contain dictionary terms
    """
    errors = []
    if len(password) < 12:
        errors.append("Password must be at least 12 characters long.")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one number.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("Password must contain at least one special character.")

    # Exclusions check
    for field_name, value in user_details.items():
        if value and len(str(value)) >= 3:
            clean_val = str(value).strip().lower()
            if clean_val in password.lower():
                errors.append(f"Password must not contain the employee's {field_name}.")

    # Common terms check
    common_words = ["password", "sakra", "finance", "admin", "welcome", "employee", "12345", "qwerty"]
    for word in common_words:
        if word in password.lower():
            errors.append(f"Password must not contain the standard dictionary word '{word}'.")

    return errors
