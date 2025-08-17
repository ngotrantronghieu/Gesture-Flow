import os
import uuid
from typing import Dict, List, Optional, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QComboBox, QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox,
    QTextEdit, QCheckBox, QGroupBox, QTabWidget, QWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog, QProgressBar,
    QSplitter, QFrame, QScrollArea, QButtonGroup, QRadioButton, QStackedWidget
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QIcon, QPalette, QColor
# Optional: live recording support via pynput
try:
    from pynput.mouse import Listener as MouseListener, Button
    from pynput.keyboard import Listener as KeyboardListener, Key
    PYNPUT_LOCAL_AVAILABLE = True
except Exception:
    PYNPUT_LOCAL_AVAILABLE = False
import time
from action_types import (
    Action, ActionType, MouseAction, KeyboardAction, ApplicationAction,
    MouseActionParameters, KeyboardActionParameters, ApplicationActionParameters,
    MacroActionParameters, ActionValidator
)
from action_mapping_manager import ActionMappingManager
from action_executor import ActionExecutor
from config import ACTION_TYPES_CONFIG, PREDEFINED_GESTURES

class ActionPreviewWorker(QThread):
    """Worker thread for action preview/testing"""
    preview_completed = Signal(bool, str)

    def __init__(self, action: Action, executor: ActionExecutor):
        super().__init__()
        self.action = action
        self.executor = executor

    def run(self):
        try:
            future = self.executor.execute_action(self.action, async_execution=False)
            result = future.result()
            self.preview_completed.emit(result.success, result.message)
        except Exception as e:
            self.preview_completed.emit(False, f"Preview failed: {str(e)}")


