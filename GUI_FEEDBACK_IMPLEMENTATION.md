# GUI-Based Human Feedback System

## Overview

This document describes the implementation plan for a GUI-based human feedback system that automatically captures human actions (clicks, typing, keyboard shortcuts) on Windows applications and converts them into structured feedback for the agent.

---

## Current State

### Existing System
- **Agent Actions**: Executes Windows GUI automation via MCP tools (Click-Tool, Type-Tool, Scroll-Tool, etc.)
- **Human Feedback**: CLI-based terminal prompts (text input only)
- **Observer**: Background thread monitoring for Ctrl+C interrupts
- **Feedback Types**:
  - Approval/Rejection with correction
  - Skip step
  - General guidance (text)
  - Procedural guidance (step-by-step instructions via text)
  - Task verification

### Limitations
- No visual feedback during agent execution
- Manual text input for corrections (tedious for GUI actions)
- Cannot demonstrate by doing (must describe in text)
- No visual context for approval decisions
- Difficult to provide precise coordinate-based corrections

---

## Proposed Enhancement

### Vision

**Enable humans to provide feedback through natural GUI interactions instead of typing text commands.**

When the agent pauses for feedback, a human can:
1. **Click directly** on the target application → Captured as corrected action
2. **Type naturally** in target fields → Captured as corrected Type-Tool action
3. **Press shortcuts** (Ctrl+C, etc.) → Captured as Shortcut-Tool action
4. **Click overlay buttons** → Quick approve/reject/skip
5. **Demonstrate procedures** → Agent learns from observed action sequence

---

## Architecture Design

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                 GUI Feedback Capture System                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────┐       │
│  │   1. GUIFeedbackCapture                              │       │
│  │      Location: agent/feedback/gui_feedback_capture.py│       │
│  ├──────────────────────────────────────────────────────┤       │
│  │   Responsibilities:                                  │       │
│  │   • Hook into Windows events (mouse, keyboard)       │       │
│  │   • Translate raw events → ActionSchema objects      │       │
│  │   • Maintain recording state machine                 │       │
│  │   • Buffer and filter captured events                │       │
│  │   • Infer feedback intent from action patterns       │       │
│  ├──────────────────────────────────────────────────────┤       │
│  │   Key Methods:                                       │       │
│  │   • start_recording(mode: RecordingMode)             │       │
│  │   • stop_recording() → List[ActionSchema]            │       │
│  │   • get_element_at_cursor() → UIElement              │       │
│  │   • translate_event(event) → ActionSchema            │       │
│  │   • infer_feedback_type() → FeedbackType             │       │
│  ├──────────────────────────────────────────────────────┤       │
│  │   Dependencies:                                      │       │
│  │   • pynput (cross-platform keyboard/mouse hooks)     │       │
│  │   • pywin32 or uiautomation (get element at cursor)  │       │
│  │   • Windows-MCP State-Tool integration               │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                   │
│  ┌──────────────────────────────────────────────────────┐       │
│  │   2. FeedbackOverlay                                 │       │
│  │      Location: agent/feedback/feedback_overlay.py    │       │
│  ├──────────────────────────────────────────────────────┤       │
│  │   Responsibilities:                                  │       │
│  │   • Display semi-transparent overlay window          │       │
│  │   • Show current step, confidence, agent reasoning   │       │
│  │   • Provide clickable feedback buttons               │       │
│  │   • Display recording indicator (red dot)            │       │
│  │   • Show guidance text input field                   │       │
│  │   • Visual verification checklist                    │       │
│  ├──────────────────────────────────────────────────────┤       │
│  │   UI Framework: tkinter (built-in, lightweight)      │       │
│  │   Alternative: PyQt5 (if more advanced UI needed)    │       │
│  ├──────────────────────────────────────────────────────┤       │
│  │   UI Elements:                                       │       │
│  │   • Header: "Agent waiting for feedback - Step X"   │       │
│  │   • Info panel: Shows proposed action details        │       │
│  │   • Button panel: [Approve] [Reject] [Skip] [Demo]  │       │
│  │   • Recording indicator: 🔴 RECORDING (when active) │       │
│  │   • Guidance input: Text area for typed guidance     │       │
│  │   • Status bar: Instructions for human              │       │
│  ├──────────────────────────────────────────────────────┤       │
│  │   Key Methods:                                       │       │
│  │   • show(action, confidence, step_num)               │       │
│  │   • hide()                                           │       │
│  │   • set_recording_mode(active: bool)                 │       │
│  │   • wait_for_user_choice() → FeedbackChoice          │       │
│  │   • show_verification(task, summary)                 │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                   │
│  ┌──────────────────────────────────────────────────────┐       │
│  │   3. HumanObserverGUI                                │       │
│  │      Location: agent/feedback/human_observer_gui.py  │       │
│  ├──────────────────────────────────────────────────────┤       │
│  │   Extends: HumanObserver (maintains backward compat) │       │
│  ├──────────────────────────────────────────────────────┤       │
│  │   Responsibilities:                                  │       │
│  │   • Detect if GUI environment available              │       │
│  │   • Orchestrate GUI feedback capture flow            │       │
│  │   • Fall back to CLI if no GUI available             │       │
│  │   • Convert captured GUI actions → HumanFeedback     │       │
│  │   • Handle all feedback modes (see below)            │       │
│  ├──────────────────────────────────────────────────────┤       │
│  │   Key Methods (override parent):                     │       │
│  │   • request_approval(...) → HumanFeedback            │       │
│  │   • request_verification(...) → TaskVerification     │       │
│  │   • _request_approval_gui(...)  # New method         │       │
│  │   • _request_approval_cli(...)  # Fallback           │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Feedback Modes

