package com.indigobyte.reboothealth.plan.application;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.indigobyte.reboothealth.audit.application.AuditLogAppender;
import com.indigobyte.reboothealth.error.ApplicationException;
import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;
import com.indigobyte.reboothealth.goal.domain.Goal;
import com.indigobyte.reboothealth.goal.domain.GoalRepository;
import com.indigobyte.reboothealth.goal.domain.GoalStatus;
import com.indigobyte.reboothealth.idempotency.application.IdempotencyApplicationService;
import com.indigobyte.reboothealth.idempotency.domain.IdempotencyRecord;
import com.indigobyte.reboothealth.idempotency.domain.IdempotencyState;
import com.indigobyte.reboothealth.plan.domain.Plan;
import com.indigobyte.reboothealth.plan.domain.PlanDay;
import com.indigobyte.reboothealth.plan.domain.PlanDayDetail;
import com.indigobyte.reboothealth.plan.domain.GoalSummarySnapshot;
import com.indigobyte.reboothealth.plan.domain.HealthConstraintSnapshot;
import com.indigobyte.reboothealth.plan.domain.PlanItem;
import com.indigobyte.reboothealth.plan.domain.PlanItemType;
import com.indigobyte.reboothealth.plan.domain.PlanRepository;
import com.indigobyte.reboothealth.plan.domain.PlanVersion;
import com.indigobyte.reboothealth.plan.domain.PlanVersionDetail;
import com.indigobyte.reboothealth.plan.domain.PlanVersionFilter;
import com.indigobyte.reboothealth.plan.domain.PlanVersionPreview;
import com.indigobyte.reboothealth.plan.domain.PlanVersionStatus;
import com.indigobyte.reboothealth.profile.domain.ConstraintStatus;
import com.indigobyte.reboothealth.profile.domain.HealthConstraintFilter;
import com.indigobyte.reboothealth.profile.domain.HealthConstraintRepository;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.function.Function;
import java.util.function.Supplier;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 计划应用服务。
 *
 * <p>负责人工计划版本的事务编排、幂等 POST、审计、确认完整性校验和版本查询；领域对象负责可变状态的核心不变量。</p>
 */
@Service
@RequiredArgsConstructor
public class PlanApplicationService {

    private static final String PLAN_RESOURCE = "PLAN";
    private static final String PLAN_VERSION_RESOURCE = "PLAN_VERSION";
    private static final String PLAN_ENTITY = "Plan";
    private static final String PLAN_VERSION_ENTITY = "PlanVersion";
    private static final String PLAN_DAY_ENTITY = "PlanDay";
    private static final String PLAN_ITEM_ENTITY = "PlanItem";

    private final PlanRepository planRepository;
    private final GoalRepository goalRepository;
    private final HealthConstraintRepository healthConstraintRepository;
    private final AuditLogAppender auditLogAppender;
    private final IdempotencyApplicationService idempotencyService;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    @Transactional
    public IdempotentResult<Plan> createPlan(String idempotencyKey, CreatePlanCommand command) {
        return executeIdempotent(idempotencyKey, "PLAN_CREATE", Map.of(), command,
                this::replayPlan,
                () -> {
                    if (planRepository.findCurrentPlan().isPresent()) {
                        throw new ApplicationException(ErrorCode.PLAN_ALREADY_EXISTS, "长期计划已存在", HttpStatus.CONFLICT);
                    }
                    Instant now = Instant.now(clock);
                    Plan plan = Plan.create(command.title(), command.summary(), now);
                    planRepository.insertPlan(plan);
                    auditLogAppender.append("PLAN_CREATED", PLAN_ENTITY, plan.getId(), null, plan);
                    return new CreatedResource<>(plan, PLAN_RESOURCE, plan.getId(), HttpStatus.CREATED.value());
                });
    }

    @Transactional(readOnly = true)
    public Plan getSingletonPlan() {
        return planRepository.findCurrentPlan().orElseThrow(() -> new ApplicationException(
                ErrorCode.PLAN_NOT_FOUND, "长期计划不存在", HttpStatus.NOT_FOUND));
    }

    @Transactional(readOnly = true)
    public Plan getPlan(UUID planId) {
        return findPlan(planId);
    }

    @Transactional(readOnly = true)
    public PlanVersionDetail getCurrentPlan(LocalDate currentDate) {
        PlanVersion version = planRepository.findCurrentConfirmedVersion(currentDate)
                .orElseThrow(() -> new ApplicationException(ErrorCode.PLAN_CURRENT_NOT_FOUND,
                        "当前日期没有已确认计划", HttpStatus.NOT_FOUND));
        return detail(version);
    }

