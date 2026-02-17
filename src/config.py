from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings #, SettingsConfigDict
from typing import List
# from pydantic import SecretStr

class Settings(BaseSettings):
    # https://docs.pydantic.dev/latest/concepts/pydantic_settings/#dotenv-env-support
    # ... loads from .env automatically when instantiating BaseSettings
    # model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    # ===== Database Settings ===== #
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str

    # ===== Redis Settings ===== #
    redis_host: str
    redis_port: int = 6379
    redis_password: str | None
    
    # ===== Redpanda/Kafka Settings ===== #
    redpanda_enabled: bool = True
    redpanda_bootstrap_servers: str
    redpanda_topic_prefix: str

    # ===== Flink ===== #
    flink_host: str
    flink_parallelism: int

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
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def async_database_url(self) -> str:
        """Construct async PostgreSQL connection URL.
        
        Returns:
            Async PostgreSQL connection string for asyncpg
        """
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL.
        
        Returns:
            Redis connection string
        """
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def redpanda_topics(self) -> dict[str, str]:
        """Get Redpanda topic names with prefix.
        
        Returns:
            Dictionary of topic names
        """
        return {
            "metrics": f"{self.redpanda_topic_prefix}.metrics",
            "alerts": f"{self.redpanda_topic_prefix}.alerts",
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

    # ===== Field Validators =====

    @field_validator('alert_threshold_high')
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        """Validate threshold is a percentage (0-1)"""
        if not 0 <= v <= 1:
            raise ValueError(f"Threshold high must be between 0-1, got {v}")
        return v

    @field_validator('alert_threshold_medium')
    @classmethod
    def validate_threshold(cls, v: float) -> float:
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

    @field_validator('depth_levels')
    @classmethod
    def validate_depth(cls, v: int) -> int:
        """Validate depth levels is reasonable."""
        if not 1 <= v <= 1000:
            raise ValueError(f"Depth levels must be 1-1000, got {v}")
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
        if self.redpanda_enabled and not self.redpanda_bootstrap_servers:
            raise ValueError("Redpanda requires bootstrap_servers")
        return self

    class Config:
        env_file = ".env"

# print(Settings().model_dump())

# ===== Singleton Instance =====
# Import this instance throughout the application
settings = Settings()