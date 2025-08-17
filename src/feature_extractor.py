import numpy as np
import mediapipe as mp
from typing import List, Optional, Tuple
from config import CUSTOM_GESTURE_CONFIG

class FeatureExtractor:
    """
    GFLOW-5 & GFLOW-7: Feature extraction from MediaPipe hand landmarks
    
    Converts raw hand landmarks into normalized feature vectors suitable
    for machine learning training and recognition.
    """
    
    def __init__(self):
        self.feature_size = CUSTOM_GESTURE_CONFIG['feature_vector_size']
        
    def extract_features(self, hand_landmarks) -> Optional[np.ndarray]:
        """
        Extract normalized feature vector from hand landmarks
        
        Args:
            hand_landmarks: MediaPipe hand landmarks object
            
        Returns:
            Normalized feature vector (42-dimensional) or None if invalid
        """
        if not hand_landmarks or not hand_landmarks.landmark:
            return None
            
        try:
            # Convert landmarks to numpy array
            landmarks = np.array([[lm.x, lm.y] for lm in hand_landmarks.landmark])
            
            # Normalize features
            normalized_features = self._normalize_landmarks(landmarks)
            
            return normalized_features
            
        except Exception as e:
            print(f"Error extracting features: {e}")
            return None
    
    def _normalize_landmarks(self, landmarks: np.ndarray) -> np.ndarray:
        """
        Normalize landmarks to be position and scale invariant
        
        Args:
            landmarks: Raw landmark coordinates (21 x 2)
            
        Returns:
            Normalized feature vector (42-dimensional)
        """
        # Get wrist position (landmark 0) as reference point
        wrist = landmarks[0]
        
        # Translate all landmarks relative to wrist
        translated = landmarks - wrist
        
        # Calculate hand size for scale normalization
        # Use distance from wrist to middle finger tip (landmark 12)
        middle_finger_tip = landmarks[12]
        hand_size = np.linalg.norm(middle_finger_tip - wrist)
        
        # Avoid division by zero
        if hand_size < 1e-6:
            hand_size = 1.0
            
        # Scale normalize
        normalized = translated / hand_size
        
        # Flatten to 1D feature vector (21 landmarks × 2 coordinates = 42 features)
        feature_vector = normalized.flatten()
        
        return feature_vector
    
    def extract_features_from_landmarks_list(self, landmarks_list: List) -> List[np.ndarray]:
        """
        Extract features from a list of hand landmarks
        
        Args:
            landmarks_list: List of MediaPipe hand landmarks
            
        Returns:
            List of feature vectors
        """
        features = []
        for landmarks in landmarks_list:
            if landmarks:  # Only process if hand is detected
                feature_vector = self.extract_features(landmarks[0])  # Use first hand
                if feature_vector is not None:
                    features.append(feature_vector)
        
        return features
    
    def validate_feature_vector(self, feature_vector: np.ndarray) -> bool:
        """
        Validate that a feature vector is properly formatted
        
        Args:
            feature_vector: Feature vector to validate
            
        Returns:
            True if valid, False otherwise
        """
        if feature_vector is None:
            return False
            
        if not isinstance(feature_vector, np.ndarray):
            return False
            
        if feature_vector.shape != (self.feature_size,):
            return False
            
        if np.any(np.isnan(feature_vector)) or np.any(np.isinf(feature_vector)):
            return False
            
        return True
    
    def calculate_feature_similarity(self, features1: np.ndarray, features2: np.ndarray) -> float:
        """
        Calculate similarity between two feature vectors using cosine similarity
        
        Args:
            features1: First feature vector
            features2: Second feature vector
            
        Returns:
            Similarity score between 0 and 1 (1 = identical)
        """
        if not self.validate_feature_vector(features1) or not self.validate_feature_vector(features2):
            return 0.0
            
        # Calculate cosine similarity
        dot_product = np.dot(features1, features2)
        norm1 = np.linalg.norm(features1)
        norm2 = np.linalg.norm(features2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        similarity = dot_product / (norm1 * norm2)
        
        # Ensure similarity is between 0 and 1
        similarity = max(0.0, min(1.0, similarity))
        
        return similarity
    
    def get_feature_statistics(self, feature_vectors: List[np.ndarray]) -> dict:
        """
        Calculate statistics for a collection of feature vectors
        
        Args:
            feature_vectors: List of feature vectors
            
        Returns:
            Dictionary with mean, std, min, max statistics
        """
        if not feature_vectors:
            return {}
            
        valid_features = [f for f in feature_vectors if self.validate_feature_vector(f)]
        
        if not valid_features:
            return {}
            
        features_array = np.array(valid_features)
        
        return {
            'count': len(valid_features),
            'mean': np.mean(features_array, axis=0),
            'std': np.std(features_array, axis=0),
            'min': np.min(features_array, axis=0),
            'max': np.max(features_array, axis=0)
        }


def create_feature_extractor() -> FeatureExtractor:
    """
    Factory function to create a FeatureExtractor instance
    
    Returns:
        Configured FeatureExtractor instance
    """
    return FeatureExtractor()


# Example usage and testing
if __name__ == "__main__":
    # Test feature extraction with dummy data
    extractor = FeatureExtractor()
    
    # Create dummy landmarks (21 landmarks with x, y coordinates)
    dummy_landmarks = []
    for i in range(21):
        landmark = type('Landmark', (), {})()
        landmark.x = 0.5 + 0.1 * np.sin(i)
        landmark.y = 0.5 + 0.1 * np.cos(i)
        dummy_landmarks.append(landmark)
    
    # Create dummy hand landmarks object
    hand_landmarks = type('HandLandmarks', (), {})()
    hand_landmarks.landmark = dummy_landmarks
    
    # Extract features
    features = extractor.extract_features(hand_landmarks)
    
    if features is not None:
        print(f"Feature extraction successful!")
        print(f"Feature vector shape: {features.shape}")
        print(f"Feature vector (first 10 values): {features[:10]}")
        print(f"Feature validation: {extractor.validate_feature_vector(features)}")
    else:
        print("Feature extraction failed!")
