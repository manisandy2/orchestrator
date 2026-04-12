from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
   
    ENV: str = Field(default="dev")    
    CRM_AUTH_KEY: str = Field(default="")
    DEFAULT_MOBILE: str = Field(default="2320000000")
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL:str = Field(default="")
    STAGE_URL:str=Field(default="")
    ANONYMOUS_LINK:str=Field(default="")
    HTTP_TIMEOUT: int = Field(default=10)
    MAX_RETRIES: int = Field(default=3)
  

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
