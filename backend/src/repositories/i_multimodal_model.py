from abc import abstractmethod
from typing import List, Dict, Any, Optional, Union
from PIL import Image
import numpy as np
from .i_model_interface import IModelInterface, ModelResponse
from .i_chat_model import ChatConversation


class MultimodalInput:
    """Represents multimodal input containing text and/or images."""
    
    def __init__(
        self,
        text: Optional[str] = None,
        images: Optional[List[Image.Image]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.text = text
        self.images = images or []
        self.metadata = metadata or {}
        
    def add_image(self, image: Image.Image):
        """Add an image to the input."""
        self.images.append(image)
        
    def has_text(self) -> bool:
        """Check if input contains text."""
        return self.text is not None and len(self.text.strip()) > 0
        
    def has_images(self) -> bool:
        """Check if input contains images."""
        return len(self.images) > 0


class IMultimodalModel(IModelInterface):
    """
    Interface for multimodal models that can process both text and images.
    Examples: CLIP, BLIP, GPT-4V, Claude 3, etc.
    """
    
    @abstractmethod
    def generate_text_from_image(
        self, 
        image: Image.Image, 
        prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ModelResponse:
        """
        Generate text description/caption from an image.
        
        Args:
            image: PIL Image to analyze
            prompt: Optional text prompt to guide generation
            max_tokens: Maximum tokens to generate
            **kwargs: Model-specific parameters
            
        Returns:
            ModelResponse: Generated text description
        """
        pass
        
    @abstractmethod
    def embed_text(self, text: str) -> ModelResponse:
        """
        Generate embedding vector from text.
        
        Args:
            text: Input text to embed
            
        Returns:
            ModelResponse: Text embedding as numpy array
        """
        pass
        
    @abstractmethod
    def embed_image(self, image: Image.Image) -> ModelResponse:
        """
        Generate embedding vector from image.
        
        Args:
            image: PIL Image to embed
            
        Returns:
            ModelResponse: Image embedding as numpy array
        """
        pass
        
    @abstractmethod
    def compute_similarity(
        self, 
        text_embedding: np.ndarray, 
        image_embedding: np.ndarray
    ) -> float:
        """
        Compute similarity between text and image embeddings.
        
        Args:
            text_embedding: Text embedding vector
            image_embedding: Image embedding vector
            
        Returns:
            Similarity score (typically cosine similarity)
        """
        pass
        
    def answer_question_about_image(
        self,
        image: Image.Image,
        question: str,
        conversation: Optional[ChatConversation] = None,
        **kwargs
    ) -> ModelResponse:
        """
        Answer a question about an image (VQA - Visual Question Answering).
        
        Args:
            image: PIL Image to analyze
            question: Question to answer about the image
            conversation: Optional conversation history
            **kwargs: Model-specific parameters
            
        Returns:
            ModelResponse: Answer to the question
        """
        # Default implementation using text generation
        prompt = f"Question: {question}\nPlease answer based on the provided image."
        return self.generate_text_from_image(image, prompt, **kwargs)
        
    def process_multimodal_input(
        self,
        multimodal_input: MultimodalInput,
        **kwargs
    ) -> ModelResponse:
        """
        Process multimodal input (text + images).
        
        Args:
            multimodal_input: MultimodalInput object
            **kwargs: Model-specific parameters
            
        Returns:
            ModelResponse: Processed result
        """
        if not multimodal_input.has_images():
            return ModelResponse(
                result=None,
                error="No images provided in multimodal input"
            )
            
        # Default: process first image with text as prompt
        image = multimodal_input.images[0]
        prompt = multimodal_input.text
        return self.generate_text_from_image(image, prompt, **kwargs)
        
    def find_similar_images(
        self,
        query_text: str,
        image_embeddings: List[np.ndarray],
        top_k: int = 5
    ) -> List[int]:
        """
        Find images most similar to a text query.
        
        Args:
            query_text: Text query
            image_embeddings: List of image embedding vectors
            top_k: Number of top results to return
            
        Returns:
            List of indices of most similar images
        """
        text_response = self.embed_text(query_text)
        if not text_response.success:
            return []
            
        text_embedding = text_response.result
        similarities = []
        
        for i, img_embedding in enumerate(image_embeddings):
            similarity = self.compute_similarity(text_embedding, img_embedding)
            similarities.append((i, similarity))
            
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return [idx for idx, _ in similarities[:top_k]]
        
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings produced by this model.
        
        Returns:
            Embedding dimension
        """
        return self.config.config.get('embedding_dimension', 512)