### Mode A: Proactive Interrupt (Anytime Feedback)

**Trigger**: Human presses global hotkey (e.g., `Ctrl+Shift+F`)

**Flow**:
1. Agent is executing step N
2. Human presses `Ctrl+Shift+F`
3. Agent pauses execution immediately
4. Overlay appears showing current/last action
5. Human has options:
   - Click "Demonstrate" → Starts recording, human performs correct sequence
   - Click "Guidance" → Type text guidance, agent continues
   - Click "Stop" → Abort current task
   - Do nothing for 10s → Agent resumes

**Use Case**:
> "I see the agent clicking the wrong button. Let me interrupt and show it the right one."

---

### Mode B: Low Confidence Approval (Agent Requests Help)

**Trigger**: Agent confidence < threshold (e.g., 0.5)

**Flow**:
1. Agent proposes action with low confidence
2. Overlay appears automatically showing:
   - Proposed action details
   - Agent's reasoning
   - Confidence score
   - Alternative actions considered
3. Human chooses:

   **Option 1: Approve**
   - Click "Approve" button
   - Agent executes as proposed

   **Option 2: Demonstrate Correction**
   - Click "Show Me" button
   - Recording starts (🔴 indicator)
   - Human performs 1 or more actions on target app
   - Click overlay "Done" or press `Esc`
   - Captured actions replace proposed action

   **Option 3: Skip**
   - Click "Skip" button
   - Agent skips this step

   **Option 4: Provide Guidance**
   - Click "Guide" button
   - Type text in overlay input field
   - Agent executes original action but stores guidance for context

**Key Innovation**:
Instead of typing `{"tool_name": "Click-Tool", "tool_arguments": {"loc": [450, 300]}}`, human just **clicks at (450, 300)** and the system captures it automatically.

---

### Mode C: Procedural Learning (Multi-Step Demonstration)

**Trigger**:
- Agent asks for procedural guidance
- Human clicks "Teach Procedure" in overlay
- Human explicitly requests via hotkey (`Ctrl+Shift+T`)

**Flow**:
1. Overlay shows: "Demonstrate the correct procedure for: [goal]"
2. Recording starts for multi-action sequence
3. Human performs complete workflow on target app:
   - Example: Open menu → Click item → Fill field → Press Enter
4. All actions captured as sequence
5. Human clicks "Done" in overlay
6. System prompts for additional metadata:
   - Goal description (text input)
   - Key points to remember (optional)
   - Common mistakes to avoid (optional)
7. Creates `ProceduralGuidance` object with action sequence
8. Agent replans using demonstrated procedure

**Example**:
```
Human demonstrates: "How to concatenate MF4 files in asammdf"
Captured sequence:
  1. Click-Tool: loc=[120, 45] (Concatenate menu)
  2. Click-Tool: loc=[200, 150] (Add files button)
  3. Type-Tool: text="C:\path\file1.mf4"
  4. Key-Tool: key="enter"
  5. Click-Tool: loc=[200, 150] (Add files button)
  6. Type-Tool: text="C:\path\file2.mf4"
  7. Key-Tool: key="enter"
  8. Click-Tool: loc=[450, 500] (OK button)

Stored as ProceduralGuidance with steps extracted.
```

