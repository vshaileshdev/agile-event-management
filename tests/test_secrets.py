import os
import json
import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

from app.secrets import (
    get_secrets_manager_client,
    get_db_credentials,
    get_db_config,
    clear_secret_cache,
)
from app.app import create_app
from app.db import get_db


@pytest.fixture(autouse=True)
def clean_environment():
    """Ensure clean environment and secret cache for every test."""
    clear_secret_cache()
    # Save original environment
    env_keys = ['DB_SECRET_NAME', 'DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PASSWORD', 'DB_NAME', 'AWS_REGION', 'SECRET_KEY', 'FLASK_ENV']
    orig_env = {k: os.environ.get(k) for k in env_keys}

    # Clean the keys
    for k in env_keys:
        os.environ.pop(k, None)

    yield

    # Restore original environment
    clear_secret_cache()
    for k, v in orig_env.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


class TestSecretsManagerRetrieval:
    def test_successful_rds_schema_retrieval(self):
        """Test retrieving secret formatted with standard AWS RDS JSON keys."""
        mock_secret = {
            "host": "rds.example.com",
            "port": 3306,
            "username": "rds_admin",
            "password": "SuperSecretPassword123!",
            "dbname": "production_event_db"
        }

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(mock_secret)
        }

        with patch("app.secrets.get_secrets_manager_client", return_value=mock_client):
            creds = get_db_credentials("my-db-secret")

        assert creds == {
            "host": "rds.example.com",
            "port": 3306,
            "user": "rds_admin",
            "password": "SuperSecretPassword123!",
            "database": "production_event_db"
        }
        mock_client.get_secret_value.assert_called_once_with(SecretId="my-db-secret")

    def test_successful_env_style_schema_retrieval(self):
        """Test retrieving secret formatted with environment-variable style JSON keys."""
        mock_secret = {
            "DB_HOST": "rds-env.example.com",
            "DB_PORT": "3307",
            "DB_USER": "env_user",
            "DB_PASSWORD": "EnvPassword456!",
            "DB_NAME": "env_event_db"
        }

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(mock_secret)
        }

        with patch("app.secrets.get_secrets_manager_client", return_value=mock_client):
            creds = get_db_credentials("my-env-secret")

        assert creds == {
            "host": "rds-env.example.com",
            "port": 3307,
            "user": "env_user",
            "password": "EnvPassword456!",
            "database": "env_event_db"
        }

    def test_default_port_when_omitted(self):
        """Test that port defaults to 3306 when omitted from secret."""
        mock_secret = {
            "host": "rds.example.com",
            "username": "admin",
            "password": "pw",
            "dbname": "events"
        }

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(mock_secret)
        }

        with patch("app.secrets.get_secrets_manager_client", return_value=mock_client):
            creds = get_db_credentials("my-secret")

        assert creds["port"] == 3306

    def test_in_memory_caching_and_force_refresh(self):
        """Test that retrieved credentials are cached in-memory and force_refresh bypasses cache."""
        mock_secret = {
            "host": "rds.example.com",
            "port": 3306,
            "username": "admin",
            "password": "pw",
            "dbname": "events"
        }

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(mock_secret)
        }

        with patch("app.secrets.get_secrets_manager_client", return_value=mock_client):
            # First call fetches from client
            creds1 = get_db_credentials("cache-secret")
            # Second call uses cache
            creds2 = get_db_credentials("cache-secret")
            assert mock_client.get_secret_value.call_count == 1
            assert creds1 == creds2

            # Third call with force_refresh=True re-fetches
            creds3 = get_db_credentials("cache-secret", force_refresh=True)
            assert mock_client.get_secret_value.call_count == 2
            assert creds3 == creds1

            # clear_secret_cache forces re-fetch
            clear_secret_cache()
            get_db_credentials("cache-secret")
            assert mock_client.get_secret_value.call_count == 3

    def test_empty_secret_name_raises_value_error(self):
        """Test that an empty secret name raises ValueError."""
        with pytest.raises(ValueError, match="Secret name must be a non-empty string"):
            get_db_credentials("")