class SubActionDialog(QDialog):
    """Dialog to create or edit a single sub-action for a macro sequence"""
    def __init__(self, parent=None, initial_action: Optional[Action] = None):
        super().__init__(parent)
        self.setWindowTitle("Add Macro Action")
        self.resize(420, 360)

        self.initial_action = initial_action

        root_layout = QVBoxLayout(self)

        # Action type selector
        type_form = QFormLayout()
        self.type_combo = QComboBox()
        # Only allow enabled, non-macro types for sub-actions
        allowed_types = [t for t in [ActionType.MOUSE, ActionType.KEYBOARD, ActionType.APPLICATION]
                         if ACTION_TYPES_CONFIG.get(t.value, {}).get('enabled', False)]
        for t in allowed_types:
            self.type_combo.addItem(t.value.title(), t.value)
        type_form.addRow("Action Type:", self.type_combo)
        root_layout.addLayout(type_form)

        # Stacked editor widgets per type
        self.editors_stack = QStackedWidget()

        # Mouse editor
        mouse_widget = QWidget(); mouse_form = QFormLayout(mouse_widget)
        self.sub_mouse_action = QComboBox()
        mouse_actions = ACTION_TYPES_CONFIG.get('mouse', {}).get('actions', [])
        self.sub_mouse_action.addItems([a.replace('_', ' ').title() for a in mouse_actions])
        # Move/Drag target position
        self.sub_mouse_x = QSpinBox(); self.sub_mouse_x.setRange(0, 9999); self.sub_mouse_x.setSpecialValueText("Current")
        self.sub_mouse_y = QSpinBox(); self.sub_mouse_y.setRange(0, 9999); self.sub_mouse_y.setSpecialValueText("Current")
        # Drag start position (from)
        self.sub_drag_from_x = QSpinBox(); self.sub_drag_from_x.setRange(0, 9999); self.sub_drag_from_x.setSpecialValueText("Current")
        self.sub_drag_from_y = QSpinBox(); self.sub_drag_from_y.setRange(0, 9999); self.sub_drag_from_y.setSpecialValueText("Current")
        self.sub_mouse_button = QComboBox(); self.sub_mouse_button.addItems(["Left", "Right", "Middle"])
        self.sub_mouse_clicks = QSpinBox(); self.sub_mouse_clicks.setRange(1, 10); self.sub_mouse_clicks.setValue(1)
        self.sub_mouse_duration = QDoubleSpinBox(); self.sub_mouse_duration.setRange(0.0, 10.0); self.sub_mouse_duration.setValue(0.3); self.sub_mouse_duration.setSuffix(" seconds")
        self.sub_scroll_dir = QComboBox(); self.sub_scroll_dir.addItems(["Up", "Down", "Left", "Right"])
        self.sub_scroll_amount = QSpinBox(); self.sub_scroll_amount.setRange(1, 20); self.sub_scroll_amount.setValue(3)
        mouse_form.addRow("Action:", self.sub_mouse_action)
        mouse_form.addRow("X Position:", self.sub_mouse_x)
        mouse_form.addRow("Y Position:", self.sub_mouse_y)
        mouse_form.addRow("From X (Drag):", self.sub_drag_from_x)
        mouse_form.addRow("From Y (Drag):", self.sub_drag_from_y)
        mouse_form.addRow("Button:", self.sub_mouse_button)
        mouse_form.addRow("Click Count:", self.sub_mouse_clicks)
        mouse_form.addRow("Duration:", self.sub_mouse_duration)
        mouse_form.addRow("Scroll Direction:", self.sub_scroll_dir)
        mouse_form.addRow("Scroll Amount:", self.sub_scroll_amount)

        # Keyboard editor
        kb_widget = QWidget(); kb_form = QFormLayout(kb_widget)
        self.sub_kb_action = QComboBox()
        kb_actions = ACTION_TYPES_CONFIG.get('keyboard', {}).get('actions', [])
        self.sub_kb_action.addItems([a.replace('_', ' ').title() for a in kb_actions])
        self.sub_kb_keys = QLineEdit(); self.sub_kb_keys.setPlaceholderText("e.g., ctrl+c or alt+tab or enter")
        self.sub_kb_text = QTextEdit(); self.sub_kb_text.setMaximumHeight(60); self.sub_kb_text.setPlaceholderText("Text to type…")
        self.sub_kb_interval = QDoubleSpinBox(); self.sub_kb_interval.setRange(0.0, 1.0); self.sub_kb_interval.setValue(0.05); self.sub_kb_interval.setSuffix(" seconds")
        kb_form.addRow("Action:", self.sub_kb_action)
        kb_form.addRow("Keys:", self.sub_kb_keys)
        kb_form.addRow("Text:", self.sub_kb_text)
        kb_form.addRow("Key Interval:", self.sub_kb_interval)

        # Application editor
        app_widget = QWidget(); app_form = QFormLayout(app_widget)
        self.sub_app_action = QComboBox()
        app_actions = ACTION_TYPES_CONFIG.get('application', {}).get('actions', [])
        self.sub_app_action.addItems([a.replace('_', ' ').title() for a in app_actions])
        self.sub_app_path = QLineEdit()
        self.sub_app_args = QLineEdit(); self.sub_app_args.setPlaceholderText("Arguments (optional)")
        self.sub_app_workdir = QLineEdit(); self.sub_app_workdir.setPlaceholderText("Working directory (optional)")
        app_form.addRow("Action:", self.sub_app_action)
        app_form.addRow("Application Path:", self.sub_app_path)
        app_form.addRow("Arguments:", self.sub_app_args)
        app_form.addRow("Working Directory:", self.sub_app_workdir)

        self.editors_stack.addWidget(mouse_widget)
        self.editors_stack.addWidget(kb_widget)
        self.editors_stack.addWidget(app_widget)
        root_layout.addWidget(self.editors_stack)

        # Name/Description (optional)
        meta_form = QFormLayout()
        self.sub_name = QLineEdit(); self.sub_desc = QTextEdit(); self.sub_desc.setMaximumHeight(50)
        meta_form.addRow("Name:", self.sub_name)
        meta_form.addRow("Description:", self.sub_desc)
        root_layout.addLayout(meta_form)

        # Buttons
        buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK"); self.cancel_button = QPushButton("Cancel")
        buttons_layout.addStretch(); buttons_layout.addWidget(self.ok_button); buttons_layout.addWidget(self.cancel_button)
        root_layout.addLayout(buttons_layout)

        # Wiring
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        self.sub_mouse_action.currentTextChanged.connect(self._update_mouse_fields)
        self.sub_kb_action.currentTextChanged.connect(self._update_keyboard_fields)
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        # Prefill if editing
        if self.initial_action:
            self._prefill_from_action(self.initial_action)
        else:
            self._on_type_changed()
        # Ensure initial visibility state
        self._update_mouse_fields()
        self._update_keyboard_fields()

    def _on_type_changed(self):
        current_type = self.type_combo.currentData()
        # Map to stacked index: mouse=0, keyboard=1, application=2
        index_map = { 'mouse': 0, 'keyboard': 1, 'application': 2 }
        self.editors_stack.setCurrentIndex(index_map.get(current_type, 0))
        # Update visibility for the newly active editor
        if current_type == 'mouse':
            self._update_mouse_fields()
        elif current_type == 'keyboard':
            self._update_keyboard_fields()

    def _prefill_from_action(self, action: Action):
        # Set type
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == action.type.value:
                self.type_combo.setCurrentIndex(i)
                break
        self._on_type_changed()
        # Fill per type
        if action.type == ActionType.MOUSE:
            self.sub_mouse_action.setCurrentText(action.subtype.replace('_', ' ').title())
            p: MouseActionParameters = action.parameters
            # Target
            if getattr(p, 'x', None) is not None: self.sub_mouse_x.setValue(p.x)
            if getattr(p, 'y', None) is not None: self.sub_mouse_y.setValue(p.y)
            # Drag from
            if getattr(p, 'from_x', None) is not None: self.sub_drag_from_x.setValue(p.from_x)
            if getattr(p, 'from_y', None) is not None: self.sub_drag_from_y.setValue(p.from_y)
            # Click specifics
            self.sub_mouse_button.setCurrentText(getattr(p, 'button', 'left').title())
            self.sub_mouse_clicks.setValue(getattr(p, 'clicks', 1) or 1)
            # Duration
            self.sub_mouse_duration.setValue(getattr(p, 'duration', 0.3) or 0.3)
            # Scroll
            self.sub_scroll_dir.setCurrentText(getattr(p, 'scroll_direction', 'Up').title())
            self.sub_scroll_amount.setValue(getattr(p, 'scroll_amount', 3) or 3)
        elif action.type == ActionType.KEYBOARD:
            self.sub_kb_action.setCurrentText(action.subtype.replace('_', ' ').title())
            p: KeyboardActionParameters = action.parameters
            # If list, join with + for display
            keys_value = p.keys if isinstance(p.keys, list) else [p.keys] if p.keys else []
            self.sub_kb_keys.setText('+'.join([str(k) for k in keys_value]) if keys_value else "")
            self.sub_kb_text.setPlainText(getattr(p, 'text', '') or '')
            self.sub_kb_interval.setValue(getattr(p, 'interval', 0.05) or 0.05)
        elif action.type == ActionType.APPLICATION:
            self.sub_app_action.setCurrentText(action.subtype.replace('_', ' ').title())
            p: ApplicationActionParameters = action.parameters
            self.sub_app_path.setText(getattr(p, 'path', '') or '')
            args = getattr(p, 'arguments', []) or []
            self.sub_app_args.setText(' '.join(args))
            self.sub_app_workdir.setText(getattr(p, 'working_directory', '') or '')

        # Meta
        self.sub_name.setText(action.name or '')
        self.sub_desc.setPlainText(action.description or '')

    def get_action(self) -> Optional[Action]:
        try:
            action_type = ActionType(self.type_combo.currentData())
            if action_type == ActionType.MOUSE:
                subtype = self.sub_mouse_action.currentText().lower().replace(' ', '_')
                if subtype == 'click':
                    params = MouseActionParameters(
                        button=self.sub_mouse_button.currentText().lower(),
                        clicks=self.sub_mouse_clicks.value(),
                        duration=self.sub_mouse_duration.value(),
                    )
                elif subtype == 'move_to':
                    params = MouseActionParameters(
                        x=self.sub_mouse_x.value() if self.sub_mouse_x.value() > 0 else None,
                        y=self.sub_mouse_y.value() if self.sub_mouse_y.value() > 0 else None,
                        duration=self.sub_mouse_duration.value(),
                    )
                elif subtype == 'drag':
                    params = MouseActionParameters(
                        from_x=self.sub_drag_from_x.value() if self.sub_drag_from_x.value() > 0 else None,
                        from_y=self.sub_drag_from_y.value() if self.sub_drag_from_y.value() > 0 else None,
                        to_x=self.sub_mouse_x.value() if self.sub_mouse_x.value() > 0 else None,
                        to_y=self.sub_mouse_y.value() if self.sub_mouse_y.value() > 0 else None,
                        duration=self.sub_mouse_duration.value(),
                    )
                elif subtype == 'scroll':
                    params = MouseActionParameters(
                        scroll_direction=self.sub_scroll_dir.currentText().lower(),
                        scroll_amount=self.sub_scroll_amount.value(),
                        duration=self.sub_mouse_duration.value(),
                    )
                else:
                    params = MouseActionParameters()
            elif action_type == ActionType.KEYBOARD:
                subtype = self.sub_kb_action.currentText().lower().replace(' ', '_')
                keys_text = self.sub_kb_keys.text().strip()
                if subtype in ('key_press', 'key_combination'):
                    if '+' in keys_text:
                        parts = [k.strip() for k in keys_text.split('+') if k.strip()]
                        modifiers = parts[:-1] if len(parts) > 1 else []
                        keys = [parts[-1]] if parts else []
                    else:
                        modifiers = []
                        keys = [keys_text] if keys_text else []
                    params = KeyboardActionParameters(
                        keys=keys,
                        text="",
                        modifiers=modifiers,
                        interval=self.sub_kb_interval.value(),
                    )
                elif subtype == 'type_text':
                    params = KeyboardActionParameters(
                        keys="",
                        text=self.sub_kb_text.toPlainText(),
                        modifiers=[],
                        interval=self.sub_kb_interval.value(),
                    )
                else:
                    params = KeyboardActionParameters()
            elif action_type == ActionType.APPLICATION:
                subtype = self.sub_app_action.currentText().lower().replace(' ', '_')
                args_text = self.sub_app_args.text().strip()
                arguments = args_text.split() if args_text else []
                params = ApplicationActionParameters(
                    path=self.sub_app_path.text().strip(),
                    arguments=arguments,
                    working_directory=self.sub_app_workdir.text().strip(),
                )
            else:
                return None

            action = Action(
                id=str(uuid.uuid4()),
                type=action_type,
                subtype=subtype,
                parameters=params,
                name=self.sub_name.text().strip(),
                description=self.sub_desc.toPlainText().strip(),
                enabled=True,
                requires_confirmation=False,
            )
            return action
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to build sub-action: {str(e)}")
            return None

    def _update_mouse_fields(self):
        current = self.sub_mouse_action.currentText().lower().replace(' ', '_')
        def set_row_visible(form: QFormLayout, row_index: int, visible: bool):
            label_item = form.itemAt(row_index, QFormLayout.LabelRole)
            field_item = form.itemAt(row_index, QFormLayout.FieldRole)
            if label_item and label_item.widget():
                label_item.widget().setVisible(visible)
            if field_item and field_item.widget():
                field_item.widget().setVisible(visible)

        # Rows: 0 Action, 1 X, 2 Y, 3 From X, 4 From Y, 5 Button, 6 Clicks, 7 Duration, 8 Scroll Dir, 9 Scroll Amount
        visible_map = {
            'click':   {1: False,2: False,3: False,4: False,5: True, 6: True, 7: True, 8: False,9: False},
            'move_to': {1: True, 2: True, 3: False,4: False,5: False,6: False,7: True, 8: False,9: False},
            'drag':    {1: True, 2: True, 3: True, 4: True, 5: False,6: False,7: True, 8: False,9: False},
            'scroll':  {1: False,2: False,3: False,4: False,5: False,6: False,7: True, 8: True, 9: True},
        }
        state = visible_map.get(current, {1: True,2: True,3: False,4: False,5: True,6: True,7: True,8: False,9: False})
        form = self.sub_mouse_action.parent().layout()
        for row_index, visible in state.items():
            set_row_visible(form, row_index, visible)

    def _update_keyboard_fields(self):
        subtype = self.sub_kb_action.currentText().lower().replace(' ', '_')
        is_key_action = subtype in ('key_press', 'key_combination')
        is_type_text = subtype == 'type_text'
        # Show/hide fields
        self.sub_kb_keys.setVisible(is_key_action)
        self.sub_kb_text.setVisible(is_type_text)
        # Toggle labels
        form = self.sub_kb_action.parent().layout()
        try:
            label_item = form.itemAt(1, QFormLayout.LabelRole)
            if label_item and label_item.widget():
                label_item.widget().setVisible(is_key_action)
            label_item = form.itemAt(2, QFormLayout.LabelRole)
            if label_item and label_item.widget():
                label_item.widget().setVisible(is_type_text)
        except Exception:
            pass
