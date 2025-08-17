import os
import re
import json
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from config import ACTION_TYPES_CONFIG, ACTION_EXECUTION_CONFIG

class ActionType(Enum):
    """Enumeration of supported action types"""
    MOUSE = "mouse"
    KEYBOARD = "keyboard"
    APPLICATION = "application"
    MACRO = "macro"
    SYSTEM = "system"


class MouseAction(Enum):
    """Mouse action subtypes"""
    CLICK = "click"
    MOVE_TO = "move_to"
    DRAG = "drag"
    SCROLL = "scroll"


class KeyboardAction(Enum):
    """Keyboard action subtypes"""
    KEY_PRESS = "key_press"
    KEY_COMBINATION = "key_combination"
    TYPE_TEXT = "type_text"


class ApplicationAction(Enum):
    """Application action subtypes"""
    LAUNCH = "launch"
    CLOSE = "close"
    FOCUS = "focus"
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


@dataclass
class ActionParameters:
    """Base class for action parameters"""
    pass


@dataclass
class MouseActionParameters(ActionParameters):
    """Parameters for mouse actions"""
    x: Optional[int] = None
    y: Optional[int] = None
    from_x: Optional[int] = None
    from_y: Optional[int] = None
    to_x: Optional[int] = None
    to_y: Optional[int] = None
    button: str = "left"  # left, right, middle
    clicks: int = 1
    duration: float = 0.0
    scroll_direction: str = "up"  # up, down, left, right
    scroll_amount: int = 1


@dataclass
class KeyboardActionParameters(ActionParameters):
    """Parameters for keyboard actions"""
    keys: Union[str, List[str]] = ""
    text: str = ""
    modifiers: List[str] = None
    interval: float = 0.05


@dataclass
class ApplicationActionParameters(ActionParameters):
    """Parameters for application actions"""
    path: str = ""
    arguments: List[str] = None
    working_directory: str = ""
    window_title: str = ""
    process_name: str = ""


@dataclass
class MacroActionParameters(ActionParameters):
    """Parameters for macro actions"""
    sequence: List[Dict[str, Any]] = None
    loop_count: int = 1
    delay_between_actions: float = 0.1


@dataclass
class Action:
    """Represents a single action that can be executed"""
    id: str
    type: ActionType
    subtype: str
    parameters: ActionParameters
    name: str = ""
    description: str = ""
    enabled: bool = True
    requires_confirmation: bool = False
    timeout: float = 5.0
    created_date: str = ""
    
    def __post_init__(self):
        if not self.created_date:
            self.created_date = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert action to dictionary for serialization"""
        result = asdict(self)
        result['type'] = self.type.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Action':
        """Create action from dictionary"""
        action_type = ActionType(data['type'])
        
        # Create appropriate parameters object
        params_data = data.get('parameters', {})
        if action_type == ActionType.MOUSE:
            parameters = MouseActionParameters(**params_data)
        elif action_type == ActionType.KEYBOARD:
            parameters = KeyboardActionParameters(**params_data)
        elif action_type == ActionType.APPLICATION:
            parameters = ApplicationActionParameters(**params_data)
        elif action_type == ActionType.MACRO:
            parameters = MacroActionParameters(**params_data)
        else:
            parameters = ActionParameters()
        
        return cls(
            id=data['id'],
            type=action_type,
            subtype=data['subtype'],
            parameters=parameters,
            name=data.get('name', ''),
            description=data.get('description', ''),
            enabled=data.get('enabled', True),
            requires_confirmation=data.get('requires_confirmation', False),
            timeout=data.get('timeout', 5.0),
            created_date=data.get('created_date', '')
        )


@dataclass
class GestureActionMapping:
    """Represents a mapping between a gesture and an action"""
    id: str
    gesture_name: str
    gesture_type: str  # 'predefined' or 'custom'
    action: Action
    enabled: bool = True
    priority: int = 0
    context_filters: List[str] = None
    created_date: str = ""
    last_used: str = ""
    use_count: int = 0
    
    def __post_init__(self):
        if not self.created_date:
            self.created_date = datetime.now().isoformat()
        if self.context_filters is None:
            self.context_filters = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert mapping to dictionary for serialization"""
        result = asdict(self)
        result['action'] = self.action.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GestureActionMapping':
        """Create mapping from dictionary"""
        action = Action.from_dict(data['action'])
        
        return cls(
            id=data['id'],
            gesture_name=data['gesture_name'],
            gesture_type=data['gesture_type'],
            action=action,
            enabled=data.get('enabled', True),
            priority=data.get('priority', 0),
            context_filters=data.get('context_filters', []),
            created_date=data.get('created_date', ''),
            last_used=data.get('last_used', ''),
            use_count=data.get('use_count', 0)
        )


