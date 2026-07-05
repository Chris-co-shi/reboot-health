package com.indigobyte.reboothealth.idempotency.application;

import com.indigobyte.reboothealth.error.ApplicationException;
import com.indigobyte.reboothealth.error.ErrorCode;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

/**
 * Idempotency-Key 校验组件。
 */
@Component
public class IdempotencyKeyValidator {

    private static final String KEY_PATTERN = "^[A-Za-z0-9._:-]{16,128}$";

    public void validate(String key) {
        if (key == null || key.isBlank()) {
            throw new ApplicationException(ErrorCode.IDEMPOTENCY_KEY_REQUIRED, "缺少 Idempotency-Key", HttpStatus.BAD_REQUEST);
        }
        if (!key.matches(KEY_PATTERN)) {
            throw new ApplicationException(ErrorCode.IDEMPOTENCY_KEY_INVALID, "Idempotency-Key 格式无效", HttpStatus.BAD_REQUEST);
        }
    }
}
