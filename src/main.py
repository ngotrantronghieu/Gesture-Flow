import sys
import cv2
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout,
                               QHBoxLayout, QWidget, QPushButton, QLabel,
                               QTextEdit, QFrame)
from PySide6.QtCore import QTimer, QThread, Signal, Qt
from PySide6.QtCore import QSettings
import json

from PySide6.QtGui import QImage, QPixmap, QFont
import mediapipe as mp
import time
import math
from typing import Optional, Dict, List, Tuple
from config import (WEBCAM_CONFIG, MEDIAPIPE_CONFIG, GESTURE_CONFIG,
                   PERFORMANCE_CONFIG, UI_CONFIG, PREDEFINED_GESTURES, CUSTOM_GESTURE_CONFIG,
                   ACTION_EXECUTION_CONFIG, VISUAL_FEEDBACK_CONFIG, MOUSE_CONTROL_CONFIG)
from custom_gesture_manager import CustomGestureManager
from gesture_recording_dialog import GestureRecordingDialog
from gesture_management_dialog import GestureManagementDialog
from action_mapping_dialog import ActionMappingDialog
from action_mapping_manager import ActionMappingManager
from action_executor import ActionExecutor
from settings_dialog import SettingsDialog
from profile_manager import ProfileManager
from profile_management_dialog import ProfileManagementDialog
from notification_widget import NotificationWidget, GestureNotificationManager

class WebcamThread(QThread):
    """
    GFLOW-1 & GFLOW-2: Webcam capture and MediaPipe hand tracking thread
    Handles webcam input and MediaPipe hand landmark detection
    """
    frame_ready = Signal(np.ndarray, list)  # frame, hand_landmarks
    error_occurred = Signal(str)
    fps_update = Signal(float)

    def __init__(self):
        super().__init__()
        self.running = False
        self.cap = None

        # Initialize MediaPipe
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=MEDIAPIPE_CONFIG['static_image_mode'],
            max_num_hands=MEDIAPIPE_CONFIG['max_num_hands'],
            min_detection_confidence=MEDIAPIPE_CONFIG['min_detection_confidence'],
            min_tracking_confidence=MEDIAPIPE_CONFIG['min_tracking_confidence']
        )
        self.mp_drawing = mp.solutions.drawing_utils

        # FPS tracking
        self.fps_counter = 0
        self.fps_start_time = time.time()

        # Store current landmarks for custom gesture recording
        self.current_landmarks = []

    def start_capture(self):
        """Start webcam capture"""
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                self.error_occurred.emit("No webcam detected or unable to access webcam")
                return False

            # Set webcam properties for better performance
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, WEBCAM_CONFIG['width'])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WEBCAM_CONFIG['height'])
            self.cap.set(cv2.CAP_PROP_FPS, WEBCAM_CONFIG['fps'])

            self.running = True
            self.start()
            return True
        except Exception as e:
            self.error_occurred.emit(f"Error starting webcam: {str(e)}")
            return False

    def stop_capture(self):
        """Stop webcam capture"""
        self.running = False
        if self.cap:
            self.cap.release()
        self.wait()

    def run(self):
        """Main capture loop"""
        while self.running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                self.error_occurred.emit("Failed to read from webcam")
                break

            # Flip frame horizontally for mirror effect (if enabled)
            if WEBCAM_CONFIG['flip_horizontal']:
                frame = cv2.flip(frame, 1)

            # Convert BGR to RGB for MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Process with MediaPipe
            results = self.hands.process(rgb_frame)

            # Extract hand landmarks
            hand_landmarks = []
            if results.multi_hand_landmarks:
                for hand_landmark in results.multi_hand_landmarks:
                    # Convert landmarks to list of (x, y) coordinates
                    landmarks = []
                    for lm in hand_landmark.landmark:
                        landmarks.append((lm.x, lm.y, lm.z))
                    hand_landmarks.append(landmarks)

                    # GFLOW-19: Draw landmarks on frame (toggleable)
                    if VISUAL_FEEDBACK_CONFIG['show_hand_landmarks']:
                        # Use configured colors and thickness
                        landmark_spec = self.mp_drawing.DrawingSpec(
                            color=VISUAL_FEEDBACK_CONFIG['landmark_color'],
                            thickness=VISUAL_FEEDBACK_CONFIG['landmark_thickness']
                        )
                        connection_spec = self.mp_drawing.DrawingSpec(
                            color=VISUAL_FEEDBACK_CONFIG['connection_color'],
                            thickness=VISUAL_FEEDBACK_CONFIG['connection_thickness']
                        )

                        self.mp_drawing.draw_landmarks(
                            frame, hand_landmark, self.mp_hands.HAND_CONNECTIONS,
                            landmark_spec, connection_spec
                        )

            # Store current landmarks for custom gesture recording
            self.current_landmarks = results.multi_hand_landmarks if results.multi_hand_landmarks else []

            # Calculate FPS
            self.fps_counter += 1
            fps_interval = PERFORMANCE_CONFIG['fps_update_interval']
            if self.fps_counter % fps_interval == 0:  # Update FPS every N frames
                current_time = time.time()
                fps = fps_interval / (current_time - self.fps_start_time)
                self.fps_update.emit(fps)
                self.fps_start_time = current_time

            # Emit frame and landmarks
            self.frame_ready.emit(frame, hand_landmarks)

            # Small delay to prevent overwhelming the UI
            self.msleep(33)  # ~30 FPS


