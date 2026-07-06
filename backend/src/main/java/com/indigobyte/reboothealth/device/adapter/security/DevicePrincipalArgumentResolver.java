package com.indigobyte.reboothealth.device.adapter.security;

import com.indigobyte.reboothealth.device.domain.DevicePrincipal;
import com.indigobyte.reboothealth.error.ApplicationException;
import com.indigobyte.reboothealth.error.ErrorCode;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.core.MethodParameter;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;

/**
 * 从统一认证过滤器写入的 request attribute 中解析当前设备身份。
 */
@Component
public class DevicePrincipalArgumentResolver implements HandlerMethodArgumentResolver {

    @Override
    public boolean supportsParameter(MethodParameter parameter) {
        return DevicePrincipal.class.equals(parameter.getParameterType());
    }

    @Override
    public Object resolveArgument(MethodParameter parameter, ModelAndViewContainer mavContainer,
                                  NativeWebRequest webRequest, WebDataBinderFactory binderFactory) {
        HttpServletRequest request = webRequest.getNativeRequest(HttpServletRequest.class);
        Object principal = request == null ? null : request.getAttribute(DeviceAuthenticationFilter.PRINCIPAL_ATTRIBUTE);
        if (principal instanceof DevicePrincipal devicePrincipal) {
            return devicePrincipal;
        }
        throw new ApplicationException(ErrorCode.DEVICE_UNAUTHORIZED, "缺少设备访问令牌", HttpStatus.UNAUTHORIZED);
    }
}