    @Transactional(readOnly = true)
    public List<PlanVersion> listVersions(UUID planId, PlanVersionFilter filter) {
        findPlan(planId);
        return planRepository.findVersions(planId, filter);
    }

    @Transactional(readOnly = true)
    public PlanVersionDetail getVersionDetail(UUID versionId) {
        return detail(findVersion(versionId));
    }

    @Transactional(readOnly = true)
    public PlanVersionPreview preview(UUID versionId) {
        PlanVersion version = findVersion(versionId);
        PlanVersionDetail detail = detail(version);
        List<String> validationIssues = collectValidationIssues(version);
        boolean canConfirm = version.getStatus() == PlanVersionStatus.DRAFT && validationIssues.isEmpty();
        return new PlanVersionPreview(detail, detail.goals(), detail.healthConstraints(), validationIssues, canConfirm);
    }

    @Transactional
    public IdempotentResult<PlanVersionDetail> createDraft(String idempotencyKey, UUID planId, CreateDraftCommand command) {
        return executeVersionIdempotent(idempotencyKey, "PLAN_VERSION_DRAFT_CREATE", Map.of("planId", planId), command,
                () -> {
                    Plan plan = findPlanForUpdate(planId);
                    Instant now = Instant.now(clock);
                    PlanVersion version = PlanVersion.createDraft(
                            plan.getId(),
                            planRepository.nextVersionNumber(plan.getId()),
                            planRepository.nextPeriodRevision(plan.getId(), command.startDate()),
                            command.startDate(),
                            command.title(),
                            command.summary(),
                            null,
                            now
                    );
                    planRepository.insertVersion(version);
                    insertDefaultDays(version, now);
                    validateGoalLinks(command.goalIds());
                    planRepository.insertGoalLinks(version.getId(), distinct(command.goalIds()), now);
                    PlanVersionDetail detail = detail(version);
                    auditLogAppender.append("PLAN_VERSION_DRAFT_CREATED", PLAN_VERSION_ENTITY, version.getId(), null, detail);
                    return new CreatedResource<>(detail, PLAN_VERSION_RESOURCE, version.getId(), HttpStatus.CREATED.value());
                });
    }

    @Transactional
    public PlanVersionDetail updateVersion(UUID versionId, UpdateVersionCommand command) {
        PlanVersion version = findVersionForUpdate(versionId);
        PlanVersion before = copyVersion(version);
        version.assertExpectedRevision(command.expectedRevision());
        version.updateDraft(command.title(), command.summary(), Instant.now(clock));
        validateGoalLinks(command.goalIds());
        assertUpdated(planRepository.updateVersion(version));
        planRepository.replaceGoalLinks(version.getId(), distinct(command.goalIds()), Instant.now(clock));
        PlanVersionDetail detail = detail(version);
        auditLogAppender.append("PLAN_VERSION_UPDATED", PLAN_VERSION_ENTITY, version.getId(), before, detail);
        return detail;
    }

    @Transactional
    public IdempotentResult<PlanVersionDetail> copyVersion(String idempotencyKey, UUID sourceVersionId, CopyVersionCommand command) {
        return executeVersionIdempotent(idempotencyKey, "PLAN_VERSION_COPY", Map.of("sourceVersionId", sourceVersionId), command,
                () -> {
                    PlanVersion source = findVersion(sourceVersionId);
                    if (source.getStatus() != PlanVersionStatus.CONFIRMED && source.getStatus() != PlanVersionStatus.SUPERSEDED) {
                        throw new ApplicationException(ErrorCode.PLAN_VERSION_SOURCE_INVALID,
                                "只能复制已确认或已替代的计划版本", HttpStatus.CONFLICT);
                    }
                    if (command.expectedSourceStatus() != null && source.getStatus() != command.expectedSourceStatus()) {
                        throw new ApplicationException(ErrorCode.PLAN_VERSION_SOURCE_INVALID,
                                "源版本状态已变化，请刷新后重试", HttpStatus.CONFLICT);
                    }
                    findPlanForUpdate(source.getPlanId());
                    Instant now = Instant.now(clock);
                    PlanVersion draft = PlanVersion.createDraft(
                            source.getPlanId(),
                            planRepository.nextVersionNumber(source.getPlanId()),
                            planRepository.nextPeriodRevision(source.getPlanId(), command.startDate()),
                            command.startDate(),
                            command.title() == null || command.title().isBlank() ? source.getTitle() : command.title(),
                            command.summary() == null ? source.getSummary() : command.summary(),
                            source.getId(),
                            now
                    );
                    planRepository.insertVersion(draft);
                    copyDaysAndItems(source, draft, now);
                    List<UUID> goalIds = planRepository.findGoalIds(source.getId());
                    validateGoalLinks(goalIds);
                    planRepository.insertGoalLinks(draft.getId(), goalIds, now);
                    PlanVersionDetail detail = detail(draft);
                    auditLogAppender.append("PLAN_VERSION_DRAFT_COPIED", PLAN_VERSION_ENTITY, draft.getId(), source, detail);
                    return new CreatedResource<>(detail, PLAN_VERSION_RESOURCE, draft.getId(), HttpStatus.CREATED.value());
                });
    }

