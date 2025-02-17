from typing import Dict, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
from .model_manager import ModelManager

@dataclass
class Concept:
    """Represents a key concept with its text and type."""
    text: str
    type: str  # 'entity', 'noun_chunk', 'keyword'
    role: str  # semantic role from dependency parsing

    def __hash__(self):
        return hash((self.text.lower(), self.type, self.role))

@dataclass
class SRLResult:
    """Result from SRL scoring."""
    score: float
    role_scores: Dict[str, float]
    missing_concepts: list[str]
    metadata: Dict

class SRLScorer:
    """Handles Semantic Role Labeling scoring."""
    
    def __init__(self):
        model_manager = ModelManager()
        self.nlp = model_manager.spacy
        self.role_weights = {
            'SUBJECT': 1.5,  # Core roles weighted more heavily
            'VERB': 1.5,
            'OBJECT': 1.5,
            'MODIFIER': 0.3,
            'FULL': 0.2
        }
    
    def get_semantic_roles(self, text: str) -> Dict[str, str]:
        """Extract semantic roles using SpaCy's dependency parsing."""
        doc = self.nlp(text)
        roles = defaultdict(list)
        
        # Find the root verb and its arguments
        for token in doc:
            if token.dep_ == "ROOT" and token.pos_ == "VERB":
                roles["VERB"].append(token.text)
                
                for child in token.children:
                    if child.dep_ in ["nsubj", "nsubjpass"]:
                        roles["SUBJECT"].extend([child.text] + [t.text for t in child.children])
                    elif child.dep_ in ["dobj", "pobj"]:
                        roles["OBJECT"].extend([child.text] + [t.text for t in child.children])
                    elif child.dep_ in ["advmod", "amod"]:
                        roles["MODIFIER"].append(child.text)
        
        return {k: ' '.join(v) for k, v in roles.items()}
    
    def extract_concepts(self, text: str, role: str = "NONE") -> Set[Concept]:
        """Extract key concepts from text."""
        doc = self.nlp(text)
        concepts = set()
        
        # Named entities
        for ent in doc.ents:
            concepts.add(Concept(text=ent.text, type='entity', role=role))
        
        # Noun chunks
        for chunk in doc.noun_chunks:
            if not any(token.pos_ == "PRON" for token in chunk) and \
               not all(token.is_stop for token in chunk):
                concepts.add(Concept(text=chunk.text, type='noun_chunk', role=role))
        
        # Important tokens
        for token in doc:
            if token.has_vector and \
               token.pos_ in ['NOUN', 'VERB', 'ADJ'] and \
               not token.is_stop and \
               not any(chunk.start <= token.i < chunk.end for chunk in doc.noun_chunks):
                
                token_role = role
                if token.dep_ in ["nsubj", "nsubjpass"]:
                    token_role = "SUBJECT"
                elif token.dep_ in ["dobj", "pobj"]:
                    token_role = "OBJECT"
                elif token.dep_ == "ROOT" and token.pos_ == "VERB":
                    token_role = "VERB"
                
                concepts.add(Concept(text=token.text, type='keyword', role=token_role))
        
        return concepts
    
    def concept_similarity(self, concept1: Concept, concept2: Concept) -> float:
        """Calculate similarity between two concepts."""
        doc1 = self.nlp(concept1.text)
        doc2 = self.nlp(concept2.text)
        
        if doc1.has_vector and doc2.has_vector:
            try:
                similarity = float(doc1.similarity(doc2))
                if isinstance(similarity, complex):
                    similarity = similarity.real
                
                # Boost score for matching types and roles
                if concept1.type == concept2.type:
                    similarity = min(1.0, similarity * 1.1)
                if concept1.role == concept2.role:
                    similarity = min(1.0, similarity * 1.1)
                
                return max(0.0, min(1.0, similarity))  # Ensure score is between 0 and 1
            except (ValueError, TypeError):
                return 0.0
        return 0.0
    
    def get_score(self, correct: str, student: str) -> SRLResult:
        """Get SRL-based score comparing student answer to correct answer."""
        # Get roles and concepts
        correct_roles = self.get_semantic_roles(correct)
        student_roles = self.get_semantic_roles(student)
        
        correct_concepts = {
            role: self.extract_concepts(text, role)
            for role, text in correct_roles.items()
        }
        student_concepts = {
            role: self.extract_concepts(text, role)
            for role, text in student_roles.items()
        }
        
        # Add full text concepts
        correct_concepts['FULL'] = self.extract_concepts(correct)
        student_concepts['FULL'] = self.extract_concepts(student)
        
        # Score each role
        role_scores = {}
        missing_concepts = []
        
        for role, c_concepts in correct_concepts.items():
            if not c_concepts:
                continue
            
            s_concepts = student_concepts.get(role, set())
            if not s_concepts and role != 'FULL':
                s_concepts = student_concepts['FULL']
                self.role_weights[role] *= 0.7  # Penalize for missing role
            
            # Score concepts
            concept_scores = []
            for c_concept in c_concepts:
                if s_concepts:
                    try:
                        best_match = max(
                            self.concept_similarity(c_concept, s_concept)
                            for s_concept in s_concepts
                        )
                        best_match = float(best_match ** 1.5)  # Make high scores harder to achieve
                    except (ValueError, TypeError):
                        best_match = 0.0
                else:
                    best_match = 0.0
                
                if best_match < 0.6:
                    missing_concepts.append(c_concept.text)
                concept_scores.append(best_match)
            
            if concept_scores:
                # Use geometric mean for stricter scoring
                import numpy as np
                role_scores[role] = np.exp(np.mean(np.log([max(0.05, score) for score in concept_scores])))
        
        # Calculate final score
        weighted_scores = []
        total_weight = 0
        
        for role, score in role_scores.items():
            weight = self.role_weights.get(role, 1.0)
            weighted_scores.append(score * weight)
            total_weight += weight
        
        if total_weight > 0:
            raw_score = sum(weighted_scores) / total_weight
        else:
            raw_score = 0.0
        
        # Apply missing concepts penalty
        if missing_concepts:
            missing_penalty = len(missing_concepts) / len([c for concepts in correct_concepts.values() for c in concepts])
            final_score = raw_score * (1 - missing_penalty * 0.7)
        else:
            final_score = raw_score
        
        return SRLResult(
            score=final_score,
            role_scores=role_scores,
            missing_concepts=missing_concepts,
            metadata={
                'correct_roles': correct_roles,
                'student_roles': student_roles
            }
        ) 