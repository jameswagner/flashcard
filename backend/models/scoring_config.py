from typing import Dict, Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Float, JSON, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from .base import Base
from datetime import datetime
from dataclasses import dataclass

@dataclass
class SRLWeights:
    """Weights for different semantic roles in SRL scoring."""
    SUBJECT: float = 1.5
    VERB: float = 1.5
    OBJECT: float = 1.5
    MODIFIER: float = 0.3
    FULL: float = 0.2

class SRLConfig(BaseModel):
    """Configuration for Semantic Role Labeling scoring."""
    role_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            'SUBJECT': 1.5,
            'VERB': 1.5,
            'OBJECT': 1.5,
            'MODIFIER': 0.3,
            'FULL': 0.2
        },
        description="Weights for different semantic roles"
    )
    concept_match_threshold: float = Field(
        default=0.6,
        description="Threshold for considering a concept matched"
    )
    concept_match_power: float = Field(
        default=1.5,
        description="Power to apply to concept match scores (higher = stricter)"
    )
    min_concept_score: float = Field(
        default=0.05,
        description="Minimum score for geometric mean calculation"
    )
    missing_penalty_factor: float = Field(
        default=0.7,
        description="Factor to multiply missing concepts penalty by"
    )
    role_penalty_factor: float = Field(
        default=0.7,
        description="Factor to multiply role weights by when falling back to full text"
    )

class SimilarityConfig(BaseModel):
    """Configuration for semantic similarity scoring."""
    model_names: Dict[str, str] = Field(
        default_factory=lambda: {
            "minilm": "sentence-transformers/all-MiniLM-L6-v2",
            "mpnet": "sentence-transformers/all-mpnet-base-v2",
            "multilingual": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        },
        description="Models to use for similarity scoring"
    )

class NLIConfig(BaseModel):
    """Configuration for NLI scoring."""
    model_name: str = Field(
        default="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
        description="Model to use for NLI scoring"
    )
    contradiction_threshold: float = Field(
        default=0.87,
        description="Threshold for considering an answer contradictory"
    )
    high_entailment_threshold: float = Field(
        default=0.8,
        description="Threshold for considering entailment high"
    )

class WeightConfig(BaseModel):
    """Configuration for score weighting."""
    high_entailment_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "entailment": 0.7,
            "similarity": 0.2,
            "srl": 0.1
        },
        description="Weights to use when entailment is high"
    )
    partial_match_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "entailment": 0.4,
            "similarity": 0.3,
            "srl": 0.3
        },
        description="Weights to use for partial matches"
    )

class ScoringConfig(BaseModel):
    """Complete configuration for answer scoring."""
    srl: SRLConfig = Field(default_factory=SRLConfig)
    similarity: SimilarityConfig = Field(default_factory=SimilarityConfig)
    nli: NLIConfig = Field(default_factory=NLIConfig)
    weights: WeightConfig = Field(default_factory=WeightConfig)
    
    class Config:
        from_attributes = True

# Database Models
class DBScoringConfig(Base):
    """Database model for storing scoring configurations."""
    __tablename__ = "scoring_configs"
    
    id = Column(Integer, primary_key=True)
    version = Column(String, nullable=False)  # Semantic version of the config
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)  # Whether this is the active config
    description = Column(String)  # Optional description of changes
    
    # Store all config as JSON
    srl_config = Column(JSON, nullable=False)
    similarity_config = Column(JSON, nullable=False)
    nli_config = Column(JSON, nullable=False)
    weight_config = Column(JSON, nullable=False)
    
    # Relationship to scores that used this config
    scores = relationship("ReviewScore", back_populates="scoring_config")
    
    @classmethod
    def from_config(cls, config: ScoringConfig, version: str, description: Optional[str] = None) -> "DBScoringConfig":
        """Create a database config from a ScoringConfig instance."""
        return cls(
            version=version,
            description=description,
            srl_config=config.srl.dict(),
            similarity_config=config.similarity.dict(),
            nli_config=config.nli.dict(),
            weight_config=config.weights.dict()
        )
    
    def to_config(self) -> ScoringConfig:
        """Convert database config to a ScoringConfig instance."""
        return ScoringConfig(
            srl=SRLConfig(**self.srl_config),
            similarity=SimilarityConfig(**self.similarity_config),
            nli=NLIConfig(**self.nli_config),
            weights=WeightConfig(**self.weight_config)
        ) 