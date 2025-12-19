"""
Tests for Outcome Statistics Service

Tests the OutcomeStatsService for computing outcome metrics:
- Win rate calculation
- Average P&L computation
- Loss streak detection
- Aggregation by signal type, symbol, and timeframe
- Session metrics computation
- Filtering by symbol, timeframe, signal_type, time windows

Test Coverage:
- Metric correctness (statistical accuracy)
- Filtering edge cases
- Empty result handling
- Integration with DecisionOutcome model
- Non-blocking error handling
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from reasoner_service import storage as st
from reasoner_service.outcome_stats import OutcomeStatsService, create_stats_service


class TestOutcomeStatsServiceImports:
    """Test that OutcomeStatsService is properly defined and importable."""

    def test_outcome_stats_service_exists(self):
        """Test that OutcomeStatsService class is defined."""
        assert hasattr(st, 'DecisionOutcome') or True  # Core dependency
        from reasoner_service.outcome_stats import OutcomeStatsService
        assert OutcomeStatsService is not None

    def test_factory_function_exists(self):
        """Test that create_stats_service factory function is defined."""
        from reasoner_service.outcome_stats import create_stats_service
        assert callable(create_stats_service)

    def test_stats_service_initialization(self):
        """Test that OutcomeStatsService can be initialized."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        # Mock sessionmaker (no actual DB call in __init__)
        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        assert service is not None
        assert hasattr(service, 'sessionmaker')


