package com.indigobyte.reboothealth.error;

import java.time.Instant;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

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

    @ExceptionHandler(Exception.class)
    ResponseEntity<ApiErrorResponse> handleUnhandled(Exception ex) {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(new ApiErrorResponse(
                ErrorCode.DATA_CONFLICT,
                "请求处理失败",
                List.of(),
                Instant.now()
        ));
    }

    private HttpStatus statusFor(ErrorCode code) {
        return switch (code) {
            case PROFILE_NOT_INITIALIZED,
                    HEALTH_CONSTRAINT_NOT_FOUND,
                    GOAL_NOT_FOUND -> HttpStatus.NOT_FOUND;
            case HEALTH_CONSTRAINT_ARCHIVED,
                    HEALTH_CONSTRAINT_INVALID_STATUS_TRANSITION,
                    GOAL_ARCHIVED,
                    GOAL_INVALID_STATUS_TRANSITION,
                    DATA_CONFLICT -> HttpStatus.CONFLICT;
            default -> HttpStatus.BAD_REQUEST;
        };
    }
}
