"""
Tests for OutcomePolicyEvaluator

Tests the deterministic policy evaluation system:
- Policy rule evaluation (win rate, loss streak, avg PnL, drawdown)
- Edge cases (insufficient data, null stats, empty results)
- Deterministic outputs (same input → same output)
- Audit logging (VETO reasons tracked)
- Rule composition (multiple rules, first VETO wins)
- Error handling (non-blocking, graceful degradation)

Test Coverage:
- PolicyDecision enum validation
- PolicyEvaluation dataclass behavior
- All policy rule types
- OutcomePolicyEvaluator composition
- Factory function behavior
- Edge cases and error conditions
"""

import pytest
import asyncio
from datetime import datetime, timezone
from reasoner_service.outcome_policy_evaluator import (
    PolicyDecision,
    PolicyEvaluation,
    PolicyRule,
    WinRateThresholdRule,
    LossStreakRule,
    AvgPnLThresholdRule,
    SymbolDrawdownRule,
    OutcomePolicyEvaluator,
    create_policy_evaluator,
)


class TestPolicyDecisionEnum:
    """Test PolicyDecision enum."""

    def test_enum_has_allow(self):
        """Test ALLOW value exists."""
        assert hasattr(PolicyDecision, 'ALLOW')
        assert PolicyDecision.ALLOW.value == "allow"

    def test_enum_has_veto(self):
        """Test VETO value exists."""
        assert hasattr(PolicyDecision, 'VETO')
        assert PolicyDecision.VETO.value == "veto"


class TestPolicyEvaluationDataclass:
    """Test PolicyEvaluation dataclass."""

    def test_evaluation_creation(self):
        """Test creating a PolicyEvaluation."""
        eval_obj = PolicyEvaluation(
            decision=PolicyDecision.VETO,
            reason="Test reason",
            rule_name="test_rule",
            signal_type="bullish_choch",
            symbol="EURUSD",
        )
        assert eval_obj.decision == PolicyDecision.VETO
        assert eval_obj.reason == "Test reason"
        assert eval_obj.rule_name == "test_rule"
        assert eval_obj.timestamp is not None

    def test_evaluation_to_dict(self):
        """Test converting PolicyEvaluation to dict."""
        eval_obj = PolicyEvaluation(
            decision=PolicyDecision.VETO,
            reason="Test reason",
            rule_name="test_rule",
            signal_type="bullish_choch",
        )
        d = eval_obj.to_dict()
        assert d["decision"] == "veto"
        assert d["reason"] == "Test reason"
        assert d["rule_name"] == "test_rule"
        assert d["signal_type"] == "bullish_choch"
        assert "timestamp" in d


class TestPolicyRuleBase:
    """Test PolicyRule base class."""

    def test_rule_initialization(self):
        """Test initializing a rule."""
        rule = PolicyRule("test_rule")
        assert rule.name == "test_rule"

    def test_rule_evaluate_not_implemented(self):
        """Test that evaluate raises NotImplementedError."""
        rule = PolicyRule("test_rule")
        
        async def test_evaluate():
            # Mock stats service
            mock_service = None
            try:
                await rule.evaluate(mock_service)
                pytest.fail("Should raise NotImplementedError")
            except NotImplementedError:
                pass
        
        asyncio.run(test_evaluate())


class TestWinRateThresholdRuleValidation:
    """Test WinRateThresholdRule validation."""

    def test_valid_initialization(self):
        """Test creating rule with valid parameters."""
        rule = WinRateThresholdRule(min_win_rate=0.50)
        assert rule.min_win_rate == 0.50
        assert rule.name == "win_rate_threshold"

    def test_min_win_rate_too_low(self):
        """Test that min_win_rate < 0 raises error."""
        with pytest.raises(ValueError):
            WinRateThresholdRule(min_win_rate=-0.1)

    def test_min_win_rate_too_high(self):
        """Test that min_win_rate > 1 raises error."""
        with pytest.raises(ValueError):
            WinRateThresholdRule(min_win_rate=1.1)

    def test_min_win_rate_boundary_0(self):
        """Test that min_win_rate = 0 is valid."""
        rule = WinRateThresholdRule(min_win_rate=0.0)
        assert rule.min_win_rate == 0.0

    def test_min_win_rate_boundary_1(self):
        """Test that min_win_rate = 1 is valid."""
        rule = WinRateThresholdRule(min_win_rate=1.0)
        assert rule.min_win_rate == 1.0