class TestSecretsManagerErrorHandling:
    def test_client_error_raises_runtime_error_without_silent_fallback(self):
        """Test that an AWS ClientError raises RuntimeError and includes error code."""
        mock_client = MagicMock()
        error_response = {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Secrets Manager can\'t find the specified secret.'}}
        mock_client.get_secret_value.side_effect = ClientError(error_response, 'GetSecretValue')

        with patch("app.secrets.get_secrets_manager_client", return_value=mock_client):
            with pytest.raises(RuntimeError) as exc_info:
                get_db_credentials("non-existent-secret")

        assert "ResourceNotFoundException" in str(exc_info.value)
        assert "Failed to retrieve database secret" in str(exc_info.value)

    def test_missing_secret_string_raises_runtime_error(self):
        """Test that secret without SecretString raises RuntimeError."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {}  # No SecretString

        with patch("app.secrets.get_secrets_manager_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="does not contain a valid SecretString"):
                get_db_credentials("binary-only-secret")

    def test_malformed_json_raises_runtime_error(self):
        """Test that malformed JSON payload raises RuntimeError."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": "{malformed_json: true"
        }

        with patch("app.secrets.get_secrets_manager_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="contains malformed JSON"):
                get_db_credentials("malformed-secret")

    def test_non_dict_json_raises_runtime_error(self):
        """Test that non-object JSON payload raises RuntimeError."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(["a", "b", "c"])
        }

        with patch("app.secrets.get_secrets_manager_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="must be an object/dict"):
                get_db_credentials("list-secret")

    def test_missing_required_fields_raises_runtime_error(self):
        """Test that missing required fields (e.g. password, host) raises RuntimeError."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"host": "rds.example.com", "username": "admin"})
        }

        with patch("app.secrets.get_secrets_manager_client", return_value=mock_client):
            with pytest.raises(RuntimeError) as exc_info:
                get_db_credentials("missing-fields-secret")

        err_msg = str(exc_info.value)
        assert "missing required fields" in err_msg
        assert "password" in err_msg
        assert "dbname" in err_msg

    def test_invalid_port_raises_runtime_error(self):
        """Test that invalid non-integer port raises RuntimeError."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps({
                "host": "rds.example.com",
                "port": "not-a-number",
                "username": "admin",
                "password": "pw",
                "dbname": "events"
            })
        }

        with patch("app.secrets.get_secrets_manager_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="invalid port value"):
                get_db_credentials("bad-port-secret")


class TestPrecedenceHierarchy:
    def test_precedence_a_secrets_manager_configured(self):
        """
        Precedence A: DB_SECRET_NAME is set.
        Credentials must be fetched from Secrets Manager.
        """
        os.environ["DB_SECRET_NAME"] = "my-prod-secret"
        # Set dummy env vars to confirm they are NOT used when secret retrieval succeeds
        os.environ["DB_HOST"] = "wrong-host.rds.amazonaws.com"
        os.environ["DB_USER"] = "wrong-user"

        mock_secret = {
            "host": "correct-secret-host.rds.amazonaws.com",
            "port": 3306,
            "username": "correct-user",
            "password": "secret-password",
            "dbname": "event_management"
        }
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {"SecretString": json.dumps(mock_secret)}

        with patch("app.secrets.get_secrets_manager_client", return_value=mock_client):
            config = get_db_config()

        assert config["host"] == "correct-secret-host.rds.amazonaws.com"
        assert config["user"] == "correct-user"

    def test_precedence_a_failure_never_silently_falls_back_to_db_password(self):
        """
        Precedence A Failure:
        If DB_SECRET_NAME is set and Secrets Manager retrieval fails,
        it MUST raise a RuntimeError and NEVER fall back to DB_PASSWORD/DB_HOST.
        """
        os.environ["DB_SECRET_NAME"] = "my-prod-secret"
        os.environ["DB_HOST"] = "fallback-host.rds.amazonaws.com"
        os.environ["DB_PASSWORD"] = "fallback-password"
        os.environ["DB_USER"] = "fallback-user"
        os.environ["DB_NAME"] = "fallback-db"

        mock_client = MagicMock()
        error_response = {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access Denied'}}
        mock_client.get_secret_value.side_effect = ClientError(error_response, 'GetSecretValue')

        with patch("app.secrets.get_secrets_manager_client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="AccessDeniedException"):
                get_db_config()

    def test_precedence_b_environment_variables_when_secret_unset(self):
        """
        Precedence B: DB_SECRET_NAME is unset, but DB_HOST is set.
        Configuration must be read from environment variables.
        """
        os.environ.pop("DB_SECRET_NAME", None)
        os.environ["DB_HOST"] = "env-db.example.com"
        os.environ["DB_PORT"] = "3306"
        os.environ["DB_USER"] = "env_admin"
        os.environ["DB_PASSWORD"] = "env_secret_pw"
        os.environ["DB_NAME"] = "event_management_db"

        config = get_db_config()
        assert config == {
            "host": "env-db.example.com",
            "port": 3306,
            "user": "env_admin",
            "password": "env_secret_pw",
            "database": "event_management_db"
        }

    def test_precedence_c_sqlite_fallback_when_both_unset(self):
        """
        Precedence C: Neither DB_SECRET_NAME nor DB_HOST is set.
        get_db_config must return None, indicating SQLite development fallback.
        """
        os.environ.pop("DB_SECRET_NAME", None)
        os.environ.pop("DB_HOST", None)

        config = get_db_config()
        assert config is None


class TestFlaskSecretKeyHardening:
    def test_secret_key_from_env_var(self):
        """Test that create_app uses SECRET_KEY from environment."""
        os.environ["SECRET_KEY"] = "super-secure-production-flask-secret-key"
        app = create_app()
        assert app.config["SECRET_KEY"] == "super-secure-production-flask-secret-key"

    def test_secret_key_development_fallback(self):
        """Test that create_app falls back to 'dev-secret-key' in development."""
        os.environ.pop("SECRET_KEY", None)
        os.environ.pop("DB_SECRET_NAME", None)
        os.environ.pop("DB_HOST", None)
        os.environ.pop("FLASK_ENV", None)

        app = create_app()
        assert app.config["SECRET_KEY"] == "dev-secret-key"

    def test_secret_key_warning_in_production(self):
        """Test that a security warning is logged when SECRET_KEY is missing in production mode."""
        os.environ.pop("SECRET_KEY", None)
        os.environ["DB_SECRET_NAME"] = "my-prod-secret"

        with patch("logging.Logger.warning") as mock_warning:
            app = create_app()
            assert app.config["SECRET_KEY"] == "dev-secret-key"
            mock_warning.assert_called_once()
            assert "SECURITY WARNING" in mock_warning.call_args[0][0]


class TestDatabaseConnectionWiring:
    def test_get_db_connects_to_mysql_using_secrets_manager(self):
        """Test that get_db invokes pymysql.connect with credentials from Secrets Manager."""
        os.environ["DB_SECRET_NAME"] = "prod-db-secret"
        mock_secret = {
            "host": "rds.example.com",
            "port": 3306,
            "username": "rds_user",
            "password": "rds_password",
            "dbname": "event_management"
        }
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {"SecretString": json.dumps(mock_secret)}

        app = create_app()
        with app.app_context():
            with patch("app.secrets.get_secrets_manager_client", return_value=mock_client):
                with patch("pymysql.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_connect.return_value = mock_conn

                    db = get_db()
                    mock_connect.assert_called_once()
                    kwargs = mock_connect.call_args[1]
                    assert kwargs["host"] == "rds.example.com"
                    assert kwargs["port"] == 3306
                    assert kwargs["user"] == "rds_user"
                    assert kwargs["password"] == "rds_password"
                    assert kwargs["database"] == "event_management"
                    assert db is not None
