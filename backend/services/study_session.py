from fastapi import HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, UTC
from typing import Dict, List, Optional

from models.study import StudySession, CardReview, ReviewScore
from models.flashcard import Flashcard
from models.set import FlashcardSet
from models.enums import StudySessionType, ReviewGrade, ReviewConfidence, ScoreType
from utils.ai_scoring.score_calculator import AnswerScoreCalculator

from api.models.requests.study_session import StudySessionCreate, CardReviewCreate, ReviewScoreCreate
from api.models.responses.study_session import (
    StudySessionResponse,
    CardReviewResponse,
    ReviewScoreResponse,
    SessionCompletionResponse
)

class StudySessionService:
    def __init__(self, db: Session):
        self.db = db

    def create_session(self, session_data: StudySessionCreate, user_id: Optional[str] = None) -> StudySession:
        """Create a new study session."""
        # Verify set exists
        flashcard_set = self.db.get(FlashcardSet, session_data.set_id)
        if not flashcard_set:
            raise HTTPException(status_code=404, detail="Flashcard set not found")

        # Create session
        session = StudySession(
            set_id=session_data.set_id,
            session_type=session_data.session_type.value,
            settings=session_data.settings or {},  # Ensure settings is a dict
            user_id=user_id or "anonymous",
            started_at=datetime.now(UTC)  # Explicitly set started_at
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        # Map to response model
        return StudySessionResponse(
            id=session.id,
            set_id=session.set_id,
            session_type=session.session_type,
            settings=session.settings or {},
            cards_reviewed=session.cards_reviewed,
            correct_count=session.correct_count,
            incorrect_count=session.incorrect_count,
            average_nli_score=None,
            average_self_assessed_score=None,
            average_confidence=session.average_confidence,
            created_at=session.started_at,  # Map started_at to created_at
            completed_at=session.completed_at,
            reviews=[]  # New session has no reviews
        )

    def get_session(self, session_id: int) -> StudySession:
        """Get a study session by ID."""
        session = self.db.get(StudySession, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Study session not found")
        return session

    def create_review(
        self,
        session_id: int,
        review_data: CardReviewCreate,
        background_tasks: BackgroundTasks
    ) -> CardReview:
        """Create a new card review in a study session."""
        # Verify session exists and is active
        session = self.get_session(session_id)
        if session.completed_at:
            raise HTTPException(status_code=400, detail="Study session is already completed")
        
        # Verify flashcard exists and belongs to the session's set
        flashcard = self.db.get(Flashcard, review_data.flashcard_id)
        if not flashcard:
            raise HTTPException(status_code=404, detail="Flashcard not found")
        if not any(s.id == session.set_id for s in flashcard.flashcard_sets):
            raise HTTPException(
                status_code=400,
                detail="Flashcard does not belong to this study session's set"
            )
        
        # Create review
        review = CardReview(
            session_id=session_id,
            flashcard_id=review_data.flashcard_id,
            answer_method=review_data.answer_method.value,
            user_answer=review_data.user_answer,
            time_to_answer=review_data.time_to_answer
        )
        self.db.add(review)
        
        # Update session stats
        session.cards_reviewed += 1
        
        # Commit to get the review ID
        self.db.commit()
        self.db.refresh(review)
        
        # If we have a user answer, create a pending score record and kick off background scoring
        if review_data.user_answer:
            # Create pending score record
            score = ReviewScore(
                review_id=review.id,
                score_type=ScoreType.FINAL_AI.value,
                score=0.0,  # Will be updated by background task
                score_metadata={"status": "pending"}
            )
            self.db.add(score)
            self.db.commit()
            
            # Schedule background scoring
            background_tasks.add_task(
                self._perform_ai_scoring,
                score.id,
                flashcard.back,
                review_data.user_answer
            )
        
        return review

    def get_review_scores(self, review_id: int) -> List[ReviewScore]:
        """Get all scores for a review."""
        review = self.db.get(CardReview, review_id)
        if not review:
            raise HTTPException(status_code=404, detail="Card review not found")
        return review.scores

    def complete_session(self, session_id: int) -> SessionCompletionResponse:
        """Complete a study session and calculate statistics."""
        session = self.get_session(session_id)
        if session.completed_at:
            raise HTTPException(status_code=400, detail="Study session is already completed")
        
        # Initialize counters and score lists
        ai_scores = {
            ScoreType.FINAL_AI.value: [],
            ScoreType.NLI_ENTAILMENT.value: [],
            ScoreType.NLI_CONTRADICTION.value: [],
            ScoreType.SEMANTIC_SIMILARITY.value: [],
            ScoreType.SEMANTIC_ROLE.value: []
        }
        self_assessed_scores = []
        confidence_values = []
        correct_count = 0
        incorrect_count = 0
        total_reviews = len(session.reviews)
        
        # Confidence value mapping
        confidence_map = {
            ReviewConfidence.VERY_LOW.value: 0.2,
            ReviewConfidence.LOW.value: 0.4,
            ReviewConfidence.MEDIUM.value: 0.6,
            ReviewConfidence.HIGH.value: 0.8,
            ReviewConfidence.PERFECT.value: 1.0
        }
        
        # Process all reviews and scores
        for review in session.reviews:
            for score in review.scores:
                if score.score_type in ai_scores:
                    ai_scores[score.score_type].append(score.score)
                
                if score.score_type == ScoreType.SELF_ASSESSED.value:
                    self_assessed_scores.append(score.score)
                    if score.grade:
                        if score.grade in [ReviewGrade.CORRECT, ReviewGrade.TOO_EASY]:
                            correct_count += 1
                        elif score.grade == ReviewGrade.INCORRECT:
                            incorrect_count += 1
                    if score.confidence:
                        confidence_values.append(confidence_map[score.confidence])
        
        # Update session counts
        session.correct_count = correct_count
        session.incorrect_count = incorrect_count
        
        # Calculate statistics
        stats = {
            "cards_reviewed": session.cards_reviewed,
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
            "accuracy": correct_count / total_reviews if total_reviews > 0 else 0,
            "average_confidence": sum(confidence_values) / len(confidence_values) if confidence_values else 0,
            "average_self_assessed_score": sum(self_assessed_scores) / len(self_assessed_scores) if self_assessed_scores else 0,
            "ai_scores": {}
        }
        
        # Add AI score averages
        for score_type, scores in ai_scores.items():
            if scores:
                avg_score = sum(scores) / len(scores)
                stats["ai_scores"][score_type] = avg_score
                
                # For backward compatibility
                if score_type == ScoreType.FINAL_AI.value:
                    session.average_nli_score = avg_score
        
        session.average_self_assessed_score = stats["average_self_assessed_score"]
        session.average_confidence = stats["average_confidence"]
        session.completed_at = datetime.now(UTC)
        
        try:
            self.db.commit()
            return SessionCompletionResponse(
                status="success",
                message="Study session completed",
                statistics=stats
            )
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to complete study session: {str(e)}"
            )

    async def _perform_ai_scoring(self, score_id: int, correct_answer: str, user_answer: str):
        """Background task to perform AI scoring of an answer."""
        try:
            calculator = AnswerScoreCalculator()
            result = await calculator.calculate_scores(correct_answer, user_answer)
            
            score = self.db.get(ReviewScore, score_id)
            if not score:
                return
            
            # Update the final score
            score.score = result.final_score
            score.score_metadata = {
                "status": "completed",
                "metadata": result.metadata
            }
            
            # Create individual component scores
            for score_type, value in result.component_scores.items():
                if score_type != ScoreType.FINAL_AI.value:
                    # Get component-specific metadata
                    metadata = {
                        "status": "completed",
                        **({
                            "similarity": result.metadata["similarity"]
                        } if score_type == ScoreType.SEMANTIC_SIMILARITY.value else {}),
                        **({
                            "srl": result.metadata["srl"]
                        } if score_type == ScoreType.SEMANTIC_ROLE.value else {}),
                        **({
                            "nli": result.metadata["nli"]
                        } if score_type in [ScoreType.NLI_ENTAILMENT.value, ScoreType.NLI_CONTRADICTION.value] else {})
                    }
                    
                    component_score = ReviewScore(
                        review_id=score.review_id,
                        score_type=score_type,
                        score=value,
                        score_metadata=metadata,
                        scoring_config_id=result.scoring_config_id
                    )
                    self.db.add(component_score)
            
            # Update scoring config ID for the final score
            score.scoring_config_id = result.scoring_config_id
            self.db.commit()
            
        except Exception as e:
            # Log error and update score status
            score = self.db.get(ReviewScore, score_id)
            if score:
                score.score_metadata = {
                    "status": "error",
                    "error": str(e)
                }
                self.db.commit()

    def create_review_score(self, review_id: int, score_data: ReviewScoreCreate) -> ReviewScore:
        """Create a new score for a review."""
        # Verify review exists
        review = self.db.get(CardReview, review_id)
        if not review:
            raise HTTPException(status_code=404, detail="Card review not found")
        
        # Validate score type
        try:
            score_type = ScoreType(score_data.score_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid score type: {score_data.score_type}")
        
        # Create score
        score = ReviewScore(
            review_id=review_id,
            score_type=score_type.value,
            score=score_data.score,
            grade=score_data.grade.value if score_data.grade else None,
            confidence=score_data.confidence.value if score_data.confidence else None,
            score_metadata=score_data.score_metadata or {},
            created_at=datetime.utcnow(),  # Use utcnow to match database model
            # Only set scoring_config_id for AI-based scores
            scoring_config_id=None if score_type == ScoreType.SELF_ASSESSED else settings.active_scoring_config_id
        )
        self.db.add(score)
        
        # Update session stats if this is a self-assessed score
        if score_type == ScoreType.SELF_ASSESSED and score_data.grade:
            session = review.session
            if score_data.grade in [ReviewGrade.CORRECT, ReviewGrade.TOO_EASY]:
                session.correct_count += 1
            elif score_data.grade == ReviewGrade.INCORRECT:
                session.incorrect_count += 1
        
        try:
            self.db.commit()
            self.db.refresh(score)
            return score
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create review score: {str(e)}"
            ) 