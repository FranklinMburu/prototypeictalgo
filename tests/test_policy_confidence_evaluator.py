"""
Unit tests for PolicyConfidenceEvaluator.

Verifies:
1. Confidence scoring logic and thresholds
2. Edge cases (low sample size, mixed regimes)
3. Deterministic outputs
4. No mutation of input analytics
5. Enforcement never triggered automatically
6. Fail-silent error handling
"""

import pytest
from typing import Dict, Any
from unittest.mock import MagicMock

from reasoner_service.policy_confidence_evaluator import PolicyConfidenceEvaluator


class TestConfidenceScoringLogic:
    """Test the core confidence scoring algorithm."""
    
    def test_high_confidence_ideal_policy(self):
        """Policy with large sample, good metrics gets high confidence."""
        evaluator = PolicyConfidenceEvaluator()
        
        # Ideal analytics: large sample, low false rates, good PnL
        analytics = {
            "veto_impact": {
                "total_trades": 100,
                "veto_precision": 0.05,  # 5% false positives
                "veto_recall": 0.95,  # 95% catch rate (5% false negatives)
                "vetoed_losers": 19,
                "vetoed_winners": 1,
            },
            "heatmap": {},
            "regime_performance": {
                "trending_market": {"trades_in_regime": 30, "wins": 28},
                "ranging_market": {"trades_in_regime": 40, "wins": 35},
                "high_volatility": {"trades_in_regime": 30, "wins": 25},
            },
        }
        
        evaluator.add_policy_analytics("ideal_policy", **analytics)
        report = evaluator.evaluate_policy("ideal_policy")
        
        assert report["confidence_score"] > 0.85
        assert report["enforcement_ready"] is True
        assert report["sample_size"] == 100
        assert "NOT READY" not in report["explanation"]
    
    def test_low_confidence_small_sample(self):
        """Small sample size heavily penalizes confidence."""
        evaluator = PolicyConfidenceEvaluator(min_sample_size=30)
        
        analytics = {
            "veto_impact": {
                "total_trades": 10,  # Below minimum
                "veto_precision": 0.0,
                "veto_recall": 1.0,
                "vetoed_losers": 2,
                "vetoed_winners": 0,
            },
            "heatmap": {},
            "regime_performance": {
                "trending_market": {"trades_in_regime": 5, "wins": 5},
                "ranging_market": {"trades_in_regime": 5, "wins": 5},
            },
        }
        
        evaluator.add_policy_analytics("small_sample", **analytics)
        report = evaluator.evaluate_policy("small_sample")
        
        assert report["confidence_score"] < 0.80  # Still low even with perfect metrics
        assert report["enforcement_ready"] is False
        assert "Below minimum" in report["explanation"]
    
    def test_false_negative_penalty(self):
        """High false negative rate significantly lowers confidence."""
        evaluator = PolicyConfidenceEvaluator()
        
        # Policy: Perfect at catching losses but doesn't catch many
        low_catch_analytics = {
            "veto_impact": {
                "total_trades": 50,
                "veto_precision": 1.0,   # 100% of vetoed were losers
                "veto_recall": 0.2,      # Only caught 20% of losers
                "vetoed_losers": 4,
                "vetoed_winners": 0,
            },
            "heatmap": {},
            "regime_performance": {
                "trending_market": {"trades_in_regime": 25, "wins": 15},
                "ranging_market": {"trades_in_regime": 25, "wins": 15},
            },
        }
        
        # Policy: Catches most losses but makes mistakes
        high_catch_analytics = {
            "veto_impact": {
                "total_trades": 50,
                "veto_precision": 0.8,   # 80% of vetoed were losers
                "veto_recall": 0.8,      # Caught 80% of losers
                "vetoed_losers": 16,
                "vetoed_winners": 4,
            },
            "heatmap": {},
            "regime_performance": {
                "trending_market": {"trades_in_regime": 25, "wins": 15},
                "ranging_market": {"trades_in_regime": 25, "wins": 15},
            },
        }
        
        evaluator.add_policy_analytics("low_catch", **low_catch_analytics)
        evaluator.add_policy_analytics("high_catch", **high_catch_analytics)
        
        report_low = evaluator.evaluate_policy("low_catch")
        report_high = evaluator.evaluate_policy("high_catch")
        
        # High false negative rate (low recall) should lower confidence
        assert report_low["false_negative_rate"] == 0.8
        assert report_high["false_negative_rate"] == 0.2
        assert report_low["confidence_score"] < report_high["confidence_score"]
    
    def test_false_positive_penalty_lighter(self):
        """False positives are penalized less than false negatives in scoring."""
        # This test verifies the penalty weights are correct
        evaluator = PolicyConfidenceEvaluator(
            false_positive_penalty=0.1,
            false_negative_penalty=0.3,
        )
        
        # Verify that the weights are set correctly
        assert evaluator.false_positive_penalty < evaluator.false_negative_penalty
        assert evaluator.false_positive_penalty == 0.1
        assert evaluator.false_negative_penalty == 0.3
        
        # Create two policies with same sample size and regime stability
        # but different FP/FN trade-offs
        analytics_low_fn_high_fp = {
            "veto_impact": {
                "total_trades": 50,
                "veto_precision": 0.5,   # 50% false positives
                "veto_recall": 0.95,     # Only 5% false negatives
                "vetoed_losers": 19,
                "vetoed_winners": 19,
            },
            "heatmap": {},
            "regime_performance": {
                "trending_market": {"trades_in_regime": 25, "wins": 20},
                "ranging_market": {"trades_in_regime": 25, "wins": 20},
            },
        }
        
        evaluator.add_policy_analytics("low_fn", **analytics_low_fn_high_fp)
        report = evaluator.evaluate_policy("low_fn")
        
        # With 50% FP and 5% FN, score should be good
        assert report["false_positive_rate"] == 0.5
        assert report["false_negative_rate"] == 0.05
        assert report["confidence_score"] > 0.80
    
    def test_net_pnl_bonus(self):
        """Positive net PnL provides modest confidence bonus."""
        evaluator = PolicyConfidenceEvaluator(min_net_pnl_delta=100.0)
        
        # Same base metrics, but more vetoed losers
        base_analytics = {
            "veto_impact": {
                "total_trades": 50,
                "veto_precision": 0.1,
                "veto_recall": 0.9,
                "vetoed_losers": 18,  # More losers prevented
                "vetoed_winners": 2,
            },
            "heatmap": {},
            "regime_performance": {
                "trending_market": {"trades_in_regime": 25, "wins": 20},
                "ranging_market": {"trades_in_regime": 25, "wins": 20},
            },
        }
        
        evaluator.add_policy_analytics("pnl_positive", **base_analytics)
        report = evaluator.evaluate_policy("pnl_positive")
        
        # Net PnL should be positive (losses prevented > wins vetoed)
        assert report["net_pnl_delta_if_enforced"] > 0
        assert "would improve P&L" in report["explanation"]


