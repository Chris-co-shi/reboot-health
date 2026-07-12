"""出站邮件端口与消息合同；邮件正文不得进入普通日志。"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class EmailMessage:
    """版本化邮件消息；敏感一次性 Token 只交给发送适配器。"""

    message_id: UUID
    recipient: str
    template: str
    template_version: int
    variables: dict[str, str]


class EmailPort(Protocol):
    """Outbox Processor 使用的幂等出站邮件端口。"""

    def send(self, message: EmailMessage) -> None:
        """发送或捕获邮件；实现必须按 message_id 幂等。"""
