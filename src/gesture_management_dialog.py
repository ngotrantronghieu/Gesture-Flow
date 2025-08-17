from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QListWidget, QListWidgetItem,
                               QMessageBox, QFrame, QTextEdit, QSplitter,
                               QWidget, QProgressBar, QSpacerItem, QSizePolicy)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon
from typing import Dict, Any, Optional
from config import CUSTOM_GESTURE_CONFIG
from custom_gesture_manager import CustomGestureManager

class GestureTrainingWorker(QThread):
    """Worker thread for gesture training to avoid blocking the UI"""
    training_complete = Signal(bool, float, str)  # success, accuracy, gesture_name

    def __init__(self, gesture_manager: CustomGestureManager, gesture_name: str, parent=None):
        super().__init__(parent)
        self.gesture_manager = gesture_manager
        self.gesture_name = gesture_name

    def run(self):
        """Train the gesture"""
        try:
            success, accuracy = self.gesture_manager.train_gesture(self.gesture_name)
            self.training_complete.emit(success, accuracy, self.gesture_name)
        except Exception as e:
            print(f"Error training gesture: {e}")
            self.training_complete.emit(False, 0.0, self.gesture_name)


class GestureListItem(QWidget):
    """Custom widget for displaying gesture information in the list"""

    def __init__(self, gesture_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.gesture_data = gesture_data
        self.setup_ui()

    def setup_ui(self):
        """Setup the item UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Gesture name
        name_label = QLabel(self.gesture_data['name'])
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(11)
        name_label.setFont(name_font)
        layout.addWidget(name_label)

        # Status and info
        info_layout = QHBoxLayout()

        # Training status
        if self.gesture_data['is_trained']:
            status_text = f"✓ Trained ({self.gesture_data['training_accuracy']:.1%} accuracy)"
            status_color = "#27ae60"
        else:
            status_text = "⚠ Not trained"
            status_color = "#e74c3c"

        status_label = QLabel(status_text)
        status_label.setStyleSheet(f"color: {status_color}; font-weight: bold;")
        info_layout.addWidget(status_label)

        info_layout.addStretch()

        # Sample count
        sample_label = QLabel(f"{self.gesture_data['sample_count']} samples")
        sample_label.setStyleSheet("color: #666;")
        info_layout.addWidget(sample_label)

        layout.addLayout(info_layout)

        # Description (if available)
        if self.gesture_data.get('description'):
            desc_label = QLabel(self.gesture_data['description'])
            desc_label.setStyleSheet("color: #666; font-style: italic;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)


class GestureManagementDialog(QDialog):
    """
    GFLOW-9: Dialog for managing custom gestures

    Provides interface for viewing, training, and deleting custom gestures.
    """

    def __init__(self, gesture_manager: CustomGestureManager, parent=None):
        super().__init__(parent)
        self.gesture_manager = gesture_manager
        self.training_worker = None

        self.setWindowTitle("Manage Custom Gestures")
        self.setModal(True)
        self.resize(700, 500)

        self.setup_ui()
        self.setup_connections()
        self.refresh_gesture_list()

    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Manage Custom Gestures")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left panel - Gesture list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        list_label = QLabel("Your Custom Gestures:")
        list_label.setFont(QFont("Arial", 10, QFont.Bold))
        left_layout.addWidget(list_label)

        self.gesture_list = QListWidget()
        self.gesture_list.setMinimumWidth(300)
        left_layout.addWidget(self.gesture_list)

        # List buttons
        list_button_layout = QHBoxLayout()

        self.train_button = QPushButton("Train Gesture")
        self.train_button.setEnabled(False)
        self.train_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        list_button_layout.addWidget(self.train_button)

        self.delete_button = QPushButton("Delete Gesture")
        self.delete_button.setEnabled(False)
        self.delete_button.setStyleSheet("""
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
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        list_button_layout.addWidget(self.delete_button)

        left_layout.addLayout(list_button_layout)

        splitter.addWidget(left_panel)

        # Right panel - Gesture details
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        details_label = QLabel("Gesture Details:")
        details_label.setFont(QFont("Arial", 10, QFont.Bold))
        right_layout.addWidget(details_label)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(200)
        right_layout.addWidget(self.details_text)

        # Training progress
        self.training_progress = QProgressBar()
        self.training_progress.setVisible(False)
        right_layout.addWidget(self.training_progress)

        # Statistics
        stats_label = QLabel("Statistics:")
        stats_label.setFont(QFont("Arial", 10, QFont.Bold))
        right_layout.addWidget(stats_label)

        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        right_layout.addWidget(self.stats_text)

        splitter.addWidget(right_panel)

        # Set splitter proportions
        splitter.setSizes([400, 300])

        # Bottom buttons
        button_layout = QHBoxLayout()

        button_layout.addStretch()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        button_layout.addWidget(self.refresh_button)

        self.close_button = QPushButton("Close")
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #34495e;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2c3e50;
            }
        """)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def setup_connections(self):
        """Setup signal connections"""
        self.gesture_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.train_button.clicked.connect(self.train_selected_gesture)
        self.delete_button.clicked.connect(self.delete_selected_gesture)
        self.refresh_button.clicked.connect(self.refresh_gesture_list)
        self.close_button.clicked.connect(self.accept)

    def refresh_gesture_list(self):
        """Refresh the gesture list"""
        self.gesture_list.clear()

        gestures = self.gesture_manager.get_gesture_list()

        if not gestures:
            item = QListWidgetItem("No custom gestures found")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.gesture_list.addItem(item)
            self.update_statistics()
            return

        for gesture_data in gestures:
            item = QListWidgetItem()
            item_widget = GestureListItem(gesture_data)
            item.setSizeHint(item_widget.sizeHint())

            self.gesture_list.addItem(item)
            self.gesture_list.setItemWidget(item, item_widget)

            # Store gesture data in item
            item.setData(Qt.UserRole, gesture_data)

        self.update_statistics()

    def on_selection_changed(self):
        """Handle gesture selection change"""
        current_item = self.gesture_list.currentItem()

        if current_item and current_item.data(Qt.UserRole):
            gesture_data = current_item.data(Qt.UserRole)
            self.show_gesture_details(gesture_data)
            self.train_button.setEnabled(gesture_data['sample_count'] >= 5)
            self.delete_button.setEnabled(True)
        else:
            self.details_text.clear()
            self.train_button.setEnabled(False)
            self.delete_button.setEnabled(False)

    def show_gesture_details(self, gesture_data: Dict[str, Any]):
        """Show details for selected gesture"""
        details = f"Name: {gesture_data['name']}\n"
        details += f"ID: {gesture_data['id']}\n"
        details += f"Description: {gesture_data.get('description', 'No description')}\n"
        details += f"Created: {gesture_data['created_date'][:10]}\n"  # Show date only
        details += f"Samples: {gesture_data['sample_count']}\n"
        details += f"Training Status: {'Trained' if gesture_data['is_trained'] else 'Not trained'}\n"

        if gesture_data['is_trained']:
            details += f"Accuracy: {gesture_data['training_accuracy']:.2%}\n"
            details += f"Last Trained: {gesture_data['last_trained'][:10] if gesture_data['last_trained'] else 'Unknown'}\n"

        self.details_text.setText(details)

    def train_selected_gesture(self):
        """Train the selected gesture"""
        current_item = self.gesture_list.currentItem()
        if not current_item or not current_item.data(Qt.UserRole):
            return

        gesture_data = current_item.data(Qt.UserRole)
        gesture_name = gesture_data['name']

        if gesture_data['sample_count'] < 5:
            QMessageBox.warning(
                self, "Insufficient Samples",
                f"Need at least 5 samples to train. Current: {gesture_data['sample_count']}"
            )
            return

        # Disable buttons during training
        self.train_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.training_progress.setVisible(True)
        self.training_progress.setRange(0, 0)  # Indeterminate progress

        # Start training worker
        self.training_worker = GestureTrainingWorker(self.gesture_manager, gesture_name, self)
        self.training_worker.training_complete.connect(self.on_training_complete)
        self.training_worker.start()

    def on_training_complete(self, success: bool, accuracy: float, gesture_name: str):
        """Handle training completion"""
        self.training_progress.setVisible(False)

        if success:
            # Check for similar gestures
            similar_gestures = self.gesture_manager.check_gesture_similarity(gesture_name)

            message = f"Gesture '{gesture_name}' trained successfully!\nAccuracy: {accuracy:.2%}"

            if similar_gestures:
                similar_names = [name for name, similarity in similar_gestures]
                message += f"\n\nWarning: This gesture is similar to: {', '.join(similar_names)}"
                message += "\nThis may cause recognition conflicts."

            QMessageBox.information(self, "Training Successful", message)
        else:
            QMessageBox.critical(
                self, "Training Failed",
                f"Failed to train gesture '{gesture_name}'. Please try again."
            )

        # Refresh the list and re-enable buttons
        self.refresh_gesture_list()
        self.train_button.setEnabled(True)
        self.delete_button.setEnabled(True)

    def delete_selected_gesture(self):
        """Delete the selected gesture"""
        current_item = self.gesture_list.currentItem()
        if not current_item or not current_item.data(Qt.UserRole):
            return

        gesture_data = current_item.data(Qt.UserRole)
        gesture_name = gesture_data['name']

        reply = QMessageBox.question(
            self, "Delete Gesture",
            f"Are you sure you want to delete the gesture '{gesture_name}'?\n\n"
            "This will permanently remove all training data and the trained model.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.gesture_manager.delete_gesture(gesture_name):
                QMessageBox.information(
                    self, "Deleted",
                    f"Gesture '{gesture_name}' has been deleted successfully."
                )
                self.refresh_gesture_list()
            else:
                QMessageBox.critical(
                    self, "Delete Failed",
                    f"Failed to delete gesture '{gesture_name}'. Please try again."
                )

    def update_statistics(self):
        """Update the statistics display"""
        gestures = self.gesture_manager.get_gesture_list()

        if not gestures:
            self.stats_text.setText("No custom gestures available.")
            return

        total_gestures = len(gestures)
        trained_gestures = sum(1 for g in gestures if g['is_trained'])
        total_samples = sum(g['sample_count'] for g in gestures)

        avg_accuracy = 0.0
        if trained_gestures > 0:
            accuracies = [g['training_accuracy'] for g in gestures if g['is_trained']]
            avg_accuracy = sum(accuracies) / len(accuracies)

        stats = f"Total Gestures: {total_gestures}\n"
        stats += f"Trained Gestures: {trained_gestures}\n"
        stats += f"Untrained Gestures: {total_gestures - trained_gestures}\n"
        stats += f"Total Samples: {total_samples}\n"

        if trained_gestures > 0:
            stats += f"Average Accuracy: {avg_accuracy:.2%}\n"

        # Show gesture with highest accuracy
        if trained_gestures > 0:
            best_gesture = max(gestures, key=lambda g: g['training_accuracy'] if g['is_trained'] else 0)
            if best_gesture['is_trained']:
                stats += f"\nBest Performing:\n{best_gesture['name']} ({best_gesture['training_accuracy']:.2%})"

        self.stats_text.setText(stats)

    def closeEvent(self, event):
        """Handle dialog close event"""
        if self.training_worker and self.training_worker.isRunning():
            self.training_worker.wait()
        event.accept()
