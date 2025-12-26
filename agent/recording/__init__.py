"""
Demonstration Recording Module

This module provides functionality to record human demonstrations of GUI workflows
and convert them into coordinate-agnostic verified skills.

Components:
- action_recorder: Captures mouse/keyboard events
- action_normalizer: Converts raw actions to ActionSchema format
- parameter_extractor: Identifies and parameterizes file paths and values
- task_inferencer: Uses LLM to infer task descriptions from action sequences
"""

from .action_recorder import ActionRecorder
from .action_normalizer import ActionNormalizer
from .parameter_extractor import ParameterExtractor
from .task_inferencer import TaskInferencer

__all__ = [
    'ActionRecorder',
    'ActionNormalizer',
    'ParameterExtractor',
    'TaskInferencer',
]