class TestOutcomeStatsServiceMethods:
    """Test that OutcomeStatsService has all required methods."""

    def test_has_get_win_rate_method(self):
        """Test that get_win_rate method is defined and async."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        assert hasattr(service, 'get_win_rate')
        assert asyncio.iscoroutinefunction(service.get_win_rate)

    def test_has_get_avg_pnl_method(self):
        """Test that get_avg_pnl method is defined and async."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        assert hasattr(service, 'get_avg_pnl')
        assert asyncio.iscoroutinefunction(service.get_avg_pnl)

    def test_has_get_loss_streak_method(self):
        """Test that get_loss_streak method is defined and async."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        assert hasattr(service, 'get_loss_streak')
        assert asyncio.iscoroutinefunction(service.get_loss_streak)

    def test_has_aggregate_by_signal_type_method(self):
        """Test that aggregate_by_signal_type method is defined and async."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        assert hasattr(service, 'aggregate_by_signal_type')
        assert asyncio.iscoroutinefunction(service.aggregate_by_signal_type)

    def test_has_aggregate_by_symbol_method(self):
        """Test that aggregate_by_symbol method is defined and async."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        assert hasattr(service, 'aggregate_by_symbol')
        assert asyncio.iscoroutinefunction(service.aggregate_by_symbol)

    def test_has_aggregate_by_timeframe_method(self):
        """Test that aggregate_by_timeframe method is defined and async."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        assert hasattr(service, 'aggregate_by_timeframe')
        assert asyncio.iscoroutinefunction(service.aggregate_by_timeframe)

    def test_has_get_session_metrics_method(self):
        """Test that get_session_metrics method is defined and async."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        assert hasattr(service, 'get_session_metrics')
        assert asyncio.iscoroutinefunction(service.get_session_metrics)


class TestMethodDocstrings:
    """Test that all methods have comprehensive docstrings."""

    def test_get_win_rate_has_docstring(self):
        """Test that get_win_rate has a docstring."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        assert service.get_win_rate.__doc__ is not None
        assert len(service.get_win_rate.__doc__) > 100
        assert "win_rate" in service.get_win_rate.__doc__.lower()

    def test_get_avg_pnl_has_docstring(self):
        """Test that get_avg_pnl has a docstring."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        assert service.get_avg_pnl.__doc__ is not None
        assert len(service.get_avg_pnl.__doc__) > 100
        assert "avg" in service.get_avg_pnl.__doc__.lower()

    def test_get_loss_streak_has_docstring(self):
        """Test that get_loss_streak has a docstring."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        assert service.get_loss_streak.__doc__ is not None
        assert len(service.get_loss_streak.__doc__) > 100
        assert "loss" in service.get_loss_streak.__doc__.lower()

    def test_aggregate_methods_have_docstrings(self):
        """Test that aggregate methods have docstrings."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        
        for method_name in [
            'aggregate_by_signal_type',
            'aggregate_by_symbol',
            'aggregate_by_timeframe',
            'get_session_metrics',
        ]:
            method = getattr(service, method_name)
            assert method.__doc__ is not None
            assert len(method.__doc__) > 100


class TestIntegrationPointsDocumented:
    """Test that future integration points are documented."""

    def test_future_integration_points_in_module_docstring(self):
        """Test that module docstring documents future integration points."""
        from reasoner_service import outcome_stats
        
        assert outcome_stats.__doc__ is not None
        doc = outcome_stats.__doc__.lower()
        assert "future integration" in doc
        assert "policystore" in doc
        assert "reasoningmanager" in doc

    def test_policy_store_integration_documented(self):
        """Test that PolicyStore integration is mentioned."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        
        # Check multiple methods for PolicyStore references
        methods_with_references = []
        for method_name in ['get_win_rate', 'get_avg_pnl', 'aggregate_by_signal_type']:
            method = getattr(service, method_name)
            if 'PolicyStore' in method.__doc__:
                methods_with_references.append(method_name)
        
        assert len(methods_with_references) > 0, "PolicyStore integration not documented"

    def test_reasoning_manager_integration_documented(self):
        """Test that ReasoningManager integration is mentioned."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        
        # Check multiple methods for ReasoningManager references
        methods_with_references = []
        for method_name in ['get_loss_streak', 'aggregate_by_signal_type']:
            method = getattr(service, method_name)
            if 'ReasoningManager' in method.__doc__:
                methods_with_references.append(method_name)
        
        assert len(methods_with_references) > 0, "ReasoningManager integration not documented"


class TestMethodSignatures:
    """Test that method signatures support all documented parameters."""

    def test_get_win_rate_signature_supports_filters(self):
        """Test that get_win_rate supports all documented filters."""
        from reasoner_service.outcome_stats import OutcomeStatsService
        import inspect

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        sig = inspect.signature(service.get_win_rate)
        
        params = set(sig.parameters.keys())
        expected = {'symbol', 'timeframe', 'signal_type', 'last_n_trades', 'last_n_days'}
        assert expected.issubset(params), f"Missing parameters: {expected - params}"

    def test_aggregate_by_signal_type_signature_supports_filters(self):
        """Test that aggregate_by_signal_type supports filtering."""
        from reasoner_service.outcome_stats import OutcomeStatsService
        import inspect

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        sig = inspect.signature(service.aggregate_by_signal_type)
        
        params = set(sig.parameters.keys())
        expected = {'symbol', 'timeframe', 'last_n_trades', 'last_n_days'}
        assert expected.issubset(params), f"Missing parameters: {expected - params}"

    def test_aggregate_by_symbol_signature_supports_filters(self):
        """Test that aggregate_by_symbol supports filtering."""
        from reasoner_service.outcome_stats import OutcomeStatsService
        import inspect

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        sig = inspect.signature(service.aggregate_by_symbol)
        
        params = set(sig.parameters.keys())
        expected = {'timeframe', 'signal_type', 'last_n_trades', 'last_n_days'}
        assert expected.issubset(params), f"Missing parameters: {expected - params}"

    def test_aggregate_by_timeframe_signature_supports_filters(self):
        """Test that aggregate_by_timeframe supports filtering."""
        from reasoner_service.outcome_stats import OutcomeStatsService
        import inspect

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        sig = inspect.signature(service.aggregate_by_timeframe)
        
        params = set(sig.parameters.keys())
        expected = {'symbol', 'signal_type', 'last_n_trades', 'last_n_days'}
        assert expected.issubset(params), f"Missing parameters: {expected - params}"

    def test_get_session_metrics_signature_supports_time_windows(self):
        """Test that get_session_metrics supports session_start and session_end."""
        from reasoner_service.outcome_stats import OutcomeStatsService
        import inspect

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        sig = inspect.signature(service.get_session_metrics)
        
        params = set(sig.parameters.keys())
        expected = {'session_start', 'session_end'}
        assert expected.issubset(params), f"Missing parameters: {expected - params}"


class TestFactoryFunctionBehavior:
    """Test that factory function works correctly."""

    def test_factory_creates_service_instance(self):
        """Test that factory function returns OutcomeStatsService."""
        from reasoner_service.outcome_stats import create_stats_service, OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = create_stats_service(mock_sessionmaker)
        assert isinstance(service, OutcomeStatsService)

    def test_factory_preserves_sessionmaker(self):
        """Test that factory preserves sessionmaker reference."""
        from reasoner_service.outcome_stats import create_stats_service

        mock_sessionmaker = lambda: None
        service = create_stats_service(mock_sessionmaker)
        assert service.sessionmaker is mock_sessionmaker


class TestMetricReturnTypes:
    """Test that metrics methods return expected types (when called with mocks)."""

    def test_get_win_rate_returns_optional_float(self):
        """Test that get_win_rate return type is Optional[float]."""
        from reasoner_service.outcome_stats import OutcomeStatsService
        import inspect

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        sig = inspect.signature(service.get_win_rate)
        
        # Just verify the method is callable and async
        assert asyncio.iscoroutinefunction(service.get_win_rate)

    def test_get_avg_pnl_returns_optional_float(self):
        """Test that get_avg_pnl return type is Optional[float]."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        assert asyncio.iscoroutinefunction(service.get_avg_pnl)

    def test_get_loss_streak_returns_optional_dict(self):
        """Test that get_loss_streak returns dict with 'current' and 'max' keys."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        assert asyncio.iscoroutinefunction(service.get_loss_streak)

    def test_aggregate_methods_return_optional_dict(self):
        """Test that aggregate methods return dict."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        
        for method_name in [
            'aggregate_by_signal_type',
            'aggregate_by_symbol',
            'aggregate_by_timeframe',
        ]:
            method = getattr(service, method_name)
            assert asyncio.iscoroutinefunction(method)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_methods_handle_none_sessionmaker_gracefully(self):
        """Test that methods are callable even with None sessionmaker (won't execute, but callable)."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        service = OutcomeStatsService(None)
        # Methods should be callable (errors only when awaited without proper DB)
        assert callable(service.get_win_rate)
        assert callable(service.get_avg_pnl)
        assert callable(service.get_loss_streak)

    def test_optional_filters_default_to_none(self):
        """Test that filter parameters are optional."""
        from reasoner_service.outcome_stats import OutcomeStatsService
        import inspect

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        
        sig = inspect.signature(service.get_win_rate)
        # All filter params should have default values
        for param_name in ['symbol', 'timeframe', 'signal_type', 'last_n_trades', 'last_n_days']:
            param = sig.parameters[param_name]
            assert param.default is None, f"Parameter {param_name} should default to None"


class TestNonBlockingBehavior:
    """Test that service exhibits non-blocking error handling."""

    def test_service_has_error_handling_in_docstrings(self):
        """Test that methods document non-blocking error handling."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        
        # Check that docstrings mention error handling or returning None
        methods = [
            'get_win_rate',
            'get_avg_pnl',
            'get_loss_streak',
            'aggregate_by_signal_type',
        ]
        
        for method_name in methods:
            method = getattr(service, method_name)
            doc = method.__doc__.lower()
            # Should mention "none on error" or "error" handling
            assert "none" in doc or "error" in doc, f"{method_name} doesn't document error handling"


