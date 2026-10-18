import os
import json
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Process-level in-memory cache for parsed database secret configuration.
# Documented refresh behavior:
# Credentials are cached per process to prevent querying AWS Secrets Manager
# on every HTTP request. To refresh credentials after a rotation in Secrets Manager,
# restart or gracefully reload the application service (e.g. systemctl reload event-management),
# or invoke get_db_credentials with force_refresh=True.
_SECRET_CACHE = {}

def get_secrets_manager_client():
    """
    Returns a boto3 Secrets Manager client using standard AWS credential chain
    (e.g., EC2 instance profile IAM role in production).
    """
    region = os.environ.get('AWS_REGION', 'us-east-1')
    return boto3.client('secretsmanager', region_name=region)

def clear_secret_cache():
    """Clears the in-memory secret cache (useful for testing or manual refreshes)."""
    global _SECRET_CACHE
    _SECRET_CACHE.clear()

def get_db_credentials(secret_name, force_refresh=False):
    """
    Retrieves and parses the database credentials from AWS Secrets Manager.

    Supported JSON schema:
    - host: Database endpoint (or DB_HOST)
    - port: Database port (or DB_PORT, defaults to 3306)
    - username: Master/application user (or user, DB_USER)
    - password: Database password (or DB_PASSWORD)
    - dbname: Database name (or database, DB_NAME)

    Returns a normalized dict:
        {'host': ..., 'port': ..., 'user': ..., 'password': ..., 'database': ...}

    Raises RuntimeError if retrieval, parsing, or validation fails.
    Credential values are never logged.
    """
    if not secret_name:
        raise ValueError("Secret name must be a non-empty string.")

    if not force_refresh and secret_name in _SECRET_CACHE:
        return _SECRET_CACHE[secret_name]

    client = get_secrets_manager_client()
    try:
        response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        logger.error("AWS Secrets Manager error for secret '%s': %s", secret_name, error_code)
        raise RuntimeError(f"Failed to retrieve database secret '{secret_name}' from AWS: {error_code}") from e
    except Exception as e:
        logger.error("Unexpected error retrieving secret '%s': %s", secret_name, type(e).__name__)
        raise RuntimeError(f"Unexpected error retrieving secret '{secret_name}': {type(e).__name__}") from e

    secret_string = response.get('SecretString')
    if not secret_string:
        raise RuntimeError(f"Secret '{secret_name}' does not contain a valid SecretString payload.")

    try:
        data = json.loads(secret_string)
    except Exception as e:
        logger.error("Failed to parse JSON for secret '%s'", secret_name)
        raise RuntimeError(f"Secret '{secret_name}' contains malformed JSON data.") from e

    if not isinstance(data, dict):
        raise RuntimeError(f"Secret '{secret_name}' JSON payload must be an object/dict.")

    # Normalize keys supporting both standard AWS RDS schema and environment-variable style
    host = data.get('host') or data.get('DB_HOST')
    raw_port = data.get('port') or data.get('DB_PORT') or 3306
    user = data.get('username') or data.get('user') or data.get('DB_USER')
    password = data.get('password') or data.get('DB_PASSWORD')
    database = data.get('dbname') or data.get('database') or data.get('DB_NAME')

    # Validate port
    try:
        port = int(raw_port)
    except (ValueError, TypeError) as e:
        raise RuntimeError(f"Secret '{secret_name}' has invalid port value: {raw_port}") from e

    # Validate required parameters
    missing = []
    if not host:
        missing.append('host')
    if not user:
        missing.append('username')
    if not password:
        missing.append('password')
    if not database:
        missing.append('dbname')

    if missing:
        raise RuntimeError(f"Secret '{secret_name}' is missing required fields: {', '.join(missing)}")

    creds = {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'database': database
    }

    _SECRET_CACHE[secret_name] = creds
    return creds

def get_db_config():
    """
    Resolves database connection configuration according to strict precedence:

    A. If DB_SECRET_NAME is configured:
       Retrieve the secret from Secrets Manager and use its credentials.
       If retrieval, parsing, or validation fails, raise an error.
       Do NOT silently fall back to DB_PASSWORD when DB_SECRET_NAME is configured.

    B. If DB_SECRET_NAME is not configured and DB_HOST is configured:
       Preserve existing environment-variable database behavior.

    C. If neither DB_SECRET_NAME nor DB_HOST is configured:
       Preserve existing SQLite development fallback (returns None).
    """
    secret_name = os.environ.get('DB_SECRET_NAME')
    if secret_name:
        # Precedence A: Secrets Manager
        # Raises RuntimeError on failure; does NOT fall back to env vars.
        return get_db_credentials(secret_name)

    db_host = os.environ.get('DB_HOST')
    if db_host:
        # Precedence B: Environment variables
        return {
            'host': db_host,
            'port': int(os.environ.get('DB_PORT', 3306)),
            'user': os.environ.get('DB_USER'),
            'password': os.environ.get('DB_PASSWORD'),
            'database': os.environ.get('DB_NAME')
        }

    # Precedence C: SQLite development fallback
    return None
