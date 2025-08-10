from abc import abstractmethod
from typing import List, Dict, Any, Optional
from .i_model_interface import IModelInterface, ModelResponse


class ChatMessage:
    """Represents a single message in a chat conversation."""
    
    def __init__(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        self.role = role  # 'user', 'assistant', 'system'
        self.content = content
        self.metadata = metadata or {}


class ChatConversation:
    """Represents a conversation with message history."""
    
    def __init__(self, messages: Optional[List[ChatMessage]] = None):
        self.messages = messages or []
        
    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a message to the conversation."""
        self.messages.append(ChatMessage(role, content, metadata))
        
    def get_messages(self) -> List[ChatMessage]:
        """Get all messages in the conversation."""
        return self.messages
        
    def clear(self):
        """Clear all messages from the conversation."""
        self.messages.clear()


class IChatModel(IModelInterface):
    """
    Interface for chat/conversational AI models like GPT, Claude, local LLMs, etc.
    """
    
    @abstractmethod
    def generate_response(
        self, 
        prompt: str, 
        conversation: Optional[ChatConversation] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> ModelResponse:
        """
        Generate a response to a text prompt.
        
        Args:
            prompt: The input text prompt
            conversation: Optional conversation history
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 to 1.0)
            **kwargs: Model-specific parameters
            
        Returns:
            ModelResponse: Generated text response
        """
        pass
        
    @abstractmethod
    def generate_stream(
        self, 
        prompt: str, 
        conversation: Optional[ChatConversation] = None,
        **kwargs
    ):
        """
        Generate a streaming response to a text prompt.
        
        Args:
            prompt: The input text prompt
            conversation: Optional conversation history
            **kwargs: Model-specific parameters
            
        Yields:
            str: Token chunks as they are generated
        """
        pass
        
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text string.
        
        Args:
            text: Input text to count tokens for
            
        Returns:
            int: Number of tokens
        """
        pass
        
    def get_max_context_length(self) -> int:
        """
        Get the maximum context length for this model.
        
        Returns:
            int: Maximum context length in tokens
        """
        return self.config.config.get('max_context_length', 4096)
        
    def truncate_conversation(
        self, 
        conversation: ChatConversation, 
        max_tokens: int
    ) -> ChatConversation:
        """
        Truncate conversation to fit within token limit.
        
        Args:
            conversation: Input conversation
            max_tokens: Maximum tokens to keep
            
        Returns:
            ChatConversation: Truncated conversation
        """
        # Default implementation - keep most recent messages
        # Override for model-specific truncation strategies
        truncated = ChatConversation()
        total_tokens = 0
        
        for message in reversed(conversation.messages):
            message_tokens = self.count_tokens(message.content)
            if total_tokens + message_tokens > max_tokens:
                break
            truncated.messages.insert(0, message)
            total_tokens += message_tokens
            
        return truncated