---

### Mode D: Post-Task Verification (Visual Confirmation)

**Trigger**: Agent completes all steps

**Flow**:
1. Overlay shows verification UI:
   - Task description
   - Execution summary (steps completed, interventions)
   - Visual comparison (before/after screenshots if available)
   - Checklist of expected outcomes
2. Human verifies by:
   - Checking application state directly
   - Reviewing overlay information
   - Clicking verification buttons
3. Options:
   - ✅ **Success** → Mark complete, optionally save as verified skill
   - ❌ **Failed** → Provide reason, agent will retry
   - ⚠️ **Partial** → Mark which steps succeeded/failed (click on step numbers)

**Key Feature**:
Visual diff showing file explorer before/after, or application state before/after task execution.

---

## Technical Implementation Details

### 1. Event Capture System

**Library**: `pynput` (cross-platform, well-maintained)

```python
from pynput import mouse, keyboard
import threading

class GUIFeedbackCapture:
    def __init__(self):
        self.recording = False
        self.captured_events = []
        self.mouse_listener = None
        self.keyboard_listener = None

    def start_recording(self, mode: RecordingMode):
        """Start capturing mouse and keyboard events"""
        self.recording = True
        self.captured_events = []

        # Start mouse listener
        self.mouse_listener = mouse.Listener(
            on_click=self._on_click,
            on_scroll=self._on_scroll
        )
        self.mouse_listener.start()

        # Start keyboard listener
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.keyboard_listener.start()

    def stop_recording(self) -> List[ActionSchema]:
        """Stop capturing and return translated actions"""
        self.recording = False
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()

        # Translate raw events to ActionSchema objects
        return self._translate_events_to_actions()

    def _on_click(self, x, y, button, pressed):
        """Capture mouse clicks"""
        if not self.recording or not pressed:
            return

        # Get UI element at cursor position
        element = self._get_element_at_cursor(x, y)

        self.captured_events.append({
            'type': 'click',
            'x': x,
            'y': y,
            'button': button.name,
            'element': element,
            'timestamp': time.time()
        })

    def _on_key_press(self, key):
        """Capture keyboard input"""
        if not self.recording:
            return

        # Detect shortcuts (Ctrl+C, etc.)
        if self._is_shortcut(key):
            self.captured_events.append({
                'type': 'shortcut',
                'keys': self._get_active_modifiers() + [key],
                'timestamp': time.time()
            })
        # Detect typed text
        elif self._is_character(key):
            self.captured_events.append({
                'type': 'type',
                'char': key.char,
                'timestamp': time.time()
            })
        # Detect special keys
        else:
            self.captured_events.append({
                'type': 'key',
                'key': key.name,
                'timestamp': time.time()
            })

    def _translate_events_to_actions(self) -> List[ActionSchema]:
        """Convert raw events to MCP tool actions"""
        actions = []

        # Group consecutive type events into single Type-Tool action
        # Convert click events to Click-Tool actions
        # Convert shortcut events to Shortcut-Tool actions
        # etc.

        # Example:
        for event in self.captured_events:
            if event['type'] == 'click':
                actions.append(ActionSchema(
                    tool_name='Click-Tool',
                    tool_arguments={
                        'loc': [event['x'], event['y']],
                        'button': event['button'],
                        'clicks': 1
                    },
                    reasoning=f"Click on {event['element']['name']} at ({event['x']}, {event['y']})"
                ))
            elif event['type'] == 'shortcut':
                actions.append(ActionSchema(
                    tool_name='Shortcut-Tool',
                    tool_arguments={
                        'shortcut': [k.name for k in event['keys']]
                    },
                    reasoning=f"Press shortcut {'+'.join([k.name for k in event['keys']])}"
                ))
            # ... handle other event types

        return actions

    def _get_element_at_cursor(self, x, y) -> dict:
        """Use uiautomation to get UI element at cursor position"""
        import uiautomation as ua
        control = ua.ControlFromPoint(x, y)
        return {
            'name': control.Name,
            'type': control.ControlTypeName,
            'automationId': control.AutomationId
        }
```

---

### 2. Overlay UI

**Library**: `tkinter` (built-in, no extra dependencies)

