from typing import Dict
import torch
from dataclasses import dataclass
from .model_manager import ModelManager

@dataclass
class NLIResult:
    """Result from NLI scoring."""
    entailment: float
    contradiction: float
    neutral: float

class NLIScorer:
    """Handles Natural Language Inference scoring."""
    
    def __init__(self):
        model_manager = ModelManager()
        self.model, self.tokenizer = model_manager.nli
    
    def get_scores(self, premise: str, hypothesis: str) -> NLIResult:
        """
        Get NLI scores for premise-hypothesis pair.
        For answer scoring, typically:
        - premise = student answer
        - hypothesis = correct answer
        """
        inputs = self.tokenizer(premise, hypothesis, return_tensors="pt", padding=True, truncation=True)
        
        # Move inputs to GPU if model is on GPU
        if next(self.model.parameters()).is_cuda:
            inputs = {k: v.cuda() for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            scores = torch.nn.functional.softmax(outputs.logits, dim=1)[0]
            
            return NLIResult(
                entailment=float(scores[0].cpu()),
                neutral=float(scores[1].cpu()),
                contradiction=float(scores[2].cpu())
            ) 