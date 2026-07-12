"""SMTP 与开发捕获邮件适配器。

SMTP 仅由提交后的 Outbox Processor 调用，不阻塞 API 事务。
"""

import smtplib
from email.message import EmailMessage as SmtpMessage

from health_platform.modules.identity.ports.email import EmailMessage


class DevelopmentCaptureEmailAdapter:
    """测试/开发捕获器；不发送网络请求且不把正文写入日志。"""

    def __init__(self) -> None:
        self.messages: dict[object, EmailMessage] = {}

    def send(self, message: EmailMessage) -> None:
        """按 message_id 幂等捕获邮件供测试断言。"""
        self.messages.setdefault(message.message_id, message)


class SmtpEmailAdapter:
    """标准 SMTP 适配器；凭据只由 Composition Root 注入。"""

    def __init__(
        self, host: str, port: int, sender: str, username: str | None, password: str | None
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._username = username
        self._password = password

    def send(self, message: EmailMessage) -> None:
        """发送模板渲染结果；调用异常交由 Outbox 退避重试和告警。"""
        smtp_message = SmtpMessage()
        smtp_message["From"] = self._sender
        smtp_message["To"] = message.recipient
        smtp_message["Subject"] = message.template
        smtp_message.set_content(
            "\n".join(f"{key}: {value}" for key, value in message.variables.items())
        )
        with smtplib.SMTP(self._host, self._port, timeout=10) as client:
            client.starttls()
            if self._username and self._password:
                client.login(self._username, self._password)
            client.send_message(smtp_message)