```python
import tkinter as tk
from tkinter import ttk

class FeedbackOverlay:
    def __init__(self):
        self.window = None
        self.user_choice = None

    def show(self, action: ActionSchema, confidence: float, step_num: int):
        """Display overlay with feedback options"""
        self.window = tk.Tk()
        self.window.title("Agent Feedback")

        # Make window topmost and semi-transparent
        self.window.attributes('-topmost', True)
        self.window.attributes('-alpha', 0.95)

        # Position in top-right corner
        self.window.geometry(f"400x300+{self.window.winfo_screenwidth()-420}+20")

        # Header
        header = tk.Label(
            self.window,
            text=f"⏸️  Agent Paused - Step {step_num + 1}",
            font=('Arial', 14, 'bold'),
            bg='#2C3E50',
            fg='white',
            pady=10
        )
        header.pack(fill='x')

        # Info panel
        info_frame = tk.Frame(self.window, bg='white', padx=10, pady=10)
        info_frame.pack(fill='both', expand=True)

        tk.Label(
            info_frame,
            text=f"Confidence: {confidence:.0%}",
            font=('Arial', 10),
            fg='orange' if confidence < 0.5 else 'green'
        ).pack(anchor='w')

        tk.Label(
            info_frame,
            text=f"Tool: {action.tool_name}",
            font=('Arial', 10, 'bold')
        ).pack(anchor='w', pady=(5,0))

        tk.Label(
            info_frame,
            text=f"Reasoning: {action.reasoning}",
            font=('Arial', 9),
            wraplength=360,
            justify='left'
        ).pack(anchor='w', pady=(5,0))

        # Button panel
        btn_frame = tk.Frame(self.window, bg='white', padx=10, pady=10)
        btn_frame.pack(fill='x')

        tk.Button(
            btn_frame,
            text="✅ Approve",
            command=lambda: self._set_choice('approve'),
            bg='#27AE60',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=12
        ).pack(side='left', padx=5)

        tk.Button(
            btn_frame,
            text="🎬 Show Me",
            command=lambda: self._set_choice('demonstrate'),
            bg='#3498DB',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=12
        ).pack(side='left', padx=5)

        tk.Button(
            btn_frame,
            text="⏭️ Skip",
            command=lambda: self._set_choice('skip'),
            bg='#95A5A6',
            fg='white',
            font=('Arial', 10, 'bold'),
            width=12
        ).pack(side='left', padx=5)

        # Recording indicator (hidden initially)
        self.recording_label = tk.Label(
            self.window,
            text="",
            bg='white',
            font=('Arial', 10, 'bold')
        )
        self.recording_label.pack(pady=5)

        # Status bar
        status = tk.Label(
            self.window,
            text="Choose an option or demonstrate the correct action",
            bg='#ECF0F1',
            font=('Arial', 9),
            pady=5
        )
        status.pack(fill='x')

        # Wait for user choice
        self.window.mainloop()

        return self.user_choice

    def _set_choice(self, choice: str):
        """Handle user button click"""
        self.user_choice = choice
        if choice != 'demonstrate':
            self.window.destroy()
        else:
            # Enter recording mode
            self.set_recording_mode(True)

    def set_recording_mode(self, active: bool):
        """Show/hide recording indicator"""
        if active:
            self.recording_label.config(
                text="🔴 RECORDING - Perform actions, then click Done",
                fg='red'
            )
            # Add "Done" button
            self.done_button = tk.Button(
                self.window,
                text="✔️ Done Recording",
                command=self._finish_recording,
                bg='#E74C3C',
                fg='white',
                font=('Arial', 10, 'bold')
            )
            self.done_button.pack(pady=10)
        else:
            self.recording_label.config(text="")

    def _finish_recording(self):
        """User finished demonstrating"""
        self.user_choice = 'demonstrated'
        self.window.destroy()

    def hide(self):
        """Close overlay"""
        if self.window:
            self.window.destroy()
```

---

### 3. Integration with HumanObserver

