"""Centralized prompts for the autonomous workflow"""

from .planning_prompt import get_planning_system_prompt, get_planning_user_prompt
from .recovery_prompt import get_recovery_prompt
from .coordinate_resolution_prompt import get_coordinate_resolution_prompt
from .doc_parsing_prompt import get_doc_parsing_prompt

__all__ = [
    'get_planning_system_prompt',
    'get_planning_user_prompt',
    'get_recovery_prompt',
    'get_coordinate_resolution_prompt',
    'get_doc_parsing_prompt',
]
