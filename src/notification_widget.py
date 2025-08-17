"""
GFLOW-19: Visual Feedback Notification Widget

Provides non-intrusive visual notifications for gesture recognition events.
Features fade-in/fade-out animations and customizable positioning.
"""

import time
from typing import Optional, Tuple
from PySide6.QtWidgets import QLabel, QWidget, QGraphicsOpacityEffect
from PySide6.QtCore import QTimer, QPropertyAnimation, QEasingCurve, QRect, Qt, Signal
from PySide6.QtGui import QFont, QPalette
from config import VISUAL_FEEDBACK_CONFIG


class NotificationWidget(QLabel):
    """
    Custom notification widget for displaying gesture recognition feedback
    
    Features:
    - Auto-positioning based on configuration
    - Fade-in/fade-out animations
    - Auto-hide with configurable duration
    - Queue management for multiple notifications
    - Non-intrusive overlay design
    """
    
    # Signal emitted when notification is fully hidden
    notification_hidden = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # Configuration
        self.config = VISUAL_FEEDBACK_CONFIG
        
        # Animation and timing
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.hide_timer = QTimer()
        self.hide_timer.setSingleShot(True)
        
        # State tracking
        self.is_showing = False
        self.notification_queue = []
        
        # Setup widget
        self._setup_widget()
        self._setup_animations()
        self._connect_signals()
        
        # Initially hidden
        self.hide()
    
    def _setup_widget(self):
        """Setup widget appearance and properties"""
        # Widget properties
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        
        # Styling
        self._apply_styling()
        
        # Font
        font = QFont()
        font.setPointSize(self.config['notification_font_size'])
        font.setBold(self.config['notification_font_weight'] == 'bold')
        self.setFont(font)
    
    def _apply_styling(self):
        """Apply CSS styling to the notification"""
        style = f"""
        QLabel {{
            background-color: {self.config['notification_background_color']};
            color: {self.config['notification_text_color']};
            border: {self.config['notification_border_width']}px solid {self.config['notification_border_color']};
            border-radius: {self.config['notification_border_radius']}px;
            padding: {self.config['notification_padding']}px;
            font-weight: {self.config['notification_font_weight']};
            font-size: {self.config['notification_font_size']}px;
        }}
        """
        self.setStyleSheet(style)
    
    def _setup_animations(self):
        """Setup fade animations"""
        if not self.config['enable_notification_animations']:
            return
            
        # Fade animation setup
        self.fade_animation.setDuration(self.config['fade_in_duration'])
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad)
        
        # Animation finished handler
        self.fade_animation.finished.connect(self._on_animation_finished)
    
    def _connect_signals(self):
        """Connect internal signals"""
        self.hide_timer.timeout.connect(self._start_fade_out)
    
    def show_notification(self, message: str, duration: Optional[float] = None):
        """
        Show a notification with the given message
        
        Args:
            message: Text to display
            duration: How long to show (uses config default if None)
        """
        if not self.config['show_gesture_notifications']:
            return
            
        # Queue management
        if self.is_showing:
            if len(self.notification_queue) < self.config['max_notifications_queue']:
                self.notification_queue.append((message, duration))
            return
        
        self._display_notification(message, duration)
    
    def _display_notification(self, message: str, duration: Optional[float] = None):
        """Internal method to display a notification"""
        # Set message and adjust size
        self.setText(message)
        self.adjustSize()
        
        # Position the notification
        self._position_notification()
        
        # Show and start fade-in
        self.is_showing = True
        self.show()
        
        if self.config['enable_notification_animations']:
            self._start_fade_in()
        else:
            self.opacity_effect.setOpacity(1.0)
        
        # Set hide timer
        hide_duration = duration or self.config['notification_duration']
        self.hide_timer.start(int(hide_duration * 1000))
    
    def _position_notification(self):
        """Position the notification based on configuration"""
        if not self.parent():
            return
            
        parent_rect = self.parent().rect()
        notification_size = self.size()
        
        # Calculate position based on configuration
        position = self.config['notification_position']
        offset_x = self.config['notification_offset_x']
        offset_y = self.config['notification_offset_y']
        
        if position == 'top_left':
            x = offset_x
            y = offset_y
        elif position == 'top_right':
            x = parent_rect.width() - notification_size.width() - offset_x
            y = offset_y
        elif position == 'bottom_left':
            x = offset_x
            y = parent_rect.height() - notification_size.height() - offset_y
        elif position == 'bottom_right':
            x = parent_rect.width() - notification_size.width() - offset_x
            y = parent_rect.height() - notification_size.height() - offset_y
        else:
            # Default to top_right
            x = parent_rect.width() - notification_size.width() - offset_x
            y = offset_y
        
        self.move(x, y)
    
    def _start_fade_in(self):
        """Start fade-in animation"""
        self.fade_animation.setDuration(self.config['fade_in_duration'])
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.start()
    
    def _start_fade_out(self):
        """Start fade-out animation"""
        if self.config['enable_notification_animations']:
            self.fade_animation.setDuration(self.config['fade_out_duration'])
            self.fade_animation.setStartValue(1.0)
            self.fade_animation.setEndValue(0.0)
            self.fade_animation.start()
        else:
            self._hide_notification()
    
    def _on_animation_finished(self):
        """Handle animation completion"""
        if self.opacity_effect.opacity() == 0.0:
            self._hide_notification()
    
    def _hide_notification(self):
        """Hide the notification and process queue"""
        self.hide()
        self.is_showing = False
        self.notification_hidden.emit()
        
        # Process next notification in queue
        if self.notification_queue:
            message, duration = self.notification_queue.pop(0)
            # Small delay before showing next notification
            QTimer.singleShot(100, lambda: self._display_notification(message, duration))
    
    def clear_queue(self):
        """Clear all queued notifications"""
        self.notification_queue.clear()
    
    def force_hide(self):
        """Immediately hide the notification"""
        self.hide_timer.stop()
        self.fade_animation.stop()
        self._hide_notification()


