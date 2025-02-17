from typing import Dict, List
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from models.enums import ScoreType
from config.env import settings
from .nli_scorer import NLIScorer
from .similarity_scorer import SemanticSimilarityScorer
from .srl_scorer import SRLScorer

@dataclass
class ScoringResult:
    """Complete scoring result with all components."""
    final_score: float
    component_scores: Dict[str, float]
    metadata: Dict
    scoring_config_id: int

class AnswerScoreCalculator:
    """Coordinates scoring components and calculates final weighted score."""
    
    def __init__(self):
        self.nli_scorer = NLIScorer()
        self.similarity_scorer = SemanticSimilarityScorer()
        self.srl_scorer = SRLScorer()
        self.executor = ThreadPoolExecutor(max_workers=3)
    
    async def calculate_scores(self, correct: str, student: str) -> ScoringResult:
        """
        Calculate all scores for a student answer asynchronously.
        Uses thread pool for CPU-bound scoring tasks.
        """
        loop = asyncio.get_event_loop()
        config = settings.scoring
        
        # Run scoring components in parallel
        tasks = [
            loop.run_in_executor(self.executor, self.nli_scorer.get_scores, student, correct),
            loop.run_in_executor(self.executor, self.similarity_scorer.get_similarity, correct, student),
            loop.run_in_executor(self.executor, self.srl_scorer.get_score, correct, student)
        ]
        
        nli_result, similarity_result, srl_result = await asyncio.gather(*tasks)
        
        # Extract scores
        component_scores = {
            ScoreType.NLI_ENTAILMENT.value: nli_result.entailment,
            ScoreType.NLI_CONTRADICTION.value: nli_result.contradiction,
            ScoreType.SEMANTIC_SIMILARITY.value: similarity_result["ensemble_score"],
            ScoreType.SEMANTIC_ROLE.value: srl_result.score
        }
        
        # If strong contradiction, zero out other scores
        if nli_result.contradiction >= config.nli.contradiction_threshold:
            final_score = 0.0
            for key in component_scores:
                if key != ScoreType.NLI_CONTRADICTION.value:
                    component_scores[key] = 0.0
        else:
            # Calculate weighted final score based on config
            if nli_result.entailment > config.nli.high_entailment_threshold:
                weights = config.weights.high_entailment_weights
            else:
                weights = config.weights.partial_match_weights
            
            final_score = (
                weights["entailment"] * nli_result.entailment +
                weights["similarity"] * similarity_result["ensemble_score"] +
                weights["srl"] * srl_result.score
            )
        
        # Add final score to component scores
        component_scores[ScoreType.FINAL_AI.value] = final_score
        
        # Combine metadata from all components
        metadata = {
            "nli": {
                "neutral": nli_result.neutral,
                "was_contradiction": nli_result.contradiction >= config.nli.contradiction_threshold
            },
            "similarity": {
                "model_scores": similarity_result["model_scores"]
            },
            "srl": {
                "role_scores": srl_result.role_scores,
                "missing_concepts": srl_result.missing_concepts,
                **srl_result.metadata
            }
        }
        
        return ScoringResult(
            final_score=final_score,
            component_scores=component_scores,
            metadata=metadata,
            scoring_config_id=settings.active_scoring_config_id
        ) 