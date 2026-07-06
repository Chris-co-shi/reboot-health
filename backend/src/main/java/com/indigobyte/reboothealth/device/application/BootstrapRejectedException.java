package com.indigobyte.reboothealth.device.application;

import com.indigobyte.reboothealth.error.ApplicationException;
import com.indigobyte.reboothealth.error.ErrorCode;
import org.springframework.http.HttpStatus;

/**
 * bootstrap code 被拒绝时抛出的业务异常。
 *
 * <p>该异常允许提交失败次数、过期状态和拒绝审计，避免安全防护状态被事务回滚。</p>
 */
public class BootstrapRejectedException extends ApplicationException {

    public BootstrapRejectedException() {
        super(ErrorCode.BOOTSTRAP_CODE_INVALID, "bootstrap code 无效", HttpStatus.CONFLICT);
    }
}