    @Transactional
    public IdempotentResult<PlanVersionDetail> confirm(String idempotencyKey, UUID versionId, ConfirmVersionCommand command) {
        return executeVersionIdempotent(idempotencyKey, "PLAN_VERSION_CONFIRM", Map.of("versionId", versionId), command,
                () -> {
                    PlanVersion draft = findVersionForUpdate(versionId);
                    draft.assertDraft();
                    draft.assertExpectedRevision(command.expectedRevision());
                    findPlanForUpdate(draft.getPlanId());
                    validateCompleteness(draft);
                    if (planRepository.findOverlappingConfirmedVersionForUpdate(
                            draft.getPlanId(), draft.getStartDate(), draft.getEndDate()
                    ).isPresent()) {
                        throw new ApplicationException(ErrorCode.PLAN_VERSION_PERIOD_OVERLAP,
                                "已存在重叠日期周期的确认计划", HttpStatus.CONFLICT);
                    }
                    PlanVersion oldConfirmed = planRepository
                            .findConfirmedVersionForPeriodForUpdate(draft.getPlanId(), draft.getStartDate())
                            .orElse(null);
                    Instant now = Instant.now(clock);
                    if (oldConfirmed != null) {
                        PlanVersion beforeOld = copyVersion(oldConfirmed);
                        oldConfirmed.supersede(now);
                        assertUpdated(planRepository.updateVersion(oldConfirmed));
                        auditLogAppender.append("PLAN_VERSION_SUPERSEDED", PLAN_VERSION_ENTITY,
                                oldConfirmed.getId(), beforeOld, oldConfirmed);
                    }
                    PlanVersion beforeDraft = copyVersion(draft);
                    List<GoalSummarySnapshot> goalSnapshots = currentGoalSummaries(planRepository.findGoalIds(draft.getId()));
                    planRepository.snapshotGoalLinks(draft.getId(), goalSnapshots);
                    draft.confirm(oldConfirmed == null ? null : oldConfirmed.getId(), activeHealthConstraintSnapshotJson(), now);
                    assertUpdated(planRepository.updateVersion(draft));
                    PlanVersionDetail detail = detail(draft);
                    auditLogAppender.append("PLAN_VERSION_CONFIRMED", PLAN_VERSION_ENTITY, draft.getId(), beforeDraft, detail);
                    return new CreatedResource<>(detail, PLAN_VERSION_RESOURCE, draft.getId(), HttpStatus.OK.value());
                });
    }

    @Transactional
    public IdempotentResult<PlanVersionDetail> cancel(String idempotencyKey, UUID versionId, CancelVersionCommand command) {
        return executeVersionIdempotent(idempotencyKey, "PLAN_VERSION_CANCEL", Map.of("versionId", versionId), command,
                () -> {
                    PlanVersion version = findVersionForUpdate(versionId);
                    version.assertDraft();
                    version.assertExpectedRevision(command.expectedRevision());
                    PlanVersion before = copyVersion(version);
                    version.cancel(command.cancelReason(), Instant.now(clock));
                    assertUpdated(planRepository.updateVersion(version));
                    PlanVersionDetail detail = detail(version);
                    auditLogAppender.append("PLAN_VERSION_CANCELLED", PLAN_VERSION_ENTITY, version.getId(), before, detail);
                    return new CreatedResource<>(detail, PLAN_VERSION_RESOURCE, version.getId(), HttpStatus.OK.value());
                });
    }

