"""SapBERT embedder singleton.

Loads once at startup from local weights (data/models/nlp/sapbert).
Used by the indexer (batch) and the /embed endpoint (single query).
"""

import logging

import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

logger = logging.getLogger(__name__)

SAPBERT_PATH = "/app/models/nlp/sapbert"
MAX_LENGTH = 512


class SapBERTEmbedder:
    _instance: "SapBERTEmbedder | None" = None

    def __init__(self) -> None:
        self._tokenizer = AutoTokenizer.from_pretrained(SAPBERT_PATH)
        self._model = AutoModel.from_pretrained(SAPBERT_PATH)
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model.to(self._device)
        self._model.eval()
        logger.info(
            "SapBERT loaded from %s on %s", SAPBERT_PATH, self._device
        )

    @classmethod
    def get(cls) -> "SapBERTEmbedder":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def encode(self, text: str) -> list[float]:
        """Encode a single text into a 768-d normalized vector."""
        inputs = self._tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_LENGTH,
            padding=True,
        ).to(self._device)

        with torch.no_grad():
            out = self._model(**inputs)
            # CLS token, normalized for cosine similarity
            vec = F.normalize(out.last_hidden_state[:, 0, :], dim=-1)

        return vec.squeeze().cpu().tolist()

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode multiple texts. More efficient than calling encode() in a loop."""
        inputs = self._tokenizer(
            texts,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_LENGTH,
            padding=True,
        ).to(self._device)

        with torch.no_grad():
            out = self._model(**inputs)
            vecs = F.normalize(out.last_hidden_state[:, 0, :], dim=-1)

        return vecs.cpu().tolist()
