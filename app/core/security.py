"""
Security module for Agentic AI Tutor.

Provides:
- JWT token generation and validation
- Password hashing with bcrypt
- API key encryption/decryption
- Security utilities
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import bcrypt
from jose import JWTError, jwt
from cryptography.fernet import Fernet
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenData(BaseModel):
    """JWT token payload data"""

    student_id: str
    email: Optional[str] = None
    exp: Optional[datetime] = None


class TokenResponse(BaseModel):
    """Token response model"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# JWT Configuration
DEFAULT_SECRET_KEY = "your-secret-key-change-in-production"

JWT_SECRET_KEY = settings.get("security.jwt_secret_key") or settings.secret_key
JWT_ALGORITHM = settings.get("security.jwt_algorithm", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = settings.get("security.access_token_expire_minutes", 30)
REFRESH_TOKEN_EXPIRE_DAYS = settings.get("security.refresh_token_expire_days", 7)


def check_jwt_secret() -> None:
    """
    Make sure the JWT signing key is not the shipped placeholder.

    Tokens signed with the default key can be forged by anyone who has read
    the repository, so refuse to start in production and warn elsewhere.
    """
    if JWT_SECRET_KEY != DEFAULT_SECRET_KEY:
        return

    if settings.environment == "production":
        raise RuntimeError(
            "SECRET_KEY is still the default placeholder. Set SECRET_KEY in the "
            "environment before running in production - JWTs signed with the "
            "default key can be forged by anyone."
        )

    logger.warning(
        "SECRET_KEY is the default placeholder - JWTs are forgeable. "
        "Set SECRET_KEY in your .env before deploying."
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password to compare

    Returns:
        bool: True if password matches
    """
    try:
        password_bytes = plain_password.encode("utf-8")
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        str: Hashed password
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Data to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        str: Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT refresh token.

    Args:
        data: Data to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        str: Encoded JWT refresh token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire, "type": "refresh"})

    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_tokens(student_id: str, email: Optional[str] = None) -> TokenResponse:
    """
    Create both access and refresh tokens for a student.

    Args:
        student_id: Student's unique ID
        email: Optional student email

    Returns:
        TokenResponse: Contains both tokens and metadata
    """
    token_data = {"sub": student_id, "email": email}

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token to verify
        token_type: Expected token type ("access" or "refresh")

    Returns:
        TokenData if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        # Verify token type
        if payload.get("type") != token_type:
            logger.warning(f"Invalid token type: expected {token_type}, got {payload.get('type')}")
            return None

        student_id: str = payload.get("sub")
        if student_id is None:
            logger.warning("Token missing 'sub' claim")
            return None

        return TokenData(
            student_id=student_id,
            email=payload.get("email"),
            exp=datetime.fromtimestamp(payload.get("exp", 0)),
        )

    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None


def refresh_access_token(refresh_token: str) -> Optional[TokenResponse]:
    """
    Generate new access token from refresh token.

    Args:
        refresh_token: Valid refresh token

    Returns:
        New TokenResponse if valid, None otherwise
    """
    token_data = verify_token(refresh_token, token_type="refresh")

    if token_data is None:
        return None

    return create_tokens(token_data.student_id, token_data.email)


# API Key Encryption
def get_fernet_cipher() -> Fernet:
    """Get Fernet cipher for API key encryption"""
    key = settings.secret_key
    # Ensure key is 32 bytes, base64-encoded
    if len(key) < 32:
        key = key.ljust(32, "0")
    elif len(key) > 32:
        key = key[:32]

    import base64

    fernet_key = base64.urlsafe_b64encode(key.encode())
    return Fernet(fernet_key)


def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt an API key for secure storage.

    Args:
        api_key: Plain text API key

    Returns:
        str: Encrypted API key
    """
    try:
        cipher = get_fernet_cipher()
        encrypted = cipher.encrypt(api_key.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Failed to encrypt API key: {e}")
        raise


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt an encrypted API key.

    Args:
        encrypted_key: Encrypted API key

    Returns:
        str: Decrypted API key
    """
    try:
        cipher = get_fernet_cipher()
        decrypted = cipher.decrypt(encrypted_key.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Failed to decrypt API key: {e}")
        raise


# Security Headers
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


def validate_password_strength(password: str) -> Dict[str, Any]:
    """
    Validate password strength.

    Args:
        password: Password to validate

    Returns:
        Dict with 'valid' boolean and 'errors' list
    """
    errors = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")

    if not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")

    if not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")

    if not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "strength": "strong" if len(errors) == 0 else "weak",
    }
