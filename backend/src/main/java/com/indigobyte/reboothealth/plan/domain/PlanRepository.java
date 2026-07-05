package com.indigobyte.reboothealth.plan.domain;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * 计划聚合仓储端口。
 *
 * <p>仓储显式区分插入和更新；需要事务锁的查询由应用服务在确认等关键流程中调用。</p>
 */
public interface PlanRepository {

    Optional<Plan> findCurrentPlan();

    Optional<Plan> findById(UUID planId);

    Optional<Plan> findByIdForUpdate(UUID planId);

    void insertPlan(Plan plan);

    boolean updatePlan(Plan plan);

    int nextVersionNumber(UUID planId);

    int nextPeriodRevision(UUID planId, LocalDate startDate);

    Optional<PlanVersion> findVersionById(UUID versionId);

    Optional<PlanVersion> findVersionByIdForUpdate(UUID versionId);

    Optional<PlanVersion> findConfirmedVersionForPeriodForUpdate(UUID planId, LocalDate startDate);

    Optional<PlanVersion> findCurrentConfirmedVersion(LocalDate currentDate);

    List<PlanVersion> findVersions(UUID planId, PlanVersionFilter filter);

    void insertVersion(PlanVersion version);

    boolean updateVersion(PlanVersion version);

    List<PlanDay> findDays(UUID versionId);

    Optional<PlanDay> findDayById(UUID dayId);

    void insertDay(PlanDay day);

    boolean updateDay(PlanDay day);

    boolean deleteDay(UUID dayId);

    List<PlanItem> findItemsByDayId(UUID dayId);

    Optional<PlanItem> findItemById(UUID itemId);

    void insertItem(PlanItem item);

    boolean updateItem(PlanItem item);

    boolean deleteItem(UUID itemId);

    List<PlanItem> deleteItemsByDayId(UUID dayId);

    List<UUID> findGoalIds(UUID versionId);

    void replaceGoalLinks(UUID versionId, List<UUID> goalIds, java.time.Instant now);

    void insertGoalLinks(UUID versionId, List<UUID> goalIds, java.time.Instant now);
}
