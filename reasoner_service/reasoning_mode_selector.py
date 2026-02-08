"""
Stage 4: Reasoning Mode Selection for Trading Decision Loop v1.1

This module implements deterministic logic to select exactly ONE reasoning mode
per decision cycle, based on HTF bias state and position state.

Modes:
  - bias_evaluation: Triggered when HTF bias is UNDEFINED or INVALIDATED
  - entry_evaluation: Triggered when HTF bias is valid AND no position is open
  - trade_management: Triggered only when a position is already open

Authority:
  The ReasoningModeSelector is the sole authority for mode selection.
  The orchestrator MUST NOT invoke reasoning_manager.reason() without
  first obtaining a valid mode from this selector.

Non-Goals:
  - Does NOT modify orchestrator state
  - Does NOT perform any reasoning
  - Does NOT access memory or historical data
  - Does NOT make trading decisions
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass


# ============================================================================
# HTF BIAS STATE ENUM
# ============================================================================

class HTFBiasState(str, Enum):
    """HTF bias state machine.
    
    UNDEFINED: No HTF bias evaluation has been performed yet. Requires bias evaluation.
    BIAS_UP: HTF shows bullish structure/context. Ready for entry evaluation.
    BIAS_DOWN: HTF shows bearish structure/context. Ready for entry evaluation.
    BIAS_NEUTRAL: HTF shows consolidating/indecisive structure. Ready for entry evaluation.
    INVALIDATED: Previous HTF bias has been invalidated (price action contradiction, etc).
                  Requires re-evaluation of bias.
    """
    UNDEFINED = "undefined"
    BIAS_UP = "bias_up"
    BIAS_DOWN = "bias_down"
    BIAS_NEUTRAL = "bias_neutral"
    INVALIDATED = "invalidated"


# ============================================================================
# REASONING MODE TYPES
# ============================================================================

ReasoningMode = Literal["bias_evaluation", "entry_evaluation", "trade_management"]


# ============================================================================
# MODE SELECTION ERROR
# ============================================================================

class ModeSelectionError(Exception):
    """Raised when mode selection encounters an unresolvable ambiguity."""
    
    def __init__(self, message: str, htf_bias_state: Optional[HTFBiasState] = None, position_open: Optional[bool] = None):
        self.message = message
        self.htf_bias_state = htf_bias_state
        self.position_open = position_open
        super().__init__(self.message)


# ============================================================================
# REASONING MODE SELECTOR
# ============================================================================

@dataclass
class ModeSelectionResult:
    """Result of a mode selection attempt.
    
    Attributes:
        mode: The selected reasoning mode, or None if selection failed.
        reason: Human-readable explanation of the selection.
        error: Error message if selection failed.
    """
    mode: Optional[ReasoningMode] = None
    reason: str = ""
    error: Optional[str] = None


class ReasoningModeSelector:
    """Deterministic reasoning mode selector for Stage 4.
    
    This class is the sole authority for selecting which reasoning mode
    to use in each decision cycle. Mode selection is purely deterministic
    based on HTF bias state and position state, with no other inputs.
    
    Mode Selection Rules (Non-Negotiable):
      1. If HTF bias is UNDEFINED or INVALIDATED → bias_evaluation
      2. Else if HTF bias is valid AND no position is open → entry_evaluation
      3. Else if a position is open → trade_management
      4. Any other state → hard error (ModeSelectionError)
    
    Example:
        selector = ReasoningModeSelector()
        
        # Case 1: No bias defined yet
        result = selector.select_mode(
            htf_bias_state=HTFBiasState.UNDEFINED,
            position_open=False
        )
        assert result.mode == "bias_evaluation"
        
        # Case 2: Bias valid, no position
        result = selector.select_mode(
            htf_bias_state=HTFBiasState.BIAS_UP,
            position_open=False
        )
        assert result.mode == "entry_evaluation"
        
        # Case 3: Position open
        result = selector.select_mode(
            htf_bias_state=HTFBiasState.BIAS_DOWN,
            position_open=True
        )
        assert result.mode == "trade_management"
    """
    
    def __init__(self):
        """Initialize the ReasoningModeSelector."""
        self._valid_bias_states = {
            HTFBiasState.BIAS_UP,
            HTFBiasState.BIAS_DOWN,
            HTFBiasState.BIAS_NEUTRAL
        }
        self._invalid_bias_states = {
            HTFBiasState.UNDEFINED,
            HTFBiasState.INVALIDATED
        }
    
    def select_mode(
        self,
        htf_bias_state: HTFBiasState,
        position_open: bool
    ) -> ModeSelectionResult:
        """Deterministically select reasoning mode based on state.
        
        Args:
            htf_bias_state: Current HTF bias state (must be HTFBiasState enum value)
            position_open: Boolean indicating if a position is currently open
            
        Returns:
            ModeSelectionResult with selected mode, reason, and optional error.
            
        Raises:
            ModeSelectionError: If inputs are invalid or state is ambiguous.
        """
        # =====================================================================
        # INPUT VALIDATION
        # =====================================================================
        
        if not isinstance(htf_bias_state, HTFBiasState):
            raise ModeSelectionError(
                f"Invalid HTF bias state type: {type(htf_bias_state)}. "
                f"Must be HTFBiasState enum value.",
                htf_bias_state=None,
                position_open=position_open
            )
        
        if not isinstance(position_open, bool):
            raise ModeSelectionError(
                f"Invalid position_open type: {type(position_open)}. Must be bool.",
                htf_bias_state=htf_bias_state,
                position_open=None
            )
        
        # =====================================================================
        # MODE SELECTION LOGIC
        # =====================================================================
        
        # Rule 1: If HTF bias is UNDEFINED or INVALIDATED → bias_evaluation
        if htf_bias_state in self._invalid_bias_states:
            return ModeSelectionResult(
                mode="bias_evaluation",
                reason=f"HTF bias state is {htf_bias_state.value}; "
                       "bias evaluation required before entry evaluation."
            )
        
        # Rule 2: If HTF bias is valid AND no position is open → entry_evaluation
        if htf_bias_state in self._valid_bias_states and not position_open:
            return ModeSelectionResult(
                mode="entry_evaluation",
                reason=f"HTF bias is {htf_bias_state.value}; "
                       "no position open; ready for entry evaluation."
            )
        
        # Rule 3: If a position is open → trade_management
        if position_open:
            return ModeSelectionResult(
                mode="trade_management",
                reason=f"Position is open; trade management mode selected "
                       f"(HTF bias: {htf_bias_state.value})."
            )
        
        # =====================================================================
        # UNRESOLVABLE STATE: Should not reach here if logic is correct
        # =====================================================================
        
        raise ModeSelectionError(
            f"Unresolvable state: HTF bias={htf_bias_state.value}, "
            f"position_open={position_open}. This should not occur with valid inputs.",
            htf_bias_state=htf_bias_state,
            position_open=position_open
        )
    
    def select_mode_from_dict(
        self,
        state: Dict[str, Any]
    ) -> ModeSelectionResult:
        """Select mode from a state dictionary.
        
        Convenience method that extracts HTF bias state and position state
        from a dictionary before calling select_mode().
        
        Args:
            state: Dictionary with optional 'htf_bias_state' and 'position_open' keys.
                   Keys must exist; values must be valid types.
                   
        Returns:
            ModeSelectionResult with selected mode, reason, and optional error.
            
        Raises:
            KeyError: If required keys are missing from state dict.
            ModeSelectionError: If state values are invalid or state is ambiguous.
        """
        try:
            htf_bias_state = state["htf_bias_state"]
            position_open = state["position_open"]
        except KeyError as e:
            raise ModeSelectionError(
                f"Missing required key in state dict: {e}. "
                f"Must have 'htf_bias_state' and 'position_open'."
            )
        
        # Convert string to enum if needed
        if isinstance(htf_bias_state, str):
            try:
                htf_bias_state = HTFBiasState(htf_bias_state)
            except ValueError:
                raise ModeSelectionError(
                    f"Invalid HTF bias state string: '{htf_bias_state}'. "
                    f"Valid values: {', '.join([s.value for s in HTFBiasState])}"
                )
        
        return self.select_mode(htf_bias_state, position_open)