```python
from agent.feedback.human_observer import HumanObserver
from agent.feedback.gui_feedback_capture import GUIFeedbackCapture
from agent.feedback.feedback_overlay import FeedbackOverlay

class HumanObserverGUI(HumanObserver):
    """GUI-enhanced human observer with automatic fallback to CLI"""

    def __init__(self, session_id: str, protocol=None, use_gui: bool = True):
        super().__init__(session_id, protocol)

        self.use_gui = use_gui and self._is_gui_available()

        if self.use_gui:
            self.capture = GUIFeedbackCapture()
            self.overlay = FeedbackOverlay()
            print("[Observer] GUI mode enabled")
        else:
            print("[Observer] CLI mode (GUI not available)")

    def _is_gui_available(self) -> bool:
        """Check if GUI environment is available"""
        try:
            import tkinter
            # Try to create a test window
            test = tkinter.Tk()
            test.withdraw()
            test.destroy()
            return True
        except:
            return False

    def request_approval(
        self,
        action: ActionSchema,
        confidence: float,
        step_num: int,
        alternatives: Optional[list] = None
    ) -> HumanFeedback:
        """Request approval - GUI or CLI based on availability"""

        if self.use_gui:
            return self._request_approval_gui(action, confidence, step_num, alternatives)
        else:
            return super().request_approval(action, confidence, step_num, alternatives)

    def _request_approval_gui(
        self,
        action: ActionSchema,
        confidence: float,
        step_num: int,
        alternatives: Optional[list]
    ) -> HumanFeedback:
        """GUI-based approval request"""

        # Show overlay
        choice = self.overlay.show(action, confidence, step_num)

        if choice == 'approve':
            # Approved
            feedback = HumanFeedback(
                session_id=self.session_id,
                approved=True,
                reasoning="Approved via GUI",
                original_action=action.model_dump(),
                agent_confidence=confidence
            )
            print("[GUI] ✅ Action approved\n")

        elif choice == 'demonstrate':
            # Human will demonstrate correct action(s)
            print("[GUI] 🔴 Recording started - perform correct actions...")

            # Start capturing
            self.capture.start_recording(mode='correction')

            # Wait for user to finish (overlay handles this)
            # When overlay closes, stop recording
            captured_actions = self.capture.stop_recording()

            print(f"[GUI] ✔️ Captured {len(captured_actions)} action(s)")

            if len(captured_actions) == 1:
                # Single action correction
                corrected_action = captured_actions[0]
                feedback = HumanFeedback(
                    session_id=self.session_id,
                    approved=False,
                    correction=corrected_action.model_dump(),
                    reasoning="Corrected via GUI demonstration",
                    original_action=action.model_dump(),
                    agent_confidence=confidence
                )
                print(f"[GUI] 🔄 Corrected to: {corrected_action.tool_name}")

            else:
                # Multi-action procedure
                # Convert to ProceduralGuidance
                goal = self._prompt_for_goal()  # Small dialog

                procedural = ProceduralGuidance(
                    goal=goal,
                    steps=[a.reasoning for a in captured_actions],
                    key_points=None,
                    mistakes_to_avoid=None,
                    alternatives=None
                )

                feedback = HumanFeedback(
                    session_id=self.session_id,
                    approved=False,
                    reasoning=f"Demonstrated procedure: {goal}",
                    original_action=action.model_dump(),
                    agent_confidence=confidence,
                    procedural_guidance=procedural
                )

                print(f"[GUI] 📚 Captured procedure with {len(captured_actions)} steps")

        elif choice == 'skip':
            # Skip step
            feedback = HumanFeedback(
                session_id=self.session_id,
                approved=False,
                correction={"type": "skip_step"},
                reasoning="Skipped via GUI",
                original_action=action.model_dump(),
                agent_confidence=confidence
            )
            print("[GUI] ⏭️ Step skipped\n")

        else:
            # Default to approval if something went wrong
            feedback = HumanFeedback(
                session_id=self.session_id,
                approved=True,
                reasoning="Default approval (GUI issue)",
                original_action=action.model_dump(),
                agent_confidence=confidence
            )

        return feedback
```

---

### 4. Workflow Integration

Modify `agent/workflows/autonomous_workflow.py` to use GUI observer:

```python
from agent.feedback.human_observer_gui import HumanObserverGUI

def execute_autonomous_task(task: str, use_gui: bool = True):
    """Execute task with HITL feedback (GUI or CLI)"""

    # Initialize GUI observer (falls back to CLI automatically)
    observer = HumanObserverGUI(
        session_id=session_id,
        use_gui=use_gui
    )
    observer.start()

    # Rest of workflow unchanged...
    # The observer automatically uses GUI when available
```

---

## Dependencies

Add to `requirements.txt`:

