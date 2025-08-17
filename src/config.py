import os

# Get the project root directory (parent of src)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Webcam Configuration
WEBCAM_CONFIG = {
    'width': 640,
    'height': 480,
    'fps': 30,
    'device_id': 0,  # Default webcam
    'flip_horizontal': True  # Mirror effect
}

# MediaPipe Hands Configuration
MEDIAPIPE_CONFIG = {
    'static_image_mode': False,
    'max_num_hands': 2,
    'min_detection_confidence': 0.7,
    'min_tracking_confidence': 0.5
}

# Gesture Recognition Configuration
GESTURE_CONFIG = {
    'recognition_threshold': 0.8,  # Confidence threshold for gesture recognition
    'gesture_hold_time': 0.5,     # Minimum time to hold gesture (seconds)
    'smoothing_frames': 3,         # Number of frames for gesture smoothing
    'debug_mode': False            # Enable debug output for gesture recognition
}

# Performance Configuration (GFLOW-4)
PERFORMANCE_CONFIG = {
    'fps_update_interval': 30,     # Update FPS every N frames
    'max_recognition_history': 100, # Keep last N recognition times
    'target_fps': 15,              # Minimum target FPS
    'max_latency_ms': 50           # Maximum acceptable recognition latency
}

# UI Configuration
UI_CONFIG = {
    'window_title': 'GestureFlow - Gesture Recognition with Custom Training',
    'window_width': 1000,
    'window_height': 700,
    'video_width': 640,
    'video_height': 480
}

# Custom Gesture Configuration (GFLOW-E02)
CUSTOM_GESTURE_CONFIG = {
    'data_directory': os.path.join(PROJECT_ROOT, 'data', 'custom_gestures'),
    'models_directory': os.path.join(PROJECT_ROOT, 'data', 'models'),
    'samples_per_gesture': 20,          # Number of samples to collect per gesture
    'sample_delay_seconds': 1.5,        # Time delay between samples (enhanced UX)
    'recording_countdown': 3,            # Countdown before recording starts
    'min_confidence_threshold': 0.6,    # Minimum confidence for recognition
    'feature_vector_size': 42,           # 21 landmarks × 2 coordinates (x,y)
    'similarity_threshold': 0.85,        # Threshold for gesture ambiguity detection
    'svm_kernel': 'rbf',                # SVM kernel type
    'svm_c': 1.0,                       # SVM regularization parameter
    'cross_validation_folds': 5,        # K-fold cross-validation
    'max_gesture_name_length': 50,      # Maximum length for gesture names
    'backup_enabled': True,             # Enable automatic backup of gesture data
    'predefined_confidence_boost': 0.1, # Boost predefined gesture confidence to prefer them over custom
    'enable_gesture_priority': True,    # Enable priority system (predefined > custom when close)
}

# Gesture Definitions (GFLOW-3)
PREDEFINED_GESTURES = {
    'open_palm': {
        'name': 'Open Palm',
        'description': 'All fingers extended',
        'enabled': True
    },
    'fist': {
        'name': 'Fist',
        'description': 'All fingers closed',
        'enabled': True
    },
    'peace_sign': {
        'name': 'Peace Sign',
        'description': 'Index and middle fingers up',
        'enabled': True
    },
    'thumbs_up': {
        'name': 'Thumbs Up',
        'description': 'Thumb extended upward',
        'enabled': True
    },
    'pointing': {
        'name': 'Pointing',
        'description': 'Index finger extended',
        'enabled': True
    }
}

# Action Execution Configuration (GFLOW-E03)
ACTION_EXECUTION_CONFIG = {
    # Library preferences
    'input_library': 'pynput',  # 'pynput' or 'pyautogui'
    'enable_failsafe': True,    # Enable safety mechanisms
    'failsafe_corner': True,    # Move mouse to corner to abort

    # Safety and security
    'require_confirmation': {
        'destructive_actions': True,    # Confirm potentially harmful actions
        'application_launch': True,     # Confirm app launches
        'system_commands': True,        # Confirm system-level commands
        'file_operations': False,       # Confirm file operations (future)
    },

    # Timing controls
    'default_action_delay': 0.1,       # Default delay between actions (seconds)
    'mouse_movement_duration': 0.3,    # Duration for mouse movements
    'key_press_interval': 0.05,        # Interval between key presses
    'action_timeout': 5.0,             # Maximum time for action execution

    # Error handling
    'max_retry_attempts': 3,           # Maximum retries for failed actions
    'error_recovery_delay': 1.0,       # Delay before retry
    'log_all_actions': True,           # Log all executed actions
    'enable_undo': True,               # Enable undo for supported actions

    # Performance
    'async_execution': True,           # Execute actions asynchronously
    'queue_max_size': 100,            # Maximum queued actions
    'execution_thread_pool': 2,       # Number of execution threads

    # Context awareness
    'context_aware_execution': True,   # Enable context-aware actions
    'application_detection': True,     # Detect active applications
    'window_focus_check': True,        # Check window focus before actions
}

