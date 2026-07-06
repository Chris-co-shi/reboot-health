package com.indigobyte.reboothealth.agent.application;

/**
 * Python Agent Runtime 客户端端口。
 *
 * <p>Java 通过该端口提交运行任务；Python 不直接连接数据库，也不回写业务状态。</p>
 */
public interface AgentRuntimeClient {

    AgentRuntimeResponse execute(AgentRuntimeRequest request);
}