    @Transactional
    public IdempotentResult<PlanVersionDetail> createDay(String idempotencyKey, UUID versionId, SaveDayCommand command) {
        return executeVersionIdempotent(idempotencyKey, "PLAN_DAY_CREATE", Map.of("versionId", versionId), command,
                () -> {
                    PlanVersion version = findVersionForUpdate(versionId);
                    version.assertExpectedRevision(command.expectedRevision());
                    ensureDateInPeriod(version, command.dayDate());
                    Instant now = Instant.now(clock);
                    PlanDay day = PlanDay.create(version.getId(), command.dayDate(), command.title(), command.note(), command.sortOrder(), now);
                    planRepository.insertDay(day);
                    version.touchDraftContent(now);
                    assertUpdated(planRepository.updateVersion(version));
                    auditLogAppender.append("PLAN_DAY_CREATED", PLAN_DAY_ENTITY, day.getId(), null, day);
                    return new CreatedResource<>(detail(version), PLAN_VERSION_RESOURCE, version.getId(), HttpStatus.CREATED.value());
                });
    }

    @Transactional
    public PlanVersionDetail updateDay(UUID dayId, SaveDayCommand command) {
        PlanDay day = findDay(dayId);
        PlanVersion version = findVersionForUpdate(day.getVersionId());
        version.assertExpectedRevision(command.expectedRevision());
        ensureDateInPeriod(version, command.dayDate());
        PlanDay before = copyDay(day);
        Instant now = Instant.now(clock);
        day.update(command.dayDate(), command.title(), command.note(), command.sortOrder(), now);
        assertUpdated(planRepository.updateDay(day));
        version.touchDraftContent(now);
        assertUpdated(planRepository.updateVersion(version));
        auditLogAppender.append("PLAN_DAY_UPDATED", PLAN_DAY_ENTITY, day.getId(), before, day);
        return detail(version);
    }

    @Transactional
    public PlanVersionDetail deleteDay(UUID dayId, Integer expectedRevision) {
        PlanDay day = findDay(dayId);
        PlanVersion version = findVersionForUpdate(day.getVersionId());
        version.assertDraft();
        version.assertExpectedRevision(expectedRevision);
        List<PlanItem> deletedItems = planRepository.deleteItemsByDayId(day.getId());
        deletedItems.forEach(item -> auditLogAppender.append("PLAN_ITEM_DELETED", PLAN_ITEM_ENTITY, item.getId(), item, null));
        assertDeleted(planRepository.deleteDay(day.getId()), ErrorCode.PLAN_DAY_NOT_FOUND, "计划日不存在");
        version.touchDraftContent(Instant.now(clock));
        assertUpdated(planRepository.updateVersion(version));
        auditLogAppender.append("PLAN_DAY_DELETED", PLAN_DAY_ENTITY, day.getId(), day, null);
        return detail(version);
    }

    @Transactional
    public IdempotentResult<PlanVersionDetail> createItem(String idempotencyKey, UUID dayId, SaveItemCommand command) {
        return executeVersionIdempotent(idempotencyKey, "PLAN_ITEM_CREATE", Map.of("dayId", dayId), command,
                () -> {
                    PlanDay day = findDay(dayId);
                    PlanVersion version = findVersionForUpdate(day.getVersionId());
                    version.assertExpectedRevision(command.expectedRevision());
                    validateGoalLink(command.goalId());
                    Instant now = Instant.now(clock);
                    PlanItem item = PlanItem.create(day.getId(), command.goalId(), command.itemType(), command.title(),
                            command.description(), command.plannedSets(), command.plannedReps(),
                            command.plannedDurationMinutes(), command.plannedDistanceMeters(), command.plannedRpe(),
                            command.sortOrder(), now);
                    planRepository.insertItem(item);
                    version.touchDraftContent(now);
                    assertUpdated(planRepository.updateVersion(version));
                    auditLogAppender.append("PLAN_ITEM_CREATED", PLAN_ITEM_ENTITY, item.getId(), null, item);
                    return new CreatedResource<>(detail(version), PLAN_VERSION_RESOURCE, version.getId(), HttpStatus.CREATED.value());
                });
    }

    @Transactional
    public PlanVersionDetail updateItem(UUID itemId, SaveItemCommand command) {
        PlanItem item = findItem(itemId);
        PlanDay day = findDay(item.getDayId());
        PlanVersion version = findVersionForUpdate(day.getVersionId());
        version.assertExpectedRevision(command.expectedRevision());
        validateGoalLink(command.goalId());
        PlanItem before = copyItem(item);
        Instant now = Instant.now(clock);
        item.update(command.goalId(), command.itemType(), command.title(), command.description(), command.plannedSets(),
                command.plannedReps(), command.plannedDurationMinutes(), command.plannedDistanceMeters(),
                command.plannedRpe(), command.sortOrder(), now);
        assertUpdated(planRepository.updateItem(item));
        version.touchDraftContent(now);
        assertUpdated(planRepository.updateVersion(version));
        auditLogAppender.append("PLAN_ITEM_UPDATED", PLAN_ITEM_ENTITY, item.getId(), before, item);
        return detail(version);
    }

