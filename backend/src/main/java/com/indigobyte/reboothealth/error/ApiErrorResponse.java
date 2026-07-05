package com.indigobyte.reboothealth.error;

import java.time.Instant;
import java.util.List;

public record ApiErrorResponse(
        ErrorCode code,
        String message,
        List<FieldErrorItem> fields,
        Instant timestamp
) {
    public record FieldErrorItem(String field, String message) {
    }
}