class GestureNotificationManager:
    """
    Manager for gesture recognition notifications
    
    Handles formatting and displaying notifications for different gesture events
    """
    
    def __init__(self, notification_widget: NotificationWidget):
        self.notification_widget = notification_widget
    
    def show_gesture_recognized(self, gesture_name: str, gesture_type: str, action_description: str):
        """
        Show notification for recognized gesture with action
        
        Args:
            gesture_name: Name of the recognized gesture
            gesture_type: Type of gesture (predefined/custom)
            action_description: Description of the triggered action
        """
        # Format the notification message
        gesture_display = self._format_gesture_name(gesture_name, gesture_type)
        action_display = self._format_action_description(action_description)
        
        message = f"Gesture: {gesture_display}\n→ Action: {action_display}"
        
        self.notification_widget.show_notification(message)
    
    def show_gesture_detected(self, gesture_name: str, gesture_type: str):
        """
        Show notification for detected gesture (without action)
        
        Args:
            gesture_name: Name of the detected gesture
            gesture_type: Type of gesture (predefined/custom)
        """
        gesture_display = self._format_gesture_name(gesture_name, gesture_type)
        message = f"Gesture Detected: {gesture_display}"
        
        self.notification_widget.show_notification(message, duration=1.0)
    
    def show_action_executed(self, action_description: str, success: bool = True):
        """
        Show notification for action execution result
        
        Args:
            action_description: Description of the executed action
            success: Whether the action was successful
        """
        status = "✓" if success else "✗"
        message = f"{status} Action: {action_description}"
        
        self.notification_widget.show_notification(message, duration=1.5)
    
    def _format_gesture_name(self, gesture_name: str, gesture_type: str) -> str:
        """Format gesture name for display"""
        if gesture_type == 'custom':
            return f"{gesture_name} (Custom)"
        else:
            # Convert predefined gesture IDs to readable names
            readable_names = {
                'open_palm': 'Open Palm',
                'fist': 'Fist',
                'thumbs_up': 'Thumbs Up',
                'peace_sign': 'Peace Sign',
                'pointing': 'Pointing'
            }
            return readable_names.get(gesture_name, gesture_name.replace('_', ' ').title())
    
    def _format_action_description(self, action_description: str) -> str:
        """Format action description for display"""
        # Truncate long descriptions
        max_length = 30
        if len(action_description) > max_length:
            return action_description[:max_length-3] + "..."
        return action_description
