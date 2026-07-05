package com.indigobyte.reboothealth.profile.adapter.api;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record ArchiveRequest(@NotBlank @Size(max = 300) String archiveReason) {
}
