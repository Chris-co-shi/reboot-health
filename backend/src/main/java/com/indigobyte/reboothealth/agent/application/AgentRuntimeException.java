package com.indigobyte.reboothealth.agent.application;

/**
 * Agent Runtime 调用或输出异常。
 */
public class AgentRuntimeException extends RuntimeException {

    private final String code;

    public AgentRuntimeException(String code, String message) {
        super(message);
        this.code = code;
    }

    public String code() {
        return code;
    }
}