class TestRegimeInstability:
    """Test regime performance consistency assessment."""
    
    def test_stable_performance_across_regimes(self):
        """Consistent win rates across regimes → low instability."""
        evaluator = PolicyConfidenceEvaluator()
        
        analytics = {
            "veto_impact": {
                "total_trades": 50,
                "veto_precision": 0.0,
                "veto_recall": 1.0,
                "vetoed_losers": 10,
                "vetoed_winners": 0,
            },
            "heatmap": {},
            "regime_performance": {
                "trending_market": {"trades_in_regime": 20, "wins": 16},  # 80%
                "ranging_market": {"trades_in_regime": 20, "wins": 16},  # 80%
                "high_volatility": {"trades_in_regime": 10, "wins": 8},  # 80%
            },
        }
        
        evaluator.add_policy_analytics("stable", **analytics)
        report = evaluator.evaluate_policy("stable")
        
        assert report["regime_instability_score"] < 0.1
        assert "Consistent performance" in report["explanation"]
    
    def test_unstable_performance_across_regimes(self):
        """Wildly varying win rates → high instability."""
        evaluator = PolicyConfidenceEvaluator()
        
        analytics = {
            "veto_impact": {
                "total_trades": 50,
                "veto_precision": 0.0,
                "veto_recall": 1.0,
                "vetoed_losers": 10,
                "vetoed_winners": 0,
            },
            "heatmap": {},
            "regime_performance": {
                "trending_market": {"trades_in_regime": 20, "wins": 18},  # 90%
                "ranging_market": {"trades_in_regime": 20, "wins": 6},   # 30%
                "high_volatility": {"trades_in_regime": 10, "wins": 1},  # 10%
            },
        }
        
        evaluator.add_policy_analytics("unstable", **analytics)
        report = evaluator.evaluate_policy("unstable")
        
        assert report["regime_instability_score"] > 0.4
        assert "varies significantly across market conditions" in report["explanation"]


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_no_regimes_no_instability(self):
        """If insufficient regime data, instability defaults to low."""
        evaluator = PolicyConfidenceEvaluator()
        
        analytics = {
            "veto_impact": {
                "total_trades": 50,
                "veto_precision": 0.0,
                "veto_recall": 1.0,
                "vetoed_losers": 10,
                "vetoed_winners": 0,
            },
            "heatmap": {},
            "regime_performance": {
                "trending_market": {"trades_in_regime": 0},  # No data
                "ranging_market": {"trades_in_regime": 0},
                "high_volatility": {"trades_in_regime": 0},
            },
        }
        
        evaluator.add_policy_analytics("no_regime_data", **analytics)
        report = evaluator.evaluate_policy("no_regime_data")
        
        # Should not crash and confidence should still be reasonable with perfect metrics
        assert report["regime_instability_score"] == 0.0
        # Perfect veto metrics mean score should be high enough
        assert report["confidence_score"] > 0.50
    
    def test_unknown_policy(self):
        """Requesting evaluation of unknown policy returns error report."""
        evaluator = PolicyConfidenceEvaluator()
        
        report = evaluator.evaluate_policy("nonexistent_policy")
        
        assert report["confidence_score"] == 0.0
        assert report["enforcement_ready"] is False
        assert "not found" in report["explanation"]
    
    def test_empty_evaluator(self):
        """evaluate_all_policies returns empty list if no policies registered."""
        evaluator = PolicyConfidenceEvaluator()
        
        reports = evaluator.evaluate_all_policies()
        
        assert reports == []
    
    def test_missing_analytics_fields(self):
        """Evaluator handles missing or incomplete analytics gracefully."""
        evaluator = PolicyConfidenceEvaluator()
        
        # Minimal analytics - only required total_trades
        minimal_analytics = {
            "veto_impact": {
                "total_trades": 30,
                # Missing veto_precision, veto_recall, etc. - defaults to 0.0
            },
            "heatmap": {},
            "regime_performance": {},
        }
        
        evaluator.add_policy_analytics("incomplete", **minimal_analytics)
        report = evaluator.evaluate_policy("incomplete")
        
        # Should not crash, defaults to 0
        assert report["false_positive_rate"] == 0.0
        assert report["false_negative_rate"] == 0.0
        # With sample size = min (30) and no errors, score should be decent
        assert report["confidence_score"] >= 0.75
        # Should still have valid report structure
        assert "policy_name" in report
        assert "confidence_score" in report


