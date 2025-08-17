import json
import os
from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget,
    QWidget, QLabel, QPushButton, QSpinBox, QDoubleSpinBox,
    QCheckBox, QComboBox, QLineEdit, QGroupBox, QSlider,
    QMessageBox, QFileDialog, QTextEdit, QFrame, QButtonGroup,
    QRadioButton, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QFont, QIntValidator, QDoubleValidator
from config import (
    WEBCAM_CONFIG, MEDIAPIPE_CONFIG, GESTURE_CONFIG, PERFORMANCE_CONFIG,
    UI_CONFIG, CUSTOM_GESTURE_CONFIG, PROJECT_ROOT, VISUAL_FEEDBACK_CONFIG, MOUSE_CONTROL_CONFIG,
    PREDEFINED_GESTURES
)
from custom_gesture_manager import CustomGestureManager

# Import ACTION_EXECUTION_CONFIG separately to handle potential import issues
try:
    from config import ACTION_EXECUTION_CONFIG
except ImportError:
    # Fallback configuration if not available
    ACTION_EXECUTION_CONFIG = {
        'input_library': 'pynput',
        'enable_failsafe': True,
        'failsafe_corner': True,
        'default_action_delay': 0.1,
        'mouse_movement_duration': 0.3,
        'action_timeout': 5.0,
        'log_all_actions': True,
        'async_execution': True,
    }