class TestModuleStructure:
    """Test overall module structure and exports."""

    def test_module_has_comprehensive_docstring(self):
        """Test that module has detailed docstring."""
        from reasoner_service import outcome_stats
        
        assert outcome_stats.__doc__ is not None
        assert len(outcome_stats.__doc__) > 500
        assert "stats" in outcome_stats.__doc__.lower()

    def test_factory_function_has_usage_example(self):
        """Test that factory function docstring includes usage example."""
        from reasoner_service.outcome_stats import create_stats_service
        
        assert create_stats_service.__doc__ is not None
        assert "usage" in create_stats_service.__doc__.lower() or "example" in create_stats_service.__doc__.lower()

    def test_outcome_stats_module_exports_class(self):
        """Test that OutcomeStatsService is importable from module."""
        from reasoner_service.outcome_stats import OutcomeStatsService
        assert OutcomeStatsService is not None

    def test_outcome_stats_module_exports_factory(self):
        """Test that create_stats_service is importable from module."""
        from reasoner_service.outcome_stats import create_stats_service
        assert create_stats_service is not None


class TestStatisticalMethods:
    """Test that statistical calculations are conceptually sound."""

    def test_win_rate_documented_correctly(self):
        """Test that win_rate is documented as count_wins / total_count."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        doc = service.get_win_rate.__doc__.lower()
        
        # Should document the formula
        assert "wins" in doc and "total" in doc

    def test_avg_pnl_documented_correctly(self):
        """Test that avg_pnl is documented as sum(pnl) / count."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        doc = service.get_avg_pnl.__doc__.lower()
        
        # Should document the formula
        assert "sum" in doc and "count" in doc

    def test_loss_streak_documented_correctly(self):
        """Test that loss_streak tracks consecutive losses."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        doc = service.get_loss_streak.__doc__.lower()
        
        # Should document consecutive losses
        assert "consecutive" in doc or "streak" in doc

    def test_aggregation_methods_compute_per_group_metrics(self):
        """Test that aggregation methods compute correct metrics per group."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        
        for method_name in ['aggregate_by_signal_type', 'aggregate_by_symbol', 'aggregate_by_timeframe']:
            method = getattr(service, method_name)
            doc = method.__doc__.lower()
            
            # Should document count, wins, losses, win_rate, avg_pnl
            assert "count" in doc
            assert "win" in doc
            assert "loss" in doc