class GestureRecognizer:
    """
    GFLOW-3 & GFLOW-8: Pre-defined and Custom Static Gesture Recognizer
    Implements rule-based recognition for basic static gestures and ML-based custom gestures
    """

    def __init__(self, custom_gesture_manager=None):
        self.gesture_names = {k: v['name'] for k, v in PREDEFINED_GESTURES.items()}

        # Initialize custom gesture manager (GFLOW-8)
        # GFLOW-18: Accept profile-aware custom gesture manager
        self.custom_gesture_manager = custom_gesture_manager or CustomGestureManager()

    def recognize_gesture(self, landmarks: List[Tuple[float, float, float]]) -> Tuple[Optional[str], str]:
        """
        Recognize static gesture from hand landmarks
        Returns tuple of (gesture_name, gesture_type) where gesture_type is 'predefined' or 'custom'
        """
        if not landmarks or len(landmarks) != 21:
            return None, ""

        try:
            # Check both custom and predefined gestures, then choose the best match
            best_gesture = None
            best_confidence = 0.0
            best_type = ""

            # Check custom gestures (GFLOW-8)
            # Convert landmarks to MediaPipe format for custom gesture recognition
            mp_landmarks = type('HandLandmarks', (), {})()
            mp_landmarks.landmark = []
            for x, y, z in landmarks:
                landmark = type('Landmark', (), {})()
                landmark.x, landmark.y, landmark.z = x, y, z
                mp_landmarks.landmark.append(landmark)

            custom_gesture, custom_confidence = self.custom_gesture_manager.recognize_gesture(mp_landmarks)
            if custom_gesture and custom_confidence >= CUSTOM_GESTURE_CONFIG['min_confidence_threshold']:
                best_gesture = custom_gesture
                best_confidence = custom_confidence
                best_type = 'custom'

            # Check predefined gestures with confidence scoring
            predefined_results = []

            # Check for Open Palm
            if self._is_open_palm(landmarks):
                predefined_results.append(('open_palm', 'predefined', 0.95))  # High confidence for rule-based

            # Check for Thumbs Up
            if self._is_thumbs_up(landmarks):
                predefined_results.append(('thumbs_up', 'predefined', 0.95))

            # Check for Fist
            if self._is_fist(landmarks):
                predefined_results.append(('fist', 'predefined', 0.95))

            # Check for Peace Sign
            if self._is_peace_sign(landmarks):
                predefined_results.append(('peace_sign', 'predefined', 0.95))

            # Check for Pointing
            if self._is_pointing(landmarks):
                predefined_results.append(('pointing', 'predefined', 0.95))

            # Apply priority system: prefer predefined gestures when confidence is close
            for gesture_id, gesture_type, confidence in predefined_results:
                # Apply confidence boost to predefined gestures if priority system is enabled
                if CUSTOM_GESTURE_CONFIG['enable_gesture_priority']:
                    effective_confidence = min(1.0, confidence + CUSTOM_GESTURE_CONFIG['predefined_confidence_boost'])
                else:
                    effective_confidence = confidence

                if effective_confidence > best_confidence:
                    best_gesture = gesture_id
                    best_confidence = effective_confidence
                    best_type = gesture_type

            # Return the best match if confidence is sufficient
            if best_gesture and best_confidence >= CUSTOM_GESTURE_CONFIG['min_confidence_threshold']:
                return best_gesture, best_type

        except Exception as e:
            print(f"Error in gesture recognition: {e}")

        return None, ""

    def _is_open_palm(self, landmarks) -> bool:
        """Check if hand shows open palm gesture"""
        # All fingertips should be extended (above their PIP joints)
        fingers_extended = [
            landmarks[8][1] < landmarks[6][1],   # Index
            landmarks[12][1] < landmarks[10][1], # Middle
            landmarks[16][1] < landmarks[14][1], # Ring
            landmarks[20][1] < landmarks[18][1]  # Pinky
        ]

        # Thumb extended - check if thumb tip is away from palm center
        wrist = landmarks[0]
        thumb_tip = landmarks[4]
        middle_mcp = landmarks[9]  # Middle finger MCP (palm center reference)

        # Thumb should be extended away from palm center
        thumb_extended = abs(thumb_tip[0] - middle_mcp[0]) > 0.08

        return all(fingers_extended) and thumb_extended

    def _is_fist(self, landmarks) -> bool:
        """Check if hand shows fist gesture"""
        # All fingertips should be below their PIP joints
        fingers_folded = [
            landmarks[8][1] > landmarks[6][1],   # Index
            landmarks[12][1] > landmarks[10][1], # Middle
            landmarks[16][1] > landmarks[14][1], # Ring
            landmarks[20][1] > landmarks[18][1]  # Pinky
        ]
        return all(fingers_folded)

    def _is_peace_sign(self, landmarks) -> bool:
        """Check if hand shows peace sign (V) gesture"""
        # Index and middle fingers extended, others folded
        index_extended = landmarks[8][1] < landmarks[6][1]
        middle_extended = landmarks[12][1] < landmarks[10][1]
        ring_folded = landmarks[16][1] > landmarks[14][1]
        pinky_folded = landmarks[20][1] > landmarks[18][1]

        return index_extended and middle_extended and ring_folded and pinky_folded

    def _is_thumbs_up(self, landmarks) -> bool:
        """Check if hand shows thumbs up gesture"""
        wrist = landmarks[0]
        thumb_tip = landmarks[4]
        thumb_mcp = landmarks[2]  # Thumb MCP joint

        # Other finger landmarks
        index_tip, index_pip = landmarks[8], landmarks[6]
        middle_tip, middle_pip = landmarks[12], landmarks[10]
        ring_tip, ring_pip = landmarks[16], landmarks[14]
        pinky_tip, pinky_pip = landmarks[20], landmarks[18]

        # 1. Thumb should be extended upward (significantly above wrist)
        thumb_up = thumb_tip[1] < wrist[1] - 0.03  # Reduced threshold for easier detection

        # 2. Thumb should be extended (tip away from MCP)
        thumb_extended = abs(thumb_tip[1] - thumb_mcp[1]) > 0.05  # Reduced threshold

        # 3. Other fingers should be folded (tips below PIP joints)
        # Allow some tolerance - at least 3 out of 4 fingers should be folded
        fingers_folded = [
            index_tip[1] > index_pip[1],
            middle_tip[1] > middle_pip[1],
            ring_tip[1] > ring_pip[1],
            pinky_tip[1] > pinky_pip[1]
        ]
        fingers_mostly_folded = sum(fingers_folded) >= 3

        # 4. Thumb should be the highest point (or close to it)
        thumb_highest = thumb_tip[1] <= min(index_tip[1], middle_tip[1], ring_tip[1], pinky_tip[1]) + 0.02

        # 5. Thumb should be separated horizontally from other fingers
        avg_finger_x = (index_tip[0] + middle_tip[0] + ring_tip[0] + pinky_tip[0]) / 4
        thumb_separated = abs(thumb_tip[0] - avg_finger_x) > 0.04  # Further reduced threshold

        # Debug output if enabled
        if GESTURE_CONFIG['debug_mode']:
            print(f"Thumbs Up Debug:")
            print(f"  thumb_up: {thumb_up} (thumb_tip_y: {thumb_tip[1]:.3f}, wrist_y: {wrist[1]:.3f})")
            print(f"  thumb_extended: {thumb_extended} (distance: {abs(thumb_tip[1] - thumb_mcp[1]):.3f})")
            print(f"  fingers_folded: {fingers_mostly_folded} {fingers_folded} (count: {sum(fingers_folded)}/4)")
            print(f"  thumb_highest: {thumb_highest}")
            print(f"  thumb_separated: {thumb_separated} (distance: {abs(thumb_tip[0] - avg_finger_x):.3f})")

        return thumb_up and thumb_extended and fingers_mostly_folded and thumb_highest and thumb_separated

    def _is_pointing(self, landmarks) -> bool:
        """Check if hand shows pointing gesture"""
        # Only index finger extended
        index_extended = landmarks[8][1] < landmarks[6][1]
        other_fingers_folded = [
            landmarks[12][1] > landmarks[10][1], # Middle
            landmarks[16][1] > landmarks[14][1], # Ring
            landmarks[20][1] > landmarks[18][1]  # Pinky
        ]
        return index_extended and all(other_fingers_folded)


