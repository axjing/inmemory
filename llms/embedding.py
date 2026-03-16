import os
import json
import base64
from typing import List, Optional, Union

from abc import ABC, abstractmethod

from openai import OpenAI


class EmbeddingBase(ABC):
    """Base class for embedding models."""
    
    def __init__(self, model_name: str, api_key: Optional[str] = None, api_base: Optional[str] = None, **kwargs):
        """Initialize embedding model.
        
        Args:
            model_name: Model name or path
            api_key: API key
            api_base: API base URL
            **kwargs: Additional configuration
        """
        self.model_name = model_name
        self.api_key = api_key
        self.api_base = api_base
        
    @abstractmethod
    def encode(self, text: Union[str, List[str]]) -> List[List[float]]:
        """Encode text into embeddings.
        
        Args:
            text: Text or list of texts to encode
            
        Returns:
            List of embeddings
        """
        raise NotImplementedError


class OpenAIEmbedding(EmbeddingBase):
    """OpenAI embedding model."""
    
    def __init__(self, model_name: str = "text-embedding-ada-002", api_key: Optional[str] = None, api_base: Optional[str] = None, **kwargs):
        super().__init__(model_name, api_key, api_base, **kwargs)
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_base,
        )
    
    def encode(self, text: Union[str, List[str]]) -> List[List[float]]:
        """Encode text into embeddings using OpenAI API."""
        if isinstance(text, str):
            text = [text]
        
        response = self.client.embeddings.create(
            model=self.model_name,
            input=text
        )
        
        return [item.embedding for item in response.data]


class LocalAIEmbedding(EmbeddingBase):
    """LocalAI embedding model."""
    
    def __init__(self, model_name: str, api_key: str = "empty", api_base: str = "http://localhost:8080/v1", **kwargs):
        super().__init__(model_name, api_key, api_base, **kwargs)
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_base,
        )
    
    def encode(self, text: Union[str, List[str]]) -> List[List[float]]:
        """Encode text into embeddings using LocalAI API."""
        if isinstance(text, str):
            text = [text]
        
        response = self.client.embeddings.create(
            model=self.model_name,
            input=text
        )
        
        return [item.embedding for item in response.data]