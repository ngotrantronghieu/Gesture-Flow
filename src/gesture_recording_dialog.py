import sys
import time
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QProgressBar, QTextEdit,
                               QMessageBox, QFrame, QSpacerItem, QSizePolicy)
from PySide6.QtCore import QTimer, Signal, Qt, QThread
from PySide6.QtGui import QFont, QPalette, QColor
from typing import Optional, List
import json
import os
from config import CUSTOM_GESTURE_CONFIG
from custom_gesture_manager import CustomGestureManager

class GestureRecordingWorker(QThread):
    """
    Worker thread for gesture recording to avoid blocking the UI
    """
    sample_recorded = Signal(int)  # sample_number
    recording_complete = Signal(bool, str)  # success, message
    countdown_update = Signal(int)  # countdown_value

    def __init__(self, gesture_manager: CustomGestureManager, gesture_name: str,
                 webcam_thread, target_samples: int, sample_delay: float, countdown_time: int, parent=None):
        super().__init__(parent)
        self.gesture_manager = gesture_manager
        self.gesture_name = gesture_name
        self.webcam_thread = webcam_thread
        self.samples_collected = 0
        self.target_samples = target_samples
        self.sample_delay = sample_delay
        self.countdown_time = countdown_time
        self.is_recording = False
        self.should_stop = False

    def run(self):
        """Main recording loop with enhanced UX"""
        try:
            # Initial countdown
            for i in range(self.countdown_time, 0, -1):
                if self.should_stop:
                    return
                self.countdown_update.emit(i)
                self.msleep(1000)

            self.countdown_update.emit(0)  # Start recording
            self.is_recording = True

            # Collect samples with delays
            while self.samples_collected < self.target_samples and not self.should_stop:
                # Get current hand landmarks from webcam thread
                if hasattr(self.webcam_thread, 'current_landmarks') and self.webcam_thread.current_landmarks:
                    hand_landmarks = self.webcam_thread.current_landmarks[0]  # Use first hand

                    # Add sample to gesture
                    if self.gesture_manager.add_gesture_sample(self.gesture_name, hand_landmarks):
                        self.samples_collected += 1
                        self.sample_recorded.emit(self.samples_collected)

                        # Delay between samples for better UX
                        if self.samples_collected < self.target_samples:
                            self.msleep(int(self.sample_delay * 1000))
                    else:
                        # No hand detected, wait a bit and try again
                        self.msleep(100)
                else:
                    # No hand detected, wait a bit and try again
                    self.msleep(100)

            self.is_recording = False

            if self.samples_collected >= self.target_samples:
                self.recording_complete.emit(True, f"Successfully recorded {self.samples_collected} samples")
            else:
                self.recording_complete.emit(False, "Recording was interrupted")

        except Exception as e:
            self.is_recording = False
            self.recording_complete.emit(False, f"Error during recording: {str(e)}")

    def stop_recording(self):
        """Stop the recording process"""
        self.should_stop = True
        self.is_recording = False


