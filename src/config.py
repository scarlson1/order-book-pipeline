from typing import List
from urllib.parse import quote, urlencode

from loguru import logger
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
# from pydantic import SecretStr

class Settings(BaseSettings):
    # https://docs.pydantic.dev/latest/concepts/pydantic_settings/#dotenv-env-support
    model_config = SettingsConfigDict(
        env_file='.env', 
        env_file_encoding='utf-8',
        extra='ignore'  # Allow extra fields in .env (like Streamlit settings)
    )

    # ===== Database Settings ===== #
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_sslmode: str | None = Field(
        default=None,
        validation_alias='POSTGRES_SSLMODE',
    )
    postgres_sslrootcert: str | None = Field(
        default=None,
        validation_alias='POSTGRES_SSLROOTCERT',
    )
    postgres_sslcert: str | None = Field(
        default=None,
        validation_alias='POSTGRES_SSLCERT',
    )
    postgres_sslkey: str | None = Field(
        default=None,
        validation_alias='POSTGRES_SSLKEY',
    )

    # ===== Redis Settings ===== #
    redis_host: str
    redis_port: int = 6379
    redis_password: str | None = None
    redis_ssl: bool = False
    redis_username: str = "default"
    redis_db: int = 0
    redis_snapshot_min_write_interval_seconds: int = 60
    redis_url_env: str | None = Field(
        default=None,
        validation_alias="REDIS_URL",
    )
    
    # ===== Redpanda/Kafka Settings ===== #
    redpanda_enabled: bool = True
    # Managed Kafka usually provides a comma-separated bootstrap list.
    redpanda_bootstrap_servers_env: str | None = Field(
        default=None,
        validation_alias='REDPANDA_BOOTSTRAP_SERVERS',
    )
    # Local fallback (Docker network style: service:port)
    redpanda_service: str = "redpanda"
    redpanda_bootstrap_port: str = "9092"
    redpanda_security_protocol: str = "PLAINTEXT"
    redpanda_sasl_mechanism: str | None = None
    redpanda_username: str | None = None
    redpanda_password: str | None = None
    redpanda_ssl_cafile: str | None = None
    redpanda_ssl_certfile: str | None = None
    redpanda_ssl_keyfile: str | None = None
    redpanda_ssl_check_hostname: bool = True
    # redpanda_admin_port: int = 19644
    redpanda_admin_url: str = 'http://redpanda:9644'
    redpanda_kafka_port: int = 19092
    redpanda_topic_prefix: str
    

    # ===== Flink ===== #
    flink_host: str
    flink_parallelism: int
    flink_port: int = 8081
    # flink_ui_url: str # = "http://localhost:8081"

    # downsampling_enabled: bool
    # downsample_bucket_seconds: int

    # ===== Binance WebSocket Settings ===== #
    binance_ws_url: str 
    symbols: str 
    depth_levels: int = 20
    update_speed: str # Can be "100ms" or "1000ms"
    
    # ===== Metric Calculation Settings ===== #
    calculate_depth: int = 10  # Number of order book levels to use
    rolling_window_seconds: int = 60  # Window for velocity calculations
    calculate_velocity: bool = True
    
    # ===== Alert Settings ===== #
    alert_threshold_high: float = 0.70  # 70% imbalance
    alert_threshold_medium: float = 0.50  # 50% imbalance
    spread_alert_multiplier: float = 2.0  # Alert when spread is 2x normal
    velocity_threshold: float = 0.05  # Alert on rapid changes
    
    # ===== Logging Settings ===== #
    log_level: str # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_file: str
    
    # ===== Application Settings ===== #
    app_name: str = "Order Book Monitor"
    environment: str # development, staging, production

    # ===== Computed Properties ===== #
    
    @property
    def symbol_list(self) -> List[str]:
        """Parse symbols string into a list.
        
        Returns:
            List of trading symbols (e.g., ['BTCUSDT', 'ETHUSDT'])
        """
        return [s.strip().upper() for s in self.symbols.split(',') if s.strip()]

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL.
        
        Returns:
            PostgreSQL connection string
        """
        user = quote(self.postgres_user, safe='')
        password = quote(self.postgres_password, safe='')
        database = quote(self.postgres_db, safe='')
        query_string = urlencode(self.postgres_ssl_query_params)
        return (
            f'postgresql://{user}:{password}@{self.postgres_host}:{self.postgres_port}/'
            f'{database}?{query_string}'
        )

    @property
    def async_database_url(self) -> str:
        """Construct async PostgreSQL connection URL.
        
        Returns:
            Async PostgreSQL connection string for asyncpg
        """
        user = quote(self.postgres_user, safe='')
        password = quote(self.postgres_password, safe='')
        database = quote(self.postgres_db, safe='')
        query_string = urlencode(self.postgres_ssl_query_params)
        return (
            f'postgresql+asyncpg://{user}:{password}@{self.postgres_host}:'
            f'{self.postgres_port}/{database}?{query_string}'
        )

    @property
    def postgres_effective_sslmode(self) -> str:
        """Resolve sslmode with environment-aware defaults."""
        if self.postgres_sslmode:
            return self.postgres_sslmode
        return 'require' if self.is_production() else 'disable'

    @property
    def postgres_ssl_query_params(self) -> dict[str, str]:
        """Build PostgreSQL SSL query parameters for DSN URLs."""
        params: dict[str, str] = {'sslmode': self.postgres_effective_sslmode}
        optional_params = {
            'sslrootcert': self.postgres_sslrootcert,
            'sslcert': self.postgres_sslcert,
            'sslkey': self.postgres_sslkey,
        }
        for key, value in optional_params.items():
            if value:
                params[key] = value
        return params

    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL.
        
        Returns:
            Redis connection string
        """
        if self.redis_url_env:
            return self.redis_url_env.strip()

        scheme = 'rediss' if self.redis_ssl else 'redis'

        if self.redis_password:
            user = quote(self.redis_username, safe="")
            pwd = quote(self.redis_password, safe="")
            return f"{scheme}://{user}:{pwd}@{self.redis_host}:{self.redis_port}/{self.redis_db}"

        return f"{scheme}://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def redpanda_bootstrap_servers(self) -> str:
        """Get Redpanda bootstrap servers """
        if self.redpanda_bootstrap_servers_env:
            return self.redpanda_bootstrap_servers_env.strip()
        return f'{self.redpanda_service}:{self.redpanda_bootstrap_port}'

    @property
    def redpanda_bootstrap_server_list(self) -> List[str]:
        """Get bootstrap servers as a list for kafka-python."""
        return [
            s.strip()
            for s in self.redpanda_bootstrap_servers.split(',')
            if s.strip()
        ]

    # @property
    # def redpanda_admin_url(self) -> str:
    #     """Get Url for pinging Redpanda health checks"""
    #     return f'http://{self.redpanda_service}:{self.redpanda_admin_port}'

    @property
    def flink_ui_url(self) -> str:
        """Get Url for pinging Flink health checks"""
        return f'http://{self.flink_host}:{self.flink_port}'

    @property
    def redpanda_topics(self) -> dict[str, str]:
        """Get Redpanda topic names with prefix.
        
        Returns:
            Dictionary of topic names
        """
        return {
            "metrics": f"{self.redpanda_topic_prefix}.metrics",
            "alerts": f"{self.redpanda_topic_prefix}.alerts",
            "windowed": f"{self.redpanda_topic_prefix}.metrics.windowed",
            "raw": f"{self.redpanda_topic_prefix}.raw",
        }

    def is_production(self) -> bool:
        """Check if running in production environment.
        
        Returns:
            True if production, False otherwise
        """
        return self.environment.lower() == "production"

    def is_development(self) -> bool:
        """Check if running in development environment.
        
        Returns:
            True if development, False otherwise
        """
        return self.environment.lower() == "development"

    def log_config(self): 
        """Log configuration at startup."""
        logger.info("=" * 60)
        logger.info("ORDER BOOK PIPELINE CONFIGURATION")
        logger.info(f"Starting {settings.app_name}")
        logger.info(f"Environment: {settings.environment}")
        logger.info("=" * 60)
        logger.info(f"Symbols: {self.symbol_list}")
        logger.info(f"Binance URL: {self.binance_ws_url}")
        logger.info(f"Database: {self.postgres_host}:{self.postgres_port}/{self.postgres_db}")
        logger.info(f"Database SSL mode: {self.postgres_effective_sslmode}")
        logger.info(f"Redis: {self.redis_host}:{self.redis_port} (ssl={self.redis_ssl})")
        logger.info(f"Kafka: {self.redpanda_bootstrap_servers}")
        logger.info("-" * 60)
        # logger.info("DOWNSAMPLING CONFIGURATION")
        # logger.info("-" * 60)
        # logger.info(f"Downsampling Enabled: {self.downsampling_enabled}")
        # logger.info(f"Bucket Size: {self.downsample_bucket_seconds} seconds")
        # logger.info(f"Depth: {self.downsample_depth} levels")
        
        # if self.downsampling_enabled:
        #     estimated_storage = (
        #         len(self.symbols) * 500 * (86400 / self.downsample_bucket_seconds)
        #     ) / (1024 * 1024)  # Convert to MB/day
        #     logger.info(f"Estimated Storage: {estimated_storage:.2f} MB/day")
        #     days_retention = 250 / estimated_storage if estimated_storage > 0 else float('inf')
        #     logger.info(f"Storage Retention (250MB): {days_retention:.0f} days")
        # else:
        #     logger.warning("⚠️  Downsampling DISABLED - Raw ticks mode (high storage!)")
        #     # logger.warning("    For production, set DOWNSAMPLING_ENABLED=true")
        
        # logger.info("-" * 60)
        logger.info(f"Alert Thresholds: HIGH={self.alert_threshold_high}, MEDIUM={self.alert_threshold_medium}")
        logger.info("=" * 60)

    # ===== Field Validators =====

    @field_validator('alert_threshold_high')
    @classmethod
    def validate_threshold_high(cls, v: float) -> float:
        """Validate threshold is a percentage (0-1)"""
        if not 0 <= v <= 1:
            raise ValueError(f"Threshold high must be between 0-1, got {v}")
        return v

    @field_validator('alert_threshold_medium')
    @classmethod
    def validate_threshold_medium(cls, v: float) -> float:
        """Validate threshold is a percentage (0-1)"""
        if not 0 <= v <= 1:
            raise ValueError(f"Threshold medium must be between 0-1, got {v}")
        return v

    @field_validator('symbols')
    @classmethod
    def validate_symbols(cls, v: str) -> str:
        """Validate symbols are not empty."""
        if not v or not v.strip():
            raise ValueError(
                "SYMBOLS environment variable is required. "
                "Example: SYMBOLS=BTCUSDT,ETHUSDT"
            )
        return v.strip().upper()

    @field_validator('postgres_sslmode')
    @classmethod
    def validate_postgres_sslmode(cls, v: str | None) -> str | None:
        """Validate PostgreSQL sslmode when explicitly provided."""
        if v is None:
            return None

        normalized = v.strip().lower()
        if not normalized:
            return None

        valid_modes = {
            'disable',
            'allow',
            'prefer',
            'require',
            'verify-ca',
            'verify-full',
        }
        if normalized not in valid_modes:
            raise ValueError(
                f'POSTGRES_SSLMODE must be one of {valid_modes}, got {v}'
            )
        return normalized

    @field_validator('depth_levels')
    @classmethod
    def validate_depth(cls, v: int) -> int:
        """Validate depth levels is reasonable."""
        if not 1 <= v <= 1000:
            raise ValueError(f"Depth levels must be 1-1000, got {v}")
        return v

    @field_validator('redis_snapshot_min_write_interval_seconds')
    @classmethod
    def validate_snapshot_write_interval(cls, v: int) -> int:
        """Validate snapshot write interval is non-negative."""
        if v < 0:
            raise ValueError(
                'REDIS_SNAPSHOT_MIN_WRITE_INTERVAL_SECONDS must be >= 0, '
                f'got {v}'
            )
        return v

    @model_validator(mode='after')
    def validate_thresholds(self) -> 'Settings':
        """Medium threshold must be less than high threshold."""
        if self.alert_threshold_medium >= self.alert_threshold_high:
            raise ValueError(
                f"Medium threshold ({self.alert_threshold_medium}) must be "
                f"less than high threshold ({self.alert_threshold_high})"
            )
        return self

    @model_validator(mode='after')
    def validate_config(self) -> 'Settings':
        if self.redpanda_enabled and not self.redpanda_bootstrap_server_list:
            raise ValueError("Redpanda requires bootstrap_servers")

        security_protocol = self.redpanda_security_protocol.upper()
        allowed_protocols = {'PLAINTEXT', 'SSL', 'SASL_PLAINTEXT', 'SASL_SSL'}
        if security_protocol not in allowed_protocols:
            raise ValueError(
                f"REDPANDA_SECURITY_PROTOCOL must be one of {allowed_protocols}, "
                f"got {self.redpanda_security_protocol}"
            )

        if security_protocol in {'SASL_PLAINTEXT', 'SASL_SSL'}:
            if not self.redpanda_sasl_mechanism:
                raise ValueError(
                    "REDPANDA_SASL_MECHANISM is required for SASL security protocols"
                )
            if not self.redpanda_username or not self.redpanda_password:
                raise ValueError(
                    "REDPANDA_USERNAME and REDPANDA_PASSWORD are required for SASL "
                    "security protocols"
                )
        return self

# print(Settings().model_dump())

# ===== Singleton Instance =====
# Import this instance throughout the application
settings = Settings()
