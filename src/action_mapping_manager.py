import os
import json
import uuid
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from action_types import (
    Action, GestureActionMapping, ActionType, ActionValidator,
    MouseActionParameters, KeyboardActionParameters, ApplicationActionParameters,
    MacroActionParameters
)
from config import ACTION_MAPPING_CONFIG, PROJECT_ROOT, ACTION_EXECUTION_CONFIG

class ActionMappingManager:
    """
    Manages gesture-to-action mappings with profile support and context awareness
    
    Features:
    - Profile-based mapping storage
    - Context-aware action filtering
    - Backup and restore functionality
    - Import/export capabilities
    - Action usage tracking
    """
    
    def __init__(self):
        self.config = ACTION_MAPPING_CONFIG
        self.execution_config = ACTION_EXECUTION_CONFIG
        self.validator = ActionValidator()
        
        # Current state
        self.current_profile = self.config.get('default_profile_name', 'default')
        self.mappings: Dict[str, GestureActionMapping] = {}
        self.profiles: Dict[str, Dict] = {}
        
        # Create directories
        self._create_directories()
        
        # Load profiles and default mapping
        self._load_profiles()
        self.load_profile(self.current_profile)
    
    def _create_directories(self):
        """Create necessary directories for data storage"""
        directories = [
            self.config['data_directory'],
            self.config['profiles_directory'],
            self.config['logs_directory'],
            self.config['backup_directory']
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def _load_profiles(self):
        """Load available profiles"""
        profiles_dir = self.config['profiles_directory']
        profiles_file = os.path.join(profiles_dir, 'profiles.json')
        
        if os.path.exists(profiles_file):
            try:
                with open(profiles_file, 'r') as f:
                    self.profiles = json.load(f)
            except Exception as e:
                print(f"Error loading profiles: {e}")
                self.profiles = {}
        
        # Ensure default profile exists
        if self.current_profile not in self.profiles:
            self._create_profile(self.current_profile, "Default profile", set_as_current=False)
        else:
            # Profile exists, make sure it's marked as active
            self.profiles[self.current_profile]['is_active'] = True
    
    def _save_profiles(self):
        """Save profiles metadata"""
        profiles_dir = self.config['profiles_directory']
        profiles_file = os.path.join(profiles_dir, 'profiles.json')
        
        try:
            with open(profiles_file, 'w') as f:
                json.dump(self.profiles, f, indent=2)
        except Exception as e:
            print(f"Error saving profiles: {e}")
    
    def create_profile(self, name: str, description: str = "") -> bool:
        """
        Create a new profile
        
        Args:
            name: Profile name
            description: Profile description
            
        Returns:
            True if created successfully
        """
        return self._create_profile(name, description, set_as_current=True)
    
    def _create_profile(self, name: str, description: str = "", set_as_current: bool = True) -> bool:
        """Internal method to create a profile"""
        if not name or name in self.profiles:
            return False
        
        profile_data = {
            'name': name,
            'description': description,
            'created_date': datetime.now().isoformat(),
            'last_modified': datetime.now().isoformat(),
            'mapping_count': 0,
            'is_active': False
        }
        
        self.profiles[name] = profile_data
        self._save_profiles()
        
        # Create empty mappings file for the profile
        self._save_profile_mappings(name, {})
        
        if set_as_current:
            self.load_profile(name)
        
        return True
    
    def delete_profile(self, name: str) -> bool:
        """
        Delete a profile
        
        Args:
            name: Profile name to delete
            
        Returns:
            True if deleted successfully
        """
        if name not in self.profiles or name == self.current_profile:
            return False
        
        # Remove profile data
        del self.profiles[name]
        self._save_profiles()
        
        # Remove profile mappings file
        mappings_file = self._get_profile_mappings_file(name)
        if os.path.exists(mappings_file):
            os.remove(mappings_file)
        
        return True
    
    def load_profile(self, name: str) -> bool:
        """
        Load a profile and make it current

        Args:
            name: Profile name to load

        Returns:
            True if loaded successfully
        """
        if name not in self.profiles:
            return False

        # Save current profile if it exists and is different from the one we're loading
        if (self.current_profile and
            self.current_profile in self.profiles and
            self.current_profile != name):
            self.save_current_profile()
            self.profiles[self.current_profile]['is_active'] = False

        # Load new profile
        self.current_profile = name
        self.profiles[name]['is_active'] = True
        self.profiles[name]['last_modified'] = datetime.now().isoformat()

        # Load mappings
        self.mappings = self._load_profile_mappings(name)

        self._save_profiles()
        return True
    
    def save_current_profile(self) -> bool:
        """Save the current profile mappings"""
        if not self.current_profile:
            return False
        
        success = self._save_profile_mappings(self.current_profile, self.mappings)
        
        if success and self.current_profile in self.profiles:
            self.profiles[self.current_profile]['mapping_count'] = len(self.mappings)
            self.profiles[self.current_profile]['last_modified'] = datetime.now().isoformat()
            self._save_profiles()
        
        return success
    
    def _get_profile_mappings_file(self, profile_name: str) -> str:
        """Get the mappings file path for a profile"""
        # GFLOW-18: Use unified profile directory structure
        profile_dir = os.path.join(PROJECT_ROOT, 'data', 'profiles', profile_name, 'action_mappings')
        os.makedirs(profile_dir, exist_ok=True)
        return os.path.join(profile_dir, 'mappings.json')
    
    def _load_profile_mappings(self, profile_name: str) -> Dict[str, GestureActionMapping]:
        """Load mappings for a specific profile"""
        mappings_file = self._get_profile_mappings_file(profile_name)
        mappings = {}

        if os.path.exists(mappings_file):
            try:
                with open(mappings_file, 'r') as f:
                    data = json.load(f)

                for mapping_id, mapping_data in data.items():
                    try:
                        mapping = GestureActionMapping.from_dict(mapping_data)
                        mappings[mapping_id] = mapping
                    except Exception as e:
                        print(f"Error loading mapping {mapping_id}: {e}")

            except Exception as e:
                print(f"Error loading mappings for profile {profile_name}: {e}")
        else:
            # GFLOW-18: Try to migrate from legacy location
            mappings = self._migrate_legacy_mappings(profile_name)

        return mappings

    def _migrate_legacy_mappings(self, profile_name: str) -> Dict[str, GestureActionMapping]:
        """Migrate mappings from legacy location to unified profile structure"""
        legacy_file = os.path.join(self.config['data_directory'], f"{profile_name}_mappings.json")
        mappings = {}

        if os.path.exists(legacy_file):
            try:
                print(f"Migrating legacy action mappings for profile: {profile_name}")

                # Load from legacy location
                with open(legacy_file, 'r') as f:
                    data = json.load(f)

                for mapping_id, mapping_data in data.items():
                    try:
                        mapping = GestureActionMapping.from_dict(mapping_data)
                        mappings[mapping_id] = mapping
                    except Exception as e:
                        print(f"Error migrating mapping {mapping_id}: {e}")

                # Save to new location
                if mappings:
                    self._save_profile_mappings(profile_name, mappings)
                    print(f"Successfully migrated {len(mappings)} action mappings for profile: {profile_name}")

                # Optionally remove legacy file (commented out for safety)
                # os.remove(legacy_file)

            except Exception as e:
                print(f"Error migrating legacy mappings for profile {profile_name}: {e}")

        return mappings
    
    def _save_profile_mappings(self, profile_name: str, mappings: Dict[str, GestureActionMapping]) -> bool:
        """Save mappings for a specific profile"""
        mappings_file = self._get_profile_mappings_file(profile_name)

        try:
            # Convert mappings to serializable format
            data = {}
            for mapping_id, mapping in mappings.items():
                data[mapping_id] = mapping.to_dict()

            with open(mappings_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True

        except Exception as e:
            print(f"Error saving mappings for profile {profile_name}: {e}")
            return False
    
    def add_mapping(self, gesture_name: str, gesture_type: str, action: Action) -> Optional[str]:
        """
        Add a new gesture-to-action mapping
        
        Args:
            gesture_name: Name of the gesture
            gesture_type: Type of gesture ('predefined' or 'custom')
            action: Action to map to the gesture
            
        Returns:
            Mapping ID if successful, None otherwise
        """
        # Validate action
        is_valid, error_message = self.validator.validate_action(action)
        if not is_valid:
            print(f"Action validation failed: {error_message}")
            return None
        
        # Check if mapping already exists for this gesture
        existing_mapping = self.get_mapping_for_gesture(gesture_name, gesture_type)
        if existing_mapping:
            print(f"Mapping already exists for gesture: {gesture_name}")
            return None
        
        # Create mapping
        mapping_id = str(uuid.uuid4())
        mapping = GestureActionMapping(
            id=mapping_id,
            gesture_name=gesture_name,
            gesture_type=gesture_type,
            action=action,
            enabled=True
        )
        
        self.mappings[mapping_id] = mapping
        
        # Auto-save if enabled
        if self.config.get('auto_save_enabled', True):
            self.save_current_profile()
        
        return mapping_id
    
    def remove_mapping(self, mapping_id: str) -> bool:
        """
        Remove a gesture-to-action mapping
        
        Args:
            mapping_id: ID of the mapping to remove
            
        Returns:
            True if removed successfully
        """
        if mapping_id not in self.mappings:
            return False
        
        del self.mappings[mapping_id]
        
        # Auto-save if enabled
        if self.config.get('auto_save_enabled', True):
            self.save_current_profile()
        
        return True
    
    def update_mapping(self, mapping_id: str, **kwargs) -> bool:
        """
        Update an existing mapping
        
        Args:
            mapping_id: ID of the mapping to update
            **kwargs: Fields to update
            
        Returns:
            True if updated successfully
        """
        if mapping_id not in self.mappings:
            return False
        
        mapping = self.mappings[mapping_id]
        
        # Update allowed fields
        for field, value in kwargs.items():
            if hasattr(mapping, field):
                setattr(mapping, field, value)
        
        # Auto-save if enabled
        if self.config.get('auto_save_enabled', True):
            self.save_current_profile()
        
        return True
    
    def get_mapping_for_gesture(self, gesture_name: str, gesture_type: str) -> Optional[GestureActionMapping]:
        """
        Get the mapping for a specific gesture
        
        Args:
            gesture_name: Name of the gesture
            gesture_type: Type of gesture
            
        Returns:
            GestureActionMapping if found, None otherwise
        """
        for mapping in self.mappings.values():
            if (mapping.gesture_name == gesture_name and 
                mapping.gesture_type == gesture_type and 
                mapping.enabled):
                return mapping
        
        return None
    
    def get_all_mappings(self, enabled_only: bool = True) -> List[GestureActionMapping]:
        """
        Get all mappings in the current profile
        
        Args:
            enabled_only: Only return enabled mappings
            
        Returns:
            List of mappings
        """
        mappings = list(self.mappings.values())
        
        if enabled_only:
            mappings = [m for m in mappings if m.enabled]
        
        # Sort by priority (higher first) then by gesture name
        mappings.sort(key=lambda m: (-m.priority, m.gesture_name))
        
        return mappings
    
    def get_available_profiles(self) -> List[Dict[str, Any]]:
        """Get list of available profiles"""
        return list(self.profiles.values())
    
    def get_current_profile_name(self) -> str:
        """Get the name of the current profile"""
        return self.current_profile
    
    def record_action_usage(self, mapping_id: str):
        """Record that an action was used"""
        if mapping_id in self.mappings:
            mapping = self.mappings[mapping_id]
            mapping.use_count += 1
            mapping.last_used = datetime.now().isoformat()
            
            # Auto-save if enabled
            if self.config.get('auto_save_enabled', True):
                self.save_current_profile()

    def export_profile(self, profile_name: str, export_path: str) -> bool:
        """
        Export a profile to a file

        Args:
            profile_name: Name of profile to export
            export_path: Path to export file

        Returns:
            True if exported successfully
        """
        if profile_name not in self.profiles:
            return False

        try:
            # Load profile mappings
            mappings = self._load_profile_mappings(profile_name)

            # Create export data
            export_data = {
                'profile': self.profiles[profile_name],
                'mappings': {mid: mapping.to_dict() for mid, mapping in mappings.items()},
                'export_date': datetime.now().isoformat(),
                'version': '1.0'
            }

            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)

            return True

        except Exception as e:
            print(f"Error exporting profile {profile_name}: {e}")
            return False

    def import_profile(self, import_path: str, new_profile_name: str = None) -> bool:
        """
        Import a profile from a file

        Args:
            import_path: Path to import file
            new_profile_name: Optional new name for the profile

        Returns:
            True if imported successfully
        """
        try:
            with open(import_path, 'r') as f:
                import_data = json.load(f)

            # Extract profile data
            profile_data = import_data.get('profile', {})
            mappings_data = import_data.get('mappings', {})

            # Use new name if provided, otherwise use original name
            profile_name = new_profile_name or profile_data.get('name', 'imported_profile')

            # Ensure unique profile name
            original_name = profile_name
            counter = 1
            while profile_name in self.profiles:
                profile_name = f"{original_name}_{counter}"
                counter += 1

            # Create profile
            if not self._create_profile(profile_name, profile_data.get('description', ''), set_as_current=False):
                return False

            # Import mappings
            mappings = {}
            for mapping_id, mapping_data in mappings_data.items():
                try:
                    mapping = GestureActionMapping.from_dict(mapping_data)
                    mappings[mapping_id] = mapping
                except Exception as e:
                    print(f"Error importing mapping {mapping_id}: {e}")

            # Save imported mappings
            self._save_profile_mappings(profile_name, mappings)

            # Update profile metadata
            self.profiles[profile_name]['mapping_count'] = len(mappings)
            self._save_profiles()

            return True

        except Exception as e:
            print(f"Error importing profile: {e}")
            return False

    def create_backup(self) -> bool:
        """Create a backup of all profiles and mappings"""
        try:
            backup_dir = self.config['backup_directory']
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(backup_dir, f"gestureflow_backup_{timestamp}.json")

            # Create backup data
            backup_data = {
                'profiles': self.profiles,
                'current_profile': self.current_profile,
                'backup_date': datetime.now().isoformat(),
                'version': '1.0',
                'mappings': {}
            }

            # Include all profile mappings
            for profile_name in self.profiles.keys():
                mappings = self._load_profile_mappings(profile_name)
                backup_data['mappings'][profile_name] = {
                    mid: mapping.to_dict() for mid, mapping in mappings.items()
                }

            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2)

            # Clean up old backups
            self._cleanup_old_backups()

            return True

        except Exception as e:
            print(f"Error creating backup: {e}")
            return False

    def restore_backup(self, backup_path: str) -> bool:
        """Restore from a backup file"""
        try:
            with open(backup_path, 'r') as f:
                backup_data = json.load(f)

            # Restore profiles
            self.profiles = backup_data.get('profiles', {})
            self._save_profiles()

            # Restore mappings for each profile
            mappings_data = backup_data.get('mappings', {})
            for profile_name, profile_mappings in mappings_data.items():
                mappings = {}
                for mapping_id, mapping_data in profile_mappings.items():
                    try:
                        mapping = GestureActionMapping.from_dict(mapping_data)
                        mappings[mapping_id] = mapping
                    except Exception as e:
                        print(f"Error restoring mapping {mapping_id}: {e}")

                self._save_profile_mappings(profile_name, mappings)

            # Restore current profile
            current_profile = backup_data.get('current_profile', self.config.get('default_profile_name', 'default'))
            if current_profile in self.profiles:
                self.load_profile(current_profile)

            return True

        except Exception as e:
            print(f"Error restoring backup: {e}")
            return False

    def _cleanup_old_backups(self):
        """Clean up old backup files"""
        try:
            backup_dir = self.config['backup_directory']
            max_backups = self.config.get('max_backup_files', 10)

            # Get all backup files
            backup_files = []
            for file in os.listdir(backup_dir):
                if file.startswith('gestureflow_backup_') and file.endswith('.json'):
                    file_path = os.path.join(backup_dir, file)
                    backup_files.append((file_path, os.path.getctime(file_path)))

            # Sort by creation time (newest first)
            backup_files.sort(key=lambda x: x[1], reverse=True)

            # Remove old backups
            for file_path, _ in backup_files[max_backups:]:
                os.remove(file_path)

        except Exception as e:
            print(f"Error cleaning up old backups: {e}")

    def get_context_filtered_mappings(self, context: Dict[str, Any] = None) -> List[GestureActionMapping]:
        """
        Get mappings filtered by context

        Args:
            context: Context information (e.g., active application, window title)

        Returns:
            List of context-appropriate mappings
        """
        if not self.execution_config.get('context_aware_execution', True):
            return self.get_all_mappings()

        all_mappings = self.get_all_mappings()

        if not context:
            return all_mappings

        # Filter mappings based on context
        filtered_mappings = []
        for mapping in all_mappings:
            if self._mapping_matches_context(mapping, context):
                filtered_mappings.append(mapping)

        return filtered_mappings

    def _mapping_matches_context(self, mapping: GestureActionMapping, context: Dict[str, Any]) -> bool:
        """Check if a mapping matches the given context"""
        if not mapping.context_filters:
            return True  # No filters means it applies to all contexts

        # Check each context filter
        for filter_rule in mapping.context_filters:
            if self._evaluate_context_filter(filter_rule, context):
                return True

        return False

    def _evaluate_context_filter(self, filter_rule: str, context: Dict[str, Any]) -> bool:
        """Evaluate a context filter rule"""
        # Simple implementation - can be extended for more complex rules
        # Format: "key:value" or "key:*" for any value

        if ':' not in filter_rule:
            return False

        key, value = filter_rule.split(':', 1)
        context_value = context.get(key, '')

        if value == '*':
            return bool(context_value)

        return str(context_value).lower() == value.lower()

    def get_statistics(self) -> Dict[str, Any]:
        """Get usage statistics for the current profile"""
        mappings = list(self.mappings.values())

        total_mappings = len(mappings)
        enabled_mappings = len([m for m in mappings if m.enabled])
        total_uses = sum(m.use_count for m in mappings)

        # Most used mappings
        most_used = sorted(mappings, key=lambda m: m.use_count, reverse=True)[:5]

        # Action type distribution
        action_types = {}
        for mapping in mappings:
            action_type = mapping.action.type.value
            action_types[action_type] = action_types.get(action_type, 0) + 1

        return {
            'profile_name': self.current_profile,
            'total_mappings': total_mappings,
            'enabled_mappings': enabled_mappings,
            'total_uses': total_uses,
            'most_used_mappings': [
                {
                    'gesture_name': m.gesture_name,
                    'action_type': m.action.type.value,
                    'use_count': m.use_count
                } for m in most_used
            ],
            'action_type_distribution': action_types
        }