class GestureRecordingDialog(QDialog):
    """
    GFLOW-6: Dialog for recording custom gestures with enhanced UX

    Provides intuitive interface for gesture recording with:
    - Time delays between samples
    - Visual feedback and progress
    - Real-time guidance
    """

    def __init__(self, gesture_manager: CustomGestureManager, webcam_thread, parent=None):
        super().__init__(parent)
        self.gesture_manager = gesture_manager
        self.webcam_thread = webcam_thread
        self.recording_worker = None

        self.setWindowTitle("Record Custom Gesture")
        self.setModal(True)
        self.resize(500, 600)

        self.setup_ui()
        self.setup_connections()
        self.load_user_preferences()

    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Record Custom Gesture")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Gesture name input
        name_frame = QFrame()
        name_layout = QVBoxLayout(name_frame)

        name_label = QLabel("Gesture Name:")
        name_label.setFont(QFont("Arial", 10, QFont.Bold))
        name_layout.addWidget(name_label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter a unique name for your gesture")
        self.name_input.setMaxLength(CUSTOM_GESTURE_CONFIG['max_gesture_name_length'])
        name_layout.addWidget(self.name_input)

        layout.addWidget(name_frame)

        # Description input
        desc_frame = QFrame()
        desc_layout = QVBoxLayout(desc_frame)

        desc_label = QLabel("Description (optional):")
        desc_label.setFont(QFont("Arial", 10, QFont.Bold))
        desc_layout.addWidget(desc_label)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Describe your gesture (optional)")
        self.description_input.setMaximumHeight(80)
        desc_layout.addWidget(self.description_input)

        layout.addWidget(desc_frame)

        # Recording settings
        settings_frame = QFrame()
        settings_frame.setFrameStyle(QFrame.Box)
        settings_layout = QVBoxLayout(settings_frame)

        settings_title = QLabel("Recording Settings:")
        settings_title.setFont(QFont("Arial", 10, QFont.Bold))
        settings_layout.addWidget(settings_title)

        # Number of samples setting
        samples_layout = QHBoxLayout()
        samples_label = QLabel("Number of samples:")
        samples_layout.addWidget(samples_label)

        from PySide6.QtWidgets import QSpinBox
        self.samples_spinbox = QSpinBox()
        self.samples_spinbox.setMinimum(5)
        self.samples_spinbox.setMaximum(50)
        self.samples_spinbox.setValue(CUSTOM_GESTURE_CONFIG['samples_per_gesture'])
        self.samples_spinbox.setToolTip("Number of gesture samples to record (5-50)")
        samples_layout.addWidget(self.samples_spinbox)

        samples_layout.addStretch()
        settings_layout.addLayout(samples_layout)

        # Delay between samples setting
        delay_layout = QHBoxLayout()
        delay_label = QLabel("Delay between samples:")
        delay_layout.addWidget(delay_label)

        from PySide6.QtWidgets import QDoubleSpinBox
        self.delay_spinbox = QDoubleSpinBox()
        self.delay_spinbox.setMinimum(0.5)
        self.delay_spinbox.setMaximum(5.0)
        self.delay_spinbox.setSingleStep(0.1)
        self.delay_spinbox.setValue(CUSTOM_GESTURE_CONFIG['sample_delay_seconds'])
        self.delay_spinbox.setSuffix(" seconds")
        self.delay_spinbox.setToolTip("Time delay between recording each sample (0.5-5.0 seconds)")
        delay_layout.addWidget(self.delay_spinbox)

        delay_layout.addStretch()
        settings_layout.addLayout(delay_layout)

        # Countdown setting
        countdown_layout = QHBoxLayout()
        countdown_label = QLabel("Countdown before recording:")
        countdown_layout.addWidget(countdown_label)

        self.countdown_spinbox = QSpinBox()
        self.countdown_spinbox.setMinimum(1)
        self.countdown_spinbox.setMaximum(10)
        self.countdown_spinbox.setValue(CUSTOM_GESTURE_CONFIG['recording_countdown'])
        self.countdown_spinbox.setSuffix(" seconds")
        self.countdown_spinbox.setToolTip("Countdown time before recording starts (1-10 seconds)")
        countdown_layout.addWidget(self.countdown_spinbox)

        countdown_layout.addStretch()
        settings_layout.addLayout(countdown_layout)

        # Reset to defaults button
        reset_layout = QHBoxLayout()
        reset_layout.addStretch()

        reset_button = QPushButton("Reset to Defaults")
        reset_button.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 9px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        reset_button.clicked.connect(self.reset_to_defaults)
        reset_layout.addWidget(reset_button)

        settings_layout.addLayout(reset_layout)

        layout.addWidget(settings_frame)

        # Instructions
        instructions_frame = QFrame()
        instructions_frame.setFrameStyle(QFrame.Box)
        instructions_layout = QVBoxLayout(instructions_frame)

        instructions_title = QLabel("Recording Instructions:")
        instructions_title.setFont(QFont("Arial", 10, QFont.Bold))
        instructions_layout.addWidget(instructions_title)

        self.instructions_text = QLabel()
        self.update_instructions_text()  # Set initial text
        self.instructions_text.setWordWrap(True)
        self.instructions_text.setStyleSheet("color: #666; padding: 10px;")
        instructions_layout.addWidget(self.instructions_text)

        layout.addWidget(instructions_frame)

        # Recording status
        self.status_label = QLabel("Ready to record")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.status_label.setStyleSheet("color: #333; padding: 10px;")
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(self.samples_spinbox.value())
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Countdown display
        self.countdown_label = QLabel("")
        self.countdown_label.setAlignment(Qt.AlignCenter)
        countdown_font = QFont("Arial", 24, QFont.Bold)
        self.countdown_label.setFont(countdown_font)
        self.countdown_label.setStyleSheet("color: #e74c3c; padding: 20px;")
        self.countdown_label.setVisible(False)
        layout.addWidget(self.countdown_label)

        # Spacer
        layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Buttons
        button_layout = QHBoxLayout()

        self.record_button = QPushButton("Start Recording")
        self.record_button.setFont(QFont("Arial", 10, QFont.Bold))
        self.record_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        button_layout.addWidget(self.record_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFont(QFont("Arial", 10))
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def setup_connections(self):
        """Setup signal connections"""
        self.record_button.clicked.connect(self.start_recording)
        self.cancel_button.clicked.connect(self.cancel_recording)
        self.name_input.textChanged.connect(self.validate_input)

        # Connect settings changes to update instructions
        self.samples_spinbox.valueChanged.connect(self.update_instructions_text)
        self.delay_spinbox.valueChanged.connect(self.update_instructions_text)
        self.countdown_spinbox.valueChanged.connect(self.update_instructions_text)

        # Update progress bar when samples count changes
        self.samples_spinbox.valueChanged.connect(self.update_progress_bar_maximum)

    def validate_input(self):
        """Validate user input"""
        name = self.name_input.text().strip()
        is_valid = bool(name) and len(name) <= CUSTOM_GESTURE_CONFIG['max_gesture_name_length']

        # Check if gesture name already exists
        if is_valid and name in self.gesture_manager.gestures_metadata:
            is_valid = False
            self.status_label.setText("Gesture name already exists")
            self.status_label.setStyleSheet("color: #e74c3c; padding: 10px;")
        elif is_valid:
            self.status_label.setText("Ready to record")
            self.status_label.setStyleSheet("color: #27ae60; padding: 10px;")
        elif name:
            self.status_label.setText("Invalid gesture name")
            self.status_label.setStyleSheet("color: #e74c3c; padding: 10px;")
        else:
            self.status_label.setText("Enter a gesture name")
            self.status_label.setStyleSheet("color: #333; padding: 10px;")

        self.record_button.setEnabled(is_valid)

    def update_instructions_text(self):
        """Update the instructions text based on current settings"""
        samples = self.samples_spinbox.value()
        delay = self.delay_spinbox.value()
        countdown = self.countdown_spinbox.value()

        instructions = (
            f"• Position your hand clearly in front of the camera\n"
            f"• You'll record {samples} samples of your gesture\n"
            f"• There will be a {countdown}-second countdown before recording starts\n"
            f"• Hold your gesture steady during each sample\n"
            f"• There's a {delay:.1f}-second delay between samples\n"
            f"• Keep your gesture consistent across all samples"
        )

        self.instructions_text.setText(instructions)

    def update_progress_bar_maximum(self):
        """Update progress bar maximum when samples count changes"""
        self.progress_bar.setMaximum(self.samples_spinbox.value())

    def reset_to_defaults(self):
        """Reset all settings to default values"""
        self.samples_spinbox.setValue(CUSTOM_GESTURE_CONFIG['samples_per_gesture'])
        self.delay_spinbox.setValue(CUSTOM_GESTURE_CONFIG['sample_delay_seconds'])
        self.countdown_spinbox.setValue(CUSTOM_GESTURE_CONFIG['recording_countdown'])

    def load_user_preferences(self):
        """Load user preferences from file"""
        prefs_file = os.path.join(CUSTOM_GESTURE_CONFIG['data_directory'], 'recording_preferences.json')

        if os.path.exists(prefs_file):
            try:
                with open(prefs_file, 'r') as f:
                    prefs = json.load(f)

                # Apply preferences if they exist and are valid
                if 'samples_per_gesture' in prefs:
                    samples = prefs['samples_per_gesture']
                    if 5 <= samples <= 50:
                        self.samples_spinbox.setValue(samples)

                if 'sample_delay_seconds' in prefs:
                    delay = prefs['sample_delay_seconds']
                    if 0.5 <= delay <= 5.0:
                        self.delay_spinbox.setValue(delay)

                if 'recording_countdown' in prefs:
                    countdown = prefs['recording_countdown']
                    if 1 <= countdown <= 10:
                        self.countdown_spinbox.setValue(countdown)

            except Exception as e:
                print(f"Error loading user preferences: {e}")

    def save_user_preferences(self):
        """Save current settings as user preferences"""
        prefs = {
            'samples_per_gesture': self.samples_spinbox.value(),
            'sample_delay_seconds': self.delay_spinbox.value(),
            'recording_countdown': self.countdown_spinbox.value()
        }

        prefs_file = os.path.join(CUSTOM_GESTURE_CONFIG['data_directory'], 'recording_preferences.json')

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(prefs_file), exist_ok=True)

            with open(prefs_file, 'w') as f:
                json.dump(prefs, f, indent=2)

        except Exception as e:
            print(f"Error saving user preferences: {e}")

    def start_recording(self):
        """Start the gesture recording process"""
        gesture_name = self.name_input.text().strip()
        description = self.description_input.toPlainText().strip()

        if not gesture_name:
            QMessageBox.warning(self, "Invalid Input", "Please enter a gesture name.")
            return

        if gesture_name in self.gesture_manager.gestures_metadata:
            QMessageBox.warning(self, "Duplicate Name", "A gesture with this name already exists.")
            return

        # Create new gesture
        if not self.gesture_manager.create_new_gesture(gesture_name, description):
            QMessageBox.critical(self, "Error", "Failed to create gesture. Please try again.")
            return

        # Setup UI for recording
        self.record_button.setEnabled(False)
        self.name_input.setEnabled(False)
        self.description_input.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.countdown_label.setVisible(True)

        # Get current settings
        target_samples = self.samples_spinbox.value()
        sample_delay = self.delay_spinbox.value()
        countdown_time = self.countdown_spinbox.value()

        # Update progress bar maximum
        self.progress_bar.setMaximum(target_samples)

        # Start recording worker
        self.recording_worker = GestureRecordingWorker(
            self.gesture_manager, gesture_name, self.webcam_thread,
            target_samples, sample_delay, countdown_time, self
        )
        self.recording_worker.sample_recorded.connect(self.on_sample_recorded)
        self.recording_worker.recording_complete.connect(self.on_recording_complete)
        self.recording_worker.countdown_update.connect(self.on_countdown_update)
        self.recording_worker.start()

        self.status_label.setText("Get ready to record your gesture...")
        self.status_label.setStyleSheet("color: #f39c12; padding: 10px;")

    def cancel_recording(self):
        """Cancel the recording process"""
        if self.recording_worker and self.recording_worker.isRunning():
            reply = QMessageBox.question(
                self, "Cancel Recording",
                "Are you sure you want to cancel the recording?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.recording_worker.stop_recording()
                self.recording_worker.wait()

                # Clean up partial gesture data
                gesture_name = self.name_input.text().strip()
                if gesture_name in self.gesture_manager.gestures_metadata:
                    self.gesture_manager.delete_gesture(gesture_name)

                self.reject()
        else:
            self.reject()

    def on_countdown_update(self, countdown_value: int):
        """Handle countdown updates"""
        if countdown_value > 0:
            self.countdown_label.setText(str(countdown_value))
            self.status_label.setText(f"Recording starts in {countdown_value}...")
        else:
            self.countdown_label.setText("RECORDING")
            self.countdown_label.setStyleSheet("color: #27ae60; padding: 20px;")
            self.status_label.setText("Recording in progress... Hold your gesture steady!")
            self.status_label.setStyleSheet("color: #27ae60; padding: 10px;")

    def on_sample_recorded(self, sample_number: int):
        """Handle sample recorded event"""
        self.progress_bar.setValue(sample_number)
        target_samples = self.samples_spinbox.value()
        remaining = target_samples - sample_number

        if remaining > 0:
            self.status_label.setText(f"Sample {sample_number} recorded! {remaining} more to go...")
        else:
            self.status_label.setText("All samples recorded! Processing...")

    def on_recording_complete(self, success: bool, message: str):
        """Handle recording completion"""
        self.countdown_label.setVisible(False)

        if success:
            self.status_label.setText("Recording completed successfully!")
            self.status_label.setStyleSheet("color: #27ae60; padding: 10px;")

            # Ask if user wants to train the gesture now
            reply = QMessageBox.question(
                self, "Training",
                "Recording completed! Would you like to train the gesture now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                self.train_gesture()
            else:
                QMessageBox.information(
                    self, "Success",
                    "Gesture recorded successfully! You can train it later from the gesture management dialog."
                )
                self.accept()
        else:
            self.status_label.setText(f"Recording failed: {message}")
            self.status_label.setStyleSheet("color: #e74c3c; padding: 10px;")

            # Clean up failed gesture
            gesture_name = self.name_input.text().strip()
            if gesture_name in self.gesture_manager.gestures_metadata:
                self.gesture_manager.delete_gesture(gesture_name)

            QMessageBox.critical(self, "Recording Failed", message)

    def train_gesture(self):
        """Train the recorded gesture"""
        gesture_name = self.name_input.text().strip()

        self.status_label.setText("Training gesture... Please wait.")
        self.status_label.setStyleSheet("color: #f39c12; padding: 10px;")

        # Train the gesture
        success, accuracy = self.gesture_manager.train_gesture(gesture_name)

        if success:
            # Check for similar gestures (GFLOW-10)
            similar_gestures = self.gesture_manager.check_gesture_similarity(gesture_name)

            message = f"Gesture trained successfully!\nAccuracy: {accuracy:.2%}"

            if similar_gestures:
                similar_names = [name for name, similarity in similar_gestures]
                message += f"\n\nWarning: This gesture is similar to: {', '.join(similar_names)}"
                message += "\nThis may cause recognition conflicts."

                reply = QMessageBox.question(
                    self, "Similar Gesture Detected",
                    message + "\n\nDo you want to keep this gesture anyway?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )

                if reply == QMessageBox.No:
                    self.gesture_manager.delete_gesture(gesture_name)
                    self.reject()
                    return

            QMessageBox.information(self, "Training Successful", message)
            self.accept()
        else:
            QMessageBox.critical(
                self, "Training Failed",
                "Failed to train the gesture. The gesture has been deleted."
            )
            self.gesture_manager.delete_gesture(gesture_name)
            self.reject()

    def closeEvent(self, event):
        """Handle dialog close event"""
        if self.recording_worker and self.recording_worker.isRunning():
            self.recording_worker.stop_recording()
            self.recording_worker.wait()

        # Save user preferences
        self.save_user_preferences()

        event.accept()
