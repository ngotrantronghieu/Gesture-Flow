import os
import json
import pickle
import shutil
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from sklearn.preprocessing import StandardScaler
import warnings
from config import CUSTOM_GESTURE_CONFIG, PROJECT_ROOT
from feature_extractor import FeatureExtractor

class CustomGestureManager:
    """
    GFLOW-5, GFLOW-7, GFLOW-8: Custom gesture data management and ML training

    Handles storage, training, and recognition of user-defined static gestures.
    """

    def __init__(self, profile_name: str = None):
        self.config = CUSTOM_GESTURE_CONFIG
        self.feature_extractor = FeatureExtractor()
        self.gestures_metadata = {}
        self.trained_models = {}

        # GFLOW-18: Profile support
        self.current_profile = profile_name or 'default'
        self.profile_base_dir = os.path.join(PROJECT_ROOT, 'data', 'profiles')

        # Create directories
        self._create_directories()

        # Load existing gestures
        self.load_all_gestures()

    def _create_directories(self):
        """Create necessary directories for data storage"""
        # GFLOW-18: Create profile-specific directories
        profile_data_dir = self._get_profile_data_directory()
        profile_models_dir = self._get_profile_models_directory()

        os.makedirs(profile_data_dir, exist_ok=True)
        os.makedirs(profile_models_dir, exist_ok=True)

        # Also create legacy directories for backward compatibility
        os.makedirs(self.config['data_directory'], exist_ok=True)
        os.makedirs(self.config['models_directory'], exist_ok=True)

    def _get_profile_data_directory(self) -> str:
        """Get profile-specific data directory"""
        return os.path.join(self.profile_base_dir, self.current_profile, 'custom_gestures')

    def _get_profile_models_directory(self) -> str:
        """Get profile-specific models directory"""
        return os.path.join(self.profile_base_dir, self.current_profile, 'custom_gestures', 'models')

    def set_profile(self, profile_name: str):
        """
        GFLOW-18: Set the current profile and reload gestures

        Args:
            profile_name: Name of the profile to set
        """
        if profile_name != self.current_profile:
            # Save current profile data
            self._save_metadata()

            # Switch to new profile
            self.current_profile = profile_name

            # Create directories for new profile
            self._create_directories()

            # Clear current data
            self.gestures_metadata = {}
            self.trained_models = {}

            # Load new profile data
            self.load_all_gestures()

    def get_current_profile(self) -> str:
        """Get the current profile name"""
        return self.current_profile

    def create_new_gesture(self, name: str, description: str = "") -> bool:
        """
        Create a new custom gesture entry

        Args:
            name: Gesture name
            description: Optional description

        Returns:
            True if created successfully, False otherwise
        """
        if not self._validate_gesture_name(name):
            return False

        if name in self.gestures_metadata:
            print(f"Gesture '{name}' already exists")
            return False

        gesture_id = self._generate_gesture_id(name)

        gesture_data = {
            'id': gesture_id,
            'name': name,
            'description': description,
            'created_date': datetime.now().isoformat(),
            'sample_count': 0,
            'is_trained': False,
            'training_accuracy': 0.0,
            'last_trained': None,
            'feature_file': f"{gesture_id}_features.pkl",
            'model_file': f"{gesture_id}_model.pkl"
        }

        self.gestures_metadata[name] = gesture_data
        self._save_metadata()

        return True

    def add_gesture_sample(self, gesture_name: str, hand_landmarks) -> bool:
        """
        Add a training sample for a gesture

        Args:
            gesture_name: Name of the gesture
            hand_landmarks: MediaPipe hand landmarks

        Returns:
            True if sample added successfully, False otherwise
        """
        if gesture_name not in self.gestures_metadata:
            return False

        # Extract features
        features = self.feature_extractor.extract_features(hand_landmarks)
        if features is None:
            return False

        # Load existing samples or create new list
        samples = self._load_gesture_samples(gesture_name)
        samples.append(features)

        # Save updated samples
        if self._save_gesture_samples(gesture_name, samples):
            self.gestures_metadata[gesture_name]['sample_count'] = len(samples)
            self._save_metadata()
            return True

        return False

    def train_gesture(self, gesture_name: str) -> Tuple[bool, float]:
        """
        Train a distance-based classifier for a gesture

        Args:
            gesture_name: Name of the gesture to train

        Returns:
            Tuple of (success, accuracy_score)
        """
        if gesture_name not in self.gestures_metadata:
            return False, 0.0

        # Load training samples
        samples = self._load_gesture_samples(gesture_name)
        if len(samples) < 5:  # Minimum samples required
            print(f"Not enough samples for '{gesture_name}'. Need at least 5, have {len(samples)}")
            return False, 0.0

        try:
            # Prepare training data
            X = np.array(samples)

            # Validate feature vectors
            valid_samples = []
            for sample in samples:
                if self.feature_extractor.validate_feature_vector(sample):
                    valid_samples.append(sample)

            if len(valid_samples) < 5:
                print(f"Not enough valid samples for '{gesture_name}'. Need at least 5, have {len(valid_samples)}")
                return False, 0.0

            X = np.array(valid_samples)

            # Create distance-based model using mean and standard deviation
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # Calculate gesture template (mean) and variability (std)
            gesture_mean = np.mean(X_scaled, axis=0)
            gesture_std = np.std(X_scaled, axis=0)

            # Prevent division by zero
            gesture_std = np.maximum(gesture_std, 0.1)

            # Create model dictionary
            model = {
                'type': 'distance_based',
                'scaler': scaler,
                'mean': gesture_mean,
                'std': gesture_std,
                'threshold': 2.0,  # Standard deviations for acceptance
                'sample_count': len(valid_samples)
            }

            # Estimate accuracy using leave-one-out validation
            correct_predictions = 0
            for i in range(len(X_scaled)):
                # Create temporary model without this sample
                temp_X = np.delete(X_scaled, i, axis=0)
                temp_mean = np.mean(temp_X, axis=0)
                temp_std = np.std(temp_X, axis=0)
                temp_std = np.maximum(temp_std, 0.1)

                # Test if the held-out sample would be recognized
                test_sample = X_scaled[i]
                distance = np.sqrt(np.mean(((test_sample - temp_mean) / temp_std) ** 2))

                if distance <= model['threshold']:
                    correct_predictions += 1

            accuracy = correct_predictions / len(X_scaled)

            # Save trained model
            # GFLOW-18: Save to profile-specific directory
            profile_models_dir = self._get_profile_models_directory()
            model_path = os.path.join(profile_models_dir,
                                    self.gestures_metadata[gesture_name]['model_file'])
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)

            # Update metadata
            self.gestures_metadata[gesture_name]['is_trained'] = True
            self.gestures_metadata[gesture_name]['training_accuracy'] = accuracy
            self.gestures_metadata[gesture_name]['last_trained'] = datetime.now().isoformat()
            self._save_metadata()

            # Load model into memory
            self.trained_models[gesture_name] = model

            return True, accuracy

        except Exception as e:
            print(f"Error training gesture '{gesture_name}': {e}")
            import traceback
            traceback.print_exc()
            return False, 0.0

    def recognize_gesture(self, hand_landmarks) -> Tuple[Optional[str], float]:
        """
        Recognize a gesture from hand landmarks using distance-based classification

        Args:
            hand_landmarks: MediaPipe hand landmarks

        Returns:
            Tuple of (gesture_name, confidence) or (None, 0.0)
        """
        features = self.feature_extractor.extract_features(hand_landmarks)
        if features is None:
            return None, 0.0

        best_gesture = None
        best_confidence = 0.0

        for gesture_name, model in self.trained_models.items():
            try:
                if model['type'] != 'distance_based':
                    continue

                # Scale the features using the trained scaler
                features_scaled = model['scaler'].transform(features.reshape(1, -1))[0]

                # Calculate normalized distance to gesture template
                distance = np.sqrt(np.mean(((features_scaled - model['mean']) / model['std']) ** 2))

                # Convert distance to confidence (closer = higher confidence)
                if distance <= model['threshold']:
                    # Confidence decreases as distance increases
                    confidence = max(0.0, 1.0 - (distance / model['threshold']))

                    if confidence > best_confidence and confidence >= self.config['min_confidence_threshold']:
                        best_confidence = confidence
                        best_gesture = gesture_name

            except Exception as e:
                print(f"Error recognizing gesture '{gesture_name}': {e}")
                continue

        return best_gesture, best_confidence

    def delete_gesture(self, gesture_name: str) -> bool:
        """
        Delete a custom gesture and all associated data

        Args:
            gesture_name: Name of gesture to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        if gesture_name not in self.gestures_metadata:
            return False

        try:
            gesture_data = self.gestures_metadata[gesture_name]

            # Delete feature file
            # GFLOW-18: Delete from profile-specific directory
            profile_data_dir = self._get_profile_data_directory()
            feature_path = os.path.join(profile_data_dir, gesture_data['feature_file'])
            if os.path.exists(feature_path):
                os.remove(feature_path)

            # Delete model file
            profile_models_dir = self._get_profile_models_directory()
            model_path = os.path.join(profile_models_dir, gesture_data['model_file'])
            if os.path.exists(model_path):
                os.remove(model_path)

            # Remove from memory
            if gesture_name in self.trained_models:
                del self.trained_models[gesture_name]

            # Remove from metadata
            del self.gestures_metadata[gesture_name]
            self._save_metadata()

            return True

        except Exception as e:
            print(f"Error deleting gesture '{gesture_name}': {e}")
            return False

    def get_gesture_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all custom gestures with their metadata

        Returns:
            List of gesture information dictionaries
        """
        return list(self.gestures_metadata.values())

    def check_gesture_similarity(self, gesture_name: str) -> List[Tuple[str, float]]:
        """
        GFLOW-10: Check similarity with existing gestures

        Args:
            gesture_name: Name of gesture to check

        Returns:
            List of (existing_gesture_name, similarity_score) tuples
        """
        if gesture_name not in self.gestures_metadata:
            return []

        target_samples = self._load_gesture_samples(gesture_name)
        if not target_samples:
            return []

        # Calculate average feature vector for target gesture
        target_features = np.mean(target_samples, axis=0)

        similarities = []

        for other_name, other_data in self.gestures_metadata.items():
            if other_name == gesture_name or not other_data['is_trained']:
                continue

            other_samples = self._load_gesture_samples(other_name)
            if not other_samples:
                continue

            # Calculate average feature vector for other gesture
            other_features = np.mean(other_samples, axis=0)

            # Calculate similarity
            similarity = self.feature_extractor.calculate_feature_similarity(
                target_features, other_features
            )

            if similarity >= self.config['similarity_threshold']:
                similarities.append((other_name, similarity))

        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities

    def load_all_gestures(self):
        """Load all existing gestures from storage"""
        # GFLOW-18: Load from profile-specific directory
        profile_data_dir = self._get_profile_data_directory()
        metadata_path = os.path.join(profile_data_dir, 'gestures_metadata.json')

        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r') as f:
                    self.gestures_metadata = json.load(f)

                # Load trained models
                for gesture_name, gesture_data in self.gestures_metadata.items():
                    if gesture_data['is_trained']:
                        self._load_trained_model(gesture_name)

            except Exception as e:
                print(f"Error loading gestures metadata: {e}")
                self.gestures_metadata = {}
        else:
            # Try to migrate from legacy location
            self._migrate_legacy_gestures()

    def _migrate_legacy_gestures(self):
        """Migrate gestures from legacy global location to profile-specific location"""
        legacy_metadata_path = os.path.join(self.config['data_directory'], 'gestures_metadata.json')

        if os.path.exists(legacy_metadata_path) and self.current_profile == 'default':
            try:
                print("Migrating legacy gestures to default profile...")

                # Load legacy metadata
                with open(legacy_metadata_path, 'r') as f:
                    legacy_metadata = json.load(f)

                # Copy to profile location
                profile_data_dir = self._get_profile_data_directory()
                profile_metadata_path = os.path.join(profile_data_dir, 'gestures_metadata.json')

                with open(profile_metadata_path, 'w') as f:
                    json.dump(legacy_metadata, f, indent=2)

                # Copy gesture data files
                for gesture_name, gesture_data in legacy_metadata.items():
                    # Copy feature files
                    legacy_feature_path = os.path.join(self.config['data_directory'], gesture_data['feature_file'])
                    if os.path.exists(legacy_feature_path):
                        profile_feature_path = os.path.join(profile_data_dir, gesture_data['feature_file'])
                        shutil.copy2(legacy_feature_path, profile_feature_path)

                    # Copy model files
                    legacy_model_path = os.path.join(self.config['models_directory'], gesture_data['model_file'])
                    if os.path.exists(legacy_model_path):
                        profile_models_dir = self._get_profile_models_directory()
                        profile_model_path = os.path.join(profile_models_dir, gesture_data['model_file'])
                        shutil.copy2(legacy_model_path, profile_model_path)

                # Load the migrated data
                self.gestures_metadata = legacy_metadata

                # Load trained models
                for gesture_name, gesture_data in self.gestures_metadata.items():
                    if gesture_data['is_trained']:
                        self._load_trained_model(gesture_name)

                print(f"Successfully migrated {len(legacy_metadata)} gestures to default profile")

            except Exception as e:
                print(f"Error migrating legacy gestures: {e}")
                self.gestures_metadata = {}
        else:
            self.gestures_metadata = {}

    def _load_trained_model(self, gesture_name: str):
        """Load a trained model from disk"""
        if gesture_name not in self.gestures_metadata:
            return

        # GFLOW-18: Load from profile-specific directory
        profile_models_dir = self._get_profile_models_directory()
        model_path = os.path.join(profile_models_dir,
                                self.gestures_metadata[gesture_name]['model_file'])

        if os.path.exists(model_path):
            try:
                with open(model_path, 'rb') as f:
                    model = pickle.load(f)

                # Validate model format
                if isinstance(model, dict) and 'type' in model:
                    self.trained_models[gesture_name] = model
                else:
                    print(f"Invalid model format for '{gesture_name}', skipping")

            except Exception as e:
                print(f"Error loading model for '{gesture_name}': {e}")

    def _save_metadata(self):
        """Save gestures metadata to disk"""
        # GFLOW-18: Save to profile-specific directory
        profile_data_dir = self._get_profile_data_directory()
        metadata_path = os.path.join(profile_data_dir, 'gestures_metadata.json')

        try:
            with open(metadata_path, 'w') as f:
                json.dump(self.gestures_metadata, f, indent=2)
        except Exception as e:
            print(f"Error saving metadata: {e}")

    def _load_gesture_samples(self, gesture_name: str) -> List[np.ndarray]:
        """Load training samples for a gesture"""
        if gesture_name not in self.gestures_metadata:
            return []

        # GFLOW-18: Load from profile-specific directory
        profile_data_dir = self._get_profile_data_directory()
        feature_path = os.path.join(profile_data_dir,
                                  self.gestures_metadata[gesture_name]['feature_file'])

        if os.path.exists(feature_path):
            try:
                with open(feature_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"Error loading samples for '{gesture_name}': {e}")

        return []

    def _save_gesture_samples(self, gesture_name: str, samples: List[np.ndarray]) -> bool:
        """Save training samples for a gesture"""
        if gesture_name not in self.gestures_metadata:
            return False

        # GFLOW-18: Save to profile-specific directory
        profile_data_dir = self._get_profile_data_directory()
        feature_path = os.path.join(profile_data_dir,
                                  self.gestures_metadata[gesture_name]['feature_file'])

        try:
            with open(feature_path, 'wb') as f:
                pickle.dump(samples, f)
            return True
        except Exception as e:
            print(f"Error saving samples for '{gesture_name}': {e}")
            return False

    def _validate_gesture_name(self, name: str) -> bool:
        """Validate gesture name"""
        if not name or not name.strip():
            return False

        if len(name) > self.config['max_gesture_name_length']:
            return False

        # Check for invalid characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        if any(char in name for char in invalid_chars):
            return False

        return True

    def _generate_gesture_id(self, name: str) -> str:
        """Generate unique ID for gesture"""
        # Create ID from name (lowercase, replace spaces with underscores)
        base_id = name.lower().replace(' ', '_').replace('-', '_')

        # Remove any remaining invalid characters
        valid_chars = 'abcdefghijklmnopqrstuvwxyz0123456789_'
        base_id = ''.join(c for c in base_id if c in valid_chars)

        # Ensure uniqueness
        gesture_id = base_id
        counter = 1
        while any(data['id'] == gesture_id for data in self.gestures_metadata.values()):
            gesture_id = f"{base_id}_{counter}"
            counter += 1

        return gesture_id


# Factory function
def create_custom_gesture_manager() -> CustomGestureManager:
    """
    Factory function to create a CustomGestureManager instance

    Returns:
        Configured CustomGestureManager instance
    """
    return CustomGestureManager()
