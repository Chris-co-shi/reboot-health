package com.indigobyte.reboothealth.device.adapter.cli;

import com.indigobyte.reboothealth.device.application.DeviceApplicationService;
import com.indigobyte.reboothealth.device.application.DeviceApplicationService.BootstrapCode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.stereotype.Component;

/**
 * 服务端 CLI bootstrap code 生成入口。
 *
 * <p>只有显式设置 app.device.bootstrap.generate=true 时才生成 code；普通 HTTP 接口不提供生成能力。</p>
 */
@Component
public class BootstrapCliRunner implements ApplicationRunner {

    private final DeviceApplicationService service;
    private final ConfigurableApplicationContext context;
    private final boolean generateBootstrapCode;

    public BootstrapCliRunner(
            DeviceApplicationService service,
            ConfigurableApplicationContext context,
            @Value("${app.device.bootstrap.generate:false}") boolean generateBootstrapCode
    ) {
        this.service = service;
        this.context = context;
        this.generateBootstrapCode = generateBootstrapCode;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (!generateBootstrapCode) {
            return;
        }
        BootstrapCode code = service.createBootstrapCodeForCli();
        System.out.println("reboot-health bootstrap code: " + code.code());
        System.out.println("expires at: " + code.expiresAt());
        SpringApplication.exit(context, () -> 0);
    }
}
