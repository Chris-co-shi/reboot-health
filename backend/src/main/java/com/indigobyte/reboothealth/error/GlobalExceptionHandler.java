package com.indigobyte.reboothealth.error;

import java.time.Instant;
import java.util.List;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

/**
 * REST API 的统一异常映射。
 *
 * <p>领域和应用异常按明确错误码返回；未预期异常记录服务端日志并返回 INTERNAL_ERROR，避免泄漏内部细节。</p>
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(ApplicationException.class)
    ResponseEntity<ApiErrorResponse> handleApplicationException(ApplicationException ex) {
        return ResponseEntity.status(ex.status()).body(new ApiErrorResponse(
                ex.code(),
                ex.getMessage(),
                List.of(),
                Instant.now()
        ));
    }

    @ExceptionHandler(DomainException.class)
    ResponseEntity<ApiErrorResponse> handleDomainException(DomainException ex) {
        return ResponseEntity.status(statusFor(ex.code())).body(new ApiErrorResponse(
                ex.code(),
                ex.getMessage(),
                List.of(),
                Instant.now()
        ));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ResponseEntity<ApiErrorResponse> handleValidation(MethodArgumentNotValidException ex) {
        var fields = ex.getBindingResult().getFieldErrors().stream()
                .map(error -> new ApiErrorResponse.FieldErrorItem(error.getField(), error.getDefaultMessage()))
                .toList();
        return ResponseEntity.badRequest().body(new ApiErrorResponse(
                ErrorCode.VALIDATION_ERROR,
                "请求参数校验失败",
                fields,
                Instant.now()
        ));
    }

    @ExceptionHandler({HttpMessageNotReadableException.class, MethodArgumentTypeMismatchException.class})
    ResponseEntity<ApiErrorResponse> handleEnumOrBodyError(Exception ex) {
        return ResponseEntity.badRequest().body(new ApiErrorResponse(
                ErrorCode.ENUM_INVALID,
                "请求中包含无效枚举值或无法解析的字段",
                List.of(),
                Instant.now()
        ));
    }

    @ExceptionHandler(DataIntegrityViolationException.class)
    ResponseEntity<ApiErrorResponse> handleDataIntegrityViolation(DataIntegrityViolationException ex) {
        String message = ex.getMostSpecificCause() == null ? ex.getMessage() : ex.getMostSpecificCause().getMessage();
        if (message != null && (
                message.contains("ex_plan_version_confirmed_period")
                        || message.contains("uk_plan_version_confirmed_period")
        )) {
            return ResponseEntity.status(HttpStatus.CONFLICT).body(new ApiErrorResponse(
                    ErrorCode.PLAN_VERSION_PERIOD_OVERLAP,
                    "已存在重叠日期周期的确认计划",
                    List.of(),
                    Instant.now()
            ));
        }
        return ResponseEntity.status(HttpStatus.CONFLICT).body(new ApiErrorResponse(
                ErrorCode.DATA_CONFLICT,
                "数据状态冲突",
                List.of(),
                Instant.now()
        ));
    }

    @ExceptionHandler(Exception.class)
    ResponseEntity<ApiErrorResponse> handleUnhandled(Exception ex) {
        log.error("未处理的服务端异常", ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(new ApiErrorResponse(
                ErrorCode.INTERNAL_ERROR,
                "请求处理失败",
                List.of(),
                Instant.now()
        ));
    }

    private HttpStatus statusFor(ErrorCode code) {
        return switch (code) {
            case PROFILE_NOT_INITIALIZED,
                    HEALTH_CONSTRAINT_NOT_FOUND,
                    GOAL_NOT_FOUND,
                    PLAN_NOT_FOUND,
                    PLAN_CURRENT_NOT_FOUND,
                    PLAN_VERSION_NOT_FOUND,
                    PLAN_DAY_NOT_FOUND,
                    PLAN_ITEM_NOT_FOUND -> HttpStatus.NOT_FOUND;
            case HEALTH_CONSTRAINT_ARCHIVED,
                    HEALTH_CONSTRAINT_INVALID_STATUS_TRANSITION,
                    GOAL_ARCHIVED,
                    GOAL_INVALID_STATUS_TRANSITION,
                    IDEMPOTENCY_KEY_REUSED,
                    PLAN_ALREADY_EXISTS,
                    PLAN_VERSION_NOT_DRAFT,
                    PLAN_VERSION_IMMUTABLE,
                    PLAN_VERSION_REVISION_CONFLICT,
                    PLAN_VERSION_PERIOD_OVERLAP,
                    PLAN_VERSION_SOURCE_INVALID,
                    DATA_CONFLICT -> HttpStatus.CONFLICT;
            default -> HttpStatus.BAD_REQUEST;
        };
    }
}
