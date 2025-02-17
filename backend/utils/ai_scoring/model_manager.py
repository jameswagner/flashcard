from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sentence_transformers import SentenceTransformer
import spacy
import torch
from typing import Dict
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time

class ModelManager:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
        return cls._instance

    async def initialize(self):
        """Async initialization method."""
        if not self._initialized:
            print("Initializing AI models...")
            start_time = time.time()
            
            await self._initialize_models()
            
            self._initialized = True
            print(f"AI models initialized successfully in {time.time() - start_time:.2f} seconds")

    async def _initialize_models(self):
        """Initialize all models in parallel."""
        # Create thread pool for parallel loading
        with ThreadPoolExecutor() as executor:
            # Schedule all model loading tasks
            loop = asyncio.get_running_loop()
            nli_future = loop.run_in_executor(executor, self._load_nli_models)
            similarity_future = loop.run_in_executor(executor, self._load_similarity_models)
            spacy_future = loop.run_in_executor(executor, self._load_spacy_model)
            
            # Wait for all futures to complete
            self.nli_model, self.nli_tokenizer = await nli_future
            self.similarity_models = await similarity_future
            self.spacy_model = await spacy_future
            
            # Move models to GPU if available
            if torch.cuda.is_available():
                self.nli_model = self.nli_model.cuda()
                for model in self.similarity_models.values():
                    model = model.cuda()

    def _load_nli_models(self):
        """Load NLI model and tokenizer."""
        print("Loading NLI models...")
        model_name = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        model.eval()
        print("NLI models loaded")
        return model, tokenizer

    def _load_similarity_models(self):
        """Load similarity models."""
        print("Loading similarity models...")
        models = {
            "minilm": SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2"),
            "mpnet": SentenceTransformer("sentence-transformers/all-mpnet-base-v2"),
            "multilingual": SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        }
        print("Similarity models loaded")
        return models

    def _load_spacy_model(self):
        """Load spaCy model."""
        print("Loading spaCy model...")
        model = spacy.load("en_core_web_lg")
        print("SpaCy model loaded")
        return model

    @property
    def nli(self) -> tuple:
        """Get NLI model and tokenizer."""
        if not self._initialized:
            raise RuntimeError("Models not initialized. Call initialize() first.")
        return self.nli_model, self.nli_tokenizer

    @property
    def similarity(self) -> Dict[str, SentenceTransformer]:
        """Get similarity models."""
        if not self._initialized:
            raise RuntimeError("Models not initialized. Call initialize() first.")
        return self.similarity_models

    @property
    def spacy(self):
        """Get spaCy model."""
        if not self._initialized:
            raise RuntimeError("Models not initialized. Call initialize() first.")
        return self.spacy_model 