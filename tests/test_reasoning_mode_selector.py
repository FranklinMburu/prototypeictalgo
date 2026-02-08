"""
Unit tests for Stage 4 — Reasoning Mode Selection.

Tests cover:
  - HTFBiasState enum values
  - ReasoningModeSelector deterministic mode selection
  - All valid state combinations
  - Error cases (invalid inputs, ambiguous states)
  - Mode selection from dict
"""

import pytest
from reasoner_service.reasoning_mode_selector import (
    HTFBiasState,
    ReasoningMode,
    ReasoningModeSelector,
    ModeSelectionResult,
    ModeSelectionError,
)


# ============================================================================
# HTF BIAS STATE ENUM TESTS
# ============================================================================

class TestHTFBiasStateEnum:
    """Test HTFBiasState enum integrity."""
    
    def test_undefined_value(self):
        """Test UNDEFINED state value."""
        assert HTFBiasState.UNDEFINED.value == "undefined"
    
    def test_bias_up_value(self):
        """Test BIAS_UP state value."""
        assert HTFBiasState.BIAS_UP.value == "bias_up"
    
    def test_bias_down_value(self):
        """Test BIAS_DOWN state value."""
        assert HTFBiasState.BIAS_DOWN.value == "bias_down"
    
    def test_bias_neutral_value(self):
        """Test BIAS_NEUTRAL state value."""
        assert HTFBiasState.BIAS_NEUTRAL.value == "bias_neutral"
    
    def test_invalidated_value(self):
        """Test INVALIDATED state value."""
        assert HTFBiasState.INVALIDATED.value == "invalidated"
    
    def test_from_string(self):
        """Test HTFBiasState can be created from string."""
        assert HTFBiasState("undefined") == HTFBiasState.UNDEFINED
        assert HTFBiasState("bias_up") == HTFBiasState.BIAS_UP
        assert HTFBiasState("bias_down") == HTFBiasState.BIAS_DOWN
        assert HTFBiasState("bias_neutral") == HTFBiasState.BIAS_NEUTRAL
        assert HTFBiasState("invalidated") == HTFBiasState.INVALIDATED


# ============================================================================
# REASONING MODE SELECTOR TESTS
# ============================================================================

