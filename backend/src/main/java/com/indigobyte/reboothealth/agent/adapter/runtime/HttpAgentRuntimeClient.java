package com.indigobyte.reboothealth.agent.adapter.runtime;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.indigobyte.reboothealth.agent.application.AgentRuntimeClient;
import com.indigobyte.reboothealth.agent.application.AgentRuntimeException;
import com.indigobyte.reboothealth.agent.application.AgentRuntimeRequest;
import com.indigobyte.reboothealth.agent.application.AgentRuntimeResponse;
import com.indigobyte.reboothealth.error.ErrorCode;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * 基于内部 HTTP 的 Python Agent Runtime 客户端。
 *
 * <p>该适配器只调用 Python 的执行接口，不暴露数据库连接或业务写接口给 Python。</p>
 */
@Component
public class HttpAgentRuntimeClient implements AgentRuntimeClient {

    private final ObjectMapper objectMapper;
    private final HttpClient httpClient;
    private final URI executeUri;
    private final Duration requestTimeout;

    public HttpAgentRuntimeClient(
            ObjectMapper objectMapper,
            @Value("${app.agent-runtime.base-url:http://localhost:8090}") String baseUrl,
            @Value("${app.agent-runtime.timeout-millis:3000}") long timeoutMillis
    ) {
        this.objectMapper = objectMapper;
        this.requestTimeout = Duration.ofMillis(timeoutMillis);
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(this.requestTimeout)
                .build();
        this.executeUri = URI.create(baseUrl + "/internal/v1/agent-runs/execute");
    }

    @Override
    public AgentRuntimeResponse execute(AgentRuntimeRequest request) {
        try {
            HttpRequest httpRequest = HttpRequest.newBuilder(executeUri)
                    .timeout(requestTimeout)
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(objectMapper.writeValueAsString(request)))
                    .build();
            HttpResponse<String> response = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new AgentRuntimeException(ErrorCode.AGENT_RUNTIME_UNAVAILABLE.name(),
                        "Agent Runtime 返回非成功状态");
            }
            return objectMapper.readValue(response.body(), AgentRuntimeResponse.class);
        } catch (JsonProcessingException ex) {
            throw new AgentRuntimeException(ErrorCode.AGENT_RUNTIME_INVALID_OUTPUT.name(), "Agent Runtime 输出无法解析");
        } catch (IOException ex) {
            throw new AgentRuntimeException(ErrorCode.AGENT_RUNTIME_UNAVAILABLE.name(), "Agent Runtime 不可用");
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new AgentRuntimeException(ErrorCode.AGENT_RUNTIME_UNAVAILABLE.name(), "Agent Runtime 调用被中断");
        }
    }
}
