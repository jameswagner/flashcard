from typing import Dict, List
import torch
from dataclasses import dataclass
from .model_manager import ModelManager

@dataclass
class SimilarityResult:
    """Result from a single similarity model."""
    model_name: str
    score: float

class SemanticSimilarityScorer:
    """Handles semantic similarity scoring using an ensemble of models."""
    
    def __init__(self):
        model_manager = ModelManager()
        self.models = model_manager.similarity
    
    def get_similarity(self, text1: str, text2: str) -> Dict[str, float]:
        """
        Calculate semantic similarity between two texts using all models.
        Returns both individual model scores and ensemble score.
        """
        model_scores: List[SimilarityResult] = []
        
        for model_name, model in self.models.items():
            # Get embeddings
            emb1 = model.encode([text1], convert_to_tensor=True)
            emb2 = model.encode([text2], convert_to_tensor=True)
            
            # Calculate cosine similarity
            score = torch.nn.functional.cosine_similarity(emb1, emb2)[0].item()
            model_scores.append(SimilarityResult(model_name, score))
        
        # Calculate ensemble score (average)
        ensemble_score = sum(result.score for result in model_scores) / len(model_scores)
        
        return {
            "ensemble_score": ensemble_score,
            "model_scores": {
                result.model_name: result.score for result in model_scores
            }
        } 