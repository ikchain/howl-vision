from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4:e4b"

    vision_service_url: str = "http://vision-service:20002"

    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection: str = "vet_cases"

    redis_host: str = "redis"
    redis_port: int = 6379

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "howlvision"
    postgres_user: str = "howl"
    postgres_password: str = "changeme_in_production"

    cors_origins: str = "http://localhost:20000"

    agent_max_iterations: int = 3
    agent_vision_confidence_threshold: float = 0.6

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