class TestReasoningModeSelector:
    """Test ReasoningModeSelector deterministic mode selection."""
    
    def setup_method(self):
        """Initialize selector for each test."""
        self.selector = ReasoningModeSelector()
    
    # ========================================================================
    # RULE 1: HTF BIAS UNDEFINED/INVALIDATED → bias_evaluation
    # ========================================================================
    
    def test_mode_selection_undefined_no_position(self):
        """Rule 1: UNDEFINED bias, no position → bias_evaluation."""
        result = self.selector.select_mode(
            htf_bias_state=HTFBiasState.UNDEFINED,
            position_open=False
        )
        assert result.mode == "bias_evaluation"
        assert result.error is None
        assert "undefined" in result.reason.lower()
    
    def test_mode_selection_undefined_with_position(self):
        """Rule 1: UNDEFINED bias, position open → bias_evaluation (not trade_management).
        
        Even if a position is open, if HTF bias is undefined, we must evaluate
        the bias first before managing the trade.
        """
        result = self.selector.select_mode(
            htf_bias_state=HTFBiasState.UNDEFINED,
            position_open=True
        )
        assert result.mode == "bias_evaluation"
        assert result.error is None
    
    def test_mode_selection_invalidated_no_position(self):
        """Rule 1: INVALIDATED bias, no position → bias_evaluation."""
        result = self.selector.select_mode(
            htf_bias_state=HTFBiasState.INVALIDATED,
            position_open=False
        )
        assert result.mode == "bias_evaluation"
        assert result.error is None
        assert "invalidated" in result.reason.lower()
    
    def test_mode_selection_invalidated_with_position(self):
        """Rule 1: INVALIDATED bias, position open → bias_evaluation (re-evaluation required)."""
        result = self.selector.select_mode(
            htf_bias_state=HTFBiasState.INVALIDATED,
            position_open=True
        )
        assert result.mode == "bias_evaluation"
        assert result.error is None
    
    # ========================================================================
    # RULE 2: HTF BIAS VALID & NO POSITION → entry_evaluation
    # ========================================================================
    
    def test_mode_selection_bias_up_no_position(self):
        """Rule 2: BIAS_UP, no position → entry_evaluation."""
        result = self.selector.select_mode(
            htf_bias_state=HTFBiasState.BIAS_UP,
            position_open=False
        )
        assert result.mode == "entry_evaluation"
        assert result.error is None
        assert "bias_up" in result.reason.lower()
    
    def test_mode_selection_bias_down_no_position(self):
        """Rule 2: BIAS_DOWN, no position → entry_evaluation."""
        result = self.selector.select_mode(
            htf_bias_state=HTFBiasState.BIAS_DOWN,
            position_open=False
        )
        assert result.mode == "entry_evaluation"
        assert result.error is None
        assert "bias_down" in result.reason.lower()
    
    def test_mode_selection_bias_neutral_no_position(self):
        """Rule 2: BIAS_NEUTRAL, no position → entry_evaluation."""
        result = self.selector.select_mode(
            htf_bias_state=HTFBiasState.BIAS_NEUTRAL,
            position_open=False
        )
        assert result.mode == "entry_evaluation"
        assert result.error is None
        assert "bias_neutral" in result.reason.lower()
    
    # ========================================================================
    # RULE 3: POSITION OPEN → trade_management
    # ========================================================================
    
    def test_mode_selection_bias_up_with_position(self):
        """Rule 3: BIAS_UP, position open → trade_management."""
        result = self.selector.select_mode(
            htf_bias_state=HTFBiasState.BIAS_UP,
            position_open=True
        )
        assert result.mode == "trade_management"
        assert result.error is None
    
    def test_mode_selection_bias_down_with_position(self):
        """Rule 3: BIAS_DOWN, position open → trade_management."""
        result = self.selector.select_mode(
            htf_bias_state=HTFBiasState.BIAS_DOWN,
            position_open=True
        )
        assert result.mode == "trade_management"
        assert result.error is None
    
    def test_mode_selection_bias_neutral_with_position(self):
        """Rule 3: BIAS_NEUTRAL, position open → trade_management."""
        result = self.selector.select_mode(
            htf_bias_state=HTFBiasState.BIAS_NEUTRAL,
            position_open=True
        )
        assert result.mode == "trade_management"
        assert result.error is None
    
    # ========================================================================
    # ERROR CASES: Invalid Input Types
    # ========================================================================
    
    def test_invalid_bias_state_type_string(self):
        """Invalid: pass string instead of HTFBiasState enum."""
        with pytest.raises(ModeSelectionError) as exc_info:
            self.selector.select_mode(
                htf_bias_state="bias_up",  # string, not enum
                position_open=False
            )
        assert "Invalid HTF bias state type" in str(exc_info.value)
    
    def test_invalid_bias_state_type_none(self):
        """Invalid: pass None as HTFBiasState."""
        with pytest.raises(ModeSelectionError) as exc_info:
            self.selector.select_mode(
                htf_bias_state=None,
                position_open=False
            )
        assert "Invalid HTF bias state type" in str(exc_info.value)
    
    def test_invalid_position_type_string(self):
        """Invalid: pass string instead of bool for position_open."""
        with pytest.raises(ModeSelectionError) as exc_info:
            self.selector.select_mode(
                htf_bias_state=HTFBiasState.UNDEFINED,
                position_open="true"  # string, not bool
            )
        assert "Invalid position_open type" in str(exc_info.value)
    
    def test_invalid_position_type_int(self):
        """Invalid: pass int instead of bool for position_open."""
        with pytest.raises(ModeSelectionError) as exc_info:
            self.selector.select_mode(
                htf_bias_state=HTFBiasState.BIAS_UP,
                position_open=1  # int, not bool
            )
        assert "Invalid position_open type" in str(exc_info.value)
    
    # ========================================================================
    # SELECT MODE FROM DICT
    # ========================================================================
    
    def test_select_mode_from_dict_valid(self):
        """select_mode_from_dict: valid dict with enum value."""
        state = {
            "htf_bias_state": HTFBiasState.BIAS_UP,
            "position_open": False
        }
        result = self.selector.select_mode_from_dict(state)
        assert result.mode == "entry_evaluation"
    
    def test_select_mode_from_dict_string_value(self):
        """select_mode_from_dict: dict with string bias state value."""
        state = {
            "htf_bias_state": "bias_down",
            "position_open": True
        }
        result = self.selector.select_mode_from_dict(state)
        assert result.mode == "trade_management"
    
    def test_select_mode_from_dict_missing_bias_state(self):
        """select_mode_from_dict: missing htf_bias_state key."""
        state = {
            "position_open": False
        }
        with pytest.raises(ModeSelectionError) as exc_info:
            self.selector.select_mode_from_dict(state)
        assert "Missing required key" in str(exc_info.value)
    
    def test_select_mode_from_dict_missing_position(self):
        """select_mode_from_dict: missing position_open key."""
        state = {
            "htf_bias_state": HTFBiasState.BIAS_UP
        }
        with pytest.raises(ModeSelectionError) as exc_info:
            self.selector.select_mode_from_dict(state)
        assert "Missing required key" in str(exc_info.value)
    
    def test_select_mode_from_dict_invalid_string_bias(self):
        """select_mode_from_dict: invalid string bias state value."""
        state = {
            "htf_bias_state": "invalid_bias",
            "position_open": False
        }
        with pytest.raises(ModeSelectionError) as exc_info:
            self.selector.select_mode_from_dict(state)
        assert "Invalid HTF bias state string" in str(exc_info.value)
    
    # ========================================================================
    # MODE SELECTION RESULT DATA CLASS
    # ========================================================================
    
    def test_mode_selection_result_defaults(self):
        """ModeSelectionResult: default values."""
        result = ModeSelectionResult()
        assert result.mode is None
        assert result.reason == ""
        assert result.error is None
    
    def test_mode_selection_result_with_values(self):
        """ModeSelectionResult: populated values."""
        result = ModeSelectionResult(
            mode="bias_evaluation",
            reason="HTF is undefined",
            error=None
        )
        assert result.mode == "bias_evaluation"
        assert result.reason == "HTF is undefined"
        assert result.error is None


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestReasoningModeSelectionIntegration:
    """Integration tests for reasoning mode selection in workflow."""
    
    def setup_method(self):
        """Initialize selector for each test."""
        self.selector = ReasoningModeSelector()
    
    def test_state_machine_progression_new_bias(self):
        """Workflow: Establish bias → then evaluate entries."""
        # Step 1: No bias defined yet
        result1 = self.selector.select_mode(HTFBiasState.UNDEFINED, False)
        assert result1.mode == "bias_evaluation"
        
        # Step 2: After bias established, ready for entries
        result2 = self.selector.select_mode(HTFBiasState.BIAS_UP, False)
        assert result2.mode == "entry_evaluation"
    
    def test_state_machine_progression_entry_to_position(self):
        """Workflow: Entry evaluation → position opened → trade management."""
        # Step 1: Entry mode
        result1 = self.selector.select_mode(HTFBiasState.BIAS_UP, False)
        assert result1.mode == "entry_evaluation"
        
        # Step 2: Position opened
        result2 = self.selector.select_mode(HTFBiasState.BIAS_UP, True)
        assert result2.mode == "trade_management"
    
    def test_state_machine_progression_invalidation(self):
        """Workflow: Valid bias → invalidated → back to bias evaluation."""
        # Step 1: Valid entry mode
        result1 = self.selector.select_mode(HTFBiasState.BIAS_DOWN, False)
        assert result1.mode == "entry_evaluation"
        
        # Step 2: Bias invalidated
        result2 = self.selector.select_mode(HTFBiasState.INVALIDATED, False)
        assert result2.mode == "bias_evaluation"
    
    def test_all_valid_combinations(self):
        """Test all valid state combinations produce valid modes."""
        bias_states = [
            HTFBiasState.UNDEFINED,
            HTFBiasState.BIAS_UP,
            HTFBiasState.BIAS_DOWN,
            HTFBiasState.BIAS_NEUTRAL,
            HTFBiasState.INVALIDATED,
        ]
        position_states = [True, False]
        
        for bias in bias_states:
            for position in position_states:
                result = self.selector.select_mode(bias, position)
                # All combinations should produce a valid mode
                assert result.mode in ["bias_evaluation", "entry_evaluation", "trade_management"]
                assert result.error is None
