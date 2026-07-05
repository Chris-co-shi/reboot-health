package com.indigobyte.reboothealth.plan.adapter.persistence;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.indigobyte.reboothealth.plan.domain.Plan;
import com.indigobyte.reboothealth.plan.domain.PlanDay;
import com.indigobyte.reboothealth.plan.domain.PlanItem;
import com.indigobyte.reboothealth.plan.domain.PlanRepository;
import com.indigobyte.reboothealth.plan.domain.PlanVersion;
import com.indigobyte.reboothealth.plan.domain.PlanVersionFilter;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

/**
 * PlanRepository 的 MyBatis-Plus 实现。
 *
 * <p>Repository 只负责持久化和必要的事务锁查询，版本状态机由领域聚合和应用服务控制。</p>
 */
@Repository
@RequiredArgsConstructor
public class MyBatisPlanRepository implements PlanRepository {

    private final PlanMapper planMapper;
    private final PlanVersionMapper versionMapper;
    private final PlanDayMapper dayMapper;
    private final PlanItemMapper itemMapper;
    private final PlanVersionGoalMapper goalMapper;

    @Override
    public Optional<Plan> findCurrentPlan() {
        return Optional.ofNullable(PlanPersistenceConverter.toPlan(planMapper.selectCurrent()));
    }

    @Override
    public Optional<Plan> findById(UUID planId) {
        return Optional.ofNullable(PlanPersistenceConverter.toPlan(planMapper.selectById(planId)));
    }

    @Override
    public Optional<Plan> findByIdForUpdate(UUID planId) {
        return Optional.ofNullable(PlanPersistenceConverter.toPlan(planMapper.selectByIdForUpdate(planId)));
    }

    @Override
    public void insertPlan(Plan plan) {
        planMapper.insert(PlanPersistenceConverter.toDataObject(plan));
    }

    @Override
    public boolean updatePlan(Plan plan) {
        return planMapper.updateById(PlanPersistenceConverter.toDataObject(plan)) == 1;
    }

    @Override
    public int nextVersionNumber(UUID planId) {
        return versionMapper.selectNextVersionNumber(planId);
    }

    @Override
    public int nextPeriodRevision(UUID planId, LocalDate startDate) {
        return versionMapper.selectNextPeriodRevision(planId, startDate);
    }

    @Override
    public Optional<PlanVersion> findVersionById(UUID versionId) {
        return Optional.ofNullable(PlanPersistenceConverter.toVersion(versionMapper.selectVersionById(versionId)));
    }

    @Override
    public Optional<PlanVersion> findVersionByIdForUpdate(UUID versionId) {
        return Optional.ofNullable(PlanPersistenceConverter.toVersion(versionMapper.selectByIdForUpdate(versionId)));
    }

    @Override
    public Optional<PlanVersion> findConfirmedVersionForPeriodForUpdate(UUID planId, LocalDate startDate) {
        return Optional.ofNullable(PlanPersistenceConverter.toVersion(
                versionMapper.selectConfirmedForPeriodForUpdate(planId, startDate)
        ));
    }

    @Override
    public Optional<PlanVersion> findCurrentConfirmedVersion(LocalDate currentDate) {
        return Optional.ofNullable(PlanPersistenceConverter.toVersion(versionMapper.selectCurrentConfirmed(currentDate)));
    }

    @Override
    public List<PlanVersion> findVersions(UUID planId, PlanVersionFilter filter) {
        String status = filter.status() == null ? null : filter.status().name();
        List<PlanVersionDataObject> versions = status == null
                ? versionMapper.selectVersions(planId)
                : versionMapper.selectVersionsByStatus(planId, status);
        return versions.stream()
                .map(PlanPersistenceConverter::toVersion)
                .toList();
    }

    @Override
    public void insertVersion(PlanVersion version) {
        versionMapper.insertVersion(PlanPersistenceConverter.toDataObject(version));
    }

    @Override
    public boolean updateVersion(PlanVersion version) {
        return versionMapper.updateVersion(PlanPersistenceConverter.toDataObject(version)) == 1;
    }

    @Override
    public List<PlanDay> findDays(UUID versionId) {
        LambdaQueryWrapper<PlanDayDataObject> query = new LambdaQueryWrapper<>();
        query.eq(PlanDayDataObject::getVersionId, versionId)
                .orderByAsc(PlanDayDataObject::getDayDate);
        return dayMapper.selectList(query).stream()
                .map(PlanPersistenceConverter::toDay)
                .toList();
    }

    @Override
    public Optional<PlanDay> findDayById(UUID dayId) {
        return Optional.ofNullable(PlanPersistenceConverter.toDay(dayMapper.selectById(dayId)));
    }

    @Override
    public void insertDay(PlanDay day) {
        dayMapper.insert(PlanPersistenceConverter.toDataObject(day));
    }

    @Override
    public boolean updateDay(PlanDay day) {
        return dayMapper.updateById(PlanPersistenceConverter.toDataObject(day)) == 1;
    }

    @Override
    public boolean deleteDay(UUID dayId) {
        return dayMapper.deleteById(dayId) == 1;
    }

    @Override
    public List<PlanItem> findItemsByDayId(UUID dayId) {
        LambdaQueryWrapper<PlanItemDataObject> query = new LambdaQueryWrapper<>();
        query.eq(PlanItemDataObject::getDayId, dayId)
                .orderByAsc(PlanItemDataObject::getSortOrder);
        return itemMapper.selectList(query).stream()
                .map(PlanPersistenceConverter::toItem)
                .toList();
    }

    @Override
    public Optional<PlanItem> findItemById(UUID itemId) {
        return Optional.ofNullable(PlanPersistenceConverter.toItem(itemMapper.selectById(itemId)));
    }

    @Override
    public void insertItem(PlanItem item) {
        itemMapper.insert(PlanPersistenceConverter.toDataObject(item));
    }

    @Override
    public boolean updateItem(PlanItem item) {
        return itemMapper.updateById(PlanPersistenceConverter.toDataObject(item)) == 1;
    }

    @Override
    public boolean deleteItem(UUID itemId) {
        return itemMapper.deleteById(itemId) == 1;
    }

    @Override
    public List<PlanItem> deleteItemsByDayId(UUID dayId) {
        List<PlanItem> items = findItemsByDayId(dayId);
        LambdaQueryWrapper<PlanItemDataObject> query = new LambdaQueryWrapper<>();
        query.eq(PlanItemDataObject::getDayId, dayId);
        itemMapper.delete(query);
        return items;
    }

    @Override
    public List<UUID> findGoalIds(UUID versionId) {
        return goalMapper.selectGoalIds(versionId);
    }

    @Override
    public void replaceGoalLinks(UUID versionId, List<UUID> goalIds, Instant now) {
        goalMapper.deleteByVersionId(versionId);
        insertGoalLinks(versionId, goalIds, now);
    }

    @Override
    public void insertGoalLinks(UUID versionId, List<UUID> goalIds, Instant now) {
        goalIds.stream().distinct().forEach(goalId -> goalMapper.insertLink(versionId, goalId, now));
    }
}