```
# GUI feedback system
pynput>=1.7.6          # Cross-platform input monitoring
pywin32>=305           # Windows UI automation (already used by Windows-MCP)
# tkinter                # Built-in with Python, no install needed
```

---

## Implementation Checklist

### Phase 1: Core Event Capture
- [ ] Create `agent/feedback/gui_feedback_capture.py`
- [ ] Implement mouse click capture
- [ ] Implement keyboard input capture (typing)
- [ ] Implement keyboard shortcut detection
- [ ] Implement event → ActionSchema translation
- [ ] Add UI element detection at cursor position
- [ ] Test with simple click/type scenarios

### Phase 2: Overlay UI
- [ ] Create `agent/feedback/feedback_overlay.py`
- [ ] Implement basic overlay window (topmost, transparent)
- [ ] Add approval buttons (Approve/Skip/Demonstrate)
- [ ] Add recording indicator
- [ ] Add action info display
- [ ] Test overlay appearance and button clicks

### Phase 3: Observer Integration
- [ ] Create `agent/feedback/human_observer_gui.py` extending `HumanObserver`
- [ ] Implement `_request_approval_gui()`
- [ ] Implement GUI/CLI auto-detection and fallback
- [ ] Integrate capture + overlay for approval flow
- [ ] Handle single-action corrections
- [ ] Handle multi-action procedural demonstrations

### Phase 4: Advanced Features
- [ ] Implement proactive interrupt (global hotkey)
- [ ] Add visual verification UI for task completion
- [ ] Add before/after screenshot comparison
- [ ] Implement action sequence optimization (merge consecutive types)
- [ ] Add keyboard shortcut reference guide in overlay

### Phase 5: Testing & Polish
- [ ] Test Mode A: Proactive interrupt during execution
- [ ] Test Mode B: Low confidence approval with demonstration
- [ ] Test Mode C: Multi-step procedural learning
- [ ] Test Mode D: Visual verification UI
- [ ] Test fallback to CLI when GUI unavailable
- [ ] Add error handling for edge cases
- [ ] Performance testing (recording latency)

### Phase 6: Documentation
- [ ] Add user guide for GUI feedback system
- [ ] Document keyboard shortcuts
- [ ] Create video demo showing GUI feedback in action
- [ ] Update README with GUI feedback features

---

## User Experience Flow Example

### Scenario: Agent tries to concatenate files with low confidence

**Step-by-step UX:**

1. **Agent proposes action:**
   ```
   Tool: Click-Tool
   Location: [450, 300]
   Confidence: 35%
   Reasoning: "Click concatenate button based on UI tree"
   ```

2. **Overlay appears** (top-right corner):
   ```
   ┌─────────────────────────────────────┐
   │ ⏸️  Agent Paused - Step 6           │
   ├─────────────────────────────────────┤
   │ Confidence: 35% ⚠️                  │
   │                                     │
   │ Tool: Click-Tool                    │
   │ Reasoning: Click concatenate button │
   │            based on UI tree         │
   │                                     │
   │ ┌──────┐ ┌──────┐ ┌──────┐        │
   │ │✅ Approve │🎬 Show Me│⏭️ Skip│     │
   │ └──────┘ └──────┘ └──────┘        │
   │                                     │
   │ Choose option or demonstrate action │
   └─────────────────────────────────────┘
   ```

3. **Human clicks "Show Me":**
   - Overlay updates:
   ```
   🔴 RECORDING - Perform actions, then click Done

   ┌────────────────────┐
   │ ✔️ Done Recording  │
   └────────────────────┘
   ```

4. **Human performs correct sequence:**
   - Clicks on menu bar at (120, 45) → Opens "Concatenate" menu
   - Clicks on "Add Files" button at (200, 150)
   - Types file path: "C:\Users\test\file1.mf4"
   - Presses Enter
   - Clicks "OK" at (450, 500)

5. **Human clicks "Done Recording":**
   - System captures 5 actions
   - Overlay closes
   - Terminal shows:
   ```
   [GUI] ✔️ Captured 5 action(s)

   Captured procedure:
   1. Click-Tool: loc=[120, 45] - Click on Concatenate menu
   2. Click-Tool: loc=[200, 150] - Click on Add Files button
   3. Type-Tool: text="C:\Users\test\file1.mf4"
   4. Key-Tool: key="enter"
   5. Click-Tool: loc=[450, 500] - Click on OK button

   [GUI] 📚 Stored as procedural guidance
   [Agent] Replanning with demonstrated procedure...
   ```