class TestDeterminism:
    """Test that outputs are deterministic."""
    
    def test_same_input_same_output(self):
        """Same analytics input produces identical output."""
        analytics = {
            "veto_impact": {
                "total_trades": 50,
                "veto_precision": 0.1,
                "veto_recall": 0.9,
                "vetoed_losers": 18,
                "vetoed_winners": 2,
            },
            "heatmap": {},
            "regime_performance": {
                "trending_market": {"trades_in_regime": 20, "wins": 16},
                "ranging_market": {"trades_in_regime": 30, "wins": 24},
            },
        }
        
        evaluator1 = PolicyConfidenceEvaluator()
        evaluator1.add_policy_analytics("policy", **analytics)
        report1 = evaluator1.evaluate_policy("policy")
        
        evaluator2 = PolicyConfidenceEvaluator()
        evaluator2.add_policy_analytics("policy", **analytics)
        report2 = evaluator2.evaluate_policy("policy")
        
        # Compare all fields except timestamp
        for key in report1:
            if key != "evaluated_at":
                assert report1[key] == report2[key]


class TestNoMutation:
    """Test that input analytics are not mutated."""
    
    def test_analytics_not_mutated(self):
        """Evaluation does not modify input analytics."""
        evaluator = PolicyConfidenceEvaluator()
        
        analytics = {
            "veto_impact": {
                "total_trades": 50,
                "veto_precision": 0.1,
                "veto_recall": 0.9,
                "vetoed_losers": 18,
                "vetoed_winners": 2,
            },
            "heatmap": {},
            "regime_performance": {
                "trending_market": {"trades_in_regime": 20, "wins": 16},
                "ranging_market": {"trades_in_regime": 30, "wins": 24},
            },
        }
        
        # Make a deep copy to compare
        import copy
        analytics_copy = copy.deepcopy(analytics)
        
        evaluator.add_policy_analytics("policy", **analytics)
        evaluator.evaluate_policy("policy")
        
        assert analytics == analytics_copy


