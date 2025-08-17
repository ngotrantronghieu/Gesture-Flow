import os
import json
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from config import PROJECT_ROOT, ACTION_MAPPING_CONFIG


@dataclass
class ProfileInfo:
    """Profile information data class"""
    name: str
    description: str
    created_date: str
    last_modified: str
    custom_gesture_count: int
    action_mapping_count: int
    is_default: bool
    is_active: bool


class ProfileManager:
    """
    GFLOW-18: Unified Profile Management System
    
    Coordinates profile management across custom gestures and action mappings,
    providing a unified interface for creating, loading, and managing user profiles.
    """
    
    def __init__(self):
        self.config = {
            'profiles_directory': os.path.join(PROJECT_ROOT, 'data', 'profiles'),
            'profiles_metadata_file': 'profiles_metadata.json',
            'default_profile_name': 'default',
            'backup_directory': os.path.join(PROJECT_ROOT, 'data', 'backups'),
        }
        
        # Current state
        self.current_profile = None
        self.profiles_metadata: Dict[str, ProfileInfo] = {}
        self.action_mapping_manager = None  # Will be injected
        self.custom_gesture_manager = None  # Will be injected
        
        # Create directories
        self._create_directories()
        
        # Load profiles metadata
        self._load_profiles_metadata()
        
        # Ensure default profile exists
        self._ensure_default_profile()
    
    def set_managers(self, action_mapping_manager, custom_gesture_manager):
        """Inject manager dependencies"""
        self.action_mapping_manager = action_mapping_manager
        self.custom_gesture_manager = custom_gesture_manager
    
    def _create_directories(self):
        """Create necessary directories"""
        os.makedirs(self.config['profiles_directory'], exist_ok=True)
        os.makedirs(self.config['backup_directory'], exist_ok=True)
    
    def _load_profiles_metadata(self):
        """Load profiles metadata from storage"""
        metadata_file = os.path.join(
            self.config['profiles_directory'], 
            self.config['profiles_metadata_file']
        )
        
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r') as f:
                    data = json.load(f)
                
                # Convert to ProfileInfo objects
                for name, profile_data in data.items():
                    self.profiles_metadata[name] = ProfileInfo(
                        name=profile_data['name'],
                        description=profile_data['description'],
                        created_date=profile_data['created_date'],
                        last_modified=profile_data['last_modified'],
                        custom_gesture_count=profile_data.get('custom_gesture_count', 0),
                        action_mapping_count=profile_data.get('action_mapping_count', 0),
                        is_default=profile_data.get('is_default', False),
                        is_active=profile_data.get('is_active', False)
                    )
                    
            except Exception as e:
                print(f"Error loading profiles metadata: {e}")
                self.profiles_metadata = {}
    
    def _save_profiles_metadata(self):
        """Save profiles metadata to storage"""
        metadata_file = os.path.join(
            self.config['profiles_directory'], 
            self.config['profiles_metadata_file']
        )
        
        try:
            # Convert ProfileInfo objects to dict
            data = {}
            for name, profile_info in self.profiles_metadata.items():
                data[name] = {
                    'name': profile_info.name,
                    'description': profile_info.description,
                    'created_date': profile_info.created_date,
                    'last_modified': profile_info.last_modified,
                    'custom_gesture_count': profile_info.custom_gesture_count,
                    'action_mapping_count': profile_info.action_mapping_count,
                    'is_default': profile_info.is_default,
                    'is_active': profile_info.is_active
                }
            
            with open(metadata_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"Error saving profiles metadata: {e}")
    
    def _ensure_default_profile(self):
        """Ensure default profile exists"""
        default_name = self.config['default_profile_name']
        
        if default_name not in self.profiles_metadata:
            self.create_profile(
                default_name, 
                "Default GestureFlow profile",
                set_as_default=True,
                set_as_current=True
            )
        else:
            # Set as current if no other profile is active
            if not any(p.is_active for p in self.profiles_metadata.values()):
                self.load_profile(default_name)
    
    def create_profile(self, name: str, description: str = "", 
                      set_as_default: bool = False, 
                      set_as_current: bool = True) -> bool:
        """
        Create a new profile
        
        Args:
            name: Profile name
            description: Profile description
            set_as_default: Set as default profile
            set_as_current: Set as current active profile
            
        Returns:
            True if created successfully
        """
        if not name or name in self.profiles_metadata:
            return False
        
        # Create profile directory structure
        profile_dir = os.path.join(self.config['profiles_directory'], name)
        custom_gestures_dir = os.path.join(profile_dir, 'custom_gestures')
        action_mappings_dir = os.path.join(profile_dir, 'action_mappings')
        
        try:
            os.makedirs(profile_dir, exist_ok=True)
            os.makedirs(custom_gestures_dir, exist_ok=True)
            os.makedirs(action_mappings_dir, exist_ok=True)
            
            # Create profile metadata
            profile_info = ProfileInfo(
                name=name,
                description=description,
                created_date=datetime.now().isoformat(),
                last_modified=datetime.now().isoformat(),
                custom_gesture_count=0,
                action_mapping_count=0,
                is_default=set_as_default,
                is_active=False
            )
            
            # Clear default flag from other profiles if setting this as default
            if set_as_default:
                for profile in self.profiles_metadata.values():
                    profile.is_default = False
            
            self.profiles_metadata[name] = profile_info
            
            # Initialize empty data files
            self._initialize_profile_data(name)

            # GFLOW-18: Create profile in ActionMappingManager if it doesn't exist
            if self.action_mapping_manager and name not in self.action_mapping_manager.profiles:
                self.action_mapping_manager._create_profile(name, description, set_as_current=False)

            # Save metadata
            self._save_profiles_metadata()

            # Set as current if requested
            if set_as_current:
                self.load_profile(name)
            
            return True
            
        except Exception as e:
            print(f"Error creating profile '{name}': {e}")
            return False
    
    def _initialize_profile_data(self, profile_name: str):
        """Initialize empty data files for a new profile"""
        profile_dir = os.path.join(self.config['profiles_directory'], profile_name)
        
        # Initialize custom gestures metadata
        custom_gestures_file = os.path.join(profile_dir, 'custom_gestures', 'gestures_metadata.json')
        with open(custom_gestures_file, 'w') as f:
            json.dump({}, f)
        
        # Initialize action mappings
        action_mappings_file = os.path.join(profile_dir, 'action_mappings', 'mappings.json')
        with open(action_mappings_file, 'w') as f:
            json.dump({}, f)
    
    def delete_profile(self, name: str) -> bool:
        """
        Delete a profile
        
        Args:
            name: Profile name to delete
            
        Returns:
            True if deleted successfully
        """
        if (name not in self.profiles_metadata or 
            name == self.config['default_profile_name'] or
            self.profiles_metadata[name].is_active):
            return False
        
        try:
            # Remove profile directory
            profile_dir = os.path.join(self.config['profiles_directory'], name)
            if os.path.exists(profile_dir):
                shutil.rmtree(profile_dir)
            
            # Remove from metadata
            del self.profiles_metadata[name]

            # GFLOW-18: Delete from ActionMappingManager as well
            if self.action_mapping_manager and name in self.action_mapping_manager.profiles:
                self.action_mapping_manager.delete_profile(name)

            # Save metadata
            self._save_profiles_metadata()
            
            return True
            
        except Exception as e:
            print(f"Error deleting profile '{name}': {e}")
            return False

    def load_profile(self, name: str) -> bool:
        """
        Load a profile and make it current

        Args:
            name: Profile name to load

        Returns:
            True if loaded successfully
        """
        if name not in self.profiles_metadata:
            return False

        try:
            # Save current profile if different
            if (self.current_profile and
                self.current_profile != name and
                self.current_profile in self.profiles_metadata):
                self._save_current_profile()
                self.profiles_metadata[self.current_profile].is_active = False

            # Set new current profile
            self.current_profile = name
            self.profiles_metadata[name].is_active = True
            self.profiles_metadata[name].last_modified = datetime.now().isoformat()

            # Load profile data in managers
            if self.action_mapping_manager:
                # GFLOW-18: Ensure ActionMappingManager loads the correct profile
                # First check if the profile exists in ActionMappingManager's system
                if name not in self.action_mapping_manager.profiles:
                    # Create the profile in ActionMappingManager if it doesn't exist
                    self.action_mapping_manager._create_profile(name, f"Profile {name}", set_as_current=False)

                # Now load the profile
                success = self.action_mapping_manager.load_profile(name)
                if not success:
                    print(f"Warning: Failed to load action mappings for profile {name}")

            if self.custom_gesture_manager:
                self.custom_gesture_manager.set_profile(name)

            # Update counts
            self._update_profile_counts(name)

            # Save metadata
            self._save_profiles_metadata()

            return True

        except Exception as e:
            print(f"Error loading profile '{name}': {e}")
            return False

    def _save_current_profile(self):
        """Save current profile data"""
        if not self.current_profile:
            return

        try:
            # Save action mappings
            if self.action_mapping_manager:
                self.action_mapping_manager.save_current_profile()

            # Save custom gestures (handled automatically by CustomGestureManager)

            # Update counts
            self._update_profile_counts(self.current_profile)

        except Exception as e:
            print(f"Error saving current profile: {e}")

    def _update_profile_counts(self, profile_name: str):
        """Update gesture and mapping counts for a profile"""
        if profile_name not in self.profiles_metadata:
            return

        try:
            # Count custom gestures
            custom_gesture_count = 0
            if self.custom_gesture_manager:
                custom_gesture_count = len(self.custom_gesture_manager.get_gesture_list())

            # Count action mappings
            action_mapping_count = 0
            if self.action_mapping_manager:
                action_mapping_count = len(self.action_mapping_manager.get_all_mappings(enabled_only=False))

            # Update metadata
            self.profiles_metadata[profile_name].custom_gesture_count = custom_gesture_count
            self.profiles_metadata[profile_name].action_mapping_count = action_mapping_count

        except Exception as e:
            print(f"Error updating profile counts: {e}")

    def get_all_profiles(self) -> List[ProfileInfo]:
        """Get list of all profiles"""
        return list(self.profiles_metadata.values())

    def get_current_profile(self) -> Optional[ProfileInfo]:
        """Get current active profile"""
        if self.current_profile and self.current_profile in self.profiles_metadata:
            return self.profiles_metadata[self.current_profile]
        return None

    def get_current_profile_name(self) -> Optional[str]:
        """Get current profile name"""
        return self.current_profile

    def set_default_profile(self, name: str) -> bool:
        """
        Set a profile as the default

        Args:
            name: Profile name to set as default

        Returns:
            True if set successfully
        """
        if name not in self.profiles_metadata:
            return False

        # Clear default flag from all profiles
        for profile in self.profiles_metadata.values():
            profile.is_default = False

        # Set new default
        self.profiles_metadata[name].is_default = True
        self.profiles_metadata[name].last_modified = datetime.now().isoformat()

        # Save metadata
        self._save_profiles_metadata()

        return True

    def get_default_profile_name(self) -> Optional[str]:
        """Get the default profile name"""
        for name, profile in self.profiles_metadata.items():
            if profile.is_default:
                return name
        return self.config['default_profile_name']

    def export_profile(self, profile_name: str, export_path: str) -> bool:
        """
        Export a profile to a file

        Args:
            profile_name: Name of profile to export
            export_path: Path to export file

        Returns:
            True if exported successfully
        """
        if profile_name not in self.profiles_metadata:
            return False

        try:
            profile_dir = os.path.join(self.config['profiles_directory'], profile_name)

            # Collect all profile data
            export_data = {
                'profile_metadata': {
                    'name': self.profiles_metadata[profile_name].name,
                    'description': self.profiles_metadata[profile_name].description,
                    'created_date': self.profiles_metadata[profile_name].created_date,
                    'custom_gesture_count': self.profiles_metadata[profile_name].custom_gesture_count,
                    'action_mapping_count': self.profiles_metadata[profile_name].action_mapping_count,
                },
                'custom_gestures': {},
                'action_mappings': {},
                'export_date': datetime.now().isoformat(),
                'version': '1.0'
            }

            # Load custom gestures data
            custom_gestures_file = os.path.join(profile_dir, 'custom_gestures', 'gestures_metadata.json')
            if os.path.exists(custom_gestures_file):
                with open(custom_gestures_file, 'r') as f:
                    export_data['custom_gestures'] = json.load(f)

            # Load action mappings data
            action_mappings_file = os.path.join(profile_dir, 'action_mappings', 'mappings.json')
            if os.path.exists(action_mappings_file):
                with open(action_mappings_file, 'r') as f:
                    export_data['action_mappings'] = json.load(f)

            # Save export file
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)

            return True

        except Exception as e:
            print(f"Error exporting profile '{profile_name}': {e}")
            return False

    def import_profile(self, import_path: str, new_name: Optional[str] = None) -> bool:
        """
        Import a profile from a file

        Args:
            import_path: Path to import file
            new_name: Optional new name for imported profile

        Returns:
            True if imported successfully
        """
        try:
            with open(import_path, 'r') as f:
                import_data = json.load(f)

            # Extract profile metadata
            profile_metadata = import_data.get('profile_metadata', {})
            profile_name = new_name or profile_metadata.get('name', 'imported_profile')

            # Ensure unique name
            original_name = profile_name
            counter = 1
            while profile_name in self.profiles_metadata:
                profile_name = f"{original_name}_{counter}"
                counter += 1

            # Create new profile
            if not self.create_profile(
                profile_name,
                profile_metadata.get('description', 'Imported profile'),
                set_as_current=False
            ):
                return False

            # Import custom gestures
            custom_gestures_data = import_data.get('custom_gestures', {})
            if custom_gestures_data:
                profile_dir = os.path.join(self.config['profiles_directory'], profile_name)
                custom_gestures_file = os.path.join(profile_dir, 'custom_gestures', 'gestures_metadata.json')
                with open(custom_gestures_file, 'w') as f:
                    json.dump(custom_gestures_data, f, indent=2)

            # Import action mappings
            action_mappings_data = import_data.get('action_mappings', {})
            if action_mappings_data:
                profile_dir = os.path.join(self.config['profiles_directory'], profile_name)
                action_mappings_file = os.path.join(profile_dir, 'action_mappings', 'mappings.json')
                with open(action_mappings_file, 'w') as f:
                    json.dump(action_mappings_data, f, indent=2)

            # Update counts
            self._update_profile_counts(profile_name)
            self._save_profiles_metadata()

            return True

        except Exception as e:
            print(f"Error importing profile: {e}")
            return False

    def create_backup(self) -> Optional[str]:
        """
        Create a backup of all profiles

        Returns:
            Path to backup file if successful, None otherwise
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(
                self.config['backup_directory'],
                f"profiles_backup_{timestamp}.json"
            )

            # Create backup data
            backup_data = {
                'profiles_metadata': {},
                'profiles_data': {},
                'backup_date': datetime.now().isoformat(),
                'version': '1.0'
            }

            # Include metadata
            for name, profile_info in self.profiles_metadata.items():
                backup_data['profiles_metadata'][name] = {
                    'name': profile_info.name,
                    'description': profile_info.description,
                    'created_date': profile_info.created_date,
                    'last_modified': profile_info.last_modified,
                    'custom_gesture_count': profile_info.custom_gesture_count,
                    'action_mapping_count': profile_info.action_mapping_count,
                    'is_default': profile_info.is_default,
                    'is_active': profile_info.is_active
                }

            # Include all profile data
            for profile_name in self.profiles_metadata.keys():
                profile_dir = os.path.join(self.config['profiles_directory'], profile_name)
                profile_data = {}

                # Include custom gestures
                custom_gestures_file = os.path.join(profile_dir, 'custom_gestures', 'gestures_metadata.json')
                if os.path.exists(custom_gestures_file):
                    with open(custom_gestures_file, 'r') as f:
                        profile_data['custom_gestures'] = json.load(f)

                # Include action mappings
                action_mappings_file = os.path.join(profile_dir, 'action_mappings', 'mappings.json')
                if os.path.exists(action_mappings_file):
                    with open(action_mappings_file, 'r') as f:
                        profile_data['action_mappings'] = json.load(f)

                backup_data['profiles_data'][profile_name] = profile_data

            # Save backup
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2)

            return backup_file

        except Exception as e:
            print(f"Error creating backup: {e}")
            return None
