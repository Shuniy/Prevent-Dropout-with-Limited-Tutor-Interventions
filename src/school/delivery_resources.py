"""Independent exact reconstruction from events and preannounced mentor calendars.

No planner counters or claimed spending enter this auditor. It validates the
lifecycle, per-session charging and historical as well as future commitments.
"""
from collections import defaultdict
from decimal import Decimal

from .delivery_contracts import LedgerSnapshot, ResourceCell, WeeklyMentor
from .money import amount


def mentor_contracts(mentors, config):
    result = []
    for m in mentors:
        if m.current_student_ids or m.max_active_students < 1:
            raise ValueError('weekly mentors need an empty initial caseload and positive capacity')
        if m.cost_units_per_hour != 0:
            raise ValueError('weekly v1 charges per session; hourly prices are unsupported')
        if amount(m.cost_units_per_session) != amount(config.cost_per_session):
            raise ValueError('weekly mentor session price must match declared scenario price')
        calendar = []
        for week in range(1, config.horizon_weeks + 1):
            row = m.availability_at(week)
            if row is None:
                calendar.append((week, '0', 0))
            else:
                hours = amount(row.available_hours)
                if type(row.max_sessions) is not int or row.max_sessions < 0:
                    raise ValueError('weekly session capacity must be an integer')
                if row.max_sessions and hours <= 0:
                    raise ValueError('weekly calendars require explicit nonzero working hours')
                calendar.append((week, str(hours), row.max_sessions))
        result.append(WeeklyMentor(m.mentor_id, tuple(m.support_types),
            min(m.max_active_students, config.max_concurrent_students),
            str(amount(m.cost_units_per_session)), tuple(calendar)))
    if len({m.mentor_id for m in result}) != len(result):
        raise ValueError('duplicate mentor identity')
    return tuple(result)


