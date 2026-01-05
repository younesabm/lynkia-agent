from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Twilio WhatsApp Configuration
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = "whatsapp:+14155238886"

    # OpenAI Configuration
    openai_api_key: str = ""

    # AWS Configuration
    dynamodb_table_name: str = ""
    s3_bucket_name: str = ""
    aws_region_name: str = "eu-west-3"

    # Application Settings
    debug: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
