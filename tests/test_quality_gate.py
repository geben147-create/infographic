"""
Tests for the quality gate feature (Plan 03-01).

Covers:
- PipelineParams accepts quality_gate_enabled field (backward compat: default False)
- PipelineResult accepts status="rejected" and status="waiting_approval"
- ApprovalSignal model validates {approved: bool, reason: str}
- ChannelConfig accepts quality_gate_enabled field (default False)
- PipelineStatus enum includes "waiting_approval" value
"""
from __future__ import annotations


class TestPipelineParamsQualityGate:
    """PipelineParams must accept quality_gate_enabled with default=False."""

    def test_pipeline_params_default_false(self):
        """PipelineParams backward compat: quality_gate_enabled defaults to False."""
        from src.workflows.content_pipeline import PipelineParams

        params = PipelineParams(run_id="run-001", topic="test", channel_id="ch01")
        assert params.quality_gate_enabled is False

    def test_pipeline_params_accepts_true(self):
        """PipelineParams accepts quality_gate_enabled=True."""
        from src.workflows.content_pipeline import PipelineParams

        params = PipelineParams(
            run_id="run-001",
            topic="test",
            channel_id="ch01",
            quality_gate_enabled=True,
        )
        assert params.quality_gate_enabled is True

    def test_pipeline_params_round_trips(self):
        """PipelineParams with quality_gate_enabled survives JSON round-trip."""
        from src.workflows.content_pipeline import PipelineParams

        original = PipelineParams(
            run_id="run-abc",
            topic="비트코인",
            channel_id="channel_01",
            quality_gate_enabled=True,
        )
        restored = PipelineParams.model_validate_json(original.model_dump_json())
        assert restored.quality_gate_enabled is True


class TestPipelineResultQualityGateStatuses:
    """PipelineResult must accept 'rejected' and 'waiting_approval' statuses."""

    def test_pipeline_result_rejected_status(self):
        """PipelineResult accepts status='rejected'."""
        from src.workflows.content_pipeline import PipelineResult

        result = PipelineResult(status="rejected")
        assert result.status == "rejected"

    def test_pipeline_result_waiting_approval_status(self):
        """PipelineResult accepts status='waiting_approval'."""
        from src.workflows.content_pipeline import PipelineResult

        result = PipelineResult(status="waiting_approval")
        assert result.status == "waiting_approval"

    def test_pipeline_result_default_status_ready_to_upload(self):
        """PipelineResult default status is 'ready_to_upload' after Phase 4 removes auto-upload."""
        from src.workflows.content_pipeline import PipelineResult

        result = PipelineResult()
        assert result.status == "ready_to_upload"


class TestApprovalSignal:
    """ApprovalSignal and ApproveRequest schemas must validate correctly."""

    def test_approval_signal_approved_true(self):
        """ApprovalSignal with approved=True and default empty reason."""
        from src.schemas.pipeline import ApprovalSignal

        sig = ApprovalSignal(approved=True)
        assert sig.approved is True
        assert sig.reason == ""

    def test_approval_signal_approved_false_with_reason(self):
        """ApprovalSignal with approved=False and custom reason."""
        from src.schemas.pipeline import ApprovalSignal

        sig = ApprovalSignal(approved=False, reason="bad audio quality")
        assert sig.approved is False
        assert sig.reason == "bad audio quality"

    def test_approve_request_schema(self):
        """ApproveRequest is a distinct schema matching ApprovalSignal fields."""
        from src.schemas.pipeline import ApproveRequest

        req = ApproveRequest(approved=True, reason="looks good")
        assert req.approved is True
        assert req.reason == "looks good"

    def test_approve_request_default_reason(self):
        """ApproveRequest reason defaults to empty string."""
        from src.schemas.pipeline import ApproveRequest

        req = ApproveRequest(approved=False)
        assert req.reason == ""

    def test_approval_signal_round_trip(self):
        """ApprovalSignal survives JSON round-trip."""
        from src.schemas.pipeline import ApprovalSignal

        original = ApprovalSignal(approved=True, reason="approved by operator")
        restored = ApprovalSignal.model_validate_json(original.model_dump_json())
        assert restored.approved is True
        assert restored.reason == "approved by operator"


class TestChannelConfigQualityGate:
    """ChannelConfig must accept quality_gate_enabled field with default=False."""

    def test_channel_config_default_false(self):
        """ChannelConfig has quality_gate_enabled defaulting to False."""
        from src.models.channel_config import ChannelConfig

        config = ChannelConfig(channel_id="ch01", niche="general")
        assert config.quality_gate_enabled is False

    def test_channel_config_accepts_true(self):
        """ChannelConfig accepts quality_gate_enabled=True."""
        from src.models.channel_config import ChannelConfig

        config = ChannelConfig(
            channel_id="ch01",
            niche="general",
            quality_gate_enabled=True,
        )
        assert config.quality_gate_enabled is True

    def test_channel_config_frozen_with_gate(self):
        """ChannelConfig with quality_gate_enabled=True is still frozen (immutable)."""
        import pytest
        from src.models.channel_config import ChannelConfig

        config = ChannelConfig(
            channel_id="ch01",
            niche="general",
            quality_gate_enabled=True,
        )
        with pytest.raises(Exception):
            config.quality_gate_enabled = False  # type: ignore[misc]


class TestPipelineStatusEnum:
    """PipelineStatus enum must include 'waiting_approval' value."""

    def test_waiting_approval_in_enum(self):
        """PipelineStatus has 'waiting_approval' member."""
        from src.schemas.pipeline import PipelineStatus

        assert PipelineStatus.waiting_approval == "waiting_approval"

    def test_waiting_approval_is_string(self):
        """PipelineStatus.waiting_approval behaves as a str enum value."""
        from src.schemas.pipeline import PipelineStatus

        assert isinstance(PipelineStatus.waiting_approval, str)
        assert PipelineStatus.waiting_approval == "waiting_approval"

    def test_existing_statuses_unchanged(self):
        """Existing PipelineStatus values are not changed."""
        from src.schemas.pipeline import PipelineStatus

        assert PipelineStatus.running == "running"
        assert PipelineStatus.completed == "completed"
        assert PipelineStatus.failed == "failed"
        assert PipelineStatus.unknown == "unknown"


class TestWorkflowSignalHandler:
    """Verify structural requirements of ContentPipelineWorkflow for quality gate."""

    def test_workflow_has_init_with_signal_state(self):
        """ContentPipelineWorkflow.__init__ initializes _approved and _reject_reason."""
        from src.workflows.content_pipeline import ContentPipelineWorkflow

        wf = ContentPipelineWorkflow()
        assert hasattr(wf, "_approved"), "missing _approved"
        assert hasattr(wf, "_reject_reason"), "missing _reject_reason"
        assert wf._approved is False
        assert wf._reject_reason == ""

    def test_workflow_has_approve_video_signal(self):
        """ContentPipelineWorkflow has approve_video method with signal decorator."""
        from src.workflows.content_pipeline import ContentPipelineWorkflow

        wf = ContentPipelineWorkflow()
        assert hasattr(wf, "approve_video"), "missing approve_video method"
        assert callable(wf.approve_video)
