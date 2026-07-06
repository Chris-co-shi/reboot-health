"""模型提供者抽象与 Mock 实现。"""

from __future__ import annotations

from agent_runtime.models import AgentCard, ExecuteRequest, ExecuteResponse


class ModelProvider:
    """模型提供者接口。"""

    def execute(self, request: ExecuteRequest) -> ExecuteResponse:
        raise NotImplementedError


class MockProvider(ModelProvider):
    """稳定、无网络依赖的模型 Mock。"""

    def execute(self, request: ExecuteRequest) -> ExecuteResponse:
        mode = (request.mock_mode or "success").lower()
        if mode == "timeout":
            raise TimeoutError("mock timeout")
        if mode == "failure":
            raise RuntimeError("mock internal failure")
        if mode == "invalid":
            return ExecuteResponse(schema_version="invalid", message="", cards=[])
        return ExecuteResponse(
            schema_version="1.0",
            message="Agent runtime is ready",
            cards=[
                AgentCard(
                    type="SYSTEM_STATUS",
                    title="AI教练服务已连接",
                    content="Java与Python运行链路正常",
                )
            ],
        )
