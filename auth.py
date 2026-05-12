from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    # Downgrade to bcrypt_sha256 which handles long passwords automatically
    truncated = password[:72]
    return pwd_context.hash(truncated)

def verify_password(plain: str, hashed: str) -> bool:
    truncated = plain[:72]
    return pwd_context.verify(truncated, hashed)