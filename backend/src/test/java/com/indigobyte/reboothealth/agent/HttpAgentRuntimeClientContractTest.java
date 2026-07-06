package com.indigobyte.reboothealth.agent;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.indigobyte.reboothealth.agent.adapter.runtime.HttpAgentRuntimeClient;
import com.indigobyte.reboothealth.agent.application.AgentRuntimeException;
import com.indigobyte.reboothealth.agent.application.AgentRuntimeRequest;
import java.io.IOException;
import java.net.ServerSocket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Path;
import java.time.Duration;
import java.util.UUID;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * Java HTTP 客户端与 Python Agent Runtime 的真实进程合同测试。
 *
 * <p>测试只启动本仓库的标准库 Runtime 和 Model Mock，不依赖外部网络或真实模型供应商。</p>
 */
class HttpAgentRuntimeClientContractTest {

    private static Process runtimeProcess;
    private static String baseUrl;

    @BeforeAll
    static void startRuntime() throws Exception {
        int port = freePort();
        Path runtimeDir = Path.of("..", "agent-runtime").toAbsolutePath().normalize();
        ProcessBuilder builder = new ProcessBuilder("python3", "-m", "agent_runtime.server",
                "--host", "127.0.0.1", "--port", String.valueOf(port));
        builder.directory(runtimeDir.toFile());
        builder.environment().put("PYTHONPATH", ".");
        builder.redirectErrorStream(true);
        runtimeProcess = builder.start();
        baseUrl = "http://127.0.0.1:" + port;
        waitForHealth();
    }

    @AfterAll
    static void stopRuntime() {
        if (runtimeProcess != null) {
            runtimeProcess.destroy();
        }
    }

    @Test
    void runtimeReturnsStableSuccessAndUnicodeCards() {
        var response = client(3000).execute(request("success", "技术链路检查"));

        assertThat(response.schemaVersion()).isEqualTo("1.0");
        assertThat(response.cards()).hasSize(1);
        assertThat(response.cards().getFirst().title()).isEqualTo("AI教练服务已连接");
    }

    @Test
    void runtimeInvalidModeReturnsParsableButInvalidStructureForJavaValidationLayer() {
        var response = client(3000).execute(request("invalid", "invalid"));

        assertThat(response.schemaVersion()).isEqualTo("invalid");
        assertThat(response.cards()).isEmpty();
    }

    @Test
    void runtimeFailureAndTimeoutAreMappedToRuntimeUnavailable() {
        assertThatThrownBy(() -> client(3000).execute(request("failure", "failure")))
                .isInstanceOf(AgentRuntimeException.class)
                .hasMessageContaining("Agent Runtime 返回非成功状态");
        assertThatThrownBy(() -> client(3000).execute(request("timeout", "timeout")))
                .isInstanceOf(AgentRuntimeException.class)
                .hasMessageContaining("Agent Runtime 返回非成功状态");
    }

    private static HttpAgentRuntimeClient client(long timeoutMillis) {
        return new HttpAgentRuntimeClient(new ObjectMapper(), baseUrl, timeoutMillis);
    }

    private static AgentRuntimeRequest request(String mockMode, String inputSummary) {
        return new AgentRuntimeRequest(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                "TECHNICAL_SMOKE_TEST", inputSummary, mockMode);
    }

    private static int freePort() throws IOException {
        try (ServerSocket socket = new ServerSocket(0)) {
            return socket.getLocalPort();
        }
    }

    private static void waitForHealth() throws Exception {
        HttpClient client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(2))
                .build();
        URI uri = URI.create(baseUrl + "/health");
        for (int attempt = 0; attempt < 30; attempt++) {
            if (!runtimeProcess.isAlive()) {
                throw new IllegalStateException("Python Agent Runtime exited before health check");
            }
            try {
                HttpResponse<String> response = client.send(
                        HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(2)).GET().build(),
                        HttpResponse.BodyHandlers.ofString()
                );
                if (response.statusCode() == 200) {
                    return;
                }
            } catch (IOException ignored) {
                // Runtime 仍在启动，继续轮询。
            }
            Thread.sleep(100);
        }
        throw new IllegalStateException("Python Agent Runtime did not become healthy");
    }
}