    @Transactional
    public PlanVersionDetail deleteItem(UUID itemId, Integer expectedRevision) {
        PlanItem item = findItem(itemId);
        PlanDay day = findDay(item.getDayId());
        PlanVersion version = findVersionForUpdate(day.getVersionId());
        version.assertDraft();
        version.assertExpectedRevision(expectedRevision);
        assertDeleted(planRepository.deleteItem(item.getId()), ErrorCode.PLAN_ITEM_NOT_FOUND, "计划条目不存在");
        version.touchDraftContent(Instant.now(clock));
        assertUpdated(planRepository.updateVersion(version));
        auditLogAppender.append("PLAN_ITEM_DELETED", PLAN_ITEM_ENTITY, item.getId(), item, null);
        return detail(version);
    }

    private IdempotentResult<PlanVersionDetail> executeVersionIdempotent(
            String key, String operationCode, Map<String, UUID> pathIds, Object command,
            Supplier<CreatedResource<PlanVersionDetail>> action
    ) {
        return executeIdempotent(key, operationCode, pathIds, command, this::replayPlanVersion, action);
    }

    private <T> IdempotentResult<T> executeIdempotent(
            String key, String operationCode, Map<String, UUID> pathIds, Object command,
            Function<IdempotencyRecord, T> replayResolver,
            Supplier<CreatedResource<T>> action
    ) {
        var start = idempotencyService.start(key, operationCode, pathIds, command);
        if (!start.newRequest()) {
            IdempotencyRecord record = start.existingRecord();
            if (record.getState() != IdempotencyState.COMPLETED) {
                throw new ApplicationException(ErrorCode.DATA_CONFLICT, "幂等请求仍在处理中，请稍后重试", HttpStatus.CONFLICT);
            }
            return new IdempotentResult<>(replayResolver.apply(record), record.getResponseStatus(), true);
        }

        CreatedResource<T> created = action.get();
        idempotencyService.complete(key, created.resourceType(), created.resourceId(), created.responseStatus());
        return new IdempotentResult<>(created.body(), created.responseStatus(), false);
    }

    private Plan replayPlan(IdempotencyRecord record) {
        if (!PLAN_RESOURCE.equals(record.getResourceType())) {
            throw new ApplicationException(ErrorCode.DATA_CONFLICT, "幂等资源类型不匹配", HttpStatus.CONFLICT);
        }
        return findPlan(record.getResourceId());
    }

    private PlanVersionDetail replayPlanVersion(IdempotencyRecord record) {
        if (!PLAN_VERSION_RESOURCE.equals(record.getResourceType())) {
            throw new ApplicationException(ErrorCode.DATA_CONFLICT, "幂等资源类型不匹配", HttpStatus.CONFLICT);
        }
        return getVersionDetail(record.getResourceId());
    }

    private Plan findPlan(UUID planId) {
        return planRepository.findById(planId).orElseThrow(() -> new ApplicationException(
                ErrorCode.PLAN_NOT_FOUND, "计划不存在", HttpStatus.NOT_FOUND));
    }

    private Plan findPlanForUpdate(UUID planId) {
        return planRepository.findByIdForUpdate(planId).orElseThrow(() -> new ApplicationException(
                ErrorCode.PLAN_NOT_FOUND, "计划不存在", HttpStatus.NOT_FOUND));
    }

    private PlanVersion findVersion(UUID versionId) {
        return planRepository.findVersionById(versionId).orElseThrow(() -> new ApplicationException(
                ErrorCode.PLAN_VERSION_NOT_FOUND, "计划版本不存在", HttpStatus.NOT_FOUND));
    }

    private PlanVersion findVersionForUpdate(UUID versionId) {
        return planRepository.findVersionByIdForUpdate(versionId).orElseThrow(() -> new ApplicationException(
                ErrorCode.PLAN_VERSION_NOT_FOUND, "计划版本不存在", HttpStatus.NOT_FOUND));
    }

    private PlanDay findDay(UUID dayId) {
        return planRepository.findDayById(dayId).orElseThrow(() -> new ApplicationException(
                ErrorCode.PLAN_DAY_NOT_FOUND, "计划日不存在", HttpStatus.NOT_FOUND));
    }

