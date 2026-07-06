package com.indigobyte.reboothealth.device.adapter.security;

import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * 设备认证 Web 配置。
 */
@Configuration
@RequiredArgsConstructor
public class DeviceSecurityWebConfig implements WebMvcConfigurer {

    private final DevicePrincipalArgumentResolver argumentResolver;

    @Override
    public void addArgumentResolvers(List<HandlerMethodArgumentResolver> resolvers) {
        resolvers.add(argumentResolver);
    }
}
