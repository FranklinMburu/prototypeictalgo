"""
Policy Confidence Evaluator

Determines whether a policy is statistically and operationally safe to enforce.

CRITICAL DISCLAIMER: This component does NOT influence live trading decisions.
It provides analytical evidence only for future policy enforcement consideration.

Confidence scoring is based on:
- Sample size (trades analyzed)
- False positive rate (vetoed winners)
- False negative rate (allowed losers)
- Net PnL delta if policy were enforced
- Regime-specific degradation
- Consistency across market conditions

Confidence does NOT automatically trigger enforcement.
This is evidence-only; enforcement decisions require separate authorization.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class PolicyConfidenceEvaluator:
    """
    Evaluates statistical and operational confidence in policies.
    
    This evaluator determines if a policy appears safe to enforce based on
    historical performance data, without affecting live trading behavior.
    
    CONSTRAINTS:
    - Read-only analytics consumption
    - Deterministic outputs
    - No database writes
    - No learning or tuning
    - Fail-silent error handling
    - No influence on live decisions
    """
    
    def __init__(
        self,
        min_sample_size: int = 30,
        min_confidence_threshold: float = 0.70,
        false_negative_penalty: float = 0.3,
        false_positive_penalty: float = 0.1,
        regime_instability_penalty: float = 0.2,
        min_net_pnl_delta: float = 100.0,
    ):
        """
        Initialize the evaluator with configurable confidence thresholds.
        
        Args:
            min_sample_size: Minimum trades required for meaningful analysis
            min_confidence_threshold: Minimum confidence score to consider
            false_negative_penalty: Penalty weight for allowing losers (higher = worse)
            false_positive_penalty: Penalty weight for vetoing winners (lower impact)
            regime_instability_penalty: Penalty for performance degradation across regimes
            min_net_pnl_delta: Minimum PnL improvement required to consider positive
        """
        self.min_sample_size = min_sample_size
        self.min_confidence_threshold = min_confidence_threshold
        self.false_negative_penalty = false_negative_penalty
        self.false_positive_penalty = false_positive_penalty
        self.regime_instability_penalty = regime_instability_penalty
        self.min_net_pnl_delta = min_net_pnl_delta
        
        # Store policy analytics for later evaluation
        self._policy_analytics: Dict[str, Dict[str, Any]] = {}
    
    def add_policy_analytics(
        self,
        policy_name: str,
        veto_impact: Dict[str, Any],
        heatmap: Dict[str, Any],
        regime_performance: Dict[str, Any],
    ) -> None:
        """
        Register analytics for a policy.
        
        Args:
            policy_name: Name of the policy
            veto_impact: Result from OutcomeAnalyticsService.policy_veto_impact()
            heatmap: Result from OutcomeAnalyticsService.signal_policy_heatmap()
            regime_performance: Result from OutcomeAnalyticsService.regime_policy_performance()
        """
        self._policy_analytics[policy_name] = {
            "veto_impact": veto_impact,
            "heatmap": heatmap,
            "regime_performance": regime_performance,
        }
    
    def evaluate_policy(self, policy_name: str) -> Dict[str, Any]:
        """
        Evaluate confidence for a single policy.
        
        Args:
            policy_name: Name of the policy to evaluate
        
        Returns:
            {
                "policy_name": str,
                "sample_size": int,
                "false_positive_rate": float,
                "false_negative_rate": float,
                "net_pnl_delta_if_enforced": float,
                "regime_instability_score": float,
                "confidence_score": float (0.0 - 1.0),
                "enforcement_ready": bool,
                "explanation": str,
                "evaluated_at": str (ISO timestamp),
                "disclaimer": str,
            }
        """
        try:
            if policy_name not in self._policy_analytics:
                return self._create_error_report(
                    policy_name,
                    "Policy not found in evaluator. No analytics registered.",
                )
            
            analytics = self._policy_analytics[policy_name]
            veto_impact = analytics.get("veto_impact", {})
            heatmap = analytics.get("heatmap", {})
            regime_perf = analytics.get("regime_performance", {})
            
            # Extract key metrics
            sample_size = veto_impact.get("total_trades", 0)
            veto_precision = veto_impact.get("veto_precision", 1.0)
            veto_recall = veto_impact.get("veto_recall", 1.0)
            
            # Veto precision = true positives / all vetoed trades
            # So (1 - veto_precision) = false positives / all vetoed trades
            false_positive_rate = 1.0 - veto_precision
            
            # Veto recall = true positives / all losers
            # So (1 - veto_recall) = false negatives / all losers
            false_negative_rate = 1.0 - veto_recall
            
            # Calculate net PnL delta (counterfactual: if policy had been enforced)
            net_pnl_delta = self._calculate_net_pnl_delta(veto_impact)
            
            # Assess regime stability
            regime_instability_score = self._assess_regime_instability(regime_perf)
            
            # Compute confidence score
            confidence_score = self._compute_confidence_score(
                sample_size=sample_size,
                false_positive_rate=false_positive_rate,
                false_negative_rate=false_negative_rate,
                regime_instability_score=regime_instability_score,
                net_pnl_delta=net_pnl_delta,
            )
            
            # Determine if enforcement-ready
            enforcement_ready = (
                confidence_score >= self.min_confidence_threshold
                and sample_size >= self.min_sample_size
            )
            
            # Generate explanation
            explanation = self._generate_explanation(
                policy_name=policy_name,
                sample_size=sample_size,
                false_positive_rate=false_positive_rate,
                false_negative_rate=false_negative_rate,
                net_pnl_delta=net_pnl_delta,
                regime_instability_score=regime_instability_score,
                confidence_score=confidence_score,
                enforcement_ready=enforcement_ready,
            )
            
            return {
                "policy_name": policy_name,
                "sample_size": sample_size,
                "false_positive_rate": round(false_positive_rate, 4),
                "false_negative_rate": round(false_negative_rate, 4),
                "net_pnl_delta_if_enforced": round(net_pnl_delta, 2),
                "regime_instability_score": round(regime_instability_score, 4),
                "confidence_score": round(confidence_score, 4),
                "enforcement_ready": enforcement_ready,
                "explanation": explanation,
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": (
                    "This analysis is evidence-only. "
                    "Enforcement decisions require separate authorization and do not occur automatically."
                ),
            }
        
        except Exception as e:
            logger.exception(
                "Error evaluating policy %s: %s",
                policy_name,
                e,
            )
            return self._create_error_report(
                policy_name,
                f"Error during evaluation: {str(e)}",
            )
    
    def evaluate_all_policies(self) -> List[Dict[str, Any]]:
        """
        Evaluate confidence for all registered policies.
        
        Returns:
            List of confidence reports, one per policy.
            Returns empty list if no policies registered.
        """
        try:
            reports = []
            for policy_name in self._policy_analytics.keys():
                report = self.evaluate_policy(policy_name)
                reports.append(report)
            return reports
        except Exception as e:
            logger.exception("Error evaluating all policies: %s", e)
            return []
    
    def _calculate_net_pnl_delta(self, veto_impact: Dict[str, Any]) -> float:
        """
        Calculate counterfactual net PnL if policy had been enforced.
        
        Logic:
        - Vetoed losers: Prevented losses (positive delta)
        - Vetoed winners: Prevented gains (negative delta)
        - Allowed trades: No change (policy wasn't enforced on them)
        
        Args:
            veto_impact: Result from policy_veto_impact()
        
        Returns:
            Net PnL delta (positive = policy would improve)
        """
        vetoed_losers = veto_impact.get("vetoed_losers", 0)
        vetoed_winners = veto_impact.get("vetoed_winners", 0)
        
        # Estimate average PnL per trade (simplified)
        # In production, would use actual PnL values from outcomes
        avg_win_pnl = 100.0  # Typical win
        avg_loss_pnl = -75.0  # Typical loss
        
        delta = (vetoed_losers * abs(avg_loss_pnl)) + (vetoed_winners * -avg_win_pnl)
        return delta
    
    def _assess_regime_instability(self, regime_perf: Dict[str, Any]) -> float:
        """
        Assess if policy performance degrades across different market regimes.
        
        High instability = performance varies wildly across trending/ranging/volatile markets
        Low instability = consistent performance across regimes
        
        Args:
            regime_perf: Result from regime_policy_performance()
        
        Returns:
            Instability score (0.0 = stable, 1.0 = highly unstable)
        """
        try:
            regimes = {
                "trending_market": regime_perf.get("trending_market", {}),
                "ranging_market": regime_perf.get("ranging_market", {}),
                "high_volatility": regime_perf.get("high_volatility", {}),
            }
            
            # Extract win rates for each regime
            win_rates = []
            for regime_name, regime_data in regimes.items():
                trades = regime_data.get("trades_in_regime", 0)
                if trades > 0:
                    # Calculate win rate for this regime
                    wins = regime_data.get("wins", 0)
                    win_rate = wins / trades if trades > 0 else 0.0
                    win_rates.append(win_rate)
            
            if len(win_rates) < 2:
                # Not enough regime data to assess instability
                return 0.0
            
            # Calculate coefficient of variation (std dev / mean)
            mean_wr = sum(win_rates) / len(win_rates)
            if mean_wr == 0:
                return 1.0
            
            variance = sum((wr - mean_wr) ** 2 for wr in win_rates) / len(win_rates)
            std_dev = variance ** 0.5
            cv = std_dev / mean_wr if mean_wr > 0 else 1.0
            
            # Normalize to 0-1 scale
            instability = min(cv, 1.0)
            return instability
        
        except Exception as e:
            logger.warning("Error assessing regime instability: %s", e)
            return 0.5  # Default to medium instability on error
    
    def _compute_confidence_score(
        self,
        sample_size: int,
        false_positive_rate: float,
        false_negative_rate: float,
        regime_instability_score: float,
        net_pnl_delta: float,
    ) -> float:
        """
        Compute overall confidence score (0.0 - 1.0).
        
        Scoring logic:
        1. Start at 1.0
        2. Penalize small sample sizes
        3. Heavily penalize high false negatives
        4. Moderately penalize false positives
        5. Penalize regime instability
        6. Bonus for positive net PnL delta
        
        Args:
            sample_size: Number of trades analyzed
            false_positive_rate: Rate of vetoing winners
            false_negative_rate: Rate of allowing losers
            regime_instability_score: Regime performance variance
            net_pnl_delta: Counterfactual PnL improvement
        
        Returns:
            Confidence score (0.0 - 1.0)
        """
        score = 1.0
        
        # Penalty: Small sample size (heavy penalty for insufficient data)
        if sample_size < self.min_sample_size:
            # Scale penalty: 0 samples = -0.5, min_sample = -0.0
            size_penalty = (1.0 - (sample_size / self.min_sample_size)) * 0.5
            score -= size_penalty
        
        # Penalty: High false negatives (very bad - allowed losers)
        score -= false_negative_rate * self.false_negative_penalty
        
        # Penalty: False positives (less bad - vetoed winners)
        score -= false_positive_rate * self.false_positive_penalty
        
        # Penalty: Regime instability
        score -= regime_instability_score * self.regime_instability_penalty
        
        # Bonus: Positive net PnL delta (but not automatic approval)
        if net_pnl_delta > self.min_net_pnl_delta:
            pnl_bonus = min(0.10, (net_pnl_delta - self.min_net_pnl_delta) / 2000.0)
            score += pnl_bonus
        
        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, score))
    
    def _generate_explanation(
        self,
        policy_name: str,
        sample_size: int,
        false_positive_rate: float,
        false_negative_rate: float,
        net_pnl_delta: float,
        regime_instability_score: float,
        confidence_score: float,
        enforcement_ready: bool,
    ) -> str:
        """
        Generate human-readable explanation of confidence assessment.
        
        Args:
            policy_name: Policy being evaluated
            sample_size: Trades analyzed
            false_positive_rate: Veto precision issue
            false_negative_rate: Recall issue (allowed losers)
            net_pnl_delta: Counterfactual PnL
            regime_instability_score: Cross-regime stability
            confidence_score: Overall score
            enforcement_ready: Whether ready for enforcement
        
        Returns:
            Human-readable explanation string
        """
        lines = [
            f"Policy: {policy_name}",
            f"Confidence Score: {confidence_score:.1%}",
            "",
            f"Sample Size: {sample_size} trades",
        ]
        
        if sample_size < self.min_sample_size:
            lines.append(
                f"  ⚠️  Below minimum ({self.min_sample_size}). "
                f"Increase data collection before enforcement."
            )
        else:
            lines.append("  ✓ Sufficient historical data.")
        
        lines.append("")
        lines.append(f"False Positives (Vetoed Winners): {false_positive_rate:.1%}")
        if false_positive_rate > 0.3:
            lines.append("  ⚠️  High false positive rate. Policy may be too aggressive.")
        else:
            lines.append("  ✓ Acceptable false positive rate.")
        
        lines.append("")
        lines.append(f"False Negatives (Allowed Losers): {false_negative_rate:.1%}")
        if false_negative_rate > 0.2:
            lines.append("  ⚠️  High false negative rate. Policy is missing trades to veto.")
        else:
            lines.append("  ✓ Good catch rate for losers.")
        
        lines.append("")
        lines.append(f"Net PnL Delta (if enforced): ${net_pnl_delta:,.2f}")
        if net_pnl_delta > self.min_net_pnl_delta:
            lines.append("  ✓ Policy would improve P&L.")
        elif net_pnl_delta > 0:
            lines.append("  ⚠️  Modest improvement. Continue monitoring.")
        else:
            lines.append("  ✗ Policy would reduce P&L.")
        
        lines.append("")
        lines.append(f"Regime Instability: {regime_instability_score:.1%}")
        if regime_instability_score > 0.5:
            lines.append("  ⚠️  Performance varies significantly across market conditions.")
        else:
            lines.append("  ✓ Consistent performance across regimes.")
        
        lines.append("")
        if enforcement_ready:
            lines.append(
                "✓ READY FOR FUTURE ENFORCEMENT CONSIDERATION "
                "(requires separate authorization)"
            )
        else:
            lines.append("✗ NOT READY for enforcement. Address issues above.")
        
        lines.append("")
        lines.append(
            "Note: This is analytical evidence only. "
            "Enforcement is NOT automatic and requires human review."
        )
        
        return "\n".join(lines)
    
    def _create_error_report(
        self,
        policy_name: str,
        error_message: str,
    ) -> Dict[str, Any]:
        """
        Create an error report when evaluation fails.
        
        Args:
            policy_name: Policy name
            error_message: Error description
        
        Returns:
            Error report dict
        """
        return {
            "policy_name": policy_name,
            "sample_size": 0,
            "false_positive_rate": 0.0,
            "false_negative_rate": 0.0,
            "net_pnl_delta_if_enforced": 0.0,
            "regime_instability_score": 0.0,
            "confidence_score": 0.0,
            "enforcement_ready": False,
            "explanation": f"Evaluation failed: {error_message}",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": (
                "This analysis is evidence-only. "
                "Enforcement decisions require separate authorization and do not occur automatically."
            ),
        }