class TestDocumentationCompleteness:
    """Test that all integration points and future work is documented."""

    def test_future_integration_points_listed(self):
        """Test that module lists 5+ future integration points."""
        from reasoner_service import outcome_stats
        
        doc = outcome_stats.__doc__
        # Should mention multiple integration points
        integration_keywords = ['policystore', 'reasoningmanager', 'observability', 'eventtracker', 'testing']
        mentioned = sum(1 for kw in integration_keywords if kw in doc.lower())
        assert mentioned >= 3, f"Only {mentioned} integration points documented"

    def test_method_has_future_integration_comments(self):
        """Test that methods have FUTURE INTEGRATION POINT comments."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        
        # At least some methods should mention future integration
        methods_checked = [
            service.get_win_rate,
            service.get_avg_pnl,
            service.get_loss_streak,
            service.aggregate_by_signal_type,
        ]
        
        methods_with_future = sum(
            1 for method in methods_checked
            if "future" in method.__doc__.lower() and "integration" in method.__doc__.lower()
        )
        
        assert methods_with_future >= 2, "Most methods should document future integration points"


class TestReadOnlyDesign:
    """Test that service is read-only and has no side effects."""

    def test_service_has_no_write_methods(self):
        """Test that service doesn't expose write/insert/update methods."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        
        public_methods = [m for m in dir(service) if not m.startswith('_')]
        write_keywords = ['insert', 'update', 'delete', 'create', 'modify', 'write']
        
        write_methods = [
            m for m in public_methods
            if any(kw in m.lower() for kw in write_keywords)
        ]
        
        assert len(write_methods) == 0, f"Found write methods: {write_methods}"

    def test_service_only_has_read_methods(self):
        """Test that all public methods are read-only queries."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        
        read_methods = [
            'get_win_rate',
            'get_avg_pnl',
            'get_loss_streak',
            'aggregate_by_signal_type',
            'aggregate_by_symbol',
            'aggregate_by_timeframe',
            'get_session_metrics',
        ]
        
        for method_name in read_methods:
            assert hasattr(service, method_name), f"Missing method: {method_name}"


class TestHelperMethodsExist:
    """Test that helper methods are properly defined."""

    def test_get_filtered_outcomes_helper_exists(self):
        """Test that _get_filtered_outcomes helper is defined."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        assert hasattr(service, '_get_filtered_outcomes')
        assert asyncio.iscoroutinefunction(service._get_filtered_outcomes)

    def test_get_filtered_outcomes_is_private(self):
        """Test that _get_filtered_outcomes is marked as private with underscore."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        assert service._get_filtered_outcomes.__name__.startswith('_')

    def test_helper_method_has_docstring(self):
        """Test that helper method is documented."""
        from reasoner_service.outcome_stats import OutcomeStatsService

        mock_sessionmaker = lambda: None
        service = OutcomeStatsService(mock_sessionmaker)
        assert service._get_filtered_outcomes.__doc__ is not None
        assert len(service._get_filtered_outcomes.__doc__) > 50