# Action Types Configuration
ACTION_TYPES_CONFIG = {
    'mouse': {
        'enabled': True,
        'actions': ['click', 'move_to', 'drag', 'scroll'],
        'validation_required': False,
        'confirmation_required': False,
    },
    'keyboard': {
        'enabled': True,
        'actions': ['key_press', 'key_combination', 'type_text'],
        'validation_required': True,
        'confirmation_required': False,
        'dangerous_keys': ['delete', 'f4', 'alt+f4', 'ctrl+alt+del'],
    },
    'application': {
        'enabled': True,
        'actions': ['launch', 'close', 'focus', 'minimize', 'maximize'],
        'validation_required': True,
        'confirmation_required': True,
        'allowed_paths': [],  # Empty means all paths allowed
        'blocked_paths': [],  # Explicitly blocked paths
    },
    'macro': {
        'enabled': True,
        'actions': ['execute', 'sequence', 'loop'],
        'max_sequence_length': 20,     # Maximum actions in a sequence
        'max_loop_iterations': 10,     # Maximum loop iterations
        'allow_nested_macros': False,  # Prevent infinite recursion
        'validation_required': True,
        'confirmation_required': True,
    },
    'system': {
        'enabled': False,  # Disabled by default for security
        'actions': ['shutdown', 'restart', 'sleep', 'lock'],
        'validation_required': True,
        'confirmation_required': True,
    }
}

# Action Mapping Storage Configuration
ACTION_MAPPING_CONFIG = {
    'data_directory': os.path.join(PROJECT_ROOT, 'data', 'action_mappings'),
    'profiles_directory': os.path.join(PROJECT_ROOT, 'data', 'profiles'),
    'logs_directory': os.path.join(PROJECT_ROOT, 'data', 'logs'),
    'backup_directory': os.path.join(PROJECT_ROOT, 'data', 'backups'),

    # File formats
    'mapping_file_format': 'json',
    'log_file_format': 'json',
    'backup_enabled': True,
    'backup_interval_hours': 24,
    'max_backup_files': 10,

    # Profile management
    'default_profile_name': 'default',
    'auto_save_enabled': True,
    'auto_save_interval': 300,  # seconds
    'profile_export_format': 'json',

    # Action history and logging
    'max_action_history': 1000,
    'log_level': 'INFO',  # DEBUG, INFO, WARNING, ERROR
    'log_rotation_size_mb': 10,
    'max_log_files': 5,
}

# Visual feedback configuration (GFLOW-19)
VISUAL_FEEDBACK_CONFIG = {
    # Hand landmarks overlay
    'show_hand_landmarks': True,
    'landmark_color': (0, 255, 0),  # Green in BGR
    'landmark_thickness': 2,
    'connection_color': (255, 0, 0),  # Blue in BGR
    'connection_thickness': 1,

    # Gesture recognition notifications
    'show_gesture_notifications': True,
    'notification_duration': 2.0,  # seconds
    'notification_fade_duration': 0.3,  # seconds
    'notification_position': 'top_right',  # top_left, top_right, bottom_left, bottom_right
    'notification_offset_x': 10,  # pixels from edge
    'notification_offset_y': 10,  # pixels from edge

    # Notification styling
    'notification_background_color': 'rgba(0, 0, 0, 180)',  # Semi-transparent black
    'notification_text_color': '#FFFFFF',  # White text
    'notification_border_color': '#3498db',  # Blue border
    'notification_border_width': 2,
    'notification_border_radius': 8,
    'notification_padding': 10,
    'notification_font_size': 12,
    'notification_font_weight': 'bold',

    # Animation settings
    'enable_notification_animations': True,
    'fade_in_duration': 200,  # milliseconds
    'fade_out_duration': 300,  # milliseconds
    'slide_distance': 20,  # pixels for slide animation

    # Performance settings
    'max_notifications_queue': 5,
    'notification_update_interval': 50,  # milliseconds
}

# Dynamic Mouse Control configuration (GFLOW-E04)
MOUSE_CONTROL_CONFIG = {
    'enabled': True,                 # Master toggle for mouse control
    'gesture_type': 'predefined',    # 'predefined' or 'custom'
    'gesture_name': 'pointing',      # Gesture id/name to hold for control
    'landmark': 'index_tip',         # 'index_tip' or 'wrist'
    'sensitivity': 1.5,              # Movement gain multiplier
    'deadzone_pixels': 3,            # Ignore small jitters under this pixel radius
    'smoothing': 0.5,                # 0=no smoothing, 1=heavy smoothing (EMA on delta)
    'invert_x': False,
    'invert_y': False,
    'activation_frames': 3,          # Frames required to activate control
    'deactivation_frames': 2         # Frames required to deactivate control
}

# ... existing code ...
ASSETS_CONFIG = {
    'assets_directory': os.path.join(PROJECT_ROOT, 'assets'),
    'app_icon_path': os.path.join(PROJECT_ROOT, 'assets', 'app_icon.svg'),
}
