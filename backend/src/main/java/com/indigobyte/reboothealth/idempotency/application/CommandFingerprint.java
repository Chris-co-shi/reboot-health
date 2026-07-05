package com.indigobyte.reboothealth.idempotency.application;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Comparator;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Component;

/**
 * 命令指纹计算器。
 *
 * <p>先对 operation、路径资源 ID 和反序列化后的 command 做确定性规范化，再计算 SHA-256，避免 JSON 字段顺序或空白影响幂等判断。</p>
 */
@Component
public class CommandFingerprint {

    private final ObjectMapper objectMapper;

    public CommandFingerprint(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public String hash(String operationCode, Map<String, UUID> pathIds, Object command) {
        StringBuilder canonical = new StringBuilder();
        canonical.append("operation=").append(operationCode).append(';');
        pathIds.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .forEach(entry -> canonical.append("path.")
                        .append(entry.getKey())
                        .append('=')
                        .append(entry.getValue())
                        .append(';'));
        canonical.append("command=").append(canonicalize(objectMapper.valueToTree(command)));
        return sha256(canonical.toString());
    }

    private String canonicalize(JsonNode node) {
        if (node == null || node.isNull()) {
            return "null";
        }
        if (node.isObject()) {
            StringBuilder builder = new StringBuilder("{");
            node.properties().stream()
                    .sorted(Comparator.comparing(Map.Entry::getKey))
                    .forEach(entry -> builder.append(entry.getKey())
                            .append(':')
                            .append(canonicalize(entry.getValue()))
                            .append(','));
            return builder.append('}').toString();
        }
        if (node.isArray()) {
            StringBuilder builder = new StringBuilder("[");
            node.forEach(item -> builder.append(canonicalize(item)).append(','));
            return builder.append(']').toString();
        }
        if (node.isNumber()) {
            return node.decimalValue().stripTrailingZeros().toPlainString();
        }
        if (node.isTextual()) {
            return '"' + node.textValue() + '"';
        }
        return node.asText();
    }

    private String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder builder = new StringBuilder(bytes.length * 2);
            for (byte b : bytes) {
                builder.append(String.format("%02x", b));
            }
            return builder.toString();
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 不可用", ex);
        }
    }
}
