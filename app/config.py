from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
     gemini_api_key: str
     mongo_uri: str = ""
     port: int = 8000

     model_config = SettingsConfigDict(env_file=".env")

settings = Settings()