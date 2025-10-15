"""Cost tracking for OpenAI API usage"""
from dataclasses import dataclass, field
from typing import Dict, List
from datetime import datetime
import json
import os


# OpenAI pricing (as of 2025)
PRICING = {
    # GPT-5 family
    "gpt-5": {
        "input": 1.250 / 1_000_000,      # $1.250 per 1M tokens
        "output": 10.000 / 1_000_000,     # $10.000 per 1M tokens
    },
    "gpt-5-mini": {
        "input": 0.250 / 1_000_000,       # $0.250 per 1M tokens
        "output": 2.000 / 1_000_000,      # $2.000 per 1M tokens
    },
    "gpt-5-nano": {
        "input": 0.050 / 1_000_000,       # $0.050 per 1M tokens
        "output": 0.400 / 1_000_000,      # $0.400 per 1M tokens
    },
    "gpt-5-pro": {
        "input": 15.00 / 1_000_000,       # $15.00 per 1M tokens
        "output": 120.00 / 1_000_000,     # $120.00 per 1M tokens
    },
    # GPT-4o family (legacy)
    "gpt-4o-mini": {
        "input": 0.15 / 1_000_000,     # $0.15 per 1M tokens
        "output": 0.60 / 1_000_000,     # $0.60 per 1M tokens
    },
    "gpt-4o": {
        "input": 2.50 / 1_000_000,      # $2.50 per 1M tokens
        "output": 10.00 / 1_000_000,       # $10.00 per 1M tokens
    },
}


@dataclass
class APICall:
    """Single API call record"""
    timestamp: str
    model: str
    component: str
    input_tokens: int
    output_tokens: int
    cost: float
    task_context: str = ""


@dataclass
class CostTracker:
    """Tracks API costs across workflow components"""
    calls: List[APICall] = field(default_factory=list)
    session_start: str = field(default_factory=lambda: datetime.now().isoformat())

    def track_call(
        self,
        model: str,
        component: str,
        input_tokens: int,
        output_tokens: int,
        task_context: str = ""
    ) -> float:
        """Track an API call and return cost

        Args:
            model: Model name (e.g., "gpt-5-mini")
            component: Component name (e.g., "planning", "recovery", "resolution")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            task_context: Optional task description for context

        Returns:
            Cost in dollars
        """
        if model not in PRICING:
            print(f"Warning: Unknown model '{model}', cost will be $0.00")
            cost = 0.0
        else:
            pricing = PRICING[model]
            cost = (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])

        call = APICall(
            timestamp=datetime.now().isoformat(),
            model=model,
            component=component,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            task_context=task_context
        )

        self.calls.append(call)
        return cost

    def get_summary(self) -> Dict:
        """Get cost summary

        Returns:
            Dictionary with cost breakdown
        """
        total_cost = sum(call.cost for call in self.calls)
        total_input_tokens = sum(call.input_tokens for call in self.calls)
        total_output_tokens = sum(call.output_tokens for call in self.calls)

        # Group by component
        by_component = {}
        for call in self.calls:
            if call.component not in by_component:
                by_component[call.component] = {
                    "calls": 0,
                    "cost": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                }
            by_component[call.component]["calls"] += 1
            by_component[call.component]["cost"] += call.cost
            by_component[call.component]["input_tokens"] += call.input_tokens
            by_component[call.component]["output_tokens"] += call.output_tokens

        # Group by model
        by_model = {}
        for call in self.calls:
            if call.model not in by_model:
                by_model[call.model] = {
                    "calls": 0,
                    "cost": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                }
            by_model[call.model]["calls"] += 1
            by_model[call.model]["cost"] += call.cost
            by_model[call.model]["input_tokens"] += call.input_tokens
            by_model[call.model]["output_tokens"] += call.output_tokens

        return {
            "session_start": self.session_start,
            "total_calls": len(self.calls),
            "total_cost": total_cost,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "by_component": by_component,
            "by_model": by_model,
        }

    def print_summary(self):
        """Print formatted cost summary"""
        summary = self.get_summary()

        print("\n" + "="*80)
        print("API COST SUMMARY")
        print("="*80)
        print(f"Session started: {summary['session_start']}")
        print(f"Total API calls: {summary['total_calls']}")
        print(f"Total cost: ${summary['total_cost']:.4f}")
        print(f"Total tokens: {summary['total_input_tokens']:,} input + {summary['total_output_tokens']:,} output")

        print("\n" + "-"*80)
        print("COST BY COMPONENT")
        print("-"*80)
        for component, stats in summary["by_component"].items():
            print(f"{component:20} | Calls: {stats['calls']:3} | Cost: ${stats['cost']:.4f} | "
                  f"Tokens: {stats['input_tokens']:,} in + {stats['output_tokens']:,} out")

        print("\n" + "-"*80)
        print("COST BY MODEL")
        print("-"*80)
        for model, stats in summary["by_model"].items():
            print(f"{model:20} | Calls: {stats['calls']:3} | Cost: ${stats['cost']:.4f} | "
                  f"Tokens: {stats['input_tokens']:,} in + {stats['output_tokens']:,} out")

        print("="*80 + "\n")

    def save_to_file(self, filepath: str = None):
        """Save cost summary to JSON file

        Args:
            filepath: Optional file path (defaults to cost_reports/cost_TIMESTAMP.json)
        """
        if filepath is None:
            os.makedirs("cost_reports", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"cost_reports/cost_{timestamp}.json"

        summary = self.get_summary()

        # Add individual calls for detailed analysis
        summary["calls"] = [
            {
                "timestamp": call.timestamp,
                "model": call.model,
                "component": call.component,
                "input_tokens": call.input_tokens,
                "output_tokens": call.output_tokens,
                "cost": call.cost,
                "task_context": call.task_context
            }
            for call in self.calls
        ]

        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"Cost summary saved to: {filepath}")
        return filepath


# Global cost tracker instance
_global_tracker = None


def get_global_tracker() -> CostTracker:
    """Get or create the global cost tracker"""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = CostTracker()
    return _global_tracker


def reset_global_tracker():
    """Reset the global cost tracker"""
    global _global_tracker
    _global_tracker = CostTracker()


def track_api_call(model: str, component: str, input_tokens: int, output_tokens: int, task_context: str = "") -> float:
    """Convenience function to track an API call

    Args:
        model: Model name
        component: Component name
        input_tokens: Input token count
        output_tokens: Output token count
        task_context: Optional task context

    Returns:
        Cost in dollars
    """
    tracker = get_global_tracker()
    return tracker.track_call(model, component, input_tokens, output_tokens, task_context)
