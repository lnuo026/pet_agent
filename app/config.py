from pydantic_settings import BaseSettings

class Settings(BaseSettings):
     gemini_api_key: str
     mongo_uri: str = ""
     port: int = 8000

     class Config:
          env_file=".env"

setting = Settings()