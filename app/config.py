from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
     # Gemini API 密钥
     gemini_api_key: str
     # MongoDB 连接 URI
     mongo_uri: str = ""
     port: int = 8000

     model_config = SettingsConfigDict(env_file=".env")

settings = Settings()