    private PlanItem findItem(UUID itemId) {
        return planRepository.findItemById(itemId).orElseThrow(() -> new ApplicationException(
                ErrorCode.PLAN_ITEM_NOT_FOUND, "计划条目不存在", HttpStatus.NOT_FOUND));
    }

    private PlanVersionDetail detail(PlanVersion version) {
        List<PlanDayDetail> dayDetails = planRepository.findDays(version.getId()).stream()
                .map(day -> new PlanDayDetail(day, planRepository.findItemsByDayId(day.getId())))
                .toList();
        List<UUID> goalIds = planRepository.findGoalIds(version.getId());
        return new PlanVersionDetail(
                version,
                dayDetails,
                goalIds,
                goalSummariesFor(version, goalIds),
                healthConstraintsFor(version)
        );
    }

    private void insertDefaultDays(PlanVersion version, Instant now) {
        for (int index = 0; index < 7; index++) {
            planRepository.insertDay(PlanDay.create(
                    version.getId(),
                    version.getStartDate().plusDays(index),
                    "第 " + (index + 1) + " 天",
                    null,
                    index + 1,
                    now
            ));
        }
    }

    private void copyDaysAndItems(PlanVersion source, PlanVersion target, Instant now) {
        for (PlanDay sourceDay : planRepository.findDays(source.getId())) {
            long offset = ChronoUnit.DAYS.between(source.getStartDate(), sourceDay.getDayDate());
            PlanDay copiedDay = PlanDay.create(target.getId(), target.getStartDate().plusDays(offset),
                    sourceDay.getTitle(), sourceDay.getNote(), sourceDay.getSortOrder(), now);
            planRepository.insertDay(copiedDay);
            for (PlanItem item : planRepository.findItemsByDayId(sourceDay.getId())) {
                planRepository.insertItem(PlanItem.create(copiedDay.getId(), item.getGoalId(), item.getItemType(),
                        item.getTitle(), item.getDescription(), item.getPlannedSets(), item.getPlannedReps(),
                        item.getPlannedDurationMinutes(), item.getPlannedDistanceMeters(), item.getPlannedRpe(),
                        item.getSortOrder(), now));
            }
        }
    }

    private void validateCompleteness(PlanVersion version) {
        List<String> issues = collectValidationIssues(version);
        if (!issues.isEmpty()) {
            throw incomplete(String.join("；", issues));
        }
    }

    private List<String> collectValidationIssues(PlanVersion version) {
        List<String> issues = new java.util.ArrayList<>();
        collectGoalIssues(planRepository.findGoalIds(version.getId()), issues);
        List<PlanDay> days = planRepository.findDays(version.getId());
        if (days.size() != 7) {
            issues.add("计划草案必须包含 7 个计划日");
        }
        Set<LocalDate> dates = new LinkedHashSet<>();
        days.forEach(day -> {
            if (day.getTitle() == null || day.getTitle().isBlank()) {
                issues.add("计划日标题不能为空");
            }
            if (day.getDayDate() == null || day.getDayDate().isBefore(version.getStartDate())
                    || day.getDayDate().isAfter(version.getEndDate())) {
                issues.add("计划日日期必须在版本周期内");
            } else {
                dates.add(day.getDayDate());
            }
        });
        for (int index = 0; index < 7; index++) {
            if (!dates.contains(version.getStartDate().plusDays(index))) {
                issues.add("计划日必须连续且不重复");
                break;
            }
        }
        try {
            currentActiveHealthConstraintSnapshot();
        } catch (RuntimeException ex) {
            issues.add("健康约束快照生成失败");
        }
        return issues.stream().distinct().toList();
    }

    private DomainException incomplete(String message) {
        return new DomainException(ErrorCode.PLAN_VERSION_INCOMPLETE, message);
    }

    private void ensureDateInPeriod(PlanVersion version, LocalDate dayDate) {
        if (dayDate == null || dayDate.isBefore(version.getStartDate()) || dayDate.isAfter(version.getEndDate())) {
            throw new DomainException(ErrorCode.PLAN_DAY_DATE_OUT_OF_RANGE, "计划日日期必须在版本周期内");
        }
    }

    private String activeHealthConstraintSnapshotJson() {
        try {
            return objectMapper.writeValueAsString(currentActiveHealthConstraintSnapshot());
        } catch (JsonProcessingException ex) {
            throw new ApplicationException(ErrorCode.INTERNAL_ERROR, "健康约束快照生成失败", HttpStatus.INTERNAL_SERVER_ERROR);
        }
    }