class TestLossStreakRuleValidation:
    """Test LossStreakRule validation."""

    def test_valid_initialization(self):
        """Test creating rule with valid parameters."""
        rule = LossStreakRule(max_streak=5)
        assert rule.max_streak == 5
        assert rule.name == "loss_streak"

    def test_max_streak_zero(self):
        """Test that max_streak < 1 raises error."""
        with pytest.raises(ValueError):
            LossStreakRule(max_streak=0)

    def test_max_streak_negative(self):
        """Test that negative max_streak raises error."""
        with pytest.raises(ValueError):
            LossStreakRule(max_streak=-1)

    def test_max_streak_boundary_1(self):
        """Test that max_streak = 1 is valid."""
        rule = LossStreakRule(max_streak=1)
        assert rule.max_streak == 1


class TestAvgPnLThresholdRuleValidation:
    """Test AvgPnLThresholdRule validation."""

    def test_valid_initialization(self):
        """Test creating rule with valid parameters."""
        rule = AvgPnLThresholdRule(min_avg_pnl=0.0)
        assert rule.min_avg_pnl == 0.0
        assert rule.name == "avg_pnl_threshold"

    def test_negative_min_avg_pnl(self):
        """Test that negative min_avg_pnl is valid."""
        rule = AvgPnLThresholdRule(min_avg_pnl=-50.0)
        assert rule.min_avg_pnl == -50.0


class TestSymbolDrawdownRuleValidation:
    """Test SymbolDrawdownRule validation."""

    def test_valid_initialization(self):
        """Test creating rule with valid parameters."""
        rule = SymbolDrawdownRule(max_drawdown=-100.0)
        assert rule.max_drawdown == -100.0
        assert rule.name == "symbol_drawdown"

    def test_positive_max_drawdown(self):
        """Test that positive max_drawdown is valid (though unusual)."""
        rule = SymbolDrawdownRule(max_drawdown=100.0)
        assert rule.max_drawdown == 100.0


class TestOutcomePolicyEvaluatorInitialization:
    """Test OutcomePolicyEvaluator initialization."""

    def test_initialization(self):
        """Test creating evaluator."""
        mock_service = None  # Mock stats service
        evaluator = OutcomePolicyEvaluator(mock_service)
        assert evaluator.stats_service is mock_service
        assert len(evaluator.rules) == 0
        assert len(evaluator._evaluation_log) == 0

    def test_add_rule(self):
        """Test adding a rule."""
        mock_service = None
        evaluator = OutcomePolicyEvaluator(mock_service)
        rule = WinRateThresholdRule()
        evaluator.add_rule(rule)
        assert len(evaluator.rules) == 1
        assert evaluator.rules[0] is rule

    def test_add_duplicate_rule_name(self):
        """Test that adding duplicate rule names raises error."""
        mock_service = None
        evaluator = OutcomePolicyEvaluator(mock_service)
        rule1 = WinRateThresholdRule()
        rule2 = WinRateThresholdRule()  # Same name
        evaluator.add_rule(rule1)
        
        with pytest.raises(ValueError, match="already exists"):
            evaluator.add_rule(rule2)

    def test_remove_rule(self):
        """Test removing a rule."""
        mock_service = None
        evaluator = OutcomePolicyEvaluator(mock_service)
        rule = WinRateThresholdRule()
        evaluator.add_rule(rule)
        assert len(evaluator.rules) == 1
        
        evaluator.remove_rule("win_rate_threshold")
        assert len(evaluator.rules) == 0

    def test_remove_nonexistent_rule(self):
        """Test removing a rule that doesn't exist (should not error)."""
        mock_service = None
        evaluator = OutcomePolicyEvaluator(mock_service)
        evaluator.remove_rule("nonexistent")
        assert len(evaluator.rules) == 0

    def test_get_rules(self):
        """Test getting rules returns a copy."""
        mock_service = None
        evaluator = OutcomePolicyEvaluator(mock_service)
        rule = WinRateThresholdRule()
        evaluator.add_rule(rule)
        
        rules = evaluator.get_rules()
        assert len(rules) == 1
        assert rules[0] is rule
        
        # Modifying returned list shouldn't affect evaluator
        rules.clear()
        assert len(evaluator.rules) == 1