6. **Agent replans and executes:**
   - Uses demonstrated sequence instead of original single click
   - Learns the correct procedure for future similar tasks
   - Stores in memory with high confidence

---

## Benefits

### For Humans:
1. **Natural interaction** - Show, don't tell
2. **Visual context** - See what agent is doing
3. **Faster feedback** - Click instead of typing JSON
4. **Better corrections** - Demonstrate exact sequence
5. **Less cognitive load** - No need to think in terms of tool names and arguments

### For Agent:
1. **Precise corrections** - Exact coordinates and sequences
2. **Procedural learning** - Learn multi-step workflows
3. **Better context** - Understand UI elements at interaction points
4. **Reusable skills** - Store verified procedures as skills
5. **Faster improvement** - More feedback means faster learning

### For System:
1. **Backward compatible** - Falls back to CLI automatically
2. **Non-intrusive** - Overlay doesn't block target application
3. **Flexible** - Supports multiple feedback modes
4. **Extensible** - Easy to add new feedback types
5. **Robust** - Handles edge cases and errors gracefully

---

## Future Enhancements

### Potential additions:
1. **Screen recording** - Record video of demonstrated procedures
2. **Visual annotations** - Draw on screen to highlight areas
3. **Voice guidance** - Add speech-to-text for verbal instructions
4. **Multi-monitor support** - Track actions across multiple screens
5. **Undo/redo** - Allow humans to undo captured actions
6. **Replay mode** - Show agent what it will do before executing
7. **Collaborative mode** - Multiple humans can provide feedback
8. **Mobile companion** - Provide feedback from phone while agent works on PC
9. **Smart suggestions** - AI suggests likely corrections based on patterns
10. **Accessibility features** - Screen reader support, high contrast mode

---

## Notes & Considerations

### Technical Challenges:
1. **Event filtering** - Need to ignore agent's own actions during execution
2. **Timing** - Sync between overlay state and agent state
3. **Thread safety** - Overlay runs in GUI thread, agent in main thread
4. **Resource usage** - Event hooks can be CPU-intensive if not optimized
5. **Security** - Keyboard hooks might be flagged by antivirus

### Design Decisions:
1. **Why tkinter over PyQt?** - Built-in, lightweight, sufficient for this use case
2. **Why pynput over pyHook?** - Cross-platform, actively maintained, better API
3. **Why overlay over separate window?** - Less intrusive, always visible
4. **Why capture raw events vs screenshot+CV?** - More precise, lower latency, no GPU needed

### Best Practices:
1. Always provide CLI fallback
2. Make overlay dismissible (Esc key)
3. Show clear recording indicator
4. Provide undo for captured actions
5. Confirm before executing captured actions
6. Log all GUI feedback events for debugging
7. Handle edge cases gracefully (e.g., agent clicked on overlay)

---

## Getting Started

Once implemented, usage will be:

```python
from agent.workflows.autonomous_workflow import execute_autonomous_task

# GUI mode (default, auto-fallback to CLI if needed)
result = execute_autonomous_task(
    task="Concatenate all MF4 files in C:\\Users\\test\\",
    use_gui=True
)

# CLI mode (force terminal-based feedback)
result = execute_autonomous_task(
    task="Concatenate all MF4 files in C:\\Users\\test\\",
    use_gui=False
)
```

No other code changes needed - the system auto-detects GUI availability!

---

## Questions for Implementation

Before implementing, consider:

1. **Hotkey for proactive interrupt**: Which key combo? (Ctrl+Shift+F, Ctrl+Pause, other?)
2. **Overlay position**: Top-right, top-left, bottom-right, or user-configurable?
3. **Recording timeout**: Auto-stop recording after N seconds of inactivity?
4. **Action confirmation**: Show captured actions for approval before sending to agent?
5. **Error handling**: What happens if capture fails mid-recording?
6. **Multi-monitor**: Track which monitor agent is working on?
7. **Accessibility**: Support for screen readers?

---

## Conclusion

This GUI feedback system transforms the human-in-the-loop experience from **tedious text input** to **natural demonstration-based teaching**.

The agent learns not just from corrections, but from **watching humans perform tasks correctly**, making it a true learning system that improves with use.

**Next Step**: Implement Phase 1 (Core Event Capture) and test with simple click/type scenarios.