    private HealthConstraintSnapshot currentActiveHealthConstraintSnapshot() {
        List<HealthConstraintSnapshot.Item> items = healthConstraintRepository.findAll(
                new HealthConstraintFilter(ConstraintStatus.ACTIVE, false)
        ).stream()
                .map(constraint -> new HealthConstraintSnapshot.Item(
                        constraint.getId(),
                        constraint.getConstraintType().name(),
                        constraint.getBodyRegion().name(),
                        constraint.getSeverity().name(),
                        constraint.getTitle(),
                        constraint.getDescription(),
                        constraint.getSourceType().name(),
                        constraint.getSourceNote(),
                        constraint.getStatus().name(),
                        constraint.getEffectiveFrom(),
                        constraint.getEffectiveTo()
                ))
                .toList();
        return new HealthConstraintSnapshot(1, Instant.now(clock), items);
    }

    private HealthConstraintSnapshot healthConstraintsFor(PlanVersion version) {
        if ((version.getStatus() == PlanVersionStatus.CONFIRMED || version.getStatus() == PlanVersionStatus.SUPERSEDED)
                && version.getHealthConstraintSnapshot() != null) {
            try {
                return readHealthConstraintSnapshot(version);
            } catch (JsonProcessingException ex) {
                throw new ApplicationException(ErrorCode.INTERNAL_ERROR, "健康约束历史快照解析失败",
                        HttpStatus.INTERNAL_SERVER_ERROR);
            }
        }
        return currentActiveHealthConstraintSnapshot();
    }

    private HealthConstraintSnapshot readHealthConstraintSnapshot(PlanVersion version) throws JsonProcessingException {
        JsonNode node = objectMapper.readTree(version.getHealthConstraintSnapshot());
        if (node.isObject() && node.has("schemaVersion")) {
            return objectMapper.treeToValue(node, HealthConstraintSnapshot.class);
        }
        if (node.isArray()) {
            List<HealthConstraintSnapshot.Item> items = new java.util.ArrayList<>();
            for (JsonNode item : node) {
                items.add(new HealthConstraintSnapshot.Item(
                        uuidOrNull(item.path("id").asText(null)),
                        item.path("constraintType").asText(null),
                        item.path("bodyRegion").asText(null),
                        item.path("severity").asText(null),
                        item.path("title").asText(null),
                        item.path("description").asText(null),
                        item.path("sourceType").asText(null),
                        item.path("sourceNote").asText(null),
                        item.path("status").asText(null),
                        localDateOrNull(item.path("effectiveFrom").asText(null)),
                        localDateOrNull(item.path("effectiveTo").asText(null))
                ));
            }
            return new HealthConstraintSnapshot(0, version.getConfirmedAt(), items);
        }
        throw new JsonProcessingException("unsupported health constraint snapshot") {
        };
    }

    private UUID uuidOrNull(String value) {
        return value == null ? null : UUID.fromString(value);
    }

    private LocalDate localDateOrNull(String value) {
        return value == null ? null : LocalDate.parse(value);
    }

    private List<GoalSummarySnapshot> goalSummariesFor(PlanVersion version, List<UUID> goalIds) {
        if (version.getStatus() == PlanVersionStatus.CONFIRMED || version.getStatus() == PlanVersionStatus.SUPERSEDED) {
            List<GoalSummarySnapshot> snapshots = planRepository.findGoalSnapshots(version.getId());
            if (snapshots.stream().allMatch(snapshot -> snapshot.title() != null)) {
                return snapshots;
            }
        }
        return currentGoalSummaries(goalIds);
    }

    private List<GoalSummarySnapshot> currentGoalSummaries(List<UUID> goalIds) {
        return distinct(goalIds).stream()
                .map(goalId -> goalRepository.findById(goalId)
                        .map(this::toGoalSummary)
                        .orElse(new GoalSummarySnapshot(goalId, null, null, null, null, null, null, null)))
                .toList();
    }

    private GoalSummarySnapshot toGoalSummary(Goal goal) {
        return new GoalSummarySnapshot(
                goal.getId(),
                goal.getTitle(),
                goal.getGoalType().name(),
                goal.getStatus().name(),
                goal.getTargetValue(),
                goal.getUnit().name(),
                goal.getBaselineValue(),
                goal.getTargetDate()
        );
    }

