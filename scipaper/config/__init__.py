"""
Configuration management for Signal.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, List
from pathlib import Path

DEFAULT_LLM_MODEL = "claude-sonnet-4-20250514"
DEFAULT_GENERATION_MODEL = "claude-opus-4-6"  # Higher quality for final article


@dataclass
class SignalConfig:
    """
    Main configuration for Signal pipeline.
    
    Load from environment variables and/or config file.
    """
    # Environment
    env: str = "development"  # development, staging, production
    
    # Paths
    data_dir: Path = Path("data")
    papers_dir: Path = Path("data/papers")
    editions_dir: Path = Path("data/editions")
    anchors_dir: Path = Path("data/anchors")
    
    # LLM Settings
    llm_provider: str = "anthropic"  # anthropic, openai
    llm_model: str = "claude-sonnet-4-20250514"
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    
    # Semantic Scholar
    semantic_scholar_api_key: Optional[str] = None
    
    # ArXiv categories to track
    arxiv_categories: List[str] = field(default_factory=lambda: [
        "cs.AI", "cs.LG", "cs.CL", "stat.ML"
    ])
    
    # Email (Buttondown — DEC-003)
    email_provider: str = "buttondown"
    email_api_key: Optional[str] = None
    email_from: str = "signal@example.com"
    email_from_name: str = "Signal"
    
    # Web
    site_url: str = "https://signal.example.com"
    
    # Logging
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> "SignalConfig":
        """Load configuration from environment variables."""
        return cls(
            env=os.getenv("SIGNAL_ENV", "development"),
            
            llm_provider=os.getenv("LLM_PROVIDER", "anthropic"),
            llm_model=os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            
            semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
            
            email_provider=os.getenv("EMAIL_PROVIDER", "buttondown"),
            email_api_key=os.getenv("BUTTONDOWN_API_KEY") or os.getenv("EMAIL_API_KEY"),
            
            site_url=os.getenv("SITE_URL", "https://signal.example.com"),
            
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
    
    def validate(self) -> List[str]:
        """Validate configuration, return list of issues."""
        issues = []
        
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            issues.append("ANTHROPIC_API_KEY not set")
        if self.llm_provider == "openai" and not self.openai_api_key:
            issues.append("OPENAI_API_KEY not set")
        
        if self.env == "production":
            if not self.email_api_key:
                issues.append("Email API key not set for production")
        
        return issues


# Global config instance
_config: Optional[SignalConfig] = None


def get_config() -> SignalConfig:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = SignalConfig.from_env()
    return _config


def set_config(config: SignalConfig):
    """Set the global config instance (for testing)."""
    global _config
    _config = config
