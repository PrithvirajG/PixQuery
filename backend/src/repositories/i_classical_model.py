from abc import abstractmethod
from typing import List, Dict, Any, Optional, Union
import numpy as np
import pandas as pd
from .i_model_interface import IModelInterface, ModelResponse


class IClassicalModel(IModelInterface):
    """
    Interface for classical machine learning models (scikit-learn, XGBoost, etc.).
    """
    
    @abstractmethod
    def train(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        validation_data: Optional[tuple] = None,
        **kwargs
    ) -> ModelResponse:
        """
        Train the model on provided data.
        
        Args:
            X: Training features
            y: Training labels
            validation_data: Optional (X_val, y_val) tuple
            **kwargs: Model-specific training parameters
            
        Returns:
            ModelResponse: Training results and metrics
        """
        pass
        
    @abstractmethod
    def predict_proba(self, X: Union[np.ndarray, pd.DataFrame]) -> ModelResponse:
        """
        Predict class probabilities.
        
        Args:
            X: Input features
            
        Returns:
            ModelResponse: Prediction probabilities
        """
        pass
        
    @abstractmethod
    def predict_single(self, sample: Union[np.ndarray, Dict[str, Any]]) -> ModelResponse:
        """
        Make prediction for a single sample.
        
        Args:
            sample: Single sample to predict
            
        Returns:
            ModelResponse: Prediction result
        """
        pass
        
    @abstractmethod
    def get_feature_importance(self) -> ModelResponse:
        """
        Get feature importance scores.
        
        Returns:
            ModelResponse: Feature importance scores
        """
        pass
        
    def evaluate(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series]
    ) -> ModelResponse:
        """
        Evaluate model performance on test data.
        
        Args:
            X: Test features
            y: True labels
            
        Returns:
            ModelResponse: Evaluation metrics
        """
        predictions = self.predict(X)
        if not predictions.success:
            return predictions
            
        # Calculate basic metrics
        y_pred = predictions.result
        accuracy = np.mean(y == y_pred) if len(y) > 0 else 0.0
        
        metrics = {
            'accuracy': accuracy,
            'n_samples': len(y),
            'n_correct': np.sum(y == y_pred)
        }
        
        return ModelResponse(result=metrics)
        
    def cross_validate(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        cv_folds: int = 5,
        **kwargs
    ) -> ModelResponse:
        """
        Perform cross-validation on the model.
        
        Args:
            X: Features
            y: Labels
            cv_folds: Number of cross-validation folds
            **kwargs: Additional parameters
            
        Returns:
            ModelResponse: Cross-validation results
        """
        # Default implementation - override for specific CV strategies
        return ModelResponse(
            result=None,
            error="Cross-validation not implemented for this model"
        )
        
    def save_model(self, filepath: str) -> ModelResponse:
        """
        Save the trained model to disk.
        
        Args:
            filepath: Path to save the model
            
        Returns:
            ModelResponse: Save operation result
        """
        return ModelResponse(
            result=None,
            error="Model saving not implemented for this model"
        )
        
    def load_model_from_file(self, filepath: str) -> ModelResponse:
        """
        Load a trained model from disk.
        
        Args:
            filepath: Path to the saved model
            
        Returns:
            ModelResponse: Load operation result
        """
        return ModelResponse(
            result=None,
            error="Model loading not implemented for this model"
        )
        
    def get_hyperparameters(self) -> Dict[str, Any]:
        """
        Get current hyperparameters of the model.
        
        Returns:
            Dictionary of hyperparameters
        """
        return self.config.config.get('hyperparameters', {})
        
    def set_hyperparameters(self, params: Dict[str, Any]) -> bool:
        """
        Set hyperparameters for the model.
        
        Args:
            params: Dictionary of hyperparameters
            
        Returns:
            True if parameters were set successfully
        """
        if 'hyperparameters' not in self.config.config:
            self.config.config['hyperparameters'] = {}
        
        self.config.config['hyperparameters'].update(params)
        return True
        
    def get_supported_metrics(self) -> List[str]:
        """
        Get list of metrics supported by this model type.
        
        Returns:
            List of supported metric names
        """
        return ['accuracy', 'precision', 'recall', 'f1_score']
        
    def is_trained(self) -> bool:
        """
        Check if the model has been trained.
        
        Returns:
            True if model is trained
        """
        return getattr(self, '_is_trained', False)