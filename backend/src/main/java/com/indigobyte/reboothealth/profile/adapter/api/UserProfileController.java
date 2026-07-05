package com.indigobyte.reboothealth.profile.adapter.api;

import com.indigobyte.reboothealth.error.ApplicationException;
import com.indigobyte.reboothealth.error.ErrorCode;
import com.indigobyte.reboothealth.profile.application.UserProfileApplicationService;
import com.indigobyte.reboothealth.profile.application.UserProfileApplicationService.SaveUserProfileCommand;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/profile")
public class UserProfileController {

    private final UserProfileApplicationService service;

    public UserProfileController(UserProfileApplicationService service) {
        this.service = service;
    }

    @GetMapping
    public UserProfileResponse getCurrentProfile() {
        return service.getCurrentProfile()
                .map(UserProfileResponse::from)
                .orElseThrow(() -> new ApplicationException(
                        ErrorCode.PROFILE_NOT_INITIALIZED,
                        "用户档案尚未初始化",
                        HttpStatus.NOT_FOUND
                ));
    }

    @PutMapping
    public UserProfileResponse saveCurrentProfile(@Valid @RequestBody UserProfileRequest request) {
        var saved = service.saveCurrentProfile(new SaveUserProfileCommand(
                request.displayName(),
                request.sex(),
                request.birthDate(),
                request.heightCm(),
                request.baselineWeightKg(),
                request.timezone()
        ));
        return UserProfileResponse.from(saved);
    }
}