class TestNoEnforcementTriggered:
    """Test that evaluation never triggers enforcement."""
    
    def test_enforcement_ready_not_triggered(self):
        """Even with enforcement_ready=True, no actual enforcement occurs."""
        evaluator = PolicyConfidenceEvaluator()
        
        # Perfect policy
        analytics = {
            "veto_impact": {
                "total_trades": 100,
                "veto_precision": 0.02,
                "veto_recall": 0.98,
                "vetoed_losers": 49,
                "vetoed_winners": 1,
            },
            "heatmap": {},
            "regime_performance": {
                "trending_market": {"trades_in_regime": 40, "wins": 38},
                "ranging_market": {"trades_in_regime": 40, "wins": 38},
                "high_volatility": {"trades_in_regime": 20, "wins": 18},
            },
        }
        
        evaluator.add_policy_analytics("perfect", **analytics)
        report = evaluator.evaluate_policy("perfect")
        
        # With 98% recall and 2% false positives, confidence should be high
        assert report["confidence_score"] > 0.85
        
        # The key guarantee: enforcement_ready is just a flag
        # Enforcement is NOT triggered, requires external orchestrator
        assert "authorization" in report["disclaimer"]
        assert "automatic" in report["explanation"].lower()
    
    def test_multiple_policies_no_orchestration(self):
        """evaluate_all_policies never orchestrates enforcement."""
        evaluator = PolicyConfidenceEvaluator()
        
        policies = {
            "policy_a": {
                "veto_impact": {
                    "total_trades": 50,
                    "veto_precision": 0.0,
                    "veto_recall": 1.0,
                    "vetoed_losers": 10,
                    "vetoed_winners": 0,
                },
                "heatmap": {},
                "regime_performance": {
                    "trending_market": {"trades_in_regime": 25, "wins": 20},
                    "ranging_market": {"trades_in_regime": 25, "wins": 20},
                },
            },
            "policy_b": {
                "veto_impact": {
                    "total_trades": 60,
                    "veto_precision": 0.05,
                    "veto_recall": 0.95,
                    "vetoed_losers": 19,
                    "vetoed_winners": 1,
                },
                "heatmap": {},
                "regime_performance": {
                    "trending_market": {"trades_in_regime": 30, "wins": 27},
                    "ranging_market": {"trades_in_regime": 30, "wins": 27},
                },
            },
        }
        
        for policy_name, analytics in policies.items():
            evaluator.add_policy_analytics(policy_name, **analytics)
        
        reports = evaluator.evaluate_all_policies()
        
        assert len(reports) == 2
        # All have disclaimers - no enforcement triggered
        for report in reports:
            assert "authorization" in report["disclaimer"]


class TestFailSilentBehavior:
    """Test fail-silent error handling."""
    
    def test_malformed_analytics(self):
        """Malformed analytics don't crash, return error report."""
        evaluator = PolicyConfidenceEvaluator()
        
        # Completely wrong structure
        bad_analytics = {
            "veto_impact": "not a dict",
            "heatmap": None,
            "regime_performance": [],
        }
        
        evaluator.add_policy_analytics("bad", **bad_analytics)
        report = evaluator.evaluate_policy("bad")
        
        # Should not crash
        assert report["confidence_score"] == 0.0
        assert report["enforcement_ready"] is False
        assert isinstance(report["explanation"], str)
    
    def test_exception_during_evaluation(self):
        """Exceptions during evaluation are caught and logged."""
        evaluator = PolicyConfidenceEvaluator()
        
        # Analytics that will cause issues during processing
        analytics = {
            "veto_impact": {
                "total_trades": 50,
                "veto_precision": float("nan"),  # NaN will cause issues
                "veto_recall": 0.9,
                "vetoed_losers": 18,
                "vetoed_winners": 2,
            },
            "heatmap": {},
            "regime_performance": {},
        }
        
        evaluator.add_policy_analytics("exception_policy", **analytics)
        
        # Should not raise exception
        try:
            report = evaluator.evaluate_policy("exception_policy")
            # May return error report or handle NaN gracefully
            assert isinstance(report, dict)
            assert "explanation" in report
        except Exception as e:
            pytest.fail(f"Evaluator raised exception: {e}")