def audit_delivery_events(config, mentors, events, *, profiles=None):
    """Rebuild every liability; reject duplicates, impossible schedules and refunds."""
    staff = {m.mentor_id: m for m in mentors}
    public_profiles = None if profiles is None else {p.student_id:p for p in profiles}
    if len(staff) != len(mentors):
        raise ValueError('duplicate mentor identity')
    programmes, sessions, identities = {}, {}, set()
    spent = Decimal(0)
    released = Decimal(0)
    admin = Decimal(0)
    admin_pending = set()
    delivered = defaultdict(int)
    missed = defaultdict(int)
    costs = defaultdict(lambda: Decimal(0))
    releases = defaultdict(lambda: Decimal(0))
    admin_costs = defaultdict(lambda: Decimal(0))
    last_week = 0

    def check_capacity():
        reserved = sum((v['price'] for v in sessions.values() if v['status'] == 'reserved'), Decimal(0))
        reserved += len(admin_pending) * amount(config.administrative_offer_cost)
        if spent + reserved > amount(config.budget):
            raise ValueError('event commitments exceed exact budget')
        usage, active = defaultdict(int), defaultdict(set)
        for session in sessions.values():
            if session['status'] != 'released':
                usage[(session['mentor'], session['week'])] += 1
        student_weeks = {}
        for pid, p in programmes.items():
            if p['status'] == 'refused':
                continue
            end = p.get('cancel_week', p['end'] + 1) - 1 if 'cancel_week' in p else p['end']
            for week in range(p['start'], end + 1):
                key = (p['student'], week)
                if key in student_weeks:
                    raise ValueError('student booked on overlapping programmes')
                student_weeks[key] = pid
                active[(p['mentor'], week)].add(p['student'])
        for mentor in mentors:
            for week, hours, slots in mentor.calendar:
                used = usage[(mentor.mentor_id, week)]
                if used > slots or used * amount(config.session_duration_hours) > amount(hours):
                    raise ValueError('event schedule exceeds mentor hours or slots')
                if len(active[(mentor.mentor_id, week)]) > mentor.max_concurrent_students:
                    raise ValueError('event schedule exceeds mentor concurrent caseload')
        return reserved, active

    for e in events:
        if e.event_id in identities or e.source_week < last_week or e.source_week > config.horizon_weeks:
            raise ValueError('duplicate event or invalid event ordering')
        identities.add(e.event_id)
        last_week = e.source_week
        if e.mentor_id not in staff:
            raise ValueError('event references unknown mentor')
        key = (e.mentor_id, e.scheduled_week or e.source_week)
        price = amount(staff[e.mentor_id].cost_per_session)
        if e.kind == 'support_offered':
            if e.programme_id in programmes or e.session_id is not None or 'tutoring' not in staff[e.mentor_id].support_types:
                raise ValueError('duplicate or malformed offer')
            if public_profiles is not None and (e.student_id not in public_profiles
                    or public_profiles[e.student_id].support_type != 'tutoring'):
                raise ValueError('unknown or incompatible student in event schedule')
            schedule = config.schedule(e.source_week)
            if schedule[-1] > config.horizon_weeks:
                raise ValueError('programme exceeds horizon')
            programmes[e.programme_id] = dict(student=e.student_id, mentor=e.mentor_id,
                start=e.source_week, end=schedule[-1], status='offered', admin=False, outcome=False)
            admin_pending.add(e.programme_id)
        else:
            p = programmes.get(e.programme_id)
            if p is None or p['student'] != e.student_id or p['mentor'] != e.mentor_id:
                raise ValueError('event programme identity mismatch')
            if e.kind == 'session_reserved':
                if (p['status'] != 'offered' or e.source_week != p['start'] or e.session_id in sessions
                        or e.scheduled_week not in config.schedule(p['start'])
                        or any(s['pid'] == e.programme_id and s['week'] == e.scheduled_week
                               for s in sessions.values()) or amount(e.money) != price):
                    raise ValueError('invalid or duplicated session reservation')
                sessions[e.session_id] = dict(pid=e.programme_id, mentor=e.mentor_id,
                    week=e.scheduled_week, status='reserved', scheduled=False, price=price)
            elif e.kind == 'administration_charged':
                if (e.programme_id not in admin_pending or e.source_week != p['start']
                        or amount(e.money) != amount(config.administrative_offer_cost)):
                    raise ValueError('duplicate or incorrect administrative charge')
                admin_pending.remove(e.programme_id)
                p['admin'] = True
                spent += amount(e.money)
                admin += amount(e.money)
                admin_costs[(e.mentor_id, e.source_week)] += amount(e.money)
                costs[(e.mentor_id, e.source_week)] += amount(e.money)
            elif e.kind in ('offer_accepted', 'offer_refused'):
                booked = [s for s in sessions.values() if s['pid'] == e.programme_id]
                if (p['status'] != 'offered' or len(booked) != config.sessions_required
                        or not p['admin'] or e.source_week != p['start']):
                    raise ValueError('uptake requires complete reservation and administration')
                p['status'] = 'accepted' if e.kind == 'offer_accepted' else 'refused'
            elif e.kind == 'session_scheduled':
                s = sessions.get(e.session_id)
                if (s is None or s['pid'] != e.programme_id or s['week'] != e.scheduled_week
                        or s['scheduled'] or p['status'] != 'accepted'):
                    raise ValueError('schedule requires a unique accepted reservation')
                s['scheduled'] = True
            elif e.kind == 'programme_active':
                if (p['status'] != 'accepted' or e.source_week != p['start']
                        or not all(s['scheduled'] for s in sessions.values() if s['pid'] == e.programme_id)):
                    raise ValueError('invalid active programme transition')
                p['status'] = 'active'
            elif e.kind in ('session_delivered', 'session_missed', 'reservation_released'):
                s = sessions.get(e.session_id)
                if (s is None or s['pid'] != e.programme_id or s['status'] != 'reserved'
                        or s['week'] != e.scheduled_week):
                    raise ValueError('service cannot be double charged or released')
                if e.kind == 'reservation_released':
                    if (p['status'] not in ('refused', 'cancelled') or s['week'] < e.source_week
                            or amount(e.money) != price):
                        raise ValueError('can release only unused current/future liabilities')
                    s['status'] = 'released'
                    released += price
                    releases[key] += price
                else:
                    expected = price if e.kind == 'session_delivered' else amount(config.missed_session_cost)
                    if (p['status'] != 'active' or not s['scheduled'] or s['week'] != e.source_week
                            or amount(e.money) != expected):
                        raise ValueError('delivery/miss requires a current active scheduled session')
                    s['status'] = 'delivered' if e.kind == 'session_delivered' else 'missed'
                    (delivered if e.kind == 'session_delivered' else missed)[key] += 1
                    spent += expected
                    costs[key] += expected
                    released += price - expected
                    releases[key] += price - expected
            elif e.kind == 'programme_cancelled':
                if p['status'] not in ('active', 'accepted') or e.source_week > p['end']:
                    raise ValueError('invalid cancellation transition')
                p.update(status='cancelled', cancel_week=e.source_week +
                         int(e.reason == 'authorized_withdrawal_registry'))
            elif e.kind in ('programme_completed', 'programme_incomplete'):
                booked = [s for s in sessions.values() if s['pid'] == e.programme_id]
                completed = all(s['status'] == 'delivered' for s in booked)
                if (p['status'] != 'active' or e.source_week != p['end']
                        or any(s['status'] == 'reserved' for s in booked)
                        or completed != (e.kind == 'programme_completed')):
                    raise ValueError('completion requires all configured sessions actually delivered')
                p['status'] = 'completed' if completed else 'incomplete'
            elif e.kind == 'programme_outcome_observed':
                if p['status'] not in ('completed', 'incomplete', 'cancelled') or p['outcome']:
                    raise ValueError('invalid or repeated outcome observation')
                p['outcome'] = True
        check_capacity()
    if admin_pending or any(p['status'] == 'offered' for p in programmes.values()):
        raise ValueError('unresolved temporary offer liabilities')
    for pid, p in programmes.items():
        booked = [s for s in sessions.values() if s['pid'] == pid]
        if len(booked) != config.sessions_required:
            raise ValueError('missing session reservations')
        if p['status'] in ('refused', 'cancelled', 'completed', 'incomplete') and any(
                s['status'] == 'reserved' for s in booked):
            raise ValueError('terminal programme retains unresolved service liabilities')
    reserved, active = check_capacity()
    cells = []
    for mentor in mentors:
        for week, hours, slots in mentor.calendar:
            key = (mentor.mentor_id, week)
            pending = [s for s in sessions.values() if s['mentor'] == mentor.mentor_id
                       and s['week'] == week and s['status'] == 'reserved']
            used_hours = (len(pending) + delivered[key] + missed[key]) * amount(config.session_duration_hours)
            cells.append(ResourceCell(mentor.mentor_id, week, hours,
                str(len(pending) * amount(config.session_duration_hours)),
                str(delivered[key] * amount(config.session_duration_hours)), slots, len(pending),
                delivered[key], missed[key], tuple(sorted(active[key])), mentor.max_concurrent_students,
                str(sum((s['price'] for s in pending), Decimal(0))), str(costs[key]),
                str(releases[key]), str(admin_costs[key]), str(amount(hours) - used_hours)))
    return LedgerSnapshot(str(amount(config.budget)), str(reserved), str(spent),
        str(amount(config.budget) - spent - reserved), str(released), str(admin), tuple(cells))