class ActionValidator:
    """Validates actions for security and correctness"""
    
    def __init__(self):
        self.config = ACTION_TYPES_CONFIG
        self.execution_config = ACTION_EXECUTION_CONFIG
    
    def validate_action(self, action: Action) -> Tuple[bool, str]:
        """
        Validate an action for security and correctness
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if action type is enabled
        action_type_config = self.config.get(action.type.value, {})
        if not action_type_config.get('enabled', False):
            return False, f"Action type '{action.type.value}' is disabled"
        
        # Check if subtype is allowed
        allowed_actions = action_type_config.get('actions', [])
        if action.subtype not in allowed_actions:
            return False, f"Action subtype '{action.subtype}' is not allowed for type '{action.type.value}'"
        
        # Type-specific validation
        if action.type == ActionType.MOUSE:
            return self._validate_mouse_action(action)
        elif action.type == ActionType.KEYBOARD:
            return self._validate_keyboard_action(action)
        elif action.type == ActionType.APPLICATION:
            return self._validate_application_action(action)
        elif action.type == ActionType.MACRO:
            return self._validate_macro_action(action)
        elif action.type == ActionType.SYSTEM:
            return self._validate_system_action(action)
        
        return True, ""
    
    def _validate_mouse_action(self, action: Action) -> Tuple[bool, str]:
        """Validate mouse action parameters"""
        params = action.parameters
        
        if action.subtype in [MouseAction.CLICK.value, MouseAction.MOVE_TO.value, MouseAction.DRAG.value]:
            if hasattr(params, 'x') and hasattr(params, 'y'):
                if params.x is not None and (params.x < 0 or params.x > 10000):
                    return False, "Mouse X coordinate out of reasonable range"
                if params.y is not None and (params.y < 0 or params.y > 10000):
                    return False, "Mouse Y coordinate out of reasonable range"

        if hasattr(params, 'button') and params.button not in ['left', 'right', 'middle']:
            return False, f"Invalid mouse button: {params.button}"
        
        return True, ""
    
    def _validate_keyboard_action(self, action: Action) -> Tuple[bool, str]:
        """Validate keyboard action parameters"""
        params = action.parameters
        dangerous_keys = self.config['keyboard'].get('dangerous_keys', [])
        
        if action.subtype in [KeyboardAction.KEY_PRESS.value, KeyboardAction.KEY_COMBINATION.value]:
            if hasattr(params, 'keys'):
                keys_str = str(params.keys).lower()
                for dangerous_key in dangerous_keys:
                    if dangerous_key.lower() in keys_str:
                        return False, f"Dangerous key combination detected: {dangerous_key}"
        
        if action.subtype == KeyboardAction.TYPE_TEXT.value:
            if hasattr(params, 'text') and len(params.text) > 1000:
                return False, "Text too long (max 1000 characters)"
        
        return True, ""
    
    def _validate_application_action(self, action: Action) -> Tuple[bool, str]:
        """Validate application action parameters"""
        params = action.parameters
        
        if action.subtype == ApplicationAction.LAUNCH.value:
            if not hasattr(params, 'path') or not params.path:
                return False, "Application path is required for launch action"
            
            # Check blocked paths
            blocked_paths = self.config['application'].get('blocked_paths', [])
            for blocked_path in blocked_paths:
                if blocked_path.lower() in params.path.lower():
                    return False, f"Application path is blocked: {blocked_path}"
            
            # Check allowed paths (if specified)
            allowed_paths = self.config['application'].get('allowed_paths', [])
            if allowed_paths:
                path_allowed = any(allowed_path.lower() in params.path.lower() 
                                 for allowed_path in allowed_paths)
                if not path_allowed:
                    return False, "Application path is not in allowed list"
        
        return True, ""
    
    def _validate_macro_action(self, action: Action) -> Tuple[bool, str]:
        """Validate macro action parameters"""
        params = action.parameters
        
        if hasattr(params, 'sequence') and params.sequence:
            max_length = self.config['macro'].get('max_sequence_length', 20)
            if len(params.sequence) > max_length:
                return False, f"Macro sequence too long (max {max_length} actions)"
            
            # Validate each action in the sequence
            for i, action_data in enumerate(params.sequence):
                try:
                    sub_action = Action.from_dict(action_data)
                    is_valid, error = self.validate_action(sub_action)
                    if not is_valid:
                        return False, f"Invalid action at position {i+1}: {error}"
                except Exception as e:
                    return False, f"Invalid action data at position {i+1}: {str(e)}"
        
        return True, ""
    
    def _validate_system_action(self, action: Action) -> Tuple[bool, str]:
        """Validate system action parameters"""
        # System actions are high-risk and require explicit validation
        if not self.config['system'].get('enabled', False):
            return False, "System actions are disabled for security"
        
        return True, ""
    
    def requires_confirmation(self, action: Action) -> bool:
        """Check if action requires user confirmation"""
        action_type_config = self.config.get(action.type.value, {})
        
        # Check type-level confirmation requirement
        if action_type_config.get('confirmation_required', False):
            return True
        
        # Check action-specific confirmation requirement
        if action.requires_confirmation:
            return True
        
        # Check global confirmation settings
        confirmation_config = self.execution_config.get('require_confirmation', {})
        
        if action.type == ActionType.APPLICATION and confirmation_config.get('application_launch', False):
            return True
        
        if action.type == ActionType.SYSTEM and confirmation_config.get('system_commands', False):
            return True
        
        return False