class ActionMappingDialog(QDialog):
    """
    Dialog for creating and managing gesture-to-action mappings

    Features:
    - Intuitive gesture selection
    - Comprehensive action configuration
    - Action preview/testing
    - Mapping management
    - Profile support
    """

    mapping_created = Signal(str)  # Emitted when a new mapping is created
    mapping_updated = Signal(str)  # Emitted when a mapping is updated

    def __init__(self, mapping_manager: ActionMappingManager, custom_gesture_manager, profile_manager=None, parent=None):
        super().__init__(parent)
        self.mapping_manager = mapping_manager
        self.custom_gesture_manager = custom_gesture_manager
        self.profile_manager = profile_manager  # GFLOW-18: Unified profile manager
        # Macro recording state
        self.is_recording_macro = False
        self._mouse_listener = None
        self._keyboard_listener = None
        self._last_click_time = None
        self.profile_manager = profile_manager  # GFLOW-18: Unified profile manager
        self.action_executor = ActionExecutor()
        self.validator = ActionValidator()

        # Current state
        self.current_mapping_id = None
        self.preview_worker = None
        self.macro_sequence: List[Dict[str, Any]] = []

        self.setWindowTitle("Gesture-to-Action Mapping")
        self.setModal(True)
        self.resize(900, 700)

        self.setup_ui()
        self.setup_connections()
        self.load_available_gestures()
        self.load_existing_mappings()

    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)

        # Create main splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Left panel - Mapping list and controls
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)

        # Right panel - Action configuration
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)

        # Set splitter proportions
        splitter.setSizes([300, 600])

        # Bottom buttons
        button_layout = QHBoxLayout()

        self.save_button = QPushButton("Save Mapping")
        self.save_button.setEnabled(False)

        self.test_button = QPushButton("Test Action")
        self.test_button.setEnabled(False)

        self.delete_button = QPushButton("Delete Mapping")
        self.delete_button.setEnabled(False)

        self.close_button = QPushButton("Close")

        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.test_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def create_left_panel(self) -> QWidget:
        """Create the left panel with mapping list and gesture selection"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # GFLOW-18: Profile information (read-only, managed by unified ProfileManager)
        profile_group = QGroupBox("Current Profile")
        profile_layout = QVBoxLayout(profile_group)

        self.profile_info_label = QLabel("Loading profile information...")
        self.profile_info_label.setStyleSheet("color: #3498db; font-weight: bold; padding: 5px;")
        profile_layout.addWidget(self.profile_info_label)

        # Note about profile management
        profile_note = QLabel("Use 'Profiles > Manage Profiles...' to switch profiles")
        profile_note.setStyleSheet("color: #7f8c8d; font-size: 10px; font-style: italic;")
        profile_layout.addWidget(profile_note)

        layout.addWidget(profile_group)

        # Update profile info
        self.update_profile_info()

        # Gesture selection
        gesture_group = QGroupBox("Select Gesture")
        gesture_layout = QFormLayout(gesture_group)

        self.gesture_type_combo = QComboBox()
        self.gesture_type_combo.addItems(["Predefined", "Custom"])

        self.gesture_combo = QComboBox()

        gesture_layout.addRow("Gesture Type:", self.gesture_type_combo)
        gesture_layout.addRow("Gesture:", self.gesture_combo)

        layout.addWidget(gesture_group)

        # Existing mappings
        mappings_group = QGroupBox("Existing Mappings")
        mappings_layout = QVBoxLayout(mappings_group)

        self.mappings_table = QTableWidget()
        self.mappings_table.setColumnCount(4)
        self.mappings_table.setHorizontalHeaderLabels([
            "Gesture", "Action Type", "Enabled", "Uses"
        ])
        self.mappings_table.horizontalHeader().setStretchLastSection(True)
        self.mappings_table.setSelectionBehavior(QTableWidget.SelectRows)

        mappings_layout.addWidget(self.mappings_table)

        layout.addWidget(mappings_group)

        return widget

    def create_right_panel(self) -> QWidget:
        """Create the right panel with action configuration"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Action type selection
        action_type_group = QGroupBox("Action Type")
        action_type_layout = QHBoxLayout(action_type_group)

        self.action_type_group = QButtonGroup()

        for action_type in ActionType:
            if ACTION_TYPES_CONFIG.get(action_type.value, {}).get('enabled', False):
                radio = QRadioButton(action_type.value.title())
                radio.setProperty('action_type', action_type.value)
                self.action_type_group.addButton(radio)
                action_type_layout.addWidget(radio)

        layout.addWidget(action_type_group)

        # Action configuration tabs
        self.action_tabs = QTabWidget()

        # Mouse actions tab
        self.mouse_tab = self.create_mouse_tab()
        self.action_tabs.addTab(self.mouse_tab, "Mouse")

        # Keyboard actions tab
        self.keyboard_tab = self.create_keyboard_tab()
        self.action_tabs.addTab(self.keyboard_tab, "Keyboard")

        # Application actions tab
        self.application_tab = self.create_application_tab()
        self.action_tabs.addTab(self.application_tab, "Application")

        # Macro actions tab
        self.macro_tab = self.create_macro_tab()
        self.action_tabs.addTab(self.macro_tab, "Macro")

        layout.addWidget(self.action_tabs)

        # Action settings
        settings_group = QGroupBox("Action Settings")
        settings_layout = QFormLayout(settings_group)

        self.action_name_edit = QLineEdit()
        self.action_description_edit = QTextEdit()
        self.action_description_edit.setMaximumHeight(60)

        self.enabled_checkbox = QCheckBox()
        self.enabled_checkbox.setChecked(True)

        self.confirmation_checkbox = QCheckBox()

        self.timeout_spinbox = QDoubleSpinBox()
        self.timeout_spinbox.setRange(0.1, 60.0)
        self.timeout_spinbox.setValue(5.0)
        self.timeout_spinbox.setSuffix(" seconds")

        settings_layout.addRow("Name:", self.action_name_edit)
        settings_layout.addRow("Description:", self.action_description_edit)
        settings_layout.addRow("Enabled:", self.enabled_checkbox)
        settings_layout.addRow("Require Confirmation:", self.confirmation_checkbox)
        settings_layout.addRow("Timeout:", self.timeout_spinbox)

        layout.addWidget(settings_group)

        # Preview area
        preview_group = QGroupBox("Action Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_text = QTextEdit()
        self.preview_text.setMaximumHeight(80)
        self.preview_text.setReadOnly(True)

        self.preview_progress = QProgressBar()
        self.preview_progress.setVisible(False)

        preview_layout.addWidget(self.preview_text)
        preview_layout.addWidget(self.preview_progress)

        layout.addWidget(preview_group)

        return widget

    def create_mouse_tab(self) -> QWidget:
        """Create mouse action configuration tab"""
        widget = QWidget()
        layout = QFormLayout(widget)
        # Keep reference to control the visibility of specific rows
        self.mouse_form_layout = layout

        self.mouse_action_combo = QComboBox()
        mouse_actions = ACTION_TYPES_CONFIG.get('mouse', {}).get('actions', [])
        self.mouse_action_combo.addItems([action.replace('_', ' ').title() for action in mouse_actions])

        # Move/Drag target position
        self.mouse_x_spinbox = QSpinBox()
        self.mouse_x_spinbox.setRange(0, 9999)
        self.mouse_x_spinbox.setSpecialValueText("Current")
        self.mouse_y_spinbox = QSpinBox()
        self.mouse_y_spinbox.setRange(0, 9999)
        self.mouse_y_spinbox.setSpecialValueText("Current")

        # Drag start position (from)
        self.drag_from_x_spinbox = QSpinBox()
        self.drag_from_x_spinbox.setRange(0, 9999)
        self.drag_from_x_spinbox.setSpecialValueText("Current")
        self.drag_from_y_spinbox = QSpinBox()
        self.drag_from_y_spinbox.setRange(0, 9999)
        self.drag_from_y_spinbox.setSpecialValueText("Current")

        self.mouse_button_combo = QComboBox()
        self.mouse_button_combo.addItems(["Left", "Right", "Middle"])

        self.mouse_clicks_spinbox = QSpinBox()
        self.mouse_clicks_spinbox.setRange(1, 10)
        self.mouse_clicks_spinbox.setValue(1)

        self.mouse_duration_spinbox = QDoubleSpinBox()
        self.mouse_duration_spinbox.setRange(0.0, 10.0)
        self.mouse_duration_spinbox.setValue(0.3)
        self.mouse_duration_spinbox.setSuffix(" seconds")

        self.scroll_direction_combo = QComboBox()
        self.scroll_direction_combo.addItems(["Up", "Down", "Left", "Right"])

        self.scroll_amount_spinbox = QSpinBox()
        self.scroll_amount_spinbox.setRange(1, 20)
        self.scroll_amount_spinbox.setValue(3)

        layout.addRow("Action:", self.mouse_action_combo)
        layout.addRow("X Position:", self.mouse_x_spinbox)
        layout.addRow("Y Position:", self.mouse_y_spinbox)
        layout.addRow("From X (Drag):", self.drag_from_x_spinbox)
        layout.addRow("From Y (Drag):", self.drag_from_y_spinbox)
        layout.addRow("Button:", self.mouse_button_combo)
        layout.addRow("Click Count:", self.mouse_clicks_spinbox)
        layout.addRow("Duration:", self.mouse_duration_spinbox)
        layout.addRow("Scroll Direction:", self.scroll_direction_combo)
        layout.addRow("Scroll Amount:", self.scroll_amount_spinbox)

        # Initialize mouse field visibility by action
        self.update_mouse_field_visibility()

        return widget

    def create_keyboard_tab(self) -> QWidget:
        """Create keyboard action configuration tab"""
        widget = QWidget()
        layout = QFormLayout(widget)

        self.keyboard_action_combo = QComboBox()
        keyboard_actions = ACTION_TYPES_CONFIG.get('keyboard', {}).get('actions', [])
        self.keyboard_action_combo.addItems([action.replace('_', ' ').title() for action in keyboard_actions])

        self.keys_edit = QLineEdit()
        self.keys_edit.setPlaceholderText("e.g., ctrl+c, enter, f1")

        self.text_edit = QTextEdit()
        self.text_edit.setMaximumHeight(80)
        self.text_edit.setPlaceholderText("Text to type...")

        self.key_interval_spinbox = QDoubleSpinBox()
        self.key_interval_spinbox.setRange(0.0, 1.0)
        self.key_interval_spinbox.setValue(0.05)
        self.key_interval_spinbox.setSuffix(" seconds")

        layout.addRow("Action:", self.keyboard_action_combo)
        layout.addRow("Keys:", self.keys_edit)
        layout.addRow("Text:", self.text_edit)
        layout.addRow("Key Interval:", self.key_interval_spinbox)

        # Toggle field visibility based on selected keyboard action
        self.keyboard_action_combo.currentTextChanged.connect(self.update_keyboard_field_visibility)
        self.update_keyboard_field_visibility()

        return widget

    def create_application_tab(self) -> QWidget:
        """Create application action configuration tab"""
        widget = QWidget()
        layout = QFormLayout(widget)

        self.app_action_combo = QComboBox()
        app_actions = ACTION_TYPES_CONFIG.get('application', {}).get('actions', [])
        self.app_action_combo.addItems([action.replace('_', ' ').title() for action in app_actions])

        self.app_path_edit = QLineEdit()

        self.app_browse_button = QPushButton("Browse...")

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.app_path_edit)
        path_layout.addWidget(self.app_browse_button)

        self.app_args_edit = QLineEdit()
        self.app_args_edit.setPlaceholderText("Command line arguments (optional)")

        self.app_workdir_edit = QLineEdit()
        self.app_workdir_edit.setPlaceholderText("Working directory (optional)")

        layout.addRow("Action:", self.app_action_combo)
        layout.addRow("Application Path:", path_layout)
        layout.addRow("Arguments:", self.app_args_edit)
        layout.addRow("Working Directory:", self.app_workdir_edit)

        return widget

    def create_macro_tab(self) -> QWidget:
        """Create macro action configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Macro settings
        settings_layout = QFormLayout()

        self.macro_loop_spinbox = QSpinBox()
        self.macro_loop_spinbox.setRange(1, 100)
        self.macro_loop_spinbox.setValue(1)

        self.macro_delay_spinbox = QDoubleSpinBox()
        self.macro_delay_spinbox.setRange(0.0, 10.0)
        self.macro_delay_spinbox.setValue(0.1)
        self.macro_delay_spinbox.setSuffix(" seconds")

        settings_layout.addRow("Loop Count:", self.macro_loop_spinbox)
        settings_layout.addRow("Delay Between Actions:", self.macro_delay_spinbox)

        layout.addLayout(settings_layout)

        # Macro sequence
        sequence_group = QGroupBox("Action Sequence")
        sequence_layout = QVBoxLayout(sequence_group)

        self.macro_table = QTableWidget()
        self.macro_table.setColumnCount(3)
        self.macro_table.setHorizontalHeaderLabels(["Order", "Action Type", "Description"])
        self.macro_table.horizontalHeader().setStretchLastSection(True)

        sequence_layout.addWidget(self.macro_table)

        # Macro buttons
        macro_buttons_layout = QHBoxLayout()
        # Recording controls (macro)
        self.record_button = QPushButton("Record")
        self.stop_record_button = QPushButton("Stop")
        self.stop_record_button.setEnabled(False)
        macro_buttons_layout.addWidget(self.record_button)
        macro_buttons_layout.addWidget(self.stop_record_button)


        self.add_action_button = QPushButton("Add Action")
        self.edit_action_button = QPushButton("Edit Action")
        self.remove_action_button = QPushButton("Remove Action")
        self.clear_all_button = QPushButton("Clear All")
        self.move_up_button = QPushButton("Move Up")
        self.move_down_button = QPushButton("Move Down")

        macro_buttons_layout.addWidget(self.add_action_button)
        macro_buttons_layout.addWidget(self.edit_action_button)
        macro_buttons_layout.addWidget(self.remove_action_button)
        macro_buttons_layout.addWidget(self.clear_all_button)
        macro_buttons_layout.addStretch()
        macro_buttons_layout.addWidget(self.move_up_button)
        macro_buttons_layout.addWidget(self.move_down_button)

        sequence_layout.addLayout(macro_buttons_layout)
        layout.addWidget(sequence_group)

        return widget

    def setup_connections(self):
        """Setup signal connections"""
        # Gesture selection (GFLOW-18: Removed profile selection)
        self.gesture_type_combo.currentTextChanged.connect(self.load_available_gestures)
        self.gesture_combo.currentTextChanged.connect(self.on_gesture_selected)

        # Action type selection
        self.action_type_group.buttonClicked.connect(self.on_action_type_changed)

        # Tab change handling
        self.action_tabs.currentChanged.connect(self.on_tab_changed)

        # Application browse button
        self.app_browse_button.clicked.connect(self.browse_application)

        # Mouse action-specific visibility
        self.mouse_action_combo.currentTextChanged.connect(self.on_mouse_action_changed)

        # Mapping table selection
        self.mappings_table.itemSelectionChanged.connect(self.on_mapping_selected)
        # Macro recording
        self.record_button.clicked.connect(self.start_macro_recording)
        self.stop_record_button.clicked.connect(self.stop_macro_recording)


        # Main buttons
        self.save_button.clicked.connect(self.save_mapping)
        self.test_button.clicked.connect(self.test_action)
        self.delete_button.clicked.connect(self.delete_mapping)
        self.close_button.clicked.connect(self.close)

        # Macro sequence buttons
        self.add_action_button.clicked.connect(self.add_macro_action)
        self.edit_action_button.clicked.connect(self.edit_macro_action)
        self.remove_action_button.clicked.connect(self.remove_macro_action)
        self.clear_all_button.clicked.connect(self.clear_all_macro_actions)
        self.move_up_button.clicked.connect(self.move_macro_action_up)
        self.move_down_button.clicked.connect(self.move_macro_action_down)

    def update_profile_info(self):
        """GFLOW-18: Update profile information display"""
        if self.profile_manager:
            current_profile = self.profile_manager.get_current_profile()
            if current_profile:
                profile_text = f"Active: {current_profile.name}"
                if current_profile.is_default:
                    profile_text += " (Default)"

                # Add mapping count
                mapping_count = len(self.mapping_manager.get_all_mappings(enabled_only=False))
                profile_text += f"\nMappings: {mapping_count}"

                self.profile_info_label.setText(profile_text)
            else:
                self.profile_info_label.setText("No active profile")
        else:
            # Fallback to old system
            current_profile = self.mapping_manager.get_current_profile_name()
            mapping_count = len(self.mapping_manager.get_all_mappings(enabled_only=False))
            self.profile_info_label.setText(f"Profile: {current_profile}\nMappings: {mapping_count}")

    def load_available_gestures(self):
        """Load available gestures based on selected type"""
        self.gesture_combo.clear()

        gesture_type = self.gesture_type_combo.currentText().lower()

        if gesture_type == "predefined":
            # Load predefined gestures
            for gesture_id, gesture_data in PREDEFINED_GESTURES.items():
                if gesture_data.get('enabled', True):
                    self.gesture_combo.addItem(gesture_data['name'], gesture_id)

        elif gesture_type == "custom":
            # Load custom gestures
            custom_gestures = self.custom_gesture_manager.get_gesture_list()
            for gesture_data in custom_gestures:
                if gesture_data.get('is_trained', False):
                    gesture_name = gesture_data['name']
                    self.gesture_combo.addItem(gesture_name, gesture_name)

    def load_existing_mappings(self):
        """Load existing mappings into the table"""
        self.mappings_table.setRowCount(0)

        mappings = self.mapping_manager.get_all_mappings(enabled_only=False)

        for mapping in mappings:
            row = self.mappings_table.rowCount()
            self.mappings_table.insertRow(row)

            # Gesture name
            gesture_item = QTableWidgetItem(mapping.gesture_name)
            gesture_item.setData(Qt.UserRole, mapping.id)
            self.mappings_table.setItem(row, 0, gesture_item)

            # Action type
            action_type_item = QTableWidgetItem(f"{mapping.action.type.value}.{mapping.action.subtype}")
            self.mappings_table.setItem(row, 1, action_type_item)

            # Enabled status
            enabled_item = QTableWidgetItem("Yes" if mapping.enabled else "No")
            self.mappings_table.setItem(row, 2, enabled_item)

            # Use count
            uses_item = QTableWidgetItem(str(mapping.use_count))
            self.mappings_table.setItem(row, 3, uses_item)

        # GFLOW-18: Update profile info when mappings are loaded
        self.update_profile_info()

    def on_gesture_selected(self):
        """Handle gesture selection"""
        self.update_form_state()

    def on_action_type_changed(self):
        """Handle action type change"""
        selected_button = self.action_type_group.checkedButton()
        if selected_button:
            action_type = selected_button.property('action_type')

            # Switch to appropriate tab
            tab_map = {
                'mouse': 0,
                'keyboard': 1,
                'application': 2,
                'macro': 3
            }

            if action_type in tab_map:
                self.action_tabs.setCurrentIndex(tab_map[action_type])

        self.update_form_state()

    def on_mapping_selected(self):
        """Handle mapping selection from table"""
        selected_items = self.mappings_table.selectedItems()
        if selected_items:
            mapping_id = selected_items[0].data(Qt.UserRole)
            self.load_mapping(mapping_id)
        else:
            self.clear_form()

    def load_mapping(self, mapping_id: str):
        """Load a mapping into the form"""
        mapping = self.mapping_manager.mappings.get(mapping_id)
        if not mapping:
            return

        self.current_mapping_id = mapping_id

        # Set gesture selection
        gesture_type = "Predefined" if mapping.gesture_type == "predefined" else "Custom"
        self.gesture_type_combo.setCurrentText(gesture_type)
        self.load_available_gestures()

        # Find and select the gesture
        for i in range(self.gesture_combo.count()):
            if self.gesture_combo.itemData(i) == mapping.gesture_name:
                self.gesture_combo.setCurrentIndex(i)
                break

        # Set action type
        action_type = mapping.action.type.value
        for button in self.action_type_group.buttons():
            if button.property('action_type') == action_type:
                button.setChecked(True)
                break

        self.on_action_type_changed()

        # Set action settings
        self.action_name_edit.setText(mapping.action.name)
        self.action_description_edit.setPlainText(mapping.action.description)
        self.enabled_checkbox.setChecked(mapping.enabled)
        self.confirmation_checkbox.setChecked(mapping.action.requires_confirmation)
        self.timeout_spinbox.setValue(mapping.action.timeout)

        # Populate type-specific fields
        if mapping.action.type == ActionType.MOUSE:
            try:
                # Select mouse subtype
                self.mouse_action_combo.setCurrentText(mapping.action.subtype.replace('_', ' ').title())
            except Exception:
                pass
            params: MouseActionParameters = mapping.action.parameters
            # Target coordinates
            if getattr(params, 'x', None) is not None:
                self.mouse_x_spinbox.setValue(params.x)
            else:
                self.mouse_x_spinbox.setValue(0)
            if getattr(params, 'y', None) is not None:
                self.mouse_y_spinbox.setValue(params.y)
            else:
                self.mouse_y_spinbox.setValue(0)
            # Drag start coordinates
            if getattr(params, 'from_x', None) is not None:
                self.drag_from_x_spinbox.setValue(params.from_x)
            else:
                self.drag_from_x_spinbox.setValue(0)
            if getattr(params, 'from_y', None) is not None:
                self.drag_from_y_spinbox.setValue(params.from_y)
            else:
                self.drag_from_y_spinbox.setValue(0)
            # Click specifics
            self.mouse_button_combo.setCurrentText(getattr(params, 'button', 'left').title())
            self.mouse_clicks_spinbox.setValue(getattr(params, 'clicks', 1) or 1)
            # Duration
            self.mouse_duration_spinbox.setValue(getattr(params, 'duration', 0.3) or 0.3)
            # Scroll
            self.scroll_direction_combo.setCurrentText(getattr(params, 'scroll_direction', 'Up').title())
            self.scroll_amount_spinbox.setValue(getattr(params, 'scroll_amount', 3) or 3)
            # Update visibility for selected mouse subtype
            self.update_mouse_field_visibility()

        elif mapping.action.type == ActionType.KEYBOARD:
            try:
                self.keyboard_action_combo.setCurrentText(mapping.action.subtype.replace('_', ' ').title())
            except Exception:
                pass
            params: KeyboardActionParameters = mapping.action.parameters
            # Keys may be str or list
            keys_value = params.keys if isinstance(params.keys, list) else [params.keys] if getattr(params, 'keys', None) else []
            self.keys_edit.setText('+'.join([str(k) for k in keys_value]) if keys_value else "")
            self.text_edit.setPlainText(getattr(params, 'text', '') or '')
            self.key_interval_spinbox.setValue(getattr(params, 'interval', 0.05) or 0.05)
            # Update visibility
            self.update_keyboard_field_visibility()

        elif mapping.action.type == ActionType.APPLICATION:
            try:
                self.app_action_combo.setCurrentText(mapping.action.subtype.replace('_', ' ').title())
            except Exception:
                pass
            params: ApplicationActionParameters = mapping.action.parameters
            self.app_path_edit.setText(getattr(params, 'path', '') or '')
            args = getattr(params, 'arguments', []) or []
            self.app_args_edit.setText(' '.join(args))
            self.app_workdir_edit.setText(getattr(params, 'working_directory', '') or '')

        # Load macro details if applicable
        if mapping.action.type == ActionType.MACRO:
            params: MacroActionParameters = mapping.action.parameters
            self.macro_loop_spinbox.setValue(getattr(params, 'loop_count', 1) or 1)
            self.macro_delay_spinbox.setValue(getattr(params, 'delay_between_actions', 0.1) or 0.1)
            self.macro_sequence = list(getattr(params, 'sequence', []) or [])
            self.refresh_macro_table()
        else:
            self.macro_sequence = []
            self.refresh_macro_table()

        self.update_form_state()

    def clear_form(self):
        """Clear the form"""
        self.current_mapping_id = None

        # Clear gesture selection
        self.gesture_combo.setCurrentIndex(-1)

        # Clear action type selection
        for button in self.action_type_group.buttons():
            button.setChecked(False)

        # Clear action settings
        self.action_name_edit.clear()
        self.action_description_edit.clear()
        self.enabled_checkbox.setChecked(True)
        self.confirmation_checkbox.setChecked(False)
        self.timeout_spinbox.setValue(5.0)

        # Clear application fields
        try:
            self.app_action_combo.setCurrentIndex(0)
        except Exception:
            pass
        self.app_path_edit.clear()
        self.app_args_edit.clear()
        self.app_workdir_edit.clear()

        # Clear macro sequence UI
        self.macro_loop_spinbox.setValue(1)
        self.macro_delay_spinbox.setValue(0.1)
        self.macro_sequence = []
        self.refresh_macro_table()

        self.update_form_state()

    def update_form_state(self):
        """Update form state based on current selections"""
        has_gesture = self.gesture_combo.currentIndex() >= 0
        has_action_type = self.action_type_group.checkedButton() is not None

        # Enable/disable save button
        self.save_button.setEnabled(has_gesture and has_action_type)

        # Enable/disable test button
        self.test_button.setEnabled(has_gesture and has_action_type)

        # Enable/disable delete button
        self.delete_button.setEnabled(self.current_mapping_id is not None)

    def update_keyboard_field_visibility(self):
        """Show only relevant keyboard fields per selected action"""
        subtype = self.keyboard_action_combo.currentText().lower().replace(' ', '_')
        is_key_action = subtype in ('key_press', 'key_combination')
        is_type_text = subtype == 'type_text'

        # Get widgets directly we own
        # Keys row visibility
        keys_visible = is_key_action
        self.keys_edit.setVisible(keys_visible)
        # Text row visibility
        text_visible = is_type_text
        self.text_edit.setVisible(text_visible)
        # Keep interval visible for both kinds
        self.key_interval_spinbox.setVisible(True)

        # Also toggle corresponding labels by scanning the keyboard tab's form layout
        # Find the keyboard tab's form layout - handle case where keyboard_tab might not exist yet
        keyboard_form = None
        if hasattr(self, 'keyboard_tab') and self.keyboard_tab:
            keyboard_form = self.keyboard_tab.layout()
        elif hasattr(self, 'keys_edit') and self.keys_edit.parent():
            # Fallback: get layout from the keys_edit parent widget
            keyboard_form = self.keys_edit.parent().layout()

        if isinstance(keyboard_form, QFormLayout):
            try:
                # Keys row label likely at index 1
                label_item = keyboard_form.itemAt(1, QFormLayout.LabelRole)
                if label_item and label_item.widget():
                    label_item.widget().setVisible(keys_visible)
                # Text row label likely at index 2
                label_item = keyboard_form.itemAt(2, QFormLayout.LabelRole)
                if label_item and label_item.widget():
                    label_item.widget().setVisible(text_visible)
            except Exception:
                pass

    def browse_application(self):
        """Browse for application executable"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Application", "",
            "Executable Files (*.exe);;All Files (*.*)"
        )

        if file_path:
            self.app_path_edit.setText(file_path)

    def on_mouse_action_changed(self):
        """Update visibility of mouse fields based on selected mouse action"""
        self.update_mouse_field_visibility()

    def on_tab_changed(self, index):
        """Handle tab change to update field visibility"""
        # Get the tab widget text to determine which tab was selected
        tab_text = self.action_tabs.tabText(index).lower()

        if tab_text == "keyboard":
            # Update keyboard field visibility when switching to keyboard tab
            self.update_keyboard_field_visibility()
        elif tab_text == "mouse":
            # Update mouse field visibility when switching to mouse tab
            self.update_mouse_field_visibility()

    def update_mouse_field_visibility(self):
        """Show parameters relevant to chosen mouse action.
        - click: show Button, Click Count, Duration; hide Scroll fields
        - move_to: show X, Y, Duration; hide Button/Clicks/Scroll
        - drag: show X, Y, Duration (to be used as 'to' position UI for now); hide Button/Clicks/Scroll
        - scroll: show Scroll Direction/Amount/Duration; hide Button/Clicks/X/Y
        """
        current = self.mouse_action_combo.currentText().lower().replace(' ', '_')

        def set_row_visible(form: QFormLayout, row_index: int, visible: bool):
            label_item = form.itemAt(row_index, QFormLayout.LabelRole)
            field_item = form.itemAt(row_index, QFormLayout.FieldRole)
            if label_item and label_item.widget():
                label_item.widget().setVisible(visible)
            if field_item and field_item.widget():
                field_item.widget().setVisible(visible)

        # Row indices per creation order:
        # 0: Action, 1: X, 2: Y, 3: From X, 4: From Y, 5: Button, 6: Click Count, 7: Duration, 8: Scroll Direction, 9: Scroll Amount
        visible_map = {
            'click':   {1: False,2: False,3: False,4: False,5: True, 6: True, 7: True, 8: False,9: False},
            'move_to': {1: True, 2: True, 3: False,4: False,5: False,6: False,7: True, 8: False,9: False},
            'drag':    {1: True, 2: True, 3: True, 4: True, 5: False,6: False,7: True, 8: False,9: False},
            'scroll':  {1: False,2: False,3: False,4: False,5: False,6: False,7: True, 8: True, 9: True},
        }
        state = visible_map.get(current, {1: True,2: True,3: False,4: False,5: True,6: True,7: True,8: False,9: False})

        # Apply visibility; always keep action row (0) visible
        for row_index, visible in state.items():
            set_row_visible(self.mouse_form_layout, row_index, visible)

    def create_action_from_form(self) -> Optional[Action]:
        """Create an Action object from the current form data"""
        try:
            # Get selected action type
            selected_button = self.action_type_group.checkedButton()
            if not selected_button:
                return None

            action_type_str = selected_button.property('action_type')
            action_type = ActionType(action_type_str)

            # Create parameters based on action type
            if action_type == ActionType.MOUSE:
                subtype = self.mouse_action_combo.currentText().lower().replace(' ', '_')
                # Build parameters based on subtype semantics
                if subtype == 'click':
                    parameters = MouseActionParameters(
                        x=None,  # Click uses current cursor position by default
                        y=None,
                        button=self.mouse_button_combo.currentText().lower(),
                        clicks=self.mouse_clicks_spinbox.value(),
                        duration=self.mouse_duration_spinbox.value(),
                    )
                elif subtype == 'move_to':
                    parameters = MouseActionParameters(
                        x=self.mouse_x_spinbox.value() if self.mouse_x_spinbox.value() > 0 else None,
                        y=self.mouse_y_spinbox.value() if self.mouse_y_spinbox.value() > 0 else None,
                        duration=self.mouse_duration_spinbox.value(),
                    )
                elif subtype == 'drag':
                    parameters = MouseActionParameters(
                        from_x=self.drag_from_x_spinbox.value() if self.drag_from_x_spinbox.value() > 0 else None,
                        from_y=self.drag_from_y_spinbox.value() if self.drag_from_y_spinbox.value() > 0 else None,
                        to_x=self.mouse_x_spinbox.value() if self.mouse_x_spinbox.value() > 0 else None,
                        to_y=self.mouse_y_spinbox.value() if self.mouse_y_spinbox.value() > 0 else None,
                        duration=self.mouse_duration_spinbox.value(),
                    )
                elif subtype == 'scroll':
                    parameters = MouseActionParameters(
                        scroll_direction=self.scroll_direction_combo.currentText().lower(),
                        scroll_amount=self.scroll_amount_spinbox.value(),
                        duration=self.mouse_duration_spinbox.value(),
                    )
                else:
                    parameters = MouseActionParameters()

            elif action_type == ActionType.KEYBOARD:
                subtype = self.keyboard_action_combo.currentText().lower().replace(' ', '_')
                keys_text = self.keys_edit.text().strip()
                if subtype in ('key_press', 'key_combination'):
                    # Parse keys
                    if '+' in keys_text:
                        parts = [k.strip() for k in keys_text.split('+') if k.strip()]
                        modifiers = parts[:-1] if len(parts) > 1 else []
                        main_keys = [parts[-1]] if parts else []
                    else:
                        modifiers = []
                        main_keys = [keys_text] if keys_text else []
                    parameters = KeyboardActionParameters(
                        keys=main_keys,
                        text="",
                        modifiers=modifiers,
                        interval=self.key_interval_spinbox.value()
                    )
                elif subtype == 'type_text':
                    parameters = KeyboardActionParameters(
                        keys="",
                        text=self.text_edit.toPlainText(),
                        modifiers=[],
                        interval=self.key_interval_spinbox.value()
                    )
                else:
                    parameters = KeyboardActionParameters()

            elif action_type == ActionType.APPLICATION:
                subtype = self.app_action_combo.currentText().lower().replace(' ', '_')
                args_text = self.app_args_edit.text().strip()
                arguments = args_text.split() if args_text else []

                parameters = ApplicationActionParameters(
                    path=self.app_path_edit.text().strip(),
                    arguments=arguments,
                    working_directory=self.app_workdir_edit.text().strip()
                )

            else:
                # Macro action
                subtype = "execute"
                parameters = MacroActionParameters(
                    sequence=list(self.macro_sequence),
                    loop_count=self.macro_loop_spinbox.value(),
                    delay_between_actions=self.macro_delay_spinbox.value(),
                )

            # Create action
            action = Action(
                id=str(uuid.uuid4()),
                type=action_type,
                subtype=subtype,
                parameters=parameters,
                name=self.action_name_edit.text().strip(),
                description=self.action_description_edit.toPlainText().strip(),
                enabled=self.enabled_checkbox.isChecked(),
                requires_confirmation=self.confirmation_checkbox.isChecked(),
                timeout=self.timeout_spinbox.value()
            )

            return action

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to create action: {str(e)}")
            return None

    def refresh_macro_table(self):
        """Refresh the macro sequence table from self.macro_sequence"""
        self.macro_table.setRowCount(0)
        for index, action_data in enumerate(self.macro_sequence, start=1):
            try:
                sub_action = Action.from_dict(action_data)
                row = self.macro_table.rowCount()
                self.macro_table.insertRow(row)
                # Order
                self.macro_table.setItem(row, 0, QTableWidgetItem(str(index)))
                # Action type
                self.macro_table.setItem(row, 1, QTableWidgetItem(f"{sub_action.type.value}.{sub_action.subtype}"))
                # Description
                description = sub_action.name or sub_action.description or ""
                if not description:
                    description = f"{sub_action.type.value.title()} {sub_action.subtype.replace('_',' ').title()}"
                self.macro_table.setItem(row, 2, QTableWidgetItem(description))
            except Exception:
                # Skip invalid entries gracefully
                continue

    def add_macro_action(self):
        dialog = SubActionDialog(self)
        if dialog.exec() == QDialog.Accepted:
            action = dialog.get_action()
            if action:
                # Validate sub-action using the main validator
                is_valid, error = self.validator.validate_action(action)
                if not is_valid:
                    QMessageBox.warning(self, "Validation Error", f"Sub-action invalid: {error}")
                    return
                self.macro_sequence.append(action.to_dict())
                self.refresh_macro_table()

    def edit_macro_action(self):
        row = self.macro_table.currentRow()
        if row < 0 or row >= len(self.macro_sequence):
            return
        try:
            existing = Action.from_dict(self.macro_sequence[row])
        except Exception:
            existing = None
        dialog = SubActionDialog(self, existing)
        if dialog.exec() == QDialog.Accepted:
            action = dialog.get_action()
            if action:
                is_valid, error = self.validator.validate_action(action)
                if not is_valid:
                    QMessageBox.warning(self, "Validation Error", f"Sub-action invalid: {error}")
                    return
                self.macro_sequence[row] = action.to_dict()
                self.refresh_macro_table()
    def start_macro_recording(self):
        if not PYNPUT_LOCAL_AVAILABLE:
            QMessageBox.warning(self, "Recorder Unavailable", "pynput not available. Install with: pip install pynput")
            return
        if self.is_recording_macro:
            return
        self.is_recording_macro = True
        self.record_button.setEnabled(False)
        self.stop_record_button.setEnabled(True)
        self._last_click_time = time.time()

        # Handlers
        def on_click(x, y, button, pressed):
            try:
                if not self.is_recording_macro:
                    return False
                if not pressed:
                    # We record on release to avoid duplicates
                    params = MouseActionParameters(x=int(x), y=int(y), button=str(button).split('.')[-1], clicks=1, duration=0)
                    action = Action(
                        id=str(uuid.uuid4()),
                        type=ActionType.MOUSE,
                        subtype=MouseAction.CLICK.value,
                        parameters=params,
                        name=f"Click {params.button.title()}",
                        description=f"Click at ({params.x},{params.y})"
                    )
                    is_valid, error = self.validator.validate_action(action)
                    if is_valid:
                        self.macro_sequence.append(action.to_dict())
                        self.refresh_macro_table()
                return True
            except Exception:
                return True

        def on_move(x, y):
            # Do not record every move; we can capture at release
            return True

        def on_scroll(x, y, dx, dy):
            try:
                if not self.is_recording_macro:
                    return False
                direction = 'up' if dy > 0 else 'down'
                params = MouseActionParameters(scroll_direction=direction, scroll_amount=abs(int(dy)) or 1, duration=0)
                action = Action(
                    id=str(uuid.uuid4()), type=ActionType.MOUSE,
                    subtype=MouseAction.SCROLL.value, parameters=params,
                    name=f"Scroll {direction.title()}", description=f"Scroll {direction} {params.scroll_amount}"
                )
                is_valid, _ = self.validator.validate_action(action)
                if is_valid:
                    self.macro_sequence.append(action.to_dict())
                    self.refresh_macro_table()
                return True
            except Exception:
                return True

        def on_press(key):
            try:
                if not self.is_recording_macro:
                    return False
                # Normalize key/modifiers
                key_name = None
                modifiers = []
                if hasattr(key, 'char') and key.char:
                    key_name = key.char
                else:
                    key_name = str(key).split('.')[-1]
                params = KeyboardActionParameters(keys=[key_name], text="", modifiers=modifiers, interval=0.0)
                action = Action(
                    id=str(uuid.uuid4()), type=ActionType.KEYBOARD,
                    subtype=KeyboardAction.KEY_PRESS.value, parameters=params,
                    name=f"Key {key_name}", description=f"Key press: {key_name}"
                )
                is_valid, _ = self.validator.validate_action(action)
                if is_valid:
                    self.macro_sequence.append(action.to_dict())
                    self.refresh_macro_table()
                return True
            except Exception:
                return True

        # Start listeners
        try:
            self._mouse_listener = MouseListener(on_click=on_click, on_move=on_move, on_scroll=on_scroll)
            self._keyboard_listener = KeyboardListener(on_press=on_press)
            self._mouse_listener.start()
            self._keyboard_listener.start()
        except Exception as e:
            QMessageBox.warning(self, "Recorder Error", f"Failed to start recorder: {e}")
            self.is_recording_macro = False
            self.record_button.setEnabled(True)
            self.stop_record_button.setEnabled(False)

    def stop_macro_recording(self):
        if not self.is_recording_macro:
            return
        self.is_recording_macro = False
        self.record_button.setEnabled(True)
        self.stop_record_button.setEnabled(False)
        try:
            if self._mouse_listener:
                self._mouse_listener.stop()
                self._mouse_listener = None
            if self._keyboard_listener:
                self._keyboard_listener.stop()
                self._keyboard_listener = None
        except Exception:
            pass
        # Refresh table
        self.refresh_macro_table()


    def remove_macro_action(self):
        row = self.macro_table.currentRow()
        if row < 0 or row >= len(self.macro_sequence):
            return
        del self.macro_sequence[row]
        self.refresh_macro_table()

    def clear_all_macro_actions(self):
        """Clear all actions from the macro sequence"""
        if not self.macro_sequence:
            return
        reply = QMessageBox.question(
            self,
            "Clear All Macro Actions",
            "Are you sure you want to clear all actions from the macro sequence?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self.macro_sequence = []
        self.refresh_macro_table()

    def move_macro_action_up(self):
        row = self.macro_table.currentRow()
        if row <= 0 or row >= len(self.macro_sequence):
            return
        self.macro_sequence[row-1], self.macro_sequence[row] = self.macro_sequence[row], self.macro_sequence[row-1]
        self.refresh_macro_table()
        self.macro_table.selectRow(row-1)

    def move_macro_action_down(self):
        row = self.macro_table.currentRow()
        if row < 0 or row >= len(self.macro_sequence)-1:
            return
        self.macro_sequence[row+1], self.macro_sequence[row] = self.macro_sequence[row], self.macro_sequence[row+1]
        self.refresh_macro_table()
        self.macro_table.selectRow(row+1)

    def save_mapping(self):
        """Save the current mapping"""
        try:
            # Get gesture information
            gesture_data = self.gesture_combo.currentData()
            gesture_display_name = self.gesture_combo.currentText()
            gesture_type = "predefined" if self.gesture_type_combo.currentText() == "Predefined" else "custom"

            if not gesture_data or not gesture_display_name:
                QMessageBox.warning(self, "Error", "Please select a gesture.")
                return

            # Use gesture_data (ID) for predefined gestures, display name for custom gestures
            if gesture_type == "predefined":
                gesture_name = gesture_data  # Use the gesture ID (e.g., "open_palm")
            else:
                gesture_name = gesture_display_name  # Use the display name for custom gestures

            # Create action
            action = self.create_action_from_form()
            if not action:
                QMessageBox.warning(self, "Error", "Please configure the action.")
                return

            # Validate action
            is_valid, error_message = self.validator.validate_action(action)
            if not is_valid:
                QMessageBox.warning(self, "Validation Error", f"Action validation failed:\n{error_message}")
                return

            # Check for confirmation if required
            if self.validator.requires_confirmation(action):
                reply = QMessageBox.question(
                    self, "Confirm Action",
                    f"This action requires confirmation due to security settings.\n\n"
                    f"Action: {action.type.value}.{action.subtype}\n"
                    f"Do you want to proceed?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                if reply != QMessageBox.Yes:
                    return

            # Save mapping
            if self.current_mapping_id:
                # Update existing mapping; also allow changing gesture assignment
                current_mapping = self.mapping_manager.mappings.get(self.current_mapping_id)

                # Determine if gesture changed
                gesture_changed = (
                    current_mapping and (
                        current_mapping.gesture_name != gesture_name or
                        current_mapping.gesture_type != gesture_type
                    )
                )

                if gesture_changed:
                    # Check for conflict on the target gesture
                    conflict = self.mapping_manager.get_mapping_for_gesture(gesture_name, gesture_type)
                    if conflict and conflict.id != self.current_mapping_id:
                        reply = QMessageBox.question(
                            self, "Replace Existing Mapping",
                            f"Another enabled mapping already exists for gesture '{gesture_name}'.\n\n"
                            f"Existing action: {conflict.action.name or conflict.action.subtype}\n"
                            f"Action type: {conflict.action.type.value}.{conflict.action.subtype}\n\n"
                            f"Do you want to overwrite it with the current action?",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No
                        )
                        if reply != QMessageBox.Yes:
                            return

                        # Overwrite the conflicting mapping and remove the old one
                        success = self.mapping_manager.update_mapping(
                            conflict.id,
                            action=action,
                            enabled=self.enabled_checkbox.isChecked(),
                            gesture_name=gesture_name,
                            gesture_type=gesture_type
                        )

                        if success:
                            # Remove the old mapping
                            if self.current_mapping_id in self.mapping_manager.mappings:
                                self.mapping_manager.remove_mapping(self.current_mapping_id)
                            self.current_mapping_id = conflict.id
                            QMessageBox.information(self, "Success", "Mapping updated successfully!")
                            self.mapping_updated.emit(conflict.id)
                        else:
                            QMessageBox.warning(self, "Error", "Failed to update mapping.")
                    else:
                        # No conflict: update current mapping including gesture fields
                        success = self.mapping_manager.update_mapping(
                            self.current_mapping_id,
                            action=action,
                            enabled=self.enabled_checkbox.isChecked(),
                            gesture_name=gesture_name,
                            gesture_type=gesture_type
                        )
                        if success:
                            QMessageBox.information(self, "Success", "Mapping updated successfully!")
                            self.mapping_updated.emit(self.current_mapping_id)
                        else:
                            QMessageBox.warning(self, "Error", "Failed to update mapping.")
                else:
                    # Gesture unchanged: update action/enabled only
                    success = self.mapping_manager.update_mapping(
                        self.current_mapping_id,
                        action=action,
                        enabled=self.enabled_checkbox.isChecked()
                    )
                    if success:
                        QMessageBox.information(self, "Success", "Mapping updated successfully!")
                        self.mapping_updated.emit(self.current_mapping_id)
                    else:
                        QMessageBox.warning(self, "Error", "Failed to update mapping.")
            else:
                # Check if mapping already exists
                existing_mapping = self.mapping_manager.get_mapping_for_gesture(gesture_name, gesture_type)
                if existing_mapping:
                    reply = QMessageBox.question(
                        self, "Mapping Already Exists",
                        f"A mapping already exists for gesture '{gesture_name}'.\n\n"
                        f"Current action: {existing_mapping.action.name}\n"
                        f"Action type: {existing_mapping.action.type.value}.{existing_mapping.action.subtype}\n\n"
                        f"Would you like to:\n"
                        f"• Yes: Update the existing mapping\n"
                        f"• No: Cancel and manually delete the existing mapping first",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )

                    if reply == QMessageBox.Yes:
                        # Update existing mapping
                        success = self.mapping_manager.update_mapping(
                            existing_mapping.id,
                            action=action,
                            enabled=self.enabled_checkbox.isChecked()
                        )

                        if success:
                            QMessageBox.information(self, "Success", "Mapping updated successfully!")
                            self.mapping_updated.emit(existing_mapping.id)
                            self.current_mapping_id = existing_mapping.id
                        else:
                            QMessageBox.warning(self, "Error", "Failed to update mapping.")
                    return

                # Create new mapping
                mapping_id = self.mapping_manager.add_mapping(gesture_name, gesture_type, action)

                if mapping_id:
                    QMessageBox.information(self, "Success", "Mapping created successfully!")
                    self.mapping_created.emit(mapping_id)
                    self.current_mapping_id = mapping_id
                else:
                    QMessageBox.warning(self, "Error", "Failed to create mapping. Please check if a mapping already exists for this gesture.")

            # Refresh the mappings table
            self.load_existing_mappings()
            self.update_form_state()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while saving:\n{str(e)}")

    def test_action(self):
        """Test the current action"""
        try:
            action = self.create_action_from_form()
            if not action:
                QMessageBox.warning(self, "Error", "Please configure the action first.")
                return

            # Validate action
            is_valid, error_message = self.validator.validate_action(action)
            if not is_valid:
                QMessageBox.warning(self, "Validation Error", f"Action validation failed:\n{error_message}")
                return

            # Confirm test execution
            reply = QMessageBox.question(
                self, "Test Action",
                f"This will execute the action for testing purposes.\n\n"
                f"Action: {action.type.value}.{action.subtype}\n"
                f"Are you sure you want to proceed?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            # Show progress
            self.preview_progress.setVisible(True)
            self.preview_progress.setRange(0, 0)  # Indeterminate progress
            self.test_button.setEnabled(False)

            # Execute action in worker thread
            self.preview_worker = ActionPreviewWorker(action, self.action_executor)
            self.preview_worker.preview_completed.connect(self.on_test_completed)
            self.preview_worker.start()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred during testing:\n{str(e)}")

    def on_test_completed(self, success: bool, message: str):
        """Handle test completion"""
        self.preview_progress.setVisible(False)
        self.test_button.setEnabled(True)

        if success:
            QMessageBox.information(self, "Test Result", f"Action executed successfully!\n\n{message}")
        else:
            QMessageBox.warning(self, "Test Result", f"Action execution failed:\n\n{message}")

    def delete_mapping(self):
        """Delete the current mapping"""
        if not self.current_mapping_id:
            return

        mapping = self.mapping_manager.mappings.get(self.current_mapping_id)
        if not mapping:
            return

        reply = QMessageBox.question(
            self, "Delete Mapping",
            f"Are you sure you want to delete the mapping for gesture '{mapping.gesture_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success = self.mapping_manager.remove_mapping(self.current_mapping_id)

            if success:
                QMessageBox.information(self, "Success", "Mapping deleted successfully!")
                self.load_existing_mappings()
                self.clear_form()
            else:
                QMessageBox.warning(self, "Error", "Failed to delete mapping.")

    def closeEvent(self, event):
        """Handle dialog close event"""
        # Shutdown action executor
        if hasattr(self, 'action_executor'):
            self.action_executor.shutdown()

        # Stop any running preview worker
        if self.preview_worker and self.preview_worker.isRunning():
            self.preview_worker.terminate()
            self.preview_worker.wait()

        event.accept()

    def refresh_for_profile_change(self):
        """GFLOW-18: Refresh dialog when profile changes"""
        self.load_available_gestures()
        self.load_existing_mappings()
        self.clear_form()
        self.update_profile_info()