def offer_cost(config, mentor):
    return amount(config.administrative_offer_cost) + config.sessions_required * amount(mentor.cost_per_session)


def validate_offers(state, action, config, *, projected=False):
    """Exact public schedule validation shared by all policies and the environment."""
    from .delivery_contracts import DeliveryAction, SupportOffer
    if not isinstance(action, DeliveryAction):
        raise ValueError('weekly step requires DeliveryAction, not monthly assignments')
    state.validate_estimates()
    students = {s.student_id: s for s in state.students}
    mentors = {m.mentor_id: m for m in state.mentors}
    cells = {(c.mentor_id, c.week): c for c in state.ledger.cells}
    slots, active = defaultdict(int), defaultdict(int)
    cost, seen = Decimal(0), set()
    if len(set(action.cancel_programme_ids)) != len(action.cancel_programme_ids):
        raise ValueError('duplicate cancellation')
    programmes = {p.programme_id: p for s in state.students for p in s.programmes}
    for pid in action.cancel_programme_ids:
        if pid not in programmes or programmes[pid].status not in ('SCHEDULED', 'ACTIVE'):
            raise ValueError('only a known continuing programme can be cancelled')
    # Cancellation capacity is intentionally released AFTER this decision. New
    # offers never borrow a speculative release from the same action.
    for offer in action.offers:
        if not isinstance(offer, SupportOffer):
            raise ValueError('invalid support offer record')
        student, mentor = students.get(offer.student_id), mentors.get(offer.mentor_id)
        if (student is None or mentor is None or not student.eligible or offer.student_id in seen
                or student.profile.support_type != 'tutoring' or 'tutoring' not in mentor.support_types):
            raise ValueError('unknown, ineligible, duplicate or incompatible offer')
        if type(offer.start_week) is not int or (offer.start_week != state.week and not projected):
            raise ValueError('executable offers must start this week')
        if offer.start_week < state.week or config.schedule(offer.start_week)[-1] > config.horizon_weeks:
            raise ValueError('offer extends beyond the weekly horizon')
        for week in config.schedule(offer.start_week):
            key = (mentor.mentor_id, week)
            cell = cells[key]
            slots[key] += 1
            occupied = slots[key] + cell.reserved_slots + cell.delivered_sessions + cell.wasted_slots
            if (occupied > cell.available_slots or
                    occupied * amount(config.session_duration_hours) > amount(cell.available_hours)):
                raise ValueError('future mentor hours or appointment capacity exceeded')
        for week in range(offer.start_week, config.schedule(offer.start_week)[-1] + 1):
            key = (mentor.mentor_id, week)
            active[key] += 1
            if active[key] + len(cells[key].active_students) > mentor.max_concurrent_students:
                raise ValueError('future concurrent caseload exceeded')
        cost += offer_cost(config, mentor)
        seen.add(offer.student_id)
    if cost > amount(state.ledger.spendable):
        raise ValueError('new offers exceed spendable budget after prior obligations')


def feasible_offers(state, config, *, end_week=None):
    from .delivery_contracts import DeliveryAction, SupportOffer
    end = state.week if end_week is None else end_week
    result = []
    for week in range(state.week, end + 1):
        for s in sorted(state.students, key=lambda s: s.student_id):
            for m in sorted(state.mentors, key=lambda m: m.mentor_id):
                offer = SupportOffer(s.student_id, m.mentor_id, week)
                try:
                    validate_offers(state, DeliveryAction((offer,)), config, projected=True)
                except ValueError:
                    continue
                result.append(offer)
    return tuple(result)