class SettingsDialog(QDialog):
    """
    GFLOW-17: Comprehensive Settings Dialog

    Provides user-friendly interface for modifying all application settings
    without requiring manual configuration file editing.
    """

    settings_changed = Signal(dict)  # Emitted when settings are applied

    def __init__(self, parent=None, profile_manager=None, custom_gesture_manager=None):
        super().__init__(parent)
        self.setWindowTitle("GestureFlow Settings")
        self.setModal(True)
        self.resize(800, 600)

        # Injected managers to reflect current profile context
        self.profile_manager = profile_manager
        self.custom_gesture_manager = custom_gesture_manager

        # Store original settings for cancel functionality
        self.original_settings = self.get_current_settings()
        self.current_settings = self.original_settings.copy()

        # QSettings for persistent storage
        self.qsettings = QSettings("GestureFlow", "Settings")

        self.setup_ui()
        self.setup_connections()
        self.load_settings()

    def setup_ui(self):
        """Setup the user interface with tabbed settings"""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Application Settings")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Create tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Create tabs
        self.create_webcam_tab()
        self.create_mediapipe_tab()
        self.create_gesture_tab()
        self.create_performance_tab()
        self.create_ui_tab()
        self.create_custom_gesture_tab()
        self.create_action_execution_tab()
        self.create_mouse_control_tab()  # GFLOW-E04

        self.create_visual_feedback_tab()  # GFLOW-19

        # Button layout
        button_layout = QHBoxLayout()

        # Reset to defaults button
        self.reset_button = QPushButton("Reset to Defaults")
        self.reset_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        button_layout.addWidget(self.reset_button)

        button_layout.addStretch()

        # Standard buttons
        self.cancel_button = QPushButton("Cancel")
        self.apply_button = QPushButton("Apply")
        self.ok_button = QPushButton("OK")

        # Style standard buttons
        for btn in [self.cancel_button, self.apply_button, self.ok_button]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
            """)

        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.ok_button)

        layout.addLayout(button_layout)

    def create_webcam_tab(self):
        """Create webcam settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Webcam Configuration Group
        webcam_group = QGroupBox("Webcam Configuration")
        webcam_layout = QFormLayout(webcam_group)

        # Resolution settings
        self.width_spin = QSpinBox()
        self.width_spin.setRange(320, 1920)
        self.width_spin.setValue(WEBCAM_CONFIG['width'])
        webcam_layout.addRow("Width:", self.width_spin)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(240, 1080)
        self.height_spin.setValue(WEBCAM_CONFIG['height'])
        webcam_layout.addRow("Height:", self.height_spin)

        # FPS setting
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(10, 60)
        self.fps_spin.setValue(WEBCAM_CONFIG['fps'])
        webcam_layout.addRow("FPS:", self.fps_spin)

        # Device ID
        self.device_spin = QSpinBox()
        self.device_spin.setRange(0, 10)
        self.device_spin.setValue(WEBCAM_CONFIG['device_id'])
        webcam_layout.addRow("Device ID:", self.device_spin)

        # Flip horizontal
        self.flip_check = QCheckBox()
        self.flip_check.setChecked(WEBCAM_CONFIG['flip_horizontal'])
        webcam_layout.addRow("Mirror Effect:", self.flip_check)

        layout.addWidget(webcam_group)
        layout.addStretch()

        self.tab_widget.addTab(tab, "Webcam")

    def create_mediapipe_tab(self):
        """Create MediaPipe settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # MediaPipe Configuration Group
        mp_group = QGroupBox("MediaPipe Hand Tracking")
        mp_layout = QFormLayout(mp_group)

        # Max number of hands
        self.max_hands_spin = QSpinBox()
        self.max_hands_spin.setRange(1, 4)
        self.max_hands_spin.setValue(MEDIAPIPE_CONFIG['max_num_hands'])
        mp_layout.addRow("Max Hands:", self.max_hands_spin)

        # Detection confidence
        self.detection_conf_spin = QDoubleSpinBox()
        self.detection_conf_spin.setRange(0.1, 1.0)
        self.detection_conf_spin.setSingleStep(0.1)
        self.detection_conf_spin.setDecimals(2)
        self.detection_conf_spin.setValue(MEDIAPIPE_CONFIG['min_detection_confidence'])
        self.detection_conf_spin.setToolTip("Minimum confidence for initial hand detection (0.1-1.0)")
        mp_layout.addRow("Detection Confidence:", self.detection_conf_spin)

        # Tracking confidence
        self.tracking_conf_spin = QDoubleSpinBox()
        self.tracking_conf_spin.setRange(0.1, 1.0)
        self.tracking_conf_spin.setSingleStep(0.1)
        self.tracking_conf_spin.setDecimals(2)
        self.tracking_conf_spin.setValue(MEDIAPIPE_CONFIG['min_tracking_confidence'])
        self.tracking_conf_spin.setToolTip("Minimum confidence for hand tracking between frames (0.1-1.0)")
        mp_layout.addRow("Tracking Confidence:", self.tracking_conf_spin)

        layout.addWidget(mp_group)
        layout.addStretch()

        self.tab_widget.addTab(tab, "MediaPipe")

    def create_gesture_tab(self):
        """Create gesture recognition settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Gesture Recognition Group
        gesture_group = QGroupBox("Gesture Recognition")
        gesture_layout = QFormLayout(gesture_group)

        # Recognition threshold
        self.recognition_threshold_spin = QDoubleSpinBox()
        self.recognition_threshold_spin.setRange(0.1, 1.0)
        self.recognition_threshold_spin.setSingleStep(0.1)
        self.recognition_threshold_spin.setDecimals(2)
        self.recognition_threshold_spin.setValue(GESTURE_CONFIG['recognition_threshold'])
        self.recognition_threshold_spin.setToolTip("Minimum confidence required to recognize a gesture (higher = more strict)")
        gesture_layout.addRow("Recognition Threshold:", self.recognition_threshold_spin)

        # Gesture hold time
        self.hold_time_spin = QDoubleSpinBox()
        self.hold_time_spin.setRange(0.1, 5.0)
        self.hold_time_spin.setSingleStep(0.1)
        self.hold_time_spin.setDecimals(1)
        self.hold_time_spin.setValue(GESTURE_CONFIG['gesture_hold_time'])
        gesture_layout.addRow("Hold Time (seconds):", self.hold_time_spin)

        # Smoothing frames
        self.smoothing_spin = QSpinBox()
        self.smoothing_spin.setRange(1, 10)
        self.smoothing_spin.setValue(GESTURE_CONFIG['smoothing_frames'])
        gesture_layout.addRow("Smoothing Frames:", self.smoothing_spin)

        # Debug mode
        self.debug_check = QCheckBox()
        self.debug_check.setChecked(GESTURE_CONFIG['debug_mode'])
        gesture_layout.addRow("Debug Mode:", self.debug_check)

        layout.addWidget(gesture_group)
        layout.addStretch()

        self.tab_widget.addTab(tab, "Gesture Recognition")

    def create_performance_tab(self):
        """Create performance settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Performance Group
        perf_group = QGroupBox("Performance Settings")
        perf_layout = QFormLayout(perf_group)

        # FPS update interval
        self.fps_interval_spin = QSpinBox()
        self.fps_interval_spin.setRange(10, 100)
        self.fps_interval_spin.setValue(PERFORMANCE_CONFIG['fps_update_interval'])
        perf_layout.addRow("FPS Update Interval:", self.fps_interval_spin)

        # Recognition history
        self.history_spin = QSpinBox()
        self.history_spin.setRange(50, 500)
        self.history_spin.setValue(PERFORMANCE_CONFIG['max_recognition_history'])
        perf_layout.addRow("Max Recognition History:", self.history_spin)

        # Target FPS
        self.target_fps_spin = QSpinBox()
        self.target_fps_spin.setRange(10, 60)
        self.target_fps_spin.setValue(PERFORMANCE_CONFIG['target_fps'])
        perf_layout.addRow("Target FPS:", self.target_fps_spin)

        # Max latency
        self.max_latency_spin = QSpinBox()
        self.max_latency_spin.setRange(10, 200)
        self.max_latency_spin.setValue(PERFORMANCE_CONFIG['max_latency_ms'])
        perf_layout.addRow("Max Latency (ms):", self.max_latency_spin)

        layout.addWidget(perf_group)
        layout.addStretch()

        self.tab_widget.addTab(tab, "Performance")

    def create_ui_tab(self):
        """Create UI settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # UI Configuration Group
        ui_group = QGroupBox("User Interface")
        ui_layout = QFormLayout(ui_group)

        # Window title
        self.window_title_edit = QLineEdit()
        self.window_title_edit.setText(UI_CONFIG['window_title'])
        ui_layout.addRow("Window Title:", self.window_title_edit)

        # Window dimensions
        self.window_width_spin = QSpinBox()
        self.window_width_spin.setRange(800, 2000)
        self.window_width_spin.setValue(UI_CONFIG['window_width'])
        ui_layout.addRow("Window Width:", self.window_width_spin)

        self.window_height_spin = QSpinBox()
        self.window_height_spin.setRange(600, 1500)
        self.window_height_spin.setValue(UI_CONFIG['window_height'])
        ui_layout.addRow("Window Height:", self.window_height_spin)

        # Video display dimensions
        self.video_width_spin = QSpinBox()
        self.video_width_spin.setRange(320, 1280)
        self.video_width_spin.setValue(UI_CONFIG['video_width'])
        ui_layout.addRow("Video Width:", self.video_width_spin)

        self.video_height_spin = QSpinBox()
        self.video_height_spin.setRange(240, 720)
        self.video_height_spin.setValue(UI_CONFIG['video_height'])
        ui_layout.addRow("Video Height:", self.video_height_spin)

        layout.addWidget(ui_group)
        layout.addStretch()

        self.tab_widget.addTab(tab, "User Interface")

    def create_custom_gesture_tab(self):
        """Create custom gesture settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Custom Gesture Configuration Group
        custom_group = QGroupBox("Custom Gesture Settings")
        custom_layout = QFormLayout(custom_group)

        # Samples per gesture
        self.samples_spin = QSpinBox()
        self.samples_spin.setRange(5, 50)
        self.samples_spin.setValue(CUSTOM_GESTURE_CONFIG['samples_per_gesture'])
        custom_layout.addRow("Samples per Gesture:", self.samples_spin)

        # Sample delay
        self.sample_delay_spin = QDoubleSpinBox()
        self.sample_delay_spin.setRange(0.5, 5.0)
        self.sample_delay_spin.setSingleStep(0.1)
        self.sample_delay_spin.setDecimals(1)
        self.sample_delay_spin.setValue(CUSTOM_GESTURE_CONFIG['sample_delay_seconds'])
        custom_layout.addRow("Sample Delay (seconds):", self.sample_delay_spin)

        # Recording countdown
        self.countdown_spin = QSpinBox()
        self.countdown_spin.setRange(1, 10)
        self.countdown_spin.setValue(CUSTOM_GESTURE_CONFIG['recording_countdown'])
        custom_layout.addRow("Recording Countdown:", self.countdown_spin)

        # Confidence threshold
        self.custom_confidence_spin = QDoubleSpinBox()
        self.custom_confidence_spin.setRange(0.1, 1.0)
        self.custom_confidence_spin.setSingleStep(0.1)
        self.custom_confidence_spin.setDecimals(2)
        self.custom_confidence_spin.setValue(CUSTOM_GESTURE_CONFIG['min_confidence_threshold'])
        custom_layout.addRow("Min Confidence:", self.custom_confidence_spin)

        # Similarity threshold
        self.similarity_spin = QDoubleSpinBox()
        self.similarity_spin.setRange(0.5, 1.0)
        self.similarity_spin.setSingleStep(0.05)
        self.similarity_spin.setDecimals(2)
        self.similarity_spin.setValue(CUSTOM_GESTURE_CONFIG['similarity_threshold'])
        custom_layout.addRow("Similarity Threshold:", self.similarity_spin)

        # Backup enabled
        self.backup_check = QCheckBox()
        self.backup_check.setChecked(CUSTOM_GESTURE_CONFIG['backup_enabled'])
        custom_layout.addRow("Enable Backup:", self.backup_check)

        # Gesture priority
        self.priority_check = QCheckBox()
        self.priority_check.setChecked(CUSTOM_GESTURE_CONFIG['enable_gesture_priority'])
        custom_layout.addRow("Predefined Priority:", self.priority_check)

        layout.addWidget(custom_group)
        layout.addStretch()
    def create_mouse_control_tab(self):
        """GFLOW-E04: Create dynamic mouse control settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox("Dynamic Mouse Control")
        form = QFormLayout(group)

        # Enable toggle
        self.mouse_enable_check = QCheckBox()
        self.mouse_enable_check.setChecked(MOUSE_CONTROL_CONFIG.get('enabled', True))
        form.addRow("Enable Mouse Control:", self.mouse_enable_check)
        # Gesture type
        self.mouse_gesture_type_combo = QComboBox()
        self.mouse_gesture_type_combo.addItems(['predefined', 'custom'])
        self.mouse_gesture_type_combo.setCurrentText(MOUSE_CONTROL_CONFIG.get('gesture_type', 'predefined'))
        form.addRow("Gesture Type:", self.mouse_gesture_type_combo)

        # Gesture select (dropdown)
        self.mouse_gesture_combo = QComboBox()
        form.addRow("Gesture:", self.mouse_gesture_combo)

        # Respond to type changes to repopulate gesture list
        self.mouse_gesture_type_combo.currentTextChanged.connect(self.populate_mouse_gesture_list)
        # Initial population
        self.populate_mouse_gesture_list()

        # Set initial selection from config
        initial_type = MOUSE_CONTROL_CONFIG.get('gesture_type', 'predefined')
        initial_name = MOUSE_CONTROL_CONFIG.get('gesture_name', 'pointing')
        self.mouse_gesture_type_combo.setCurrentText(initial_type)
        # populate_mouse_gesture_list() runs via signal, ensure selection
        index = self.mouse_gesture_combo.findData(initial_name)
        if index == -1:
            index = self.mouse_gesture_combo.findText(initial_name)
        if index >= 0:
            self.mouse_gesture_combo.setCurrentIndex(index)

        # Landmark choice
        self.mouse_landmark_combo = QComboBox()
        self.mouse_landmark_combo.addItems(['index_tip', 'wrist'])
        self.mouse_landmark_combo.setCurrentText(MOUSE_CONTROL_CONFIG.get('landmark', 'index_tip'))
        form.addRow("Reference Landmark:", self.mouse_landmark_combo)

        # Sensitivity
        self.mouse_sensitivity_spin = QDoubleSpinBox()
        self.mouse_sensitivity_spin.setRange(0.1, 5.0)
        self.mouse_sensitivity_spin.setSingleStep(0.1)
        self.mouse_sensitivity_spin.setDecimals(2)
        self.mouse_sensitivity_spin.setValue(MOUSE_CONTROL_CONFIG.get('sensitivity', 1.5))
        form.addRow("Sensitivity (gain):", self.mouse_sensitivity_spin)

        # Deadzone
        self.mouse_deadzone_spin = QSpinBox()
        self.mouse_deadzone_spin.setRange(0, 50)
        self.mouse_deadzone_spin.setValue(MOUSE_CONTROL_CONFIG.get('deadzone_pixels', 3))
        form.addRow("Deadzone (px):", self.mouse_deadzone_spin)

        # Smoothing
        self.mouse_smoothing_spin = QDoubleSpinBox()
        self.mouse_smoothing_spin.setRange(0.0, 0.95)
        self.mouse_smoothing_spin.setSingleStep(0.05)
        self.mouse_smoothing_spin.setDecimals(2)
        self.mouse_smoothing_spin.setValue(MOUSE_CONTROL_CONFIG.get('smoothing', 0.5))
        form.addRow("Smoothing (EMA):", self.mouse_smoothing_spin)

        # Invert axes
        self.mouse_invert_x_check = QCheckBox()
        self.mouse_invert_x_check.setChecked(MOUSE_CONTROL_CONFIG.get('invert_x', False))
        form.addRow("Invert X:", self.mouse_invert_x_check)

        self.mouse_invert_y_check = QCheckBox()
        self.mouse_invert_y_check.setChecked(MOUSE_CONTROL_CONFIG.get('invert_y', False))
        form.addRow("Invert Y:", self.mouse_invert_y_check)

        # Activation/deactivation frames
        self.mouse_activation_frames_spin = QSpinBox()
        self.mouse_activation_frames_spin.setRange(1, 10)
        self.mouse_activation_frames_spin.setValue(MOUSE_CONTROL_CONFIG.get('activation_frames', 3))
        form.addRow("Activation Frames:", self.mouse_activation_frames_spin)

        self.mouse_deactivation_frames_spin = QSpinBox()
        self.mouse_deactivation_frames_spin.setRange(1, 10)
        self.mouse_deactivation_frames_spin.setValue(MOUSE_CONTROL_CONFIG.get('deactivation_frames', 2))
        form.addRow("Deactivation Frames:", self.mouse_deactivation_frames_spin)

        layout.addWidget(group)
        layout.addStretch()
        self.tab_widget.addTab(tab, "Mouse Control")

    def populate_mouse_gesture_list(self):
        """Populate gesture dropdown based on selected type and current profile's custom gestures."""
        try:
            self.mouse_gesture_combo.clear()
            gtype = self.mouse_gesture_type_combo.currentText().lower() if hasattr(self, 'mouse_gesture_type_combo') else 'predefined'

            if gtype == 'predefined':
                # Use config PREDEFINED_GESTURES
                for gesture_id, gesture_data in PREDEFINED_GESTURES.items():
                    if gesture_data.get('enabled', True):
                        display = gesture_data.get('name', gesture_id.replace('_', ' ').title())
                        self.mouse_gesture_combo.addItem(display, gesture_id)
            elif gtype == 'custom':
                # Use injected custom_gesture_manager if available (current profile)
                if self.custom_gesture_manager is not None:
                    for g in self.custom_gesture_manager.get_gesture_list():
                        if g.get('is_trained', False):
                            name = g['name']
                            self.mouse_gesture_combo.addItem(name, name)
                else:
                    # Fallback: use current profile via ProfileManager
                    from profile_manager import ProfileManager
                    pm = ProfileManager()
                    cgm = CustomGestureManager(pm.get_current_profile_name() or 'default')
                    for g in cgm.get_gesture_list():
                        if g.get('is_trained', False):
                            name = g['name']
                            self.mouse_gesture_combo.addItem(name, name)

            # Ensure current config selection remains if present
            current_name = MOUSE_CONTROL_CONFIG.get('gesture_name', 'pointing')
            idx = self.mouse_gesture_combo.findData(current_name)
            if idx == -1:
                idx = self.mouse_gesture_combo.findText(current_name)
            if idx >= 0:
                self.mouse_gesture_combo.setCurrentIndex(idx)
        except Exception as e:
            print(f"Failed to populate gesture list: {e}")

        # Note: Rest of the controls are added inside create_mouse_control_tab, not here.


    def create_action_execution_tab(self):
        """Create action execution settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Action Execution Group
        action_group = QGroupBox("Action Execution Settings")
        action_layout = QFormLayout(action_group)

        # Input library selection
        self.input_library_combo = QComboBox()
        self.input_library_combo.addItems(['pynput', 'pyautogui'])
        self.input_library_combo.setCurrentText(ACTION_EXECUTION_CONFIG['input_library'])
        action_layout.addRow("Input Library:", self.input_library_combo)

        # Enable failsafe
        self.failsafe_check = QCheckBox()
        self.failsafe_check.setChecked(ACTION_EXECUTION_CONFIG['enable_failsafe'])
        action_layout.addRow("Enable Failsafe:", self.failsafe_check)

        # Default action delay
        self.action_delay_spin = QDoubleSpinBox()
        self.action_delay_spin.setRange(0.0, 2.0)
        self.action_delay_spin.setSingleStep(0.1)
        self.action_delay_spin.setDecimals(2)
        self.action_delay_spin.setValue(ACTION_EXECUTION_CONFIG['default_action_delay'])
        action_layout.addRow("Action Delay (seconds):", self.action_delay_spin)

        # Mouse movement duration
        self.mouse_duration_spin = QDoubleSpinBox()
        self.mouse_duration_spin.setRange(0.1, 2.0)
        self.mouse_duration_spin.setSingleStep(0.1)
        self.mouse_duration_spin.setDecimals(1)
        self.mouse_duration_spin.setValue(ACTION_EXECUTION_CONFIG['mouse_movement_duration'])
        action_layout.addRow("Mouse Duration (seconds):", self.mouse_duration_spin)

        # Action timeout
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(1.0, 30.0)
        self.timeout_spin.setSingleStep(1.0)
        self.timeout_spin.setDecimals(1)
        self.timeout_spin.setValue(ACTION_EXECUTION_CONFIG['action_timeout'])
        action_layout.addRow("Action Timeout (seconds):", self.timeout_spin)

        # Log all actions
        self.log_actions_check = QCheckBox()
        self.log_actions_check.setChecked(ACTION_EXECUTION_CONFIG['log_all_actions'])
        action_layout.addRow("Log All Actions:", self.log_actions_check)

        # Async execution
        self.async_check = QCheckBox()
        self.async_check.setChecked(ACTION_EXECUTION_CONFIG['async_execution'])
        action_layout.addRow("Async Execution:", self.async_check)

        layout.addWidget(action_group)
        layout.addStretch()

        self.tab_widget.addTab(tab, "Action Execution")

    def create_visual_feedback_tab(self):
        """GFLOW-19: Create visual feedback settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Hand Landmarks Group
        landmarks_group = QGroupBox("Hand Landmarks Display")
        landmarks_layout = QFormLayout(landmarks_group)

        # Show landmarks toggle
        self.show_landmarks_check = QCheckBox()
        self.show_landmarks_check.setChecked(VISUAL_FEEDBACK_CONFIG['show_hand_landmarks'])
        landmarks_layout.addRow("Show Hand Landmarks:", self.show_landmarks_check)

        # Landmark thickness
        self.landmark_thickness_spin = QSpinBox()
        self.landmark_thickness_spin.setRange(1, 5)
        self.landmark_thickness_spin.setValue(VISUAL_FEEDBACK_CONFIG['landmark_thickness'])
        landmarks_layout.addRow("Landmark Thickness:", self.landmark_thickness_spin)

        # Connection thickness
        self.connection_thickness_spin = QSpinBox()
        self.connection_thickness_spin.setRange(1, 5)
        self.connection_thickness_spin.setValue(VISUAL_FEEDBACK_CONFIG['connection_thickness'])
        landmarks_layout.addRow("Connection Thickness:", self.connection_thickness_spin)

        layout.addWidget(landmarks_group)

        # Gesture Notifications Group
        notifications_group = QGroupBox("Gesture Recognition Notifications")
        notifications_layout = QFormLayout(notifications_group)

        # Show notifications toggle
        self.show_notifications_check = QCheckBox()
        self.show_notifications_check.setChecked(VISUAL_FEEDBACK_CONFIG['show_gesture_notifications'])
        notifications_layout.addRow("Show Notifications:", self.show_notifications_check)

        # Notification duration
        self.notification_duration_spin = QDoubleSpinBox()
        self.notification_duration_spin.setRange(0.5, 10.0)
        self.notification_duration_spin.setSingleStep(0.5)
        self.notification_duration_spin.setDecimals(1)
        self.notification_duration_spin.setValue(VISUAL_FEEDBACK_CONFIG['notification_duration'])
        notifications_layout.addRow("Duration (seconds):", self.notification_duration_spin)

        # Notification position
        self.notification_position_combo = QComboBox()
        self.notification_position_combo.addItems(['top_left', 'top_right', 'bottom_left', 'bottom_right'])
        self.notification_position_combo.setCurrentText(VISUAL_FEEDBACK_CONFIG['notification_position'])
        notifications_layout.addRow("Position:", self.notification_position_combo)

        # Font size
        self.notification_font_size_spin = QSpinBox()
        self.notification_font_size_spin.setRange(8, 24)
        self.notification_font_size_spin.setValue(VISUAL_FEEDBACK_CONFIG['notification_font_size'])
        notifications_layout.addRow("Font Size:", self.notification_font_size_spin)

        # Enable animations
        self.enable_animations_check = QCheckBox()
        self.enable_animations_check.setChecked(VISUAL_FEEDBACK_CONFIG['enable_notification_animations'])
        notifications_layout.addRow("Enable Animations:", self.enable_animations_check)

        layout.addWidget(notifications_group)
        layout.addStretch()

        self.tab_widget.addTab(tab, "Visual Feedback")

    def setup_connections(self):
        """Setup signal connections"""
        self.ok_button.clicked.connect(self.accept_settings)
        self.apply_button.clicked.connect(self.apply_settings)
        self.cancel_button.clicked.connect(self.reject)
        self.reset_button.clicked.connect(self.reset_to_defaults)

    def get_current_settings(self) -> Dict[str, Any]:
        """Get current settings from configuration"""
        return {
            'webcam': WEBCAM_CONFIG.copy(),
            'mediapipe': MEDIAPIPE_CONFIG.copy(),
            'gesture': GESTURE_CONFIG.copy(),
            'performance': PERFORMANCE_CONFIG.copy(),
            'ui': UI_CONFIG.copy(),
            'custom_gesture': CUSTOM_GESTURE_CONFIG.copy(),
            'action_execution': ACTION_EXECUTION_CONFIG.copy(),
            'visual_feedback': VISUAL_FEEDBACK_CONFIG.copy(),  # GFLOW-19
            'mouse_control': MOUSE_CONTROL_CONFIG.copy()  # GFLOW-E04
        }

    def load_settings(self):
        """Load settings from persistent storage"""
        # Load from QSettings if available
        if self.qsettings.contains("settings"):
            try:
                settings_str = self.qsettings.value("settings")
                if settings_str:
                    saved_settings = json.loads(settings_str)
                    self.apply_loaded_settings(saved_settings)
            except (json.JSONDecodeError, Exception) as e:
                print(f"Error loading saved settings: {e}")

    def apply_loaded_settings(self, settings: Dict[str, Any]):
        """Apply loaded settings to UI controls"""
        try:
            # Helper function to safely set widget values
            def safe_set_value(widget, method_name, value, *args):
                try:
                    if widget and hasattr(widget, method_name):
                        method = getattr(widget, method_name)
                        if callable(method):
                            method(value, *args)
                except RuntimeError:
                    # Widget has been deleted, skip
                    pass

            # Webcam settings
            if 'webcam' in settings:
                webcam = settings['webcam']
                safe_set_value(self.width_spin, 'setValue', webcam.get('width', WEBCAM_CONFIG['width']))
                safe_set_value(self.height_spin, 'setValue', webcam.get('height', WEBCAM_CONFIG['height']))
                safe_set_value(self.fps_spin, 'setValue', webcam.get('fps', WEBCAM_CONFIG['fps']))
                safe_set_value(self.device_spin, 'setValue', webcam.get('device_id', WEBCAM_CONFIG['device_id']))
                safe_set_value(self.flip_check, 'setChecked', webcam.get('flip_horizontal', WEBCAM_CONFIG['flip_horizontal']))

            # MediaPipe settings
            if 'mediapipe' in settings:
                mp = settings['mediapipe']
                safe_set_value(self.max_hands_spin, 'setValue', mp.get('max_num_hands', MEDIAPIPE_CONFIG['max_num_hands']))
                safe_set_value(self.detection_conf_spin, 'setValue', mp.get('min_detection_confidence', MEDIAPIPE_CONFIG['min_detection_confidence']))
                safe_set_value(self.tracking_conf_spin, 'setValue', mp.get('min_tracking_confidence', MEDIAPIPE_CONFIG['min_tracking_confidence']))

            # Gesture settings
            if 'gesture' in settings:
                gesture = settings['gesture']
                safe_set_value(self.recognition_threshold_spin, 'setValue', gesture.get('recognition_threshold', GESTURE_CONFIG['recognition_threshold']))
                safe_set_value(self.hold_time_spin, 'setValue', gesture.get('gesture_hold_time', GESTURE_CONFIG['gesture_hold_time']))
                safe_set_value(self.smoothing_spin, 'setValue', gesture.get('smoothing_frames', GESTURE_CONFIG['smoothing_frames']))
                safe_set_value(self.debug_check, 'setChecked', gesture.get('debug_mode', GESTURE_CONFIG['debug_mode']))

            # Performance settings
            if 'performance' in settings:
                perf = settings['performance']
                safe_set_value(self.fps_interval_spin, 'setValue', perf.get('fps_update_interval', PERFORMANCE_CONFIG['fps_update_interval']))
                safe_set_value(self.history_spin, 'setValue', perf.get('max_recognition_history', PERFORMANCE_CONFIG['max_recognition_history']))
                safe_set_value(self.target_fps_spin, 'setValue', perf.get('target_fps', PERFORMANCE_CONFIG['target_fps']))
                safe_set_value(self.max_latency_spin, 'setValue', perf.get('max_latency_ms', PERFORMANCE_CONFIG['max_latency_ms']))

            # UI settings
            if 'ui' in settings:
                ui = settings['ui']
                safe_set_value(self.window_title_edit, 'setText', ui.get('window_title', UI_CONFIG['window_title']))
                safe_set_value(self.window_width_spin, 'setValue', ui.get('window_width', UI_CONFIG['window_width']))
                safe_set_value(self.window_height_spin, 'setValue', ui.get('window_height', UI_CONFIG['window_height']))
                safe_set_value(self.video_width_spin, 'setValue', ui.get('video_width', UI_CONFIG['video_width']))
                safe_set_value(self.video_height_spin, 'setValue', ui.get('video_height', UI_CONFIG['video_height']))

            # Custom gesture settings
            if 'custom_gesture' in settings:
                custom = settings['custom_gesture']
                safe_set_value(self.samples_spin, 'setValue', custom.get('samples_per_gesture', CUSTOM_GESTURE_CONFIG['samples_per_gesture']))
                safe_set_value(self.sample_delay_spin, 'setValue', custom.get('sample_delay_seconds', CUSTOM_GESTURE_CONFIG['sample_delay_seconds']))
                safe_set_value(self.countdown_spin, 'setValue', custom.get('recording_countdown', CUSTOM_GESTURE_CONFIG['recording_countdown']))
                safe_set_value(self.custom_confidence_spin, 'setValue', custom.get('min_confidence_threshold', CUSTOM_GESTURE_CONFIG['min_confidence_threshold']))
                safe_set_value(self.similarity_spin, 'setValue', custom.get('similarity_threshold', CUSTOM_GESTURE_CONFIG['similarity_threshold']))
                safe_set_value(self.backup_check, 'setChecked', custom.get('backup_enabled', CUSTOM_GESTURE_CONFIG['backup_enabled']))
                safe_set_value(self.priority_check, 'setChecked', custom.get('enable_gesture_priority', CUSTOM_GESTURE_CONFIG['enable_gesture_priority']))

            # Action execution settings
            if 'action_execution' in settings:
                action = settings['action_execution']
                safe_set_value(self.input_library_combo, 'setCurrentText', action.get('input_library', ACTION_EXECUTION_CONFIG['input_library']))
                safe_set_value(self.failsafe_check, 'setChecked', action.get('enable_failsafe', ACTION_EXECUTION_CONFIG['enable_failsafe']))
                safe_set_value(self.action_delay_spin, 'setValue', action.get('default_action_delay', ACTION_EXECUTION_CONFIG['default_action_delay']))
                safe_set_value(self.mouse_duration_spin, 'setValue', action.get('mouse_movement_duration', ACTION_EXECUTION_CONFIG['mouse_movement_duration']))
                safe_set_value(self.timeout_spin, 'setValue', action.get('action_timeout', ACTION_EXECUTION_CONFIG['action_timeout']))
                safe_set_value(self.log_actions_check, 'setChecked', action.get('log_all_actions', ACTION_EXECUTION_CONFIG['log_all_actions']))
                safe_set_value(self.async_check, 'setChecked', action.get('async_execution', ACTION_EXECUTION_CONFIG['async_execution']))

            # GFLOW-19: Visual feedback settings
            if 'visual_feedback' in settings:
                visual = settings['visual_feedback']
                safe_set_value(self.show_landmarks_check, 'setChecked', visual.get('show_hand_landmarks', VISUAL_FEEDBACK_CONFIG['show_hand_landmarks']))
                safe_set_value(self.landmark_thickness_spin, 'setValue', visual.get('landmark_thickness', VISUAL_FEEDBACK_CONFIG['landmark_thickness']))
                safe_set_value(self.connection_thickness_spin, 'setValue', visual.get('connection_thickness', VISUAL_FEEDBACK_CONFIG['connection_thickness']))
                safe_set_value(self.show_notifications_check, 'setChecked', visual.get('show_gesture_notifications', VISUAL_FEEDBACK_CONFIG['show_gesture_notifications']))
                safe_set_value(self.notification_duration_spin, 'setValue', visual.get('notification_duration', VISUAL_FEEDBACK_CONFIG['notification_duration']))
                safe_set_value(self.notification_position_combo, 'setCurrentText', visual.get('notification_position', VISUAL_FEEDBACK_CONFIG['notification_position']))
                safe_set_value(self.notification_font_size_spin, 'setValue', visual.get('notification_font_size', VISUAL_FEEDBACK_CONFIG['notification_font_size']))
                safe_set_value(self.enable_animations_check, 'setChecked', visual.get('enable_notification_animations', VISUAL_FEEDBACK_CONFIG['enable_notification_animations']))

            # GFLOW-E04: Mouse control settings
            if 'mouse_control' in settings:
                mc = settings['mouse_control']
                safe_set_value(self.mouse_enable_check, 'setChecked', mc.get('enabled', True))
                safe_set_value(self.mouse_gesture_type_combo, 'setCurrentText', mc.get('gesture_type', 'predefined'))
                # Repopulate and select gesture
                self.populate_mouse_gesture_list()
                idx = self.mouse_gesture_combo.findData(mc.get('gesture_name', 'pointing'))
                if idx == -1:
                    idx = self.mouse_gesture_combo.findText(mc.get('gesture_name', 'pointing'))
                if idx >= 0:
                    self.mouse_gesture_combo.setCurrentIndex(idx)
                safe_set_value(self.mouse_landmark_combo, 'setCurrentText', mc.get('landmark', 'index_tip'))
                safe_set_value(self.mouse_sensitivity_spin, 'setValue', mc.get('sensitivity', 1.5))
                safe_set_value(self.mouse_deadzone_spin, 'setValue', mc.get('deadzone_pixels', 3))
                safe_set_value(self.mouse_smoothing_spin, 'setValue', mc.get('smoothing', 0.5))
                safe_set_value(self.mouse_invert_x_check, 'setChecked', mc.get('invert_x', False))
                safe_set_value(self.mouse_invert_y_check, 'setChecked', mc.get('invert_y', False))
                safe_set_value(self.mouse_activation_frames_spin, 'setValue', mc.get('activation_frames', 3))
                safe_set_value(self.mouse_deactivation_frames_spin, 'setValue', mc.get('deactivation_frames', 2))

        except Exception as e:
            print(f"Error applying loaded settings: {e}")

    def collect_current_settings(self) -> Dict[str, Any]:
        """Collect current settings from UI controls"""
        # Helper function to safely get widget values
        def safe_get_value(widget, method_name='value', default=None):
            try:
                if widget and hasattr(widget, method_name):
                    method = getattr(widget, method_name)
                    return method() if callable(method) else method
                return default
            except RuntimeError:
                # Widget has been deleted
                return default

        return {
            'webcam': {
                'width': safe_get_value(self.width_spin, 'value', WEBCAM_CONFIG['width']),
                'height': safe_get_value(self.height_spin, 'value', WEBCAM_CONFIG['height']),
                'fps': safe_get_value(self.fps_spin, 'value', WEBCAM_CONFIG['fps']),
                'device_id': safe_get_value(self.device_spin, 'value', WEBCAM_CONFIG['device_id']),
                'flip_horizontal': safe_get_value(self.flip_check, 'isChecked', WEBCAM_CONFIG['flip_horizontal'])
            },
            'mediapipe': {
                'static_image_mode': MEDIAPIPE_CONFIG['static_image_mode'],  # Keep original
                'max_num_hands': safe_get_value(self.max_hands_spin, 'value', MEDIAPIPE_CONFIG['max_num_hands']),
                'min_detection_confidence': safe_get_value(self.detection_conf_spin, 'value', MEDIAPIPE_CONFIG['min_detection_confidence']),
                'min_tracking_confidence': safe_get_value(self.tracking_conf_spin, 'value', MEDIAPIPE_CONFIG['min_tracking_confidence'])
            },
            'gesture': {
                'recognition_threshold': safe_get_value(self.recognition_threshold_spin, 'value', GESTURE_CONFIG['recognition_threshold']),
                'gesture_hold_time': safe_get_value(self.hold_time_spin, 'value', GESTURE_CONFIG['gesture_hold_time']),
                'smoothing_frames': safe_get_value(self.smoothing_spin, 'value', GESTURE_CONFIG['smoothing_frames']),
                'debug_mode': safe_get_value(self.debug_check, 'isChecked', GESTURE_CONFIG['debug_mode'])
            },
            'performance': {
                'fps_update_interval': safe_get_value(self.fps_interval_spin, 'value', PERFORMANCE_CONFIG['fps_update_interval']),
                'max_recognition_history': safe_get_value(self.history_spin, 'value', PERFORMANCE_CONFIG['max_recognition_history']),
                'target_fps': safe_get_value(self.target_fps_spin, 'value', PERFORMANCE_CONFIG['target_fps']),
                'max_latency_ms': safe_get_value(self.max_latency_spin, 'value', PERFORMANCE_CONFIG['max_latency_ms'])
            },
            'ui': {
                'window_title': safe_get_value(self.window_title_edit, 'text', UI_CONFIG['window_title']),
                'window_width': safe_get_value(self.window_width_spin, 'value', UI_CONFIG['window_width']),
                'window_height': safe_get_value(self.window_height_spin, 'value', UI_CONFIG['window_height']),
                'video_width': safe_get_value(self.video_width_spin, 'value', UI_CONFIG['video_width']),
                'video_height': safe_get_value(self.video_height_spin, 'value', UI_CONFIG['video_height'])
            },
            'custom_gesture': {
                'data_directory': CUSTOM_GESTURE_CONFIG['data_directory'],  # Keep original paths
                'models_directory': CUSTOM_GESTURE_CONFIG['models_directory'],
                'samples_per_gesture': safe_get_value(self.samples_spin, 'value', CUSTOM_GESTURE_CONFIG['samples_per_gesture']),
                'sample_delay_seconds': safe_get_value(self.sample_delay_spin, 'value', CUSTOM_GESTURE_CONFIG['sample_delay_seconds']),
                'recording_countdown': safe_get_value(self.countdown_spin, 'value', CUSTOM_GESTURE_CONFIG['recording_countdown']),
                'min_confidence_threshold': safe_get_value(self.custom_confidence_spin, 'value', CUSTOM_GESTURE_CONFIG['min_confidence_threshold']),
                'feature_vector_size': CUSTOM_GESTURE_CONFIG['feature_vector_size'],  # Keep original
                'similarity_threshold': safe_get_value(self.similarity_spin, 'value', CUSTOM_GESTURE_CONFIG['similarity_threshold']),
                'svm_kernel': CUSTOM_GESTURE_CONFIG['svm_kernel'],  # Keep original
                'svm_c': CUSTOM_GESTURE_CONFIG['svm_c'],  # Keep original
                'cross_validation_folds': CUSTOM_GESTURE_CONFIG['cross_validation_folds'],  # Keep original
                'max_gesture_name_length': CUSTOM_GESTURE_CONFIG['max_gesture_name_length'],  # Keep original
                'backup_enabled': safe_get_value(self.backup_check, 'isChecked', CUSTOM_GESTURE_CONFIG['backup_enabled']),
                'predefined_confidence_boost': CUSTOM_GESTURE_CONFIG['predefined_confidence_boost'],  # Keep original
                'enable_gesture_priority': safe_get_value(self.priority_check, 'isChecked', CUSTOM_GESTURE_CONFIG['enable_gesture_priority'])
            },
            'action_execution': {
                'input_library': safe_get_value(self.input_library_combo, 'currentText', ACTION_EXECUTION_CONFIG['input_library']),
                'enable_failsafe': safe_get_value(self.failsafe_check, 'isChecked', ACTION_EXECUTION_CONFIG['enable_failsafe']),
                'failsafe_corner': ACTION_EXECUTION_CONFIG['failsafe_corner'],  # Keep original
                'require_confirmation': ACTION_EXECUTION_CONFIG['require_confirmation'],  # Keep original
                'default_action_delay': safe_get_value(self.action_delay_spin, 'value', ACTION_EXECUTION_CONFIG['default_action_delay']),
                'mouse_movement_duration': safe_get_value(self.mouse_duration_spin, 'value', ACTION_EXECUTION_CONFIG['mouse_movement_duration']),
                'key_press_interval': ACTION_EXECUTION_CONFIG['key_press_interval'],  # Keep original
                'action_timeout': safe_get_value(self.timeout_spin, 'value', ACTION_EXECUTION_CONFIG['action_timeout']),
                'max_retry_attempts': ACTION_EXECUTION_CONFIG['max_retry_attempts'],  # Keep original
                'error_recovery_delay': ACTION_EXECUTION_CONFIG['error_recovery_delay'],  # Keep original
                'log_all_actions': safe_get_value(self.log_actions_check, 'isChecked', ACTION_EXECUTION_CONFIG['log_all_actions']),
                'enable_undo': ACTION_EXECUTION_CONFIG['enable_undo'],  # Keep original
                'async_execution': safe_get_value(self.async_check, 'isChecked', ACTION_EXECUTION_CONFIG['async_execution']),
                'queue_max_size': ACTION_EXECUTION_CONFIG['queue_max_size'],  # Keep original
                'execution_thread_pool': ACTION_EXECUTION_CONFIG['execution_thread_pool'],  # Keep original
                'context_aware_execution': ACTION_EXECUTION_CONFIG['context_aware_execution'],  # Keep original
                'application_detection': ACTION_EXECUTION_CONFIG['application_detection'],  # Keep original
                'window_focus_check': ACTION_EXECUTION_CONFIG['window_focus_check']  # Keep original
            },
            # GFLOW-19: Visual feedback settings
            'visual_feedback': {
                'show_hand_landmarks': safe_get_value(self.show_landmarks_check, 'isChecked', VISUAL_FEEDBACK_CONFIG['show_hand_landmarks']),
                'landmark_color': VISUAL_FEEDBACK_CONFIG['landmark_color'],  # Keep original
                'landmark_thickness': safe_get_value(self.landmark_thickness_spin, 'value', VISUAL_FEEDBACK_CONFIG['landmark_thickness']),
                'connection_color': VISUAL_FEEDBACK_CONFIG['connection_color'],  # Keep original
                'connection_thickness': safe_get_value(self.connection_thickness_spin, 'value', VISUAL_FEEDBACK_CONFIG['connection_thickness']),
                'show_gesture_notifications': safe_get_value(self.show_notifications_check, 'isChecked', VISUAL_FEEDBACK_CONFIG['show_gesture_notifications']),
                'notification_duration': safe_get_value(self.notification_duration_spin, 'value', VISUAL_FEEDBACK_CONFIG['notification_duration']),
                'notification_fade_duration': VISUAL_FEEDBACK_CONFIG['notification_fade_duration'],  # Keep original
                'notification_position': safe_get_value(self.notification_position_combo, 'currentText', VISUAL_FEEDBACK_CONFIG['notification_position']),
                'notification_offset_x': VISUAL_FEEDBACK_CONFIG['notification_offset_x'],  # Keep original
                'notification_offset_y': VISUAL_FEEDBACK_CONFIG['notification_offset_y'],  # Keep original
                'notification_background_color': VISUAL_FEEDBACK_CONFIG['notification_background_color'],  # Keep original
                'notification_text_color': VISUAL_FEEDBACK_CONFIG['notification_text_color'],  # Keep original
                'notification_border_color': VISUAL_FEEDBACK_CONFIG['notification_border_color'],  # Keep original
                'notification_border_width': VISUAL_FEEDBACK_CONFIG['notification_border_width'],  # Keep original
                'notification_border_radius': VISUAL_FEEDBACK_CONFIG['notification_border_radius'],  # Keep original
                'notification_padding': VISUAL_FEEDBACK_CONFIG['notification_padding'],  # Keep original
                'notification_font_size': safe_get_value(self.notification_font_size_spin, 'value', VISUAL_FEEDBACK_CONFIG['notification_font_size']),
                'notification_font_weight': VISUAL_FEEDBACK_CONFIG['notification_font_weight'],  # Keep original
                'enable_notification_animations': safe_get_value(self.enable_animations_check, 'isChecked', VISUAL_FEEDBACK_CONFIG['enable_notification_animations']),
                'fade_in_duration': VISUAL_FEEDBACK_CONFIG['fade_in_duration'],  # Keep original
                'fade_out_duration': VISUAL_FEEDBACK_CONFIG['fade_out_duration'],  # Keep original
                'slide_distance': VISUAL_FEEDBACK_CONFIG['slide_distance'],  # Keep original
                'max_notifications_queue': VISUAL_FEEDBACK_CONFIG['max_notifications_queue'],  # Keep original
                'notification_update_interval': VISUAL_FEEDBACK_CONFIG['notification_update_interval']  # Keep original
            }
,
            # GFLOW-E04: Mouse control settings
            'mouse_control': {
                'enabled': safe_get_value(self.mouse_enable_check, 'isChecked', MOUSE_CONTROL_CONFIG['enabled']),
                'gesture_type': safe_get_value(self.mouse_gesture_type_combo, 'currentText', MOUSE_CONTROL_CONFIG['gesture_type']),
                'gesture_name': safe_get_value(self.mouse_gesture_combo, 'currentData', MOUSE_CONTROL_CONFIG['gesture_name']) or safe_get_value(self.mouse_gesture_combo, 'currentText', MOUSE_CONTROL_CONFIG['gesture_name']),
                'landmark': safe_get_value(self.mouse_landmark_combo, 'currentText', MOUSE_CONTROL_CONFIG['landmark']),
                'sensitivity': safe_get_value(self.mouse_sensitivity_spin, 'value', MOUSE_CONTROL_CONFIG['sensitivity']),
                'deadzone_pixels': safe_get_value(self.mouse_deadzone_spin, 'value', MOUSE_CONTROL_CONFIG['deadzone_pixels']),
                'smoothing': safe_get_value(self.mouse_smoothing_spin, 'value', MOUSE_CONTROL_CONFIG['smoothing']),
                'invert_x': safe_get_value(self.mouse_invert_x_check, 'isChecked', MOUSE_CONTROL_CONFIG['invert_x']),
                'invert_y': safe_get_value(self.mouse_invert_y_check, 'isChecked', MOUSE_CONTROL_CONFIG['invert_y']),
                'activation_frames': safe_get_value(self.mouse_activation_frames_spin, 'value', MOUSE_CONTROL_CONFIG['activation_frames']),
                'deactivation_frames': safe_get_value(self.mouse_deactivation_frames_spin, 'value', MOUSE_CONTROL_CONFIG['deactivation_frames'])
            }
        }


    def apply_settings(self):
        """Apply current settings"""
        try:
            # Check if widgets are still valid before collecting settings
            if not self.width_spin or not hasattr(self.width_spin, 'value'):
                QMessageBox.warning(
                    self, "Error",
                    "Settings dialog widgets are no longer valid. Please reopen the dialog."
                )
                return

            # Collect current settings
            new_settings = self.collect_current_settings()

            # Validate settings
            if not self.validate_settings(new_settings):
                return

            # Save to persistent storage
            self.qsettings.setValue("settings", json.dumps(new_settings))

            # Update current settings
            self.current_settings = new_settings

            # Emit signal for main application to update
            self.settings_changed.emit(new_settings)

            QMessageBox.information(
                self, "Settings Applied",
                "Settings have been applied successfully.\nSome changes may require restarting the application."
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to apply settings: {str(e)}"
            )

    def accept_settings(self):
        """Apply settings and close dialog"""
        try:
            # Check if widgets are still valid before applying settings
            if not self.width_spin or not hasattr(self.width_spin, 'value'):
                QMessageBox.warning(
                    self, "Error",
                    "Settings dialog widgets are no longer valid. Please reopen the dialog."
                )
                return

            # Collect current settings first
            new_settings = self.collect_current_settings()

            # Validate settings
            if not self.validate_settings(new_settings):
                return

            # Save to persistent storage
            self.qsettings.setValue("settings", json.dumps(new_settings))

            # Update current settings
            self.current_settings = new_settings

            # Emit signal for main application to update
            self.settings_changed.emit(new_settings)

            # Close the dialog
            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to apply settings: {str(e)}"
            )

    def validate_settings(self, settings: Dict[str, Any]) -> bool:
        """Validate settings before applying"""
        try:
            # Validate webcam settings
            webcam = settings['webcam']
            if webcam['width'] < 320 or webcam['height'] < 240:
                QMessageBox.warning(self, "Invalid Settings", "Webcam resolution too low.")
                return False

            # Validate MediaPipe settings
            mp = settings['mediapipe']
            # Note: Detection confidence can actually be higher than tracking confidence
            # This is a common MediaPipe configuration, so we'll remove this validation
            # and just ensure both values are within valid ranges
            if not (0.0 <= mp['min_detection_confidence'] <= 1.0):
                QMessageBox.warning(
                    self, "Invalid Settings",
                    "Detection confidence must be between 0.0 and 1.0."
                )
                return False

            if not (0.0 <= mp['min_tracking_confidence'] <= 1.0):
                QMessageBox.warning(
                    self, "Invalid Settings",
                    "Tracking confidence must be between 0.0 and 1.0."
                )
                return False

            # Validate performance settings
            perf = settings['performance']
            if perf['target_fps'] > webcam['fps']:
                QMessageBox.warning(
                    self, "Invalid Settings",
                    f"Target FPS ({perf['target_fps']}) cannot be higher than webcam FPS ({webcam['fps']})."
                )
                return False

            # Validate other performance settings
            if perf['max_latency_ms'] < 10:
                QMessageBox.warning(
                    self, "Invalid Settings",
                    "Maximum latency must be at least 10ms."
                )
                return False

            # Validate custom gesture settings
            custom = settings['custom_gesture']
            if custom['samples_per_gesture'] < 5:
                QMessageBox.warning(
                    self, "Invalid Settings",
                    "Samples per gesture must be at least 5 for reliable training."
                )
                return False

            if custom['sample_delay_seconds'] < 0.1:
                QMessageBox.warning(
                    self, "Invalid Settings",
                    "Sample delay must be at least 0.1 seconds."
                )
                return False

            return True

        except Exception as e:
            QMessageBox.critical(self, "Validation Error", f"Settings validation failed: {str(e)}")
            return False

    def reset_to_defaults(self):
        """Reset all settings to default values"""
        reply = QMessageBox.question(
            self, "Reset Settings",
            "Are you sure you want to reset all settings to default values?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Reset to original configuration values
            self.apply_loaded_settings(self.original_settings)

            # Clear persistent storage
            self.qsettings.remove("settings")

            QMessageBox.information(
                self, "Settings Reset",
                "All settings have been reset to default values."
            )

    def save_settings_to_file(self):
        """Save current settings to a file"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save Settings",
                os.path.join(PROJECT_ROOT, "settings_backup.json"),
                "JSON Files (*.json)"
            )

            if filename:
                settings = self.collect_current_settings()
                with open(filename, 'w') as f:
                    json.dump(settings, f, indent=2)

                QMessageBox.information(
                    self, "Settings Saved",
                    f"Settings saved to {filename}"
                )

        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to save settings: {str(e)}"
            )

    def load_settings_from_file(self):
        """Load settings from a file"""
        try:
            filename, _ = QFileDialog.getOpenFileName(
                self, "Load Settings",
                PROJECT_ROOT,
                "JSON Files (*.json)"
            )

            if filename:
                with open(filename, 'r') as f:
                    settings = json.load(f)

                self.apply_loaded_settings(settings)

                QMessageBox.information(
                    self, "Settings Loaded",
                    f"Settings loaded from {filename}"
                )

        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to load settings: {str(e)}"
            )
