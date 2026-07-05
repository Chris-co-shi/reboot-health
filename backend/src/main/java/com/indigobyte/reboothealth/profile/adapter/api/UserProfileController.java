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

/**
 * 个人档案 REST API。
 *
 * <p>个人版只暴露当前档案的读取和幂等保存，不引入账号、登录或多用户语义。</p>
 */
@RestController
@RequestMapping("/api/v1/profile")
public class UserProfileController {

    private final UserProfileApplicationService service;

    public UserProfileController(UserProfileApplicationService service) {
        this.service = service;
    }

    /**
     * 获取当前个人档案。
     *
     * @return 个人档案响应对象
     * @throws ApplicationException 如果档案尚未初始化，返回 404
     */
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

    /**
     * 保存或更新当前个人档案。
     *
     * <p>如果档案不存在则创建，存在则进行幂等更新。业务内容无变化时不写审计日志。</p>
     *
     * @param request 包含档案信息的请求对象
     * @return 保存后的个人档案响应对象
     */
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
