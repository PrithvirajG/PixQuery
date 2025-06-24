from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union

class IDatabaseManager(ABC):
    """
    Abstract Base Class (Interface) for event database operations.
    Defines what operations an event repository must support,
    regardless of the underlying database technology.
    """

    @abstractmethod
    def add_image(self, image_path: str):
        """Adds a new event to the database and returns its ID."""
        pass

    @abstractmethod
    def get_all_images_database(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_multiple_images_by_ids(self, image_ids: List[int]) -> List[Dict[str, Any]]:
        """Retrieves multiple images by their IDs."""
        pass

    @abstractmethod
    def get_processed_images(self):
        """Retrieves all processed images from the database."""
        pass

    @abstractmethod
    def get_unprocessed_images(self) -> List[str]:
        """Retrieves all unprocessed images from the database."""
        pass

    @abstractmethod
    def update_image_metadata(self, image_id: int, detections: str, description: str) -> None:
        """Updates the detections and description for a given image ID."""
        pass

    @abstractmethod
    def update_metadata_by_cursor(self, cursor, detections: str, description: str) -> None:
        """Updates the metadata for a given image using a cursor."""
        pass

    @abstractmethod
    def get_image_by_id(self, image_id: int) -> Union[Dict[str, Any], None]:
        """Retrieves an image by its ID."""
        pass

    @abstractmethod
    def get_image_by_path(self, image_path: str) -> Union[Dict[str, Any], None]:
        """Retrieves an image by its path."""
        pass

    def get_cursor_by_path(self, image_path: str):
        """Retrieves a cursor for an image by its path."""
        pass

    @abstractmethod
    def get_processed_image_by_path(self, image_path: str) -> Union[Dict[str, Any], None]:
        """Retrieves an processed image by its path."""
        pass

    @abstractmethod
    def delete_image_by_id(self, image_id: int) -> None:
        """Deletes an image by its ID."""
        pass

    @abstractmethod
    def delete_image_by_path(self, image_path: str) -> None:
        """Deletes an image by its path."""
        pass

    # @abstractmethod
    # def get_event_by_id(self, event_id: int) -> Union[Dict[str, Any], None]:
    #     """Retrieves an event by its ID."""
    #     pass
    #
    # @abstractmethod
    # def get_events_by_type(self, event_type: str, limit: int = 100) -> List[Dict[str, Any]]:
    #     """Retrieves a list of events by type."""
    #     pass
    #
    # @abstractmethod
    # def count_events(self) -> int:
    #     """Counts total number of events."""
    #     pass

    # Add other common operations as needed (e.g., update_event, delete_event)