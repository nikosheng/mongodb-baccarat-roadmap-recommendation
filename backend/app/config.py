import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve repo-root .env regardless of CWD (backend/app/config.py -> repo root)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
_ROOT_ENV = os.path.join(_REPO_ROOT, ".env")
_BACKEND_ENV = os.path.join(_REPO_ROOT, "backend", ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_ROOT_ENV, _BACKEND_ENV),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "baccarat_vector_demo"

    # Voyage AI
    voyage_api_key: str = ""
    voyage_base_url: str = "https://ai.mongodb.com/v1"
    voyage_model: str = "voyage-3-large"
    voyage_dim: int = 1024

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-6-luna"
    azure_openai_api_version: str = "2024-08-01-preview"

    # Match thresholds
    pattern_min_score: float = 0.82
    min_window_for_match: int = 4
    max_window: int = 10
    top_k: int = 5
    # Two structurally-eligible candidates whose scores are within this
    # absolute cosine distance of each other are considered a genuine tie
    # (e.g. observed gap ~0.0009 between two legitimately-in-progress
    # narratives at the same window) rather than a confident top pick (e.g.
    # observed gap ~0.0244 for an early/ambiguous window where one candidate
    # is just incidentally scored higher). Surfaced via
    # PatternMatch.alsoConsistentWith so the UI can show "also consistent
    # with: X" instead of silently picking one name.
    pattern_tie_epsilon: float = 0.01

    # NL describer version
    nl_describer_version: str = "1.2.0"

    # Derived roads (下三路: Big Eye Boy / Small Road / Cockroach Pig)
    # Calibrated via `make calibrate-derived` (see app/seed/calibrate_derived.py):
    # realistic-scenario recall floor 0.857, cross-archetype noise ceiling
    # 0.800 -> 0.82 sits strictly between the two with margin on both sides.
    derived_pattern_min_score: float | None = 0.82
    derived_top_k: int = 5
    derived_tail_length: int = 12
    nl_derived_describer_version: str = "3.0.0"

    # Server
    backend_port: int = 8000
    frontend_port: int = 5173
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"

    # Mocking (for local dev without real API keys)
    use_mock_embedder: bool = False
    use_mock_llm: bool = False

    # Side Bet (Lucky 6 v1) — see docs/side-bet-lucky6-plan.md §1
    side_bet_window: int = 10
    side_bet_supported_windows: str = "1,3,5,10"
    side_bet_dataset: str = "demo"
    side_bet_top_k: int = 10
    side_bet_candidate_multiplier: int = 20  # numCandidates = top_k * this, before per-shoe dedupe
    side_bet_min_samples_for_lift: int = 3
    side_bet_corpus_version: str = "v1"
    side_bet_feature_version: str = "sidebet-v1"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def side_bet_supported_window_list(self) -> list[int]:
        return [int(w.strip()) for w in self.side_bet_supported_windows.split(",") if w.strip()]

    def validate_side_bet_window(self) -> None:
        supported = self.side_bet_supported_window_list
        if self.side_bet_window not in supported:
            raise ValueError(
                f"SIDE_BET_WINDOW={self.side_bet_window} is not in "
                f"SIDE_BET_SUPPORTED_WINDOWS={supported}. Available values: {supported}."
            )
        if self.side_bet_dataset not in ("demo", "monte_carlo"):
            raise ValueError(
                f"SIDE_BET_DATASET={self.side_bet_dataset!r} must be 'demo' or 'monte_carlo'."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