class MainWindow(QMainWindow):
    """
    Main application window implementing GFLOW-1 through GFLOW-4
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle(UI_CONFIG['window_title'])
        self.setGeometry(100, 100, UI_CONFIG['window_width'], UI_CONFIG['window_height'])

        # Initialize components
        self.webcam_thread = WebcamThread()

        # GFLOW-18: Initialize profile manager first
        self.profile_manager = ProfileManager()

        # Initialize managers with profile support
        self.action_mapping_manager = ActionMappingManager()

        # Create profile-aware custom gesture manager
        default_profile = self.profile_manager.get_default_profile_name()
        self.custom_gesture_manager = CustomGestureManager(default_profile)

        # Initialize gesture recognizer with profile-aware custom gesture manager
        self.gesture_recognizer = GestureRecognizer(self.custom_gesture_manager)

        # Set up profile manager dependencies
        self.profile_manager.set_managers(
            self.action_mapping_manager,
            self.custom_gesture_manager
        )

        # Load default profile
        if default_profile:
            self.profile_manager.load_profile(default_profile)

        # Load persisted application settings at startup (GFLOW-17)
        try:
            qs = QSettings("GestureFlow", "Settings")
            if qs.contains("settings"):
                settings_str = qs.value("settings")
                if settings_str:
                    saved_settings = json.loads(settings_str)
                    # Apply to runtime configs
                    self.apply_new_settings(saved_settings)
        except Exception as e:
            print(f"Failed to load persisted settings at startup: {e}")

        # Initialize action execution components (GFLOW-E03)
        self.action_executor = ActionExecutor()

        # Setup action execution callbacks
        self.action_executor.on_action_executed = self.on_action_executed
        self.action_executor.on_action_failed = self.on_action_failed

        # Performance tracking (GFLOW-4)
        self.frame_count = 0
        self.recognition_times = []
        self.start_time = time.time()

        # Action execution tracking
        self.last_executed_gesture = None
        self.last_execution_time = 0
        # GFLOW-E04: Mouse control state
        self.mouse_control_active = False
        self.mouse_activation_counter = 0
        self.mouse_deactivation_counter = 0
        self.prev_ref_point: Optional[Tuple[float, float]] = None
        self.prev_delta: Tuple[float, float] = (0.0, 0.0)


        # GFLOW-17: Enhanced recognition control
        self.recognition_enabled = True  # Separate from webcam control

        self.setup_ui()

        # GFLOW-19: Initialize visual feedback system
        self.setup_visual_feedback()

        self.connect_signals()

        # GFLOW-18: Update profile status after UI setup
        self.update_profile_status()

    def setup_ui(self):
        """Setup the user interface"""
        # Create menu bar
        self.create_menu_bar()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)

        # Left panel - Video feed
        left_panel = QVBoxLayout()

        # Video display
        self.video_label = QLabel()
        self.video_label.setMinimumSize(UI_CONFIG['video_width'], UI_CONFIG['video_height'])
        self.video_label.setStyleSheet("border: 2px solid gray; background-color: black;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setText("Webcam feed will appear here")
        left_panel.addWidget(self.video_label)

        # Control buttons
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Webcam")
        self.stop_button = QPushButton("Stop Webcam")
        self.stop_button.setEnabled(False)

        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        left_panel.addLayout(button_layout)

        # GFLOW-17: Recognition control buttons
        recognition_layout = QHBoxLayout()
        self.recognition_toggle_button = QPushButton("Disable Recognition")
        self.recognition_toggle_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        recognition_layout.addWidget(self.recognition_toggle_button)
        left_panel.addLayout(recognition_layout)

        # GFLOW-19: Visual feedback controls
        visual_feedback_layout = QHBoxLayout()
        self.landmarks_toggle_button = QPushButton("Hide Landmarks" if VISUAL_FEEDBACK_CONFIG['show_hand_landmarks'] else "Show Landmarks")
        self.landmarks_toggle_button.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        visual_feedback_layout.addWidget(self.landmarks_toggle_button)
        left_panel.addLayout(visual_feedback_layout)

        # Right panel - Information and status
        right_widget = QWidget()
        right_widget.setMaximumWidth(350)
        right_panel = QVBoxLayout(right_widget)

        # Status section
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Box)
        status_layout = QVBoxLayout(status_frame)

        status_title = QLabel("System Status")
        status_title.setFont(QFont("Arial", 12, QFont.Bold))
        status_layout.addWidget(status_title)

        self.status_label = QLabel("Ready to start")
        self.fps_label = QLabel("FPS: --")
        self.hands_label = QLabel("Hands detected: 0")
        # GFLOW-17: Enhanced status indicators
        self.recognition_status_label = QLabel("Recognition: Enabled")
        self.recognition_status_label.setStyleSheet("color: green; font-weight: bold;")

        # GFLOW-18: Profile status indicator
        self.profile_status_label = QLabel("Profile: Loading...")
        self.profile_status_label.setStyleSheet("color: #3498db; font-weight: bold;")

        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.fps_label)
        status_layout.addWidget(self.hands_label)
        status_layout.addWidget(self.recognition_status_label)
        status_layout.addWidget(self.profile_status_label)

        right_panel.addWidget(status_frame)

        # Gesture recognition section
        gesture_frame = QFrame()
        gesture_frame.setFrameStyle(QFrame.Box)
        gesture_layout = QVBoxLayout(gesture_frame)

        gesture_title = QLabel("Gesture Recognition")
        gesture_title.setFont(QFont("Arial", 12, QFont.Bold))
        gesture_layout.addWidget(gesture_title)

        self.gesture_label = QLabel("No gesture detected")
        self.gesture_label.setFont(QFont("Arial", 14))
        self.gesture_label.setStyleSheet("color: blue; font-weight: bold;")
        gesture_layout.addWidget(self.gesture_label)

        # Supported gestures list
        supported_label = QLabel("Supported Gestures:")
        supported_label.setFont(QFont("Arial", 10, QFont.Bold))
        gesture_layout.addWidget(supported_label)

        gestures_text = QTextEdit()
        gestures_text.setMaximumHeight(120)
        gestures_text.setReadOnly(True)

        # Build gesture list from configuration
        gesture_list = []
        for gesture_id, gesture_info in PREDEFINED_GESTURES.items():
            if gesture_info['enabled']:
                gesture_list.append(f"• {gesture_info['name']} - {gesture_info['description']}")
        gestures_text.setText("\n".join(gesture_list))
        gesture_layout.addWidget(gestures_text)

        right_panel.addWidget(gesture_frame)

        # Performance metrics section (GFLOW-4)
        perf_frame = QFrame()
        perf_frame.setFrameStyle(QFrame.Box)
        perf_layout = QVBoxLayout(perf_frame)

        perf_title = QLabel("Performance Metrics")
        perf_title.setFont(QFont("Arial", 12, QFont.Bold))
        perf_layout.addWidget(perf_title)

        self.perf_label = QLabel("Recognition latency: -- ms\nFrames processed: 0")
        perf_layout.addWidget(self.perf_label)

        right_panel.addWidget(perf_frame)

        # Add panels to main layout
        main_layout.addLayout(left_panel, 2)
        main_layout.addWidget(right_widget, 1)

    def setup_visual_feedback(self):
        """GFLOW-19: Setup visual feedback system"""
        # Create notification widget as overlay on video area
        self.notification_widget = NotificationWidget(self.video_label)

        # Create notification manager
        self.notification_manager = GestureNotificationManager(self.notification_widget)

        # Position notification widget initially (will be repositioned when shown)
        self.notification_widget.hide()

    def create_menu_bar(self):
        """Create menu bar with custom gesture options"""
        menubar = self.menuBar()

        # Gestures menu
        gestures_menu = menubar.addMenu('Gestures')

        # Record new gesture action
        record_action = gestures_menu.addAction('Record New Gesture...')
        record_action.setShortcut('Ctrl+R')
        record_action.triggered.connect(self.open_recording_dialog)

        # Manage gestures action
        manage_action = gestures_menu.addAction('Manage Gestures...')
        manage_action.setShortcut('Ctrl+M')
        manage_action.triggered.connect(self.open_management_dialog)

        gestures_menu.addSeparator()

        # Refresh gestures action
        refresh_action = gestures_menu.addAction('Refresh Gestures')
        refresh_action.setShortcut('F5')
        refresh_action.triggered.connect(self.refresh_gestures)

        # Actions menu (GFLOW-E03)
        actions_menu = menubar.addMenu('Actions')

        # Gesture-to-Action mapping
        mapping_action = actions_menu.addAction('Gesture-to-Action Mapping...')
        mapping_action.setShortcut('Ctrl+A')
        mapping_action.triggered.connect(self.open_action_mapping_dialog)

        actions_menu.addSeparator()

        # Emergency stop
        emergency_stop_action = actions_menu.addAction('Emergency Stop')
        emergency_stop_action.setShortcut('Ctrl+E')
        emergency_stop_action.triggered.connect(self.emergency_stop_actions)

        # Resume actions
        resume_action = actions_menu.addAction('Resume Actions')
        resume_action.triggered.connect(self.resume_actions)

        # GFLOW-17: Settings menu
        settings_menu = menubar.addMenu('Settings')

        # Application settings
        settings_action = settings_menu.addAction('Application Settings...')
        settings_action.setShortcut('Ctrl+,')
        settings_action.triggered.connect(self.open_settings_dialog)

        settings_menu.addSeparator()

        # Export/Import settings
        export_action = settings_menu.addAction('Export Settings...')
        export_action.triggered.connect(self.export_settings)

        import_action = settings_menu.addAction('Import Settings...')
        import_action.triggered.connect(self.import_settings)

        # GFLOW-18: Profiles menu
        profiles_menu = menubar.addMenu('Profiles')

        # Manage profiles
        manage_profiles_action = profiles_menu.addAction('Manage Profiles...')
        manage_profiles_action.setShortcut('Ctrl+P')
        manage_profiles_action.triggered.connect(self.open_profile_management_dialog)

        profiles_menu.addSeparator()

        # Quick profile switching (will be populated dynamically)
        self.profiles_submenu = profiles_menu.addMenu('Switch Profile')
        self.update_profiles_menu()

    def open_recording_dialog(self):
        """Open the gesture recording dialog"""
        if not self.webcam_thread.running:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Webcam Required",
                "Please start the webcam before recording gestures."
            )
            return

        dialog = GestureRecordingDialog(
            self.custom_gesture_manager,
            self.webcam_thread,
            self
        )
        dialog.exec()

        # Refresh gesture list after recording
        self.refresh_gestures()

    def open_management_dialog(self):
        """Open the gesture management dialog"""
        dialog = GestureManagementDialog(
            self.custom_gesture_manager,
            self
        )
        dialog.exec()

        # Refresh gesture list after management
        self.refresh_gestures()

    def open_profile_management_dialog(self):
        """GFLOW-18: Open the profile management dialog"""
        dialog = ProfileManagementDialog(self.profile_manager, self)
        dialog.profile_changed.connect(self.on_profile_changed)
        dialog.exec()

        # Update profile status and menu
        self.update_profile_status()
        self.update_profiles_menu()

    def on_profile_changed(self, profile_name: str):
        """Handle profile change"""
        # Refresh gesture recognizer with new profile data
        self.refresh_gestures()

        # Update UI
        self.update_profile_status()
        self.update_profiles_menu()

        print(f"Profile changed to: {profile_name}")

    def update_profile_status(self):
        """Update the profile status display"""
        current_profile = self.profile_manager.get_current_profile()
        if current_profile:
            status_text = f"Profile: {current_profile.name}"
            if current_profile.is_default:
                status_text += " (Default)"
            self.profile_status_label.setText(status_text)
        else:
            self.profile_status_label.setText("Profile: None")

    def update_profiles_menu(self):
        """Update the profiles submenu with available profiles"""
        # Clear existing actions
        self.profiles_submenu.clear()

        # Add profile switching actions
        profiles = self.profile_manager.get_all_profiles()
        current_profile_name = self.profile_manager.get_current_profile_name()

        for profile in profiles:
            action = self.profiles_submenu.addAction(profile.name)

            # Mark current profile
            if profile.name == current_profile_name:
                action.setText(f"✓ {profile.name}")
                action.setEnabled(False)

            # Connect to profile switching
            action.triggered.connect(lambda checked, name=profile.name: self.switch_to_profile(name))

    def switch_to_profile(self, profile_name: str):
        """Switch to a different profile"""
        if self.profile_manager.load_profile(profile_name):
            self.on_profile_changed(profile_name)

            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Profile Switched",
                f"Switched to profile: {profile_name}"
            )
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self, "Error",
                f"Failed to switch to profile: {profile_name}"
            )

    def toggle_recognition(self):
        """GFLOW-17: Toggle gesture recognition on/off"""
        self.recognition_enabled = not self.recognition_enabled

        if self.recognition_enabled:
            self.recognition_toggle_button.setText("Disable Recognition")
            self.recognition_toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
            """)
            self.recognition_status_label.setText("Recognition: Enabled")
            self.recognition_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.recognition_toggle_button.setText("Enable Recognition")
            self.recognition_toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #229954;
                }
            """)
            self.recognition_status_label.setText("Recognition: Disabled")
            self.recognition_status_label.setStyleSheet("color: red; font-weight: bold;")

            # Clear gesture display when disabled
            self.gesture_label.setText("Recognition disabled")
            self.gesture_label.setStyleSheet("color: gray; font-weight: bold;")

    def toggle_landmarks(self):
        """GFLOW-19: Toggle hand landmarks display"""
        current_state = VISUAL_FEEDBACK_CONFIG['show_hand_landmarks']
        VISUAL_FEEDBACK_CONFIG['show_hand_landmarks'] = not current_state

        # Update button text and style
        if VISUAL_FEEDBACK_CONFIG['show_hand_landmarks']:
            self.landmarks_toggle_button.setText("Hide Landmarks")
            self.landmarks_toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
            """)
        else:
            self.landmarks_toggle_button.setText("Show Landmarks")
            self.landmarks_toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: #2ecc71;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #27ae60;
                }
            """)

    def open_settings_dialog(self):
        """GFLOW-17: Open the settings dialog"""
        dialog = SettingsDialog(self, profile_manager=self.profile_manager, custom_gesture_manager=self.custom_gesture_manager)
        dialog.settings_changed.connect(self.apply_new_settings)

        # Keep a reference to prevent garbage collection
        self._settings_dialog = dialog

        # Connect finished signal to clean up reference
        dialog.finished.connect(lambda: setattr(self, '_settings_dialog', None))

        dialog.exec()

    def apply_new_settings(self, settings: dict):
        """Apply new settings from settings dialog"""
        try:
            # Update global configuration (this would ideally update the config module)
            # For now, we'll store the settings and apply what we can immediately

            # Update UI elements that can be changed immediately
            if 'ui' in settings:
                ui_settings = settings['ui']
                if ui_settings.get('window_title') != UI_CONFIG['window_title']:
                    self.setWindowTitle(ui_settings['window_title'])
                    UI_CONFIG['window_title'] = ui_settings['window_title']

            # Update webcam settings (requires restart of webcam)
            if 'webcam' in settings and self.webcam_thread.running:
                from PySide6.QtWidgets import QMessageBox
                reply = QMessageBox.question(
                    self, "Restart Webcam",
                    "Webcam settings have changed. Restart webcam to apply changes?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )

                if reply == QMessageBox.Yes:
                    # Update webcam config and restart
                    WEBCAM_CONFIG.update(settings['webcam'])
                    self.stop_webcam()
                    # Small delay before restart
                    QTimer.singleShot(500, self.start_webcam)
                else:
                    # Still update the config for next time
                    WEBCAM_CONFIG.update(settings['webcam'])
            elif 'webcam' in settings:
                # Update webcam config even if not running
                WEBCAM_CONFIG.update(settings['webcam'])

            # Update other configurations safely
            if 'mediapipe' in settings:
                MEDIAPIPE_CONFIG.update(settings['mediapipe'])

            if 'gesture' in settings:
                GESTURE_CONFIG.update(settings['gesture'])

            if 'performance' in settings:
                PERFORMANCE_CONFIG.update(settings['performance'])

            if 'custom_gesture' in settings:
                CUSTOM_GESTURE_CONFIG.update(settings['custom_gesture'])

            if 'action_execution' in settings:
                # Check if ACTION_EXECUTION_CONFIG exists before updating
                try:
                    from config import ACTION_EXECUTION_CONFIG
                    ACTION_EXECUTION_CONFIG.update(settings['action_execution'])
                except (ImportError, NameError) as e:
                    print(f"ACTION_EXECUTION_CONFIG not available, skipping action execution settings: {e}")

            print("Settings applied successfully")
            if 'mouse_control' in settings:
                try:
                    from config import MOUSE_CONTROL_CONFIG
                    MOUSE_CONTROL_CONFIG.update(settings['mouse_control'])
                except (ImportError, NameError) as e:
                    print(f"MOUSE_CONTROL_CONFIG not available, skipping mouse control settings: {e}")

            if 'visual_feedback' in settings:
                try:
                    from config import VISUAL_FEEDBACK_CONFIG
                    VISUAL_FEEDBACK_CONFIG.update(settings['visual_feedback'])
                except (ImportError, NameError) as e:
                    print(f"VISUAL_FEEDBACK_CONFIG not available, skipping visual feedback settings: {e}")

        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self, "Settings Error",
                f"Failed to apply some settings: {str(e)}\n\nDetails: {type(e).__name__}"
            )

    def export_settings(self):
        """Export current settings to file"""
        try:
            from PySide6.QtWidgets import QFileDialog
            import json

            filename, _ = QFileDialog.getSaveFileName(
                self, "Export Settings",
                "gestureflow_settings.json",
                "JSON Files (*.json)"
            )

            if filename:
                settings = {
                    'webcam': WEBCAM_CONFIG,
                    'mediapipe': MEDIAPIPE_CONFIG,
                    'gesture': GESTURE_CONFIG,
                    'performance': PERFORMANCE_CONFIG,
                    'ui': UI_CONFIG,
                    'custom_gesture': CUSTOM_GESTURE_CONFIG,
                }

                # Add action execution config if available
                try:
                    settings['action_execution'] = ACTION_EXECUTION_CONFIG
                except NameError:
                    print("ACTION_EXECUTION_CONFIG not available for export")

                with open(filename, 'w') as f:
                    json.dump(settings, f, indent=2)

                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self, "Export Complete",
                    f"Settings exported to {filename}"
                )

        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self, "Export Error",
                f"Failed to export settings: {str(e)}"
            )

    def import_settings(self):
        """Import settings from file"""
        try:
            from PySide6.QtWidgets import QFileDialog, QMessageBox
            import json

            filename, _ = QFileDialog.getOpenFileName(
                self, "Import Settings",
                "",
                "JSON Files (*.json)"
            )

            if filename:
                with open(filename, 'r') as f:
                    settings = json.load(f)

                # Apply imported settings
                self.apply_new_settings(settings)

                QMessageBox.information(
                    self, "Import Complete",
                    f"Settings imported from {filename}"
                )

        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self, "Import Error",
                f"Failed to import settings: {str(e)}"
            )

    def refresh_gestures(self):
        """Refresh the custom gesture models"""
        # Reload all gestures in the custom gesture manager
        self.custom_gesture_manager.load_all_gestures()

    def connect_signals(self):
        """Connect UI signals"""
        self.start_button.clicked.connect(self.start_webcam)
        self.stop_button.clicked.connect(self.stop_webcam)

        # GFLOW-17: Recognition toggle connection
        self.recognition_toggle_button.clicked.connect(self.toggle_recognition)

        # GFLOW-19: Visual feedback connections
        self.landmarks_toggle_button.clicked.connect(self.toggle_landmarks)

        # Webcam thread signals
        self.webcam_thread.frame_ready.connect(self.update_frame)
        self.webcam_thread.error_occurred.connect(self.handle_error)
        self.webcam_thread.fps_update.connect(self.update_fps)

    def start_webcam(self):
        """Start webcam capture"""
        if self.webcam_thread.start_capture():
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.status_label.setText("Webcam active")
            self.start_time = time.time()
            self.frame_count = 0

    def stop_webcam(self):
        """Stop webcam capture"""
        self.webcam_thread.stop_capture()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("Webcam stopped")
        self.video_label.setText("Webcam feed will appear here")
        self.gesture_label.setText("No gesture detected")

    def update_frame(self, frame: np.ndarray, hand_landmarks: List):
        """Update video frame and process gestures"""
        # Convert frame to Qt format and display
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)

        # Scale image to fit label
        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.video_label.setPixmap(scaled_pixmap)

        # Update hands detected count
        self.hands_label.setText(f"Hands detected: {len(hand_landmarks)}")

        # Process gesture recognition (GFLOW-17: Check if recognition is enabled)
        if hand_landmarks and self.recognition_enabled:
            start_recognition = time.time()

            # Process first detected hand
            gesture, gesture_type = self.gesture_recognizer.recognize_gesture(hand_landmarks[0])

            recognition_time = (time.time() - start_recognition) * 1000  # Convert to ms
            self.recognition_times.append(recognition_time)

            # GFLOW-E04: Dynamic mouse control while holding a gesture (process every frame)
            self._process_mouse_control(hand_landmarks[0], gesture, gesture_type)

            if gesture:
                if gesture_type == 'predefined':
                    gesture_name = self.gesture_recognizer.gesture_names.get(gesture, gesture)
                    self.gesture_label.setText(f"Detected: {gesture_name}")
                    self.gesture_label.setStyleSheet("color: green; font-weight: bold;")
                elif gesture_type == 'custom':
                    self.gesture_label.setText(f"Custom: {gesture}")
                    self.gesture_label.setStyleSheet("color: purple; font-weight: bold;")

                # Execute action if mapped (GFLOW-E03)
                self.execute_gesture_action(gesture, gesture_type)
            else:
                self.gesture_label.setText("Hand detected - No gesture")
                self.gesture_label.setStyleSheet("color: orange; font-weight: bold;")
        elif hand_landmarks and not self.recognition_enabled:
            # Show that hands are detected but recognition is disabled
            self.gesture_label.setText("Hand detected - Recognition disabled")
            self.gesture_label.setStyleSheet("color: gray; font-weight: bold;")
        else:
            if self.recognition_enabled:
                self.gesture_label.setText("No gesture detected")
                self.gesture_label.setStyleSheet("color: blue; font-weight: bold;")
            else:
                self.gesture_label.setText("Recognition disabled")
                self.gesture_label.setStyleSheet("color: gray; font-weight: bold;")

        # Update performance metrics (GFLOW-4)
        self.frame_count += 1
        if self.recognition_times:
            # Keep only recent recognition times
            max_history = PERFORMANCE_CONFIG['max_recognition_history']
            if len(self.recognition_times) > max_history:
                self.recognition_times = self.recognition_times[-max_history:]

            # Calculate average latency from recent measurements
            recent_times = self.recognition_times[-30:] if len(self.recognition_times) >= 30 else self.recognition_times
            avg_latency = sum(recent_times) / len(recent_times)

            self.perf_label.setText(
                f"Recognition latency: {avg_latency:.1f} ms\n"
                f"Frames processed: {self.frame_count}"
            )

    def _process_mouse_control(self, landmarks: List[Tuple[float, float, float]], detected_gesture: Optional[str], detected_type: str):
        """While the configured gesture is held, move the OS mouse cursor following hand movement.
        Uses chosen landmark and applies deadzone, sensitivity, and smoothing.
        """
        try:
            cfg = MOUSE_CONTROL_CONFIG
            if not cfg.get('enabled', True):
                # Reset state
                self.mouse_control_active = False
                self.mouse_activation_counter = 0
                self.prev_ref_point = None
                self.prev_delta = (0.0, 0.0)
                return

            # Check if current detection matches configured activation gesture
            match = (detected_gesture == cfg.get('gesture_name') and
                     detected_type == cfg.get('gesture_type'))

            if match:
                self.mouse_activation_counter += 1
                self.mouse_deactivation_counter = 0
            else:
                self.mouse_deactivation_counter += 1
                self.mouse_activation_counter = 0

            # Update active state with hysteresis
            if not self.mouse_control_active and self.mouse_activation_counter >= cfg.get('activation_frames', 3):
                self.mouse_control_active = True
                # Reset reference when activating to avoid jump
                self.prev_ref_point = None
                self.prev_delta = (0.0, 0.0)
            elif self.mouse_control_active and self.mouse_deactivation_counter >= cfg.get('deactivation_frames', 2):
                self.mouse_control_active = False
                self.prev_ref_point = None
                self.prev_delta = (0.0, 0.0)

            if not self.mouse_control_active:
                return

            # Pick reference landmark (normalized coords in [0,1])
            idx_map = {
                'wrist': 0,
                'index_tip': 8
            }
            lm_index = idx_map.get(cfg.get('landmark', 'index_tip'), 8)
            if lm_index < 0 or lm_index >= len(landmarks):
                return
            ref_x, ref_y, _ = landmarks[lm_index]

            # Convert normalized movement to pixel delta relative to previous point
            # Use video widget size as movement reference, then let ActionExecutor clamp to screen
            video_w = self.video_label.width()
            video_h = self.video_label.height()
            cur_px = (ref_x * video_w, ref_y * video_h)

            if self.prev_ref_point is None:
                self.prev_ref_point = cur_px
                return

            dx = cur_px[0] - self.prev_ref_point[0]
            dy = cur_px[1] - self.prev_ref_point[1]

            # Invert axes if configured
            if cfg.get('invert_x', False):
                dx = -dx
            if cfg.get('invert_y', False):
                dy = -dy

            # Apply deadzone (Euclidean radius)
            dead = float(cfg.get('deadzone_pixels', 3))
            if math.hypot(dx, dy) < dead:
                dx, dy = 0.0, 0.0

            # Sensitivity gain
            gain = float(cfg.get('sensitivity', 1.5))
            dx *= gain
            dy *= gain

            # Smoothing via exponential moving average on delta
            alpha = float(cfg.get('smoothing', 0.5))  # 0=no smoothing, 1=heavy
            if alpha > 0.0:
                smoothed_dx = (1 - alpha) * dx + alpha * self.prev_delta[0]
                smoothed_dy = (1 - alpha) * dy + alpha * self.prev_delta[1]
            else:
                smoothed_dx, smoothed_dy = dx, dy

            self.prev_delta = (smoothed_dx, smoothed_dy)
            self.prev_ref_point = cur_px

            # Apply movement via action executor immediate utility (no queue)
            self.action_executor.move_cursor_relative(smoothed_dx, smoothed_dy)
        except Exception as e:
            # Avoid crashing the UI loop due to unexpected errors
            print(f"Mouse control error: {e}")

    def update_fps(self, fps: float):
        """Update FPS display"""
        self.fps_label.setText(f"FPS: {fps:.1f}")

    def handle_error(self, error_message: str):
        """Handle errors from webcam thread"""
        self.status_label.setText(f"Error: {error_message}")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def open_action_mapping_dialog(self):
        """Open the action mapping dialog"""
        dialog = ActionMappingDialog(
            self.action_mapping_manager,
            self.custom_gesture_manager,
            self.profile_manager,  # GFLOW-18: Pass unified profile manager
            self
        )
        dialog.exec()

    def emergency_stop_actions(self):
        """Emergency stop all action execution"""
        self.action_executor.emergency_stop_all()
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Emergency Stop",
            "All action execution has been stopped.\nUse 'Resume Actions' to continue."
        )

    def resume_actions(self):
        """Resume action execution"""
        self.action_executor.resume_execution()
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Actions Resumed",
            "Action execution has been resumed."
        )

    def execute_gesture_action(self, gesture: str, gesture_type: str):
        """Execute action mapped to a gesture"""
        try:
            # Prevent rapid repeated execution of the same gesture
            current_time = time.time()
            if (self.last_executed_gesture == gesture and
                current_time - self.last_execution_time < 1.0):  # 1 second cooldown
                return

            # Get mapping for the gesture
            mapping = self.action_mapping_manager.get_mapping_for_gesture(gesture, gesture_type)
            if not mapping or not mapping.enabled:
                return

            # Record usage
            self.action_mapping_manager.record_action_usage(mapping.id)

            # GFLOW-19: Show gesture recognition notification
            if hasattr(self, 'notification_manager'):
                action_description = f"{mapping.action.type.value}.{mapping.action.subtype}"
                self.notification_manager.show_gesture_recognized(gesture, gesture_type, action_description)

            # Execute action asynchronously
            future = self.action_executor.execute_action(mapping.action)

            # Update tracking
            self.last_executed_gesture = gesture
            self.last_execution_time = current_time

        except Exception as e:
            print(f"Error executing gesture action: {e}")

    def on_action_executed(self, action, result):
        """Callback for successful action execution"""
        print(f"Action executed successfully: {action.type.value}.{action.subtype}")

        # GFLOW-19: Show visual notification
        if hasattr(self, 'notification_manager'):
            action_description = f"{action.type.value}.{action.subtype}"
            self.notification_manager.show_action_executed(action_description, success=True)

    def on_action_failed(self, action, result):
        """Callback for failed action execution"""
        print(f"Action execution failed: {action.type.value}.{action.subtype} - {result.message}")

        # GFLOW-19: Show visual notification for failure
        if hasattr(self, 'notification_manager'):
            action_description = f"{action.type.value}.{action.subtype}"
            self.notification_manager.show_action_executed(f"{action_description} (Failed)", success=False)

    def closeEvent(self, event):
        """Handle application close"""
        # Shutdown action execution components
        if hasattr(self, 'action_executor'):
            self.action_executor.shutdown()

        # Save current action mapping profile
        if hasattr(self, 'action_mapping_manager'):
            self.action_mapping_manager.save_current_profile()

        self.webcam_thread.stop_capture()
        event.accept()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("GestureFlow")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("GestureFlow Team")

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
