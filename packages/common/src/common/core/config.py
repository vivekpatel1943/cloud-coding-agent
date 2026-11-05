from pathlib import Path

from pydantic_settings import BaseSettings , SettingsConfigDict

# config.py -> core -> common -> src -> common -> packages -> <repo root>
# Only valid because uv installs workspace members as editable (source stays in place).
REPO_ROOT = Path(__file__).resolve().parents[5]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env",extra="ignore")
    
    gemini_api_key : str
    gemini_model : str = "gemini-3.5-flash-lite"
    bash_path : str | None = None  # Git Bash on Windows, e.g. C:\Program Files\Git\bin\bash.exe
    workspace_root : str = str(REPO_ROOT / "agent_playground" / "test_files")
    max_steps : int = 25
    session_memory : int = 3  # REPL: how many earlier tasks are summarised into each prompt (0 = off)
