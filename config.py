"""
Centralized configuration loader for the Fraud Investigation Agent.
Reads .env, validates required keys, and exposes a typed config object.
"""
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class TigerGraphConfig:
    host: str = ""
    graphname: str = "HHGOA_IEEE"
    username: str = "tigergraph"
    password: str = ""
    rest_port: int = 443
    gs_port: int = 443


@dataclass
class LLMConfig:
    provider: str = "google"
    api_key: str = ""
    model: str = "gemini-2.0-flash"


@dataclass
class EmbeddingConfig:
    model_name: str = "all-MiniLM-L6-v2"
    dimension: int = 384


@dataclass
class AgentConfig:
    confidence_threshold: float = 0.25
    max_evidence_loops: int = 5


@dataclass
class DataConfig:
    raw_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "raw")
    processed_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "processed")


@dataclass
class Config:
    tigergraph: TigerGraphConfig = field(default_factory=TigerGraphConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    data: DataConfig = field(default_factory=DataConfig)
    project_root: Path = PROJECT_ROOT


def load_config() -> Config:
    """Load configuration from environment variables."""
    cfg = Config()

    # TigerGraph
    cfg.tigergraph.host = os.getenv("TG_HOST", "")
    cfg.tigergraph.graphname = os.getenv("TG_GRAPHNAME", "HHGOA_IEEE")
    cfg.tigergraph.username = os.getenv("TG_USERNAME", "tigergraph")
    cfg.tigergraph.password = os.getenv("TG_PASSWORD", "")
    cfg.tigergraph.rest_port = int(os.getenv("TG_REST_PORT", "443"))
    cfg.tigergraph.gs_port = int(os.getenv("TG_GS_PORT", "443"))

    # LLM
    cfg.llm.api_key = os.getenv("GOOGLE_API_KEY", "")
    cfg.llm.model = os.getenv("LLM_MODEL", "gemini-2.0-flash")

    # Embedding
    cfg.embedding.model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    cfg.embedding.dimension = int(os.getenv("EMBEDDING_DIM", "384"))

    # Agent
    cfg.agent.confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.25"))
    cfg.agent.max_evidence_loops = int(os.getenv("MAX_EVIDENCE_LOOPS", "5"))

    # Data paths
    cfg.data.raw_dir = Path(os.getenv("RAW_DATA_DIR", PROJECT_ROOT / "data" / "raw"))
    cfg.data.processed_dir = Path(os.getenv("PROCESSED_DATA_DIR", PROJECT_ROOT / "data" / "processed"))

    return cfg


def validate_config(cfg: Config, require_tg: bool = True, require_llm: bool = True) -> list[str]:
    """Validate configuration; returns list of error messages (empty = valid)."""
    errors = []
    if require_tg:
        if not cfg.tigergraph.host:
            errors.append("TG_HOST is required. Set it in .env")
        if not cfg.tigergraph.password:
            errors.append("TG_PASSWORD is required. Set it in .env")
    if require_llm:
        if not cfg.llm.api_key:
            errors.append("GOOGLE_API_KEY is required. Set it in .env")
    return errors


# Singleton config instance
config = load_config()