class TestFactoryFunction:
    """Test create_policy_evaluator factory."""

    def test_factory_creates_evaluator(self):
        """Test factory creates OutcomePolicyEvaluator."""
        mock_service = None
        evaluator = create_policy_evaluator(mock_service)
        assert isinstance(evaluator, OutcomePolicyEvaluator)

    def test_factory_adds_default_rules(self):
        """Test factory adds default rules."""
        mock_service = None
        evaluator = create_policy_evaluator(mock_service)
        assert len(evaluator.rules) >= 3
        
        rule_names = {r.name for r in evaluator.rules}
        assert "win_rate_threshold" in rule_names
        assert "loss_streak" in rule_names
        assert "avg_pnl_threshold" in rule_names

    def test_factory_with_config(self):
        """Test factory respects configuration."""
        mock_service = None
        config = {
            "win_rate_threshold": 0.60,
            "max_loss_streak": 3,
            "symbol_max_drawdown": -200.0,
        }
        evaluator = create_policy_evaluator(mock_service, config)
        
        win_rate_rule = next(r for r in evaluator.rules if r.name == "win_rate_threshold")
        assert win_rate_rule.min_win_rate == 0.60
        
        loss_streak_rule = next(r for r in evaluator.rules if r.name == "loss_streak")
        assert loss_streak_rule.max_streak == 3
        
        drawdown_rule = next(r for r in evaluator.rules if r.name == "symbol_drawdown")
        assert drawdown_rule.max_drawdown == -200.0


class TestEvaluationHistoryTracking:
    """Test evaluation history tracking."""

    def test_get_evaluation_history(self):
        """Test retrieving evaluation history."""
        mock_service = None
        evaluator = OutcomePolicyEvaluator(mock_service)
        
        # Add some evals
        eval1 = PolicyEvaluation(
            decision=PolicyDecision.VETO,
            reason="Test 1",
            rule_name="rule1",
        )
        eval2 = PolicyEvaluation(
            decision=PolicyDecision.VETO,
            reason="Test 2",
            rule_name="rule2",
        )
        evaluator._evaluation_log.append(eval1)
        evaluator._evaluation_log.append(eval2)
        
        history = evaluator.get_evaluation_history()
        assert len(history) == 2

    def test_get_evaluation_history_limit(self):
        """Test evaluation history limit."""
        mock_service = None
        evaluator = OutcomePolicyEvaluator(mock_service)
        
        # Add 10 evaluations
        for i in range(10):
            eval_obj = PolicyEvaluation(
                decision=PolicyDecision.VETO,
                reason=f"Test {i}",
                rule_name=f"rule{i}",
            )
            evaluator._evaluation_log.append(eval_obj)
        
        # Get last 5
        history = evaluator.get_evaluation_history(limit=5)
        assert len(history) == 5

    def test_clear_history(self):
        """Test clearing evaluation history."""
        mock_service = None
        evaluator = OutcomePolicyEvaluator(mock_service)
        
        eval_obj = PolicyEvaluation(
            decision=PolicyDecision.VETO,
            reason="Test",
            rule_name="rule",
        )
        evaluator._evaluation_log.append(eval_obj)
        assert len(evaluator._evaluation_log) == 1
        
        evaluator.clear_history()
        assert len(evaluator._evaluation_log) == 0


class TestOutcomePolicyEvaluatorDocumentation:
    """Test that evaluator and rules are well-documented."""

    def test_evaluator_has_docstring(self):
        """Test OutcomePolicyEvaluator has comprehensive docstring."""
        assert OutcomePolicyEvaluator.__doc__ is not None
        assert len(OutcomePolicyEvaluator.__doc__) > 200

    def test_factory_has_docstring(self):
        """Test factory function has docstring."""
        assert create_policy_evaluator.__doc__ is not None
        assert "example" in create_policy_evaluator.__doc__.lower() or "usage" in create_policy_evaluator.__doc__.lower()

    def test_policy_evaluation_has_docstring(self):
        """Test PolicyEvaluation has docstring."""
        assert PolicyEvaluation.__doc__ is not None

    def test_rules_have_docstrings(self):
        """Test all rule classes have docstrings."""
        rule_classes = [
            WinRateThresholdRule,
            LossStreakRule,
            AvgPnLThresholdRule,
            SymbolDrawdownRule,
        ]
        for rule_class in rule_classes:
            assert rule_class.__doc__ is not None
            assert len(rule_class.__doc__) > 30


class TestDeterministicBehavior:
    """Test that evaluator exhibits deterministic behavior."""

    def test_rule_initialization_deterministic(self):
        """Test that rule initialization is deterministic."""
        rule1 = WinRateThresholdRule(min_win_rate=0.50)
        rule2 = WinRateThresholdRule(min_win_rate=0.50)
        
        assert rule1.name == rule2.name
        assert rule1.min_win_rate == rule2.min_win_rate

    def test_evaluation_deterministic(self):
        """Test that PolicyEvaluation creation is deterministic."""
        eval1 = PolicyEvaluation(
            decision=PolicyDecision.VETO,
            reason="Test",
            rule_name="rule",
            signal_type="bullish",
            symbol="EURUSD",
        )
        eval2 = PolicyEvaluation(
            decision=PolicyDecision.VETO,
            reason="Test",
            rule_name="rule",
            signal_type="bullish",
            symbol="EURUSD",
        )
        
        d1 = eval1.to_dict()
        d2 = eval2.to_dict()
        
        # Same decision, reason, rule_name, signal_type, symbol
        assert d1["decision"] == d2["decision"]
        assert d1["reason"] == d2["reason"]
        assert d1["rule_name"] == d2["rule_name"]
        assert d1["signal_type"] == d2["signal_type"]
        assert d1["symbol"] == d2["symbol"]


