# Gesture Flow

A desktop application for real‑time hand gesture recognition and automation. Use your webcam to detect gestures and trigger system actions like keyboard shortcuts, mouse operations, launching apps, and more. Build custom gestures, manage profiles, and compose macro sequences — all with a modern Qt (PySide6) UI.

<img width="1252" height="914" alt="image" src="https://github.com/user-attachments/assets/d35ab01b-8df8-4d57-b414-0e0c53d7f2dd" />

## Key Features
- Real‑time hand tracking and gesture recognition (MediaPipe + OpenCV)
- Predefined gesture support (e.g., open palm, fist, thumbs up, peace sign, pointing)
- Custom gesture recording, training, and management
- Action mapping: assign gestures to actions (keyboard, mouse, app launch, macros, etc.)
- Macro builder: sequence multiple actions with delays, reordering, and editing
- Profile management: create and switch between multiple action mapping profiles
- Settings UI: camera, performance, execution, mouse control, and UI preferences
- Visual notifications for executed actions
- Persistent storage for profiles, logs, and backups

## Project Structure
- src/
  - main.py — Application entry point (launches the main window)
  - action_mapping_dialog.py — Map gestures to actions and create macros
  - action_executor.py — Executes mapped actions (keyboard/mouse/app)
  - gesture_recording_dialog.py — Record and train custom gestures
  - gesture_management_dialog.py — Manage custom gestures and training
  - profile_management_dialog.py — Manage mapping profiles
  - settings_dialog.py — Application settings UI
  - profile_manager.py — Profile load/save logic
  - notification_widget.py — In‑app notifications
  - action_mapping_manager.py — Mapping persistence and coordination
  - action_types.py — Action type definitions
  - config.py — App configuration defaults
- data/
  - profiles/ — Profile data and metadata
  - action_mappings/ — Default and test mappings
  - custom_gestures/ — Custom gesture models and metadata
  - logs/ — App and execution logs
  - backups/ — Automatic backups of important data

## Requirements
- OS: Windows 10/11 (primary target). Other platforms may work if dependencies are available.
- Python: 3.12 (recommended)
- Webcam: Any UVC‑compatible webcam
- Dependencies (see requirements.txt):
  - PySide6, opencv-python, mediapipe, scikit-learn, pynput, pyautogui, numpy

## Setup
1) Create and activate a virtual environment
- PowerShell (Windows):
  - python -m venv venv
  - .\venv\Scripts\Activate.ps1

2) Install dependencies
- pip install -r requirements.txt

## Run
- python src/main.py

On first launch:
- Ensure your webcam is connected and not in use by other apps
- Grant camera permissions if prompted by the OS

## Usage Overview
- Recognize gestures: The live feed shows detections; recognized gestures appear in the UI
- Map actions:
  - Open Action Mapping (from the main window)
  - Select a gesture and configure the corresponding action or macro
  - Save the mapping to the active profile
- Build macros:
  - Use the Macro tab to add/edit/remove steps, reorder them, or clear all
  - Set delays/loop counts as needed
- Manage profiles:
  - Create, rename, delete, and switch profiles in Profile Management
  - Mappings are saved per profile
- Custom gestures:
  - Record new gestures, train the model, and manage them in the Gestures dialogs
- Settings:
  - Configure camera, performance, action execution, mouse control, and UI options

## Data and Persistence
- Profiles: data/profiles/
- Mappings: data/action_mappings/
- Custom gestures: data/custom_gestures/
- Logs: data/logs/
- Backups: data/backups/

## Troubleshooting
- Webcam not detected: Close other apps using the camera and re‑launch
- High CPU usage: Lower resolution/FPS in Settings or reduce processing options
- Actions not executing:
  - Verify mappings are saved to the active profile
  - Some actions may require OS permissions (e.g., input control)
- Gesture misclassification: Record more samples and retrain custom gestures

## Development Notes
- Tech stack: PySide6 (Qt), OpenCV, MediaPipe, scikit‑learn, pynput, pyautogui, numpy
- Entry point: src/main.py (see main())
- Logs are helpful for debugging: see data/logs/

## Contributing
Issues and pull requests are welcome. Please describe reproduction steps and include logs if relevant.
