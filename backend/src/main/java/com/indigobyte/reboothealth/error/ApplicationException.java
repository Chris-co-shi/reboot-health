package com.indigobyte.reboothealth.error;

import org.springframework.http.HttpStatus;

public class ApplicationException extends RuntimeException {

    private final ErrorCode code;
    private final HttpStatus status;

    public ApplicationException(ErrorCode code, String message, HttpStatus status) {
        super(message);
        this.code = code;
        this.status = status;
    }

    public ErrorCode code() {
        return code;
    }

    public HttpStatus status() {
        return status;
    }
}