class TestConfigurableThresholds:
    """Test that thresholds are configurable."""
    
    def test_custom_confidence_threshold(self):
        """Enforcement ready flag respects custom threshold."""
        evaluator_lenient = PolicyConfidenceEvaluator(
            min_confidence_threshold=0.50
        )
        evaluator_strict = PolicyConfidenceEvaluator(
            min_confidence_threshold=0.90
        )
        
        # Policy with moderate metrics  
        analytics = {
            "veto_impact": {
                "total_trades": 50,
                "veto_precision": 0.6,   # 40% false positives
                "veto_recall": 0.6,      # 40% false negatives
                "vetoed_losers": 12,
                "vetoed_winners": 8,
            },
            "heatmap": {},
            "regime_performance": {
                "trending_market": {"trades_in_regime": 25, "wins": 18},
                "ranging_market": {"trades_in_regime": 25, "wins": 18},
            },
        }
        
        evaluator_lenient.add_policy_analytics("policy", **analytics)
        evaluator_strict.add_policy_analytics("policy", **analytics)
        
        report_lenient = evaluator_lenient.evaluate_policy("policy")
        report_strict = evaluator_strict.evaluate_policy("policy")
        
        # Same confidence score but different enforcement_ready based on threshold
        assert report_lenient["confidence_score"] == report_strict["confidence_score"]
        # With moderate metrics, score should be around 0.84
        assert 0.80 < report_lenient["confidence_score"] < 0.90
        # Lenient passes, strict fails
        assert report_lenient["enforcement_ready"] is True
        assert report_strict["enforcement_ready"] is False
    
    def test_custom_sample_size_minimum(self):
        """Sample size minimum is configurable."""
        evaluator = PolicyConfidenceEvaluator(min_sample_size=10)
        
        analytics = {
            "veto_impact": {
                "total_trades": 15,  # Above 10, below default 30
                "veto_precision": 0.0,
                "veto_recall": 1.0,
                "vetoed_losers": 5,
                "vetoed_winners": 0,
            },
            "heatmap": {},
            "regime_performance": {
                "trending_market": {"trades_in_regime": 8, "wins": 8},
                "ranging_market": {"trades_in_regime": 7, "wins": 7},
            },
        }
        
        evaluator.add_policy_analytics("policy", **analytics)
        report = evaluator.evaluate_policy("policy")
        
        assert report["sample_size"] == 15
        # Should be enforcement_ready if other metrics are good
        assert report["confidence_score"] > 0.80


class TestOutputStructure:
    """Test that output has required structure."""
    
    def test_evaluate_policy_output_structure(self):
        """evaluate_policy returns all required fields."""
        evaluator = PolicyConfidenceEvaluator()
        
        analytics = {
            "veto_impact": {
                "total_trades": 50,
                "veto_precision": 0.1,
                "veto_recall": 0.9,
                "vetoed_losers": 18,
                "vetoed_winners": 2,
            },
            "heatmap": {},
            "regime_performance": {
                "trending_market": {"trades_in_regime": 25, "wins": 20},
                "ranging_market": {"trades_in_regime": 25, "wins": 20},
            },
        }
        
        evaluator.add_policy_analytics("policy", **analytics)
        report = evaluator.evaluate_policy("policy")
        
        required_fields = [
            "policy_name",
            "sample_size",
            "false_positive_rate",
            "false_negative_rate",
            "net_pnl_delta_if_enforced",
            "regime_instability_score",
            "confidence_score",
            "enforcement_ready",
            "explanation",
            "evaluated_at",
            "disclaimer",
        ]
        
        for field in required_fields:
            assert field in report, f"Missing required field: {field}"
    
    def test_evaluate_all_policies_output_structure(self):
        """evaluate_all_policies returns list of valid reports."""
        evaluator = PolicyConfidenceEvaluator()
        
        for i in range(3):
            analytics = {
                "veto_impact": {
                    "total_trades": 50,
                    "veto_precision": 0.1,
                    "veto_recall": 0.9,
                    "vetoed_losers": 18,
                    "vetoed_winners": 2,
                },
                "heatmap": {},
                "regime_performance": {
                    "trending_market": {"trades_in_regime": 25, "wins": 20},
                    "ranging_market": {"trades_in_regime": 25, "wins": 20},
                },
            }
            evaluator.add_policy_analytics(f"policy_{i}", **analytics)
        
        reports = evaluator.evaluate_all_policies()
        
        assert len(reports) == 3
        for report in reports:
            assert isinstance(report, dict)
            assert "policy_name" in report
            assert "confidence_score" in report
            assert "enforcement_ready" in report