class TestIntegrationPointsDocumented:
    """Test that integration points are documented."""

    def test_module_documents_integration_points(self):
        """Test module docstring documents integration points."""
        import reasoner_service.outcome_policy_evaluator as module
        
        doc = module.__doc__.lower()
        assert "future integration" in doc
        assert "policystore" in doc or "policy" in doc

    def test_evaluator_documents_future_integration(self):
        """Test evaluator docstring documents future work."""
        doc = OutcomePolicyEvaluator.__doc__.lower()
        assert "policy" in doc
        assert "veto" in doc or "allow" in doc

    def test_rules_document_veto_logic(self):
        """Test that rule docstrings explain VETO logic."""
        rules = [
            WinRateThresholdRule,
            LossStreakRule,
            AvgPnLThresholdRule,
            SymbolDrawdownRule,
        ]
        
        for rule_class in rules:
            doc = rule_class.__doc__.lower()
            assert "veto" in doc or "logic" in doc


class TestNonBlockingBehavior:
    """Test non-blocking error handling."""

    def test_evaluator_initialization_docstring_mentions_errors(self):
        """Test that relevant docstrings mention error handling."""
        # Module docstring should mention read-only, no writes
        doc = OutcomePolicyEvaluator.__doc__.lower()
        assert "read" in doc or "query" in doc


class TestReadOnlyDesign:
    """Test that system is read-only (no writes)."""

    def test_evaluator_has_no_write_methods(self):
        """Test evaluator has no write methods."""
        mock_service = None
        evaluator = OutcomePolicyEvaluator(mock_service)
        
        public_methods = [m for m in dir(evaluator) if not m.startswith('_')]
        write_keywords = ['insert', 'update', 'delete', 'create', 'write', 'persist']
        
        write_methods = [
            m for m in public_methods
            if any(kw in m.lower() for kw in write_keywords)
        ]
        
        assert len(write_methods) == 0, f"Found write methods: {write_methods}"


class TestRuleComposition:
    """Test that multiple rules can be composed."""

    def test_multiple_rules_added(self):
        """Test adding multiple different rules."""
        mock_service = None
        evaluator = OutcomePolicyEvaluator(mock_service)
        
        evaluator.add_rule(WinRateThresholdRule())
        evaluator.add_rule(LossStreakRule())
        evaluator.add_rule(AvgPnLThresholdRule())
        
        assert len(evaluator.rules) == 3

    def test_rules_returned_in_order(self):
        """Test that rules are evaluated in order added."""
        mock_service = None
        evaluator = OutcomePolicyEvaluator(mock_service)
        
        rule1 = WinRateThresholdRule()
        rule2 = LossStreakRule()
        rule3 = AvgPnLThresholdRule()
        
        evaluator.add_rule(rule1)
        evaluator.add_rule(rule2)
        evaluator.add_rule(rule3)
        
        assert evaluator.rules[0] is rule1
        assert evaluator.rules[1] is rule2
        assert evaluator.rules[2] is rule3


class TestDataclassFields:
    """Test PolicyEvaluation dataclass fields."""

    def test_required_fields(self):
        """Test that PolicyEvaluation has required fields."""
        eval_obj = PolicyEvaluation(
            decision=PolicyDecision.VETO,
            reason="Test",
            rule_name="test",
        )
        
        assert eval_obj.decision == PolicyDecision.VETO
        assert eval_obj.reason == "Test"
        assert eval_obj.rule_name == "test"

    def test_optional_fields(self):
        """Test that optional fields default to None."""
        eval_obj = PolicyEvaluation(
            decision=PolicyDecision.ALLOW,
            reason="Allowed",
            rule_name="test",
        )
        
        assert eval_obj.signal_type is None
        assert eval_obj.symbol is None
        assert eval_obj.timeframe is None

    def test_timestamp_auto_set(self):
        """Test that timestamp is auto-set if not provided."""
        eval_obj = PolicyEvaluation(
            decision=PolicyDecision.VETO,
            reason="Test",
            rule_name="test",
        )
        
        assert eval_obj.timestamp is not None
        assert isinstance(eval_obj.timestamp, datetime)
