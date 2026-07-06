package com.indigobyte.reboothealth.device.adapter.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.indigobyte.reboothealth.device.application.DeviceApplicationService;
import com.indigobyte.reboothealth.device.domain.DevicePrincipal;
import com.indigobyte.reboothealth.error.ApiErrorResponse;
import com.indigobyte.reboothealth.error.ApplicationException;
import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.time.Clock;
import java.time.Instant;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * 统一设备访问令牌认证过滤器。
 *
 * <p>除明确白名单外，所有 /api/v1/** 请求都需要有效设备 access token；Controller 不再各自解析 Authorization。</p>
 */
@Component
public class DeviceAuthenticationFilter extends OncePerRequestFilter {

    public static final String PRINCIPAL_ATTRIBUTE = DevicePrincipal.class.getName();

    private final DeviceApplicationService deviceService;
    private final ObjectMapper objectMapper;
    private final Clock clock;
    private final boolean enabled;

    public DeviceAuthenticationFilter(
            DeviceApplicationService deviceService,
            ObjectMapper objectMapper,
            Clock clock,
            @Value("${app.device.auth.enabled:true}") boolean enabled
    ) {
        this.deviceService = deviceService;
        this.objectMapper = objectMapper;
        this.clock = clock;
        this.enabled = enabled;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        if (!enabled || !requiresDeviceAuth(request)) {
            filterChain.doFilter(request, response);
            return;
        }
        try {
            DevicePrincipal principal = deviceService.authenticate(request.getHeader("Authorization"));
            request.setAttribute(PRINCIPAL_ATTRIBUTE, principal);
            filterChain.doFilter(request, response);
        } catch (ApplicationException ex) {
            writeError(response, ex.status(), ex.code(), ex.getMessage());
        } catch (DomainException ex) {
            writeError(response, HttpStatus.UNAUTHORIZED, ex.code(), "设备访问令牌无效");
        }
    }

    private boolean requiresDeviceAuth(HttpServletRequest request) {
        String path = request.getRequestURI();
        String method = request.getMethod();
        if (!path.startsWith("/api/v1/")) {
            return false;
        }
        return !(
                ("GET".equals(method) && (path.startsWith("/actuator/health") || "/actuator/info".equals(path)))
                        || ("GET".equals(method) && "/api/v1/device-bootstrap/status".equals(path))
                        || ("POST".equals(method) && "/api/v1/device-bootstrap/consume".equals(path))
                        || ("POST".equals(method) && "/api/v1/devices/pair".equals(path))
                        || ("POST".equals(method) && "/api/v1/devices/token/refresh".equals(path))
        );
    }

    private void writeError(HttpServletResponse response, HttpStatus status, ErrorCode code, String message)
            throws IOException {
        response.setStatus(status.value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        objectMapper.writeValue(response.getWriter(), new ApiErrorResponse(code, message, List.of(), Instant.now(clock)));
    }
}
