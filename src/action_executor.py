import os
import sys
import time
import logging
import subprocess
import threading
from queue import Queue, Empty
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future

try:
    import pynput
    from pynput import mouse, keyboard
    from pynput.mouse import Button, Listener as MouseListener
    from pynput.keyboard import Key, Listener as KeyboardListener
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("Warning: pynput not available. Install with: pip install pynput")

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("Warning: pyautogui not available. Install with: pip install pyautogui")

from action_types import (
    Action, ActionType, MouseAction, KeyboardAction, ApplicationAction,
    MouseActionParameters, KeyboardActionParameters, ApplicationActionParameters,
    MacroActionParameters, ActionValidator
)
from config import ACTION_EXECUTION_CONFIG, ACTION_TYPES_CONFIG


class ActionExecutionResult:
    """Result of action execution"""

    def __init__(self, success: bool, message: str = "", execution_time: float = 0.0,
                 action_id: str = "", error_code: str = ""):
        self.success = success
        self.message = message
        self.execution_time = execution_time
        self.action_id = action_id
        self.error_code = error_code
        self.timestamp = datetime.now().isoformat()


class ActionExecutor:
    """
    Core action execution engine with enhanced security and UX features

    Features:
    - Cross-platform input automation (pynput/pyautogui)
    - Safety mechanisms and validation
    - Action sequences and macros
    - Comprehensive error handling and logging
    - Asynchronous execution with queuing
    """

    def __init__(self):
        self.config = ACTION_EXECUTION_CONFIG
        self.types_config = ACTION_TYPES_CONFIG
        self.validator = ActionValidator()

        # Setup logging
        self._setup_logging()

        # Initialize input libraries
        self._initialize_libraries()

        # Execution state
        self.is_running = True
        self.execution_queue = Queue(maxsize=self.config.get('queue_max_size', 100))
        self.execution_history = []
        self.active_futures = []

        # Thread pool for async execution
        max_workers = self.config.get('execution_thread_pool', 2)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # Safety mechanisms
        self.failsafe_enabled = self.config.get('enable_failsafe', True)
        self.emergency_stop = False

        # Callbacks
        self.on_action_executed: Optional[Callable] = None
        self.on_action_failed: Optional[Callable] = None

        # Start background processing if async execution is enabled
        if self.config.get('async_execution', True):
            self._start_background_processing()

    def _setup_logging(self):
        """Setup logging for action execution"""
        log_level = getattr(logging, self.config.get('log_level', 'INFO'))

        # Create logs directory
        logs_dir = 'data/logs'
        os.makedirs(logs_dir, exist_ok=True)

        # Setup logger
        self.logger = logging.getLogger('ActionExecutor')
        self.logger.setLevel(log_level)

        # File handler
        log_file = os.path.join(logs_dir, 'action_execution.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)

    def _initialize_libraries(self):
        """Initialize input automation libraries"""
        library_preference = self.config.get('input_library', 'pynput')

        if library_preference == 'pynput' and PYNPUT_AVAILABLE:
            self.input_library = 'pynput'
            self.mouse_controller = mouse.Controller()
            self.keyboard_controller = keyboard.Controller()
            self.logger.info("Initialized pynput for input automation")
        elif library_preference == 'pyautogui' and PYAUTOGUI_AVAILABLE:
            self.input_library = 'pyautogui'
            # Configure PyAutoGUI safety features
            if self.failsafe_enabled:
                pyautogui.FAILSAFE = True
                pyautogui.PAUSE = self.config.get('default_action_delay', 0.1)
            self.logger.info("Initialized PyAutoGUI for input automation")
        else:
            # Fallback to available library
            if PYNPUT_AVAILABLE:
                self.input_library = 'pynput'
                self.mouse_controller = mouse.Controller()
                self.keyboard_controller = keyboard.Controller()
                self.logger.warning("Fallback to pynput")
            elif PYAUTOGUI_AVAILABLE:
                self.input_library = 'pyautogui'
                if self.failsafe_enabled:
                    pyautogui.FAILSAFE = True
                    pyautogui.PAUSE = self.config.get('default_action_delay', 0.1)
                self.logger.warning("Fallback to PyAutoGUI")
            else:
                self.input_library = None
                self.logger.error("No input automation library available!")
                raise RuntimeError("No input automation library available. Install pynput or pyautogui.")


    # --- Lightweight cursor utilities for dynamic control (no queuing/logging) ---
    def get_cursor_position(self) -> tuple[int, int]:
        """Get current mouse cursor position."""
        try:
            if self.input_library == 'pynput' and hasattr(self, 'mouse_controller'):
                return tuple(self.mouse_controller.position)  # type: ignore
            elif self.input_library == 'pyautogui' and PYAUTOGUI_AVAILABLE:
                pos = pyautogui.position()
                return (pos.x, pos.y)
        except Exception:
            pass
        return (0, 0)

    def _get_screen_size(self) -> tuple[int, int]:
        """Best-effort screen size detection without Qt dependency."""
        # Prefer pyautogui if available
        try:
            if PYAUTOGUI_AVAILABLE:
                size = pyautogui.size()
                return (size.width, size.height)
        except Exception:
            pass
        # Fallback using Windows API
        try:
            import ctypes
            user32 = ctypes.windll.user32
            return (int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1)))
        except Exception:
            pass
        # Reasonable default
        return (1920, 1080)

    def move_cursor_relative(self, dx: float, dy: float):
        """Move cursor by relative dx, dy immediately (clamped to screen)."""
        try:
            cur_x, cur_y = self.get_cursor_position()
            new_x = int(cur_x + dx)
            new_y = int(cur_y + dy)
            screen_w, screen_h = self._get_screen_size()
            new_x = max(0, min(screen_w - 1, new_x))
            new_y = max(0, min(screen_h - 1, new_y))
            if self.input_library == 'pynput' and hasattr(self, 'mouse_controller'):
                self.mouse_controller.position = (new_x, new_y)  # type: ignore
            elif self.input_library == 'pyautogui' and PYAUTOGUI_AVAILABLE:
                pyautogui.moveTo(new_x, new_y, duration=0)
        except Exception:
            # Keep silent to avoid flooding logs during continuous control
            pass

    def _start_background_processing(self):
        """Start background thread for processing queued actions"""
        def process_queue():
            while self.is_running:
                try:
                    action, callback = self.execution_queue.get(timeout=1.0)
                    if action is None:  # Shutdown signal
                        break

                    result = self._execute_action_sync(action)
                    if callback:
                        callback(result)

                    self.execution_queue.task_done()
                except Empty:
                    continue
                except Exception as e:
                    self.logger.error(f"Error in background processing: {e}")

        self.background_thread = threading.Thread(target=process_queue, daemon=True)
        self.background_thread.start()
        self.logger.info("Started background action processing")

    def execute_action(self, action: Action, async_execution: bool = None) -> Future[ActionExecutionResult]:
        """
        Execute an action with validation and safety checks

        Args:
            action: Action to execute
            async_execution: Override async setting for this action

        Returns:
            Future containing ActionExecutionResult
        """
        if async_execution is None:
            async_execution = self.config.get('async_execution', True)

        # Validate action
        is_valid, error_message = self.validator.validate_action(action)
        if not is_valid:
            result = ActionExecutionResult(
                success=False,
                message=f"Validation failed: {error_message}",
                action_id=action.id,
                error_code="VALIDATION_ERROR"
            )
            return self._create_completed_future(result)

        # Check emergency stop
        if self.emergency_stop:
            result = ActionExecutionResult(
                success=False,
                message="Emergency stop activated",
                action_id=action.id,
                error_code="EMERGENCY_STOP"
            )
            return self._create_completed_future(result)

        # Log action execution attempt
        self.logger.info(f"Executing action: {action.type.value}.{action.subtype} (ID: {action.id})")

        if async_execution:
            # Submit to thread pool
            future = self.executor.submit(self._execute_action_sync, action)
            self.active_futures.append(future)
            return future
        else:
            # Execute synchronously
            result = self._execute_action_sync(action)
            return self._create_completed_future(result)

    def _create_completed_future(self, result: ActionExecutionResult) -> Future:
        """Create a completed future with the given result"""
        future = Future()
        future.set_result(result)
        return future

    def _execute_action_sync(self, action: Action) -> ActionExecutionResult:
        """Execute action synchronously with timing and error handling"""
        start_time = time.time()

        try:
            # Apply default delay
            default_delay = self.config.get('default_action_delay', 0.1)
            if default_delay > 0:
                time.sleep(default_delay)

            # Execute based on action type
            if action.type == ActionType.MOUSE:
                success, message = self._execute_mouse_action(action)
            elif action.type == ActionType.KEYBOARD:
                success, message = self._execute_keyboard_action(action)
            elif action.type == ActionType.APPLICATION:
                success, message = self._execute_application_action(action)
            elif action.type == ActionType.MACRO:
                success, message = self._execute_macro_action(action)
            else:
                success, message = False, f"Unsupported action type: {action.type.value}"

            execution_time = time.time() - start_time

            result = ActionExecutionResult(
                success=success,
                message=message,
                execution_time=execution_time,
                action_id=action.id
            )

            # Add to history
            self._add_to_history(action, result)

            # Call callbacks
            if success and self.on_action_executed:
                self.on_action_executed(action, result)
            elif not success and self.on_action_failed:
                self.on_action_failed(action, result)

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            error_message = f"Execution error: {str(e)}"

            self.logger.error(f"Action execution failed: {error_message}")

            result = ActionExecutionResult(
                success=False,
                message=error_message,
                execution_time=execution_time,
                action_id=action.id,
                error_code="EXECUTION_ERROR"
            )

            self._add_to_history(action, result)

            if self.on_action_failed:
                self.on_action_failed(action, result)

            return result

    def _execute_mouse_action(self, action: Action) -> tuple[bool, str]:
        """Execute mouse action using the configured library"""
        params = action.parameters

        try:
            if self.input_library == 'pynput':
                return self._execute_mouse_action_pynput(action.subtype, params)
            elif self.input_library == 'pyautogui':
                return self._execute_mouse_action_pyautogui(action.subtype, params)
            else:
                return False, "No input library available"
        except Exception as e:
            return False, f"Mouse action failed: {str(e)}"

    def _execute_mouse_action_pynput(self, subtype: str, params: MouseActionParameters) -> tuple[bool, str]:
        """Execute mouse action using pynput"""
        if subtype == MouseAction.CLICK.value:
            if params.x is not None and params.y is not None:
                self.mouse_controller.position = (params.x, params.y)

            button_map = {
                'left': Button.left,
                'right': Button.right,
                'middle': Button.middle
            }
            button = button_map.get(params.button, Button.left)

            for _ in range(params.clicks):
                self.mouse_controller.click(button)
                if params.clicks > 1:
                    time.sleep(0.1)  # Small delay between clicks

            return True, f"Mouse {params.button} click executed"
        elif subtype == MouseAction.MOVE_TO.value:
            if params.x is not None and params.y is not None:
                self.mouse_controller.position = (params.x, params.y)
                return True, f"Mouse moved to ({params.x}, {params.y})"
            return False, "Mouse move requires x and y coordinates"

        elif subtype == MouseAction.DRAG.value:
            # Drag from (from_x, from_y) to (to_x, to_y)
            try:
                # Use left button for drag
                start_x = params.from_x if params.from_x is not None else self.mouse_controller.position[0]
                start_y = params.from_y if params.from_y is not None else self.mouse_controller.position[1]
                end_x = params.to_x if params.to_x is not None else params.x
                end_y = params.to_y if params.to_y is not None else params.y
                if end_x is None or end_y is None:
                    return False, "Drag requires destination X and Y"
                # Move to start if needed
                self.mouse_controller.position = (start_x, start_y)
                self.mouse_controller.press(Button.left)
                # Optional duration: break drag into small steps
                duration = params.duration or 0.0
                if duration > 0:
                    steps = max(1, int(duration / 0.02))
                    dx = (end_x - start_x) / steps
                    dy = (end_y - start_y) / steps
                    for i in range(1, steps + 1):
                        self.mouse_controller.position = (int(start_x + dx * i), int(start_y + dy * i))
                        time.sleep(0.02)
                else:
                    self.mouse_controller.position = (end_x, end_y)
                self.mouse_controller.release(Button.left)
                return True, f"Mouse dragged to ({end_x}, {end_y})"
            except Exception as e:
                return False, f"Drag failed: {str(e)}"

        elif subtype == MouseAction.SCROLL.value:
            scroll_map = {
                'up': (0, 1),
                'down': (0, -1),
                'left': (-1, 0),
                'right': (1, 0)
            }
            dx, dy = scroll_map.get(params.scroll_direction, (0, 1))
            delay = params.duration or 0.05
            for _ in range(params.scroll_amount):
                self.mouse_controller.scroll(dx, dy)
                if delay > 0:
                    time.sleep(delay)
            return True, f"Mouse scrolled {params.scroll_direction} {params.scroll_amount} steps"

        return False, f"Unsupported mouse action: {subtype}"

    def _execute_mouse_action_pyautogui(self, subtype: str, params: MouseActionParameters) -> tuple[bool, str]:
        """Execute mouse action using PyAutoGUI"""
        if subtype == MouseAction.CLICK.value:
            x, y = params.x, params.y
            button = params.button
            clicks = params.clicks

            pyautogui.click(x, y, clicks=clicks, button=button)

            return True, f"Mouse {button} click executed"

        elif subtype == MouseAction.MOVE_TO.value:
            duration = params.duration or self.config.get('mouse_movement_duration', 0.3)
            pyautogui.moveTo(params.x, params.y, duration=duration)
            return True, f"Mouse moved to ({params.x}, {params.y})"

        elif subtype == MouseAction.DRAG.value:
            # Drag using PyAutoGUI
            duration = params.duration or self.config.get('mouse_movement_duration', 0.3)
            start_x = params.from_x
            start_y = params.from_y
            end_x = params.to_x if params.to_x is not None else params.x
            end_y = params.to_y if params.to_y is not None else params.y
            if end_x is None or end_y is None:
                return False, "Drag requires destination X and Y"
            if start_x is not None and start_y is not None:
                pyautogui.moveTo(start_x, start_y, duration=0)
            pyautogui.dragTo(end_x, end_y, duration=duration, button='left')
            return True, f"Mouse dragged to ({end_x}, {end_y})"

        elif subtype == MouseAction.SCROLL.value:
            scroll_amount = params.scroll_amount
            if params.scroll_direction == 'down':
                scroll_amount = -scroll_amount

            pyautogui.scroll(scroll_amount)
            return True, f"Mouse scrolled {params.scroll_direction} {abs(scroll_amount)} steps"

        return False, f"Unsupported mouse action: {subtype}"

    def _execute_keyboard_action(self, action: Action) -> tuple[bool, str]:
        """Execute keyboard action using the configured library"""
        params = action.parameters

        try:
            if self.input_library == 'pynput':
                return self._execute_keyboard_action_pynput(action.subtype, params)
            elif self.input_library == 'pyautogui':
                return self._execute_keyboard_action_pyautogui(action.subtype, params)
            else:
                return False, "No input library available"
        except Exception as e:
            return False, f"Keyboard action failed: {str(e)}"

    def _execute_keyboard_action_pynput(self, subtype: str, params: KeyboardActionParameters) -> tuple[bool, str]:
        """Execute keyboard action using pynput"""
        if subtype == KeyboardAction.KEY_PRESS.value:
            keys = params.keys if isinstance(params.keys, list) else [params.keys]

            for key_name in keys:
                # Handle special keys
                if hasattr(Key, key_name.lower()):
                    key = getattr(Key, key_name.lower())
                else:
                    key = key_name

                self.keyboard_controller.press(key)
                self.keyboard_controller.release(key)

                if len(keys) > 1:
                    time.sleep(params.interval or 0.05)

            return True, f"Key press executed: {', '.join(keys)}"

        elif subtype == KeyboardAction.KEY_COMBINATION.value:
            keys = params.keys if isinstance(params.keys, list) else [params.keys]
            modifiers = params.modifiers or []

            # Press modifiers first
            pressed_keys = []
            for modifier in modifiers:
                if hasattr(Key, modifier.lower()):
                    mod_key = getattr(Key, modifier.lower())
                    self.keyboard_controller.press(mod_key)
                    pressed_keys.append(mod_key)

            # Press main keys
            for key_name in keys:
                if hasattr(Key, key_name.lower()):
                    key = getattr(Key, key_name.lower())
                else:
                    key = key_name

                self.keyboard_controller.press(key)
                pressed_keys.append(key)

            # Release in reverse order
            for key in reversed(pressed_keys):
                self.keyboard_controller.release(key)
                time.sleep(0.01)

            return True, f"Key combination executed: {'+'.join(modifiers + keys)}"

        elif subtype == KeyboardAction.TYPE_TEXT.value:
            text = params.text
            interval = params.interval or 0.05

            for char in text:
                self.keyboard_controller.type(char)
                if interval > 0:
                    time.sleep(interval)

            return True, f"Text typed: {len(text)} characters"

        return False, f"Unsupported keyboard action: {subtype}"

    def _execute_keyboard_action_pyautogui(self, subtype: str, params: KeyboardActionParameters) -> tuple[bool, str]:
        """Execute keyboard action using PyAutoGUI"""
        if subtype == KeyboardAction.KEY_PRESS.value:
            keys = params.keys if isinstance(params.keys, list) else [params.keys]

            for key_name in keys:
                pyautogui.press(key_name)
                if len(keys) > 1:
                    time.sleep(params.interval or 0.05)

            return True, f"Key press executed: {', '.join(keys)}"

        elif subtype == KeyboardAction.KEY_COMBINATION.value:
            keys = params.keys if isinstance(params.keys, list) else [params.keys]
            modifiers = params.modifiers or []

            all_keys = modifiers + keys
            pyautogui.hotkey(*all_keys)

            return True, f"Key combination executed: {'+'.join(all_keys)}"

        elif subtype == KeyboardAction.TYPE_TEXT.value:
            text = params.text
            interval = params.interval or 0.05

            pyautogui.write(text, interval=interval)

            return True, f"Text typed: {len(text)} characters"

        return False, f"Unsupported keyboard action: {subtype}"

    def _execute_application_action(self, action: Action) -> tuple[bool, str]:
        """Execute application action"""
        params = action.parameters

        try:
            if action.subtype == ApplicationAction.LAUNCH.value:
                return self._launch_application(params)
            elif action.subtype == ApplicationAction.CLOSE.value:
                return self._close_application(params)
            elif action.subtype == ApplicationAction.FOCUS.value:
                return self._focus_application(params)
            else:
                return False, f"Unsupported application action: {action.subtype}"
        except Exception as e:
            return False, f"Application action failed: {str(e)}"

    def _launch_application(self, params: ApplicationActionParameters) -> tuple[bool, str]:
        """Launch an application"""
        if not params.path:
            return False, "Application path is required"

        try:
            # Prepare command
            cmd = [params.path]
            if params.arguments:
                cmd.extend(params.arguments)

            # Set working directory
            cwd = params.working_directory or None

            # Launch application
            if sys.platform.startswith('win'):
                # Windows
                subprocess.Popen(cmd, cwd=cwd, shell=True)
            else:
                # Unix-like systems
                subprocess.Popen(cmd, cwd=cwd)

            return True, f"Application launched: {params.path}"

        except FileNotFoundError:
            return False, f"Application not found: {params.path}"
        except PermissionError:
            return False, f"Permission denied: {params.path}"
        except Exception as e:
            return False, f"Failed to launch application: {str(e)}"

    def _close_application(self, params: ApplicationActionParameters) -> tuple[bool, str]:
        """Close an application (basic implementation)"""
        # This is a simplified implementation
        # In a full implementation, you would use platform-specific APIs
        # to find and close applications by name or window title
        return False, "Application close not implemented yet"

    def _focus_application(self, params: ApplicationActionParameters) -> tuple[bool, str]:
        """Focus an application window (basic implementation)"""
        # This is a simplified implementation
        # In a full implementation, you would use platform-specific APIs
        # to find and focus application windows
        return False, "Application focus not implemented yet"

    def _execute_macro_action(self, action: Action) -> tuple[bool, str]:
        """Execute a macro (sequence of actions)"""
        params = action.parameters

        if not params.sequence:
            return False, "Macro sequence is empty"

        try:
            executed_actions = 0
            total_actions = len(params.sequence) * params.loop_count

            for loop in range(params.loop_count):
                for i, action_data in enumerate(params.sequence):
                    # Check for emergency stop
                    if self.emergency_stop:
                        return False, f"Macro stopped by emergency stop after {executed_actions} actions"

                    # Create action from data
                    sub_action = Action.from_dict(action_data)

                    # Execute sub-action synchronously
                    result = self._execute_action_sync(sub_action)
                    executed_actions += 1

                    if not result.success:
                        return False, f"Macro failed at action {i+1} (loop {loop+1}): {result.message}"

                    # Delay between actions
                    delay = params.delay_between_actions or self.config.get('default_action_delay', 0.1)
                    if delay > 0 and executed_actions < total_actions:
                        time.sleep(delay)

            return True, f"Macro executed successfully: {executed_actions} actions"

        except Exception as e:
            return False, f"Macro execution failed: {str(e)}"

    def _add_to_history(self, action: Action, result: ActionExecutionResult):
        """Add action execution to history"""
        history_entry = {
            'action': action.to_dict(),
            'result': {
                'success': result.success,
                'message': result.message,
                'execution_time': result.execution_time,
                'timestamp': result.timestamp,
                'error_code': result.error_code
            }
        }

        self.execution_history.append(history_entry)

        # Limit history size
        max_history = self.config.get('max_action_history', 1000)
        if len(self.execution_history) > max_history:
            self.execution_history = self.execution_history[-max_history:]

        # Log to file if enabled
        if self.config.get('log_all_actions', True):
            self.logger.info(f"Action executed: {action.type.value}.{action.subtype} - "
                           f"Success: {result.success} - Time: {result.execution_time:.3f}s")

    def emergency_stop_all(self):
        """Emergency stop all action execution"""
        self.emergency_stop = True
        self.logger.warning("Emergency stop activated - all action execution halted")

    def resume_execution(self):
        """Resume action execution after emergency stop"""
        self.emergency_stop = False
        self.logger.info("Action execution resumed")

    def get_execution_history(self, limit: int = 100) -> List[Dict]:
        """Get recent execution history"""
        return self.execution_history[-limit:]

    def clear_execution_history(self):
        """Clear execution history"""
        self.execution_history.clear()
        self.logger.info("Execution history cleared")

    def shutdown(self):
        """Shutdown the action executor"""
        self.is_running = False

        # Signal background thread to stop
        if hasattr(self, 'execution_queue'):
            self.execution_queue.put((None, None))

        # Shutdown thread pool
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)

        self.logger.info("Action executor shutdown complete")
