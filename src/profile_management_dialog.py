import os
from datetime import datetime
from typing import Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QListWidget,
    QListWidgetItem, QLabel, QPushButton, QLineEdit, QTextEdit,
    QGroupBox, QMessageBox, QFileDialog, QSplitter, QFrame,
    QWidget, QScrollArea, QGridLayout
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QIcon, QPixmap
from profile_manager import ProfileManager, ProfileInfo


class ProfileManagementDialog(QDialog):
    """
    GFLOW-18: Profile Management Dialog
    
    Provides a comprehensive interface for managing gesture profiles,
    including creating, loading, deleting, and importing/exporting profiles.
    """
    
    profile_changed = Signal(str)  # Emitted when profile is switched
    
    def __init__(self, profile_manager: ProfileManager, parent=None):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.current_profile_item = None
        
        self.setWindowTitle("Profile Management - GestureFlow")
        self.setModal(True)
        self.resize(900, 600)
        
        self.setup_ui()
        self.setup_connections()
        self.refresh_profile_list()
    
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("Gesture Profile Management")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Main content area
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # Left panel - Profile list
        self.create_profile_list_panel(splitter)
        
        # Right panel - Profile details and actions
        self.create_profile_details_panel(splitter)
        
        # Set splitter proportions
        splitter.setSizes([300, 600])
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Create backup button
        self.backup_button = QPushButton("Create Backup")
        self.backup_button.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
        """)
        button_layout.addWidget(self.backup_button)
        
        button_layout.addStretch()
        
        # Standard buttons
        self.close_button = QPushButton("Close")
        self.close_button.setStyleSheet("""
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
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def create_profile_list_panel(self, parent):
        """Create the profile list panel"""
        # Left panel container
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Profile list header
        list_header = QLabel("Available Profiles")
        list_header.setFont(QFont("Arial", 12, QFont.Bold))
        left_layout.addWidget(list_header)
        
        # Profile list
        self.profile_list = QListWidget()
        self.profile_list.setMinimumWidth(280)
        left_layout.addWidget(self.profile_list)
        
        # Profile list buttons
        list_button_layout = QHBoxLayout()
        
        self.new_profile_button = QPushButton("New Profile")
        self.new_profile_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        list_button_layout.addWidget(self.new_profile_button)
        
        self.delete_profile_button = QPushButton("Delete")
        self.delete_profile_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.delete_profile_button.setEnabled(False)
        list_button_layout.addWidget(self.delete_profile_button)
        
        left_layout.addLayout(list_button_layout)
        
        parent.addWidget(left_panel)
    
    def create_profile_details_panel(self, parent):
        """Create the profile details panel"""
        # Right panel container
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Profile details group
        details_group = QGroupBox("Profile Details")
        details_layout = QFormLayout(details_group)
        
        # Profile name
        self.profile_name_label = QLabel("No profile selected")
        self.profile_name_label.setFont(QFont("Arial", 14, QFont.Bold))
        details_layout.addRow("Name:", self.profile_name_label)
        
        # Profile description
        self.profile_description_label = QLabel("-")
        self.profile_description_label.setWordWrap(True)
        details_layout.addRow("Description:", self.profile_description_label)
        
        # Profile statistics
        self.profile_created_label = QLabel("-")
        details_layout.addRow("Created:", self.profile_created_label)
        
        self.profile_modified_label = QLabel("-")
        details_layout.addRow("Last Modified:", self.profile_modified_label)
        
        self.profile_gestures_label = QLabel("-")
        details_layout.addRow("Custom Gestures:", self.profile_gestures_label)
        
        self.profile_mappings_label = QLabel("-")
        details_layout.addRow("Action Mappings:", self.profile_mappings_label)
        
        # Profile status
        self.profile_status_label = QLabel("-")
        details_layout.addRow("Status:", self.profile_status_label)
        
        right_layout.addWidget(details_group)
        
        # Profile actions group
        actions_group = QGroupBox("Profile Actions")
        actions_layout = QGridLayout(actions_group)
        
        # Load profile button
        self.load_profile_button = QPushButton("Load Profile")
        self.load_profile_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.load_profile_button.setEnabled(False)
        actions_layout.addWidget(self.load_profile_button, 0, 0)
        
        # Set as default button
        self.set_default_button = QPushButton("Set as Default")
        self.set_default_button.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
        """)
        self.set_default_button.setEnabled(False)
        actions_layout.addWidget(self.set_default_button, 0, 1)
        
        # Export profile button
        self.export_profile_button = QPushButton("Export Profile")
        self.export_profile_button.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
        """)
        self.export_profile_button.setEnabled(False)
        actions_layout.addWidget(self.export_profile_button, 1, 0)
        
        # Import profile button
        self.import_profile_button = QPushButton("Import Profile")
        self.import_profile_button.setStyleSheet("""
            QPushButton {
                background-color: #16a085;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #138d75;
            }
        """)
        actions_layout.addWidget(self.import_profile_button, 1, 1)
        
        right_layout.addWidget(actions_group)
        
        # Current profile status
        current_group = QGroupBox("Current Active Profile")
        current_layout = QVBoxLayout(current_group)
        
        self.current_profile_label = QLabel("Loading...")
        self.current_profile_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.current_profile_label.setStyleSheet("color: #27ae60;")
        current_layout.addWidget(self.current_profile_label)
        
        right_layout.addWidget(current_group)
        
        right_layout.addStretch()
        
        parent.addWidget(right_panel)

    def setup_connections(self):
        """Setup signal connections"""
        self.profile_list.itemSelectionChanged.connect(self.on_profile_selection_changed)
        self.new_profile_button.clicked.connect(self.create_new_profile)
        self.delete_profile_button.clicked.connect(self.delete_selected_profile)
        self.load_profile_button.clicked.connect(self.load_selected_profile)
        self.set_default_button.clicked.connect(self.set_selected_as_default)
        self.export_profile_button.clicked.connect(self.export_selected_profile)
        self.import_profile_button.clicked.connect(self.import_profile)
        self.backup_button.clicked.connect(self.create_backup)
        self.close_button.clicked.connect(self.accept)

    def refresh_profile_list(self):
        """Refresh the profile list display"""
        self.profile_list.clear()

        profiles = self.profile_manager.get_all_profiles()
        current_profile_name = self.profile_manager.get_current_profile_name()

        for profile in profiles:
            item = QListWidgetItem()

            # Create display text
            display_text = profile.name
            if profile.is_default:
                display_text += " (Default)"
            if profile.is_active:
                display_text += " (Active)"

            item.setText(display_text)
            item.setData(Qt.UserRole, profile.name)

            # Style active profile
            if profile.is_active:
                item.setBackground(Qt.lightGray)
                font = item.font()
                font.setBold(True)
                item.setFont(font)

            self.profile_list.addItem(item)

            # Select current profile
            if profile.name == current_profile_name:
                self.profile_list.setCurrentItem(item)

        # Update current profile display
        if current_profile_name:
            self.current_profile_label.setText(f"Active: {current_profile_name}")
        else:
            self.current_profile_label.setText("No active profile")

    def on_profile_selection_changed(self):
        """Handle profile selection change"""
        current_item = self.profile_list.currentItem()

        if current_item:
            profile_name = current_item.data(Qt.UserRole)
            profile = None

            # Find the profile info
            for p in self.profile_manager.get_all_profiles():
                if p.name == profile_name:
                    profile = p
                    break

            if profile:
                self.update_profile_details(profile)
                self.enable_profile_actions(True, profile)
            else:
                self.clear_profile_details()
                self.enable_profile_actions(False)
        else:
            self.clear_profile_details()
            self.enable_profile_actions(False)

    def update_profile_details(self, profile: ProfileInfo):
        """Update the profile details display"""
        self.profile_name_label.setText(profile.name)
        self.profile_description_label.setText(profile.description or "No description")

        # Format dates
        try:
            created_date = datetime.fromisoformat(profile.created_date)
            self.profile_created_label.setText(created_date.strftime("%Y-%m-%d %H:%M"))
        except:
            self.profile_created_label.setText(profile.created_date)

        try:
            modified_date = datetime.fromisoformat(profile.last_modified)
            self.profile_modified_label.setText(modified_date.strftime("%Y-%m-%d %H:%M"))
        except:
            self.profile_modified_label.setText(profile.last_modified)

        # Statistics
        self.profile_gestures_label.setText(str(profile.custom_gesture_count))
        self.profile_mappings_label.setText(str(profile.action_mapping_count))

        # Status
        status_parts = []
        if profile.is_active:
            status_parts.append("Active")
        if profile.is_default:
            status_parts.append("Default")

        if status_parts:
            status_text = ", ".join(status_parts)
            self.profile_status_label.setText(status_text)
            self.profile_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.profile_status_label.setText("Inactive")
            self.profile_status_label.setStyleSheet("color: #7f8c8d;")

    def clear_profile_details(self):
        """Clear the profile details display"""
        self.profile_name_label.setText("No profile selected")
        self.profile_description_label.setText("-")
        self.profile_created_label.setText("-")
        self.profile_modified_label.setText("-")
        self.profile_gestures_label.setText("-")
        self.profile_mappings_label.setText("-")
        self.profile_status_label.setText("-")
        self.profile_status_label.setStyleSheet("")

    def enable_profile_actions(self, enabled: bool, profile: ProfileInfo = None):
        """Enable/disable profile action buttons"""
        self.load_profile_button.setEnabled(enabled)
        self.set_default_button.setEnabled(enabled)
        self.export_profile_button.setEnabled(enabled)

        # Delete button - can't delete default profile or active profile
        can_delete = enabled and profile and not profile.is_default and not profile.is_active
        self.delete_profile_button.setEnabled(can_delete)

    def create_new_profile(self):
        """Create a new profile"""
        from PySide6.QtWidgets import QInputDialog

        # Get profile name
        name, ok = QInputDialog.getText(
            self, "New Profile",
            "Enter profile name:",
            text="New Profile"
        )

        if not ok or not name.strip():
            return

        name = name.strip()

        # Check if name already exists
        existing_profiles = [p.name for p in self.profile_manager.get_all_profiles()]
        if name in existing_profiles:
            QMessageBox.warning(
                self, "Profile Exists",
                f"A profile named '{name}' already exists."
            )
            return

        # Get description
        description, ok = QInputDialog.getText(
            self, "Profile Description",
            "Enter profile description (optional):",
            text=""
        )

        if not ok:
            return

        # Create profile
        if self.profile_manager.create_profile(name, description.strip()):
            QMessageBox.information(
                self, "Profile Created",
                f"Profile '{name}' created successfully."
            )
            self.refresh_profile_list()
        else:
            QMessageBox.critical(
                self, "Error",
                f"Failed to create profile '{name}'."
            )

    def delete_selected_profile(self):
        """Delete the selected profile"""
        current_item = self.profile_list.currentItem()
        if not current_item:
            return

        profile_name = current_item.data(Qt.UserRole)

        # Confirm deletion
        reply = QMessageBox.question(
            self, "Delete Profile",
            f"Are you sure you want to delete profile '{profile_name}'?\n\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.profile_manager.delete_profile(profile_name):
                QMessageBox.information(
                    self, "Profile Deleted",
                    f"Profile '{profile_name}' deleted successfully."
                )
                self.refresh_profile_list()
            else:
                QMessageBox.critical(
                    self, "Error",
                    f"Failed to delete profile '{profile_name}'."
                )

    def load_selected_profile(self):
        """Load the selected profile"""
        current_item = self.profile_list.currentItem()
        if not current_item:
            return

        profile_name = current_item.data(Qt.UserRole)

        if self.profile_manager.load_profile(profile_name):
            QMessageBox.information(
                self, "Profile Loaded",
                f"Profile '{profile_name}' loaded successfully."
            )
            self.refresh_profile_list()
            self.profile_changed.emit(profile_name)
        else:
            QMessageBox.critical(
                self, "Error",
                f"Failed to load profile '{profile_name}'."
            )

    def set_selected_as_default(self):
        """Set the selected profile as default"""
        current_item = self.profile_list.currentItem()
        if not current_item:
            return

        profile_name = current_item.data(Qt.UserRole)

        if self.profile_manager.set_default_profile(profile_name):
            QMessageBox.information(
                self, "Default Profile Set",
                f"Profile '{profile_name}' is now the default profile."
            )
            self.refresh_profile_list()
        else:
            QMessageBox.critical(
                self, "Error",
                f"Failed to set '{profile_name}' as default profile."
            )

    def export_selected_profile(self):
        """Export the selected profile"""
        current_item = self.profile_list.currentItem()
        if not current_item:
            return

        profile_name = current_item.data(Qt.UserRole)

        # Get export file path
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Profile",
            f"{profile_name}_profile.json",
            "JSON Files (*.json)"
        )

        if filename:
            if self.profile_manager.export_profile(profile_name, filename):
                QMessageBox.information(
                    self, "Profile Exported",
                    f"Profile '{profile_name}' exported to {filename}"
                )
            else:
                QMessageBox.critical(
                    self, "Export Error",
                    f"Failed to export profile '{profile_name}'."
                )

    def import_profile(self):
        """Import a profile from file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import Profile",
            "",
            "JSON Files (*.json)"
        )

        if filename:
            if self.profile_manager.import_profile(filename):
                QMessageBox.information(
                    self, "Profile Imported",
                    f"Profile imported successfully from {filename}"
                )
                self.refresh_profile_list()
            else:
                QMessageBox.critical(
                    self, "Import Error",
                    f"Failed to import profile from {filename}"
                )

    def create_backup(self):
        """Create a backup of all profiles"""
        backup_file = self.profile_manager.create_backup()

        if backup_file:
            QMessageBox.information(
                self, "Backup Created",
                f"Backup created successfully:\n{backup_file}"
            )
        else:
            QMessageBox.critical(
                self, "Backup Error",
                "Failed to create backup."
            )