    private void collectGoalIssues(List<UUID> goalIds, List<String> issues) {
        distinct(goalIds).forEach(goalId -> {
            var goal = goalRepository.findById(goalId);
            if (goal.isEmpty()) {
                issues.add("关联目标不存在: " + goalId);
                return;
            }
            GoalStatus status = goal.get().getStatus();
            if (status != GoalStatus.ACTIVE && status != GoalStatus.PAUSED) {
                issues.add("只能关联进行中或暂停的目标: " + goal.get().getTitle());
            }
        });
    }

    private void validateGoalLinks(List<UUID> goalIds) {
        distinct(goalIds).forEach(this::validateGoalLink);
    }

    private void validateGoalLink(UUID goalId) {
        if (goalId == null) {
            return;
        }
        var goal = goalRepository.findById(goalId).orElseThrow(() -> new ApplicationException(
                ErrorCode.GOAL_NOT_FOUND, "关联目标不存在", HttpStatus.NOT_FOUND));
        if (goal.getStatus() != GoalStatus.ACTIVE && goal.getStatus() != GoalStatus.PAUSED) {
            throw new ApplicationException(ErrorCode.GOAL_INVALID_STATUS_TRANSITION,
                    "只能关联进行中或暂停的目标", HttpStatus.CONFLICT);
        }
    }

    private List<UUID> distinct(List<UUID> goalIds) {
        if (goalIds == null) {
            return List.of();
        }
        return goalIds.stream().filter(java.util.Objects::nonNull).distinct().toList();
    }

    private void assertUpdated(boolean updated) {
        if (!updated) {
            throw new ApplicationException(ErrorCode.DATA_CONFLICT, "数据已变化，请刷新后重试", HttpStatus.CONFLICT);
        }
    }

    private void assertDeleted(boolean deleted, ErrorCode errorCode, String message) {
        if (!deleted) {
            throw new ApplicationException(errorCode, message, HttpStatus.NOT_FOUND);
        }
    }

    private PlanVersion copyVersion(PlanVersion version) {
        return new PlanVersion(version.getId(), version.getPlanId(), version.getVersionNumber(),
                version.getPeriodRevision(), version.getStatus(), version.getStartDate(), version.getEndDate(),
                version.getTitle(), version.getSummary(), version.getCopiedFromVersionId(),
                version.getSupersedesVersionId(), version.getHealthConstraintSnapshot(), version.getRevision(),
                version.getConfirmedAt(), version.getSupersededAt(), version.getCancelledAt(),
                version.getCancelReason(), version.getCreatedAt(), version.getUpdatedAt());
    }

    private PlanDay copyDay(PlanDay day) {
        return new PlanDay(day.getId(), day.getVersionId(), day.getDayDate(), day.getTitle(), day.getNote(),
                day.getSortOrder(), day.getCreatedAt(), day.getUpdatedAt());
    }

    private PlanItem copyItem(PlanItem item) {
        return new PlanItem(item.getId(), item.getDayId(), item.getGoalId(), item.getItemType(), item.getTitle(),
                item.getDescription(), item.getPlannedSets(), item.getPlannedReps(),
                item.getPlannedDurationMinutes(), item.getPlannedDistanceMeters(), item.getPlannedRpe(),
                item.getSortOrder(), item.getCreatedAt(), item.getUpdatedAt());
    }

    private record CreatedResource<T>(T body, String resourceType, UUID resourceId, int responseStatus) {
    }

    public record CreatePlanCommand(String title, String summary) {
    }

    public record CreateDraftCommand(LocalDate startDate, String title, String summary, List<UUID> goalIds) {
    }

    public record UpdateVersionCommand(String title, String summary, List<UUID> goalIds, Integer expectedRevision) {
    }

    public record CopyVersionCommand(LocalDate startDate, String title, String summary,
                                     PlanVersionStatus expectedSourceStatus) {
    }

    public record ConfirmVersionCommand(Integer expectedRevision) {
    }

    public record CancelVersionCommand(String cancelReason, Integer expectedRevision) {
    }

    public record SaveDayCommand(LocalDate dayDate, String title, String note, Integer sortOrder, Integer expectedRevision) {
    }

    public record SaveItemCommand(UUID goalId, PlanItemType itemType, String title, String description,
                                  BigDecimal plannedSets, BigDecimal plannedReps,
                                  BigDecimal plannedDurationMinutes, BigDecimal plannedDistanceMeters,
                                  BigDecimal plannedRpe, Integer sortOrder, Integer expectedRevision) {
    }
}
