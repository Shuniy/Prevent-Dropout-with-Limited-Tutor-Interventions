#!/usr/bin/env python3
"""Create fictional linked student-mentor intervention-series transcripts.
All content is synthetic; no intervention response or dropout outcome is inferred.
"""
from __future__ import annotations

if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.utils.constants import (
    HISTORY_OUT as OUT,
    HISTORY_ZIP as ZIP,
    HISTORY_SEED as SEED,
    HISTORY_CONFIG as CONFIG,
    HISTORY_SUPPORT_ORDER as SUPPORT_ORDER,
    HISTORY_FOLLOWUP as FOLLOWUP,
    HISTORY_INTRO as INTRO,
    HISTORY_FOLLOW_OPEN as FOLLOW_OPEN,
    HISTORY_PROMPTS as PROMPTS,
    HISTORY_ENDINGS as ENDINGS,
)
import csv, datetime as dt, hashlib, io, json, random, re, shutil, zipfile
from collections import Counter, defaultdict
from pathlib import Path

R = random.Random(SEED)

# Issue rows: (short concern, student account, example, secondary constraint, what student wants)
# Activity rows: (mentor's in-session exercise/action, student's reaction, mentor's feedback, next agreed action)

assert len(SUPPORT_ORDER) == 13

# Distinct follow-up outcomes: status applies to the previous agreed between-session action.


# The extra prompts are designed as additional dialogue rather than generic filler.

# Administrative stopping patterns appear in the manifest ONLY, not retroactively in a session.


def slug(s):
    return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')


def sections_for_session(cfg, issue, task, stage, prior_plan, prior_status, rng, is_last):
    focus, account, concrete, constraint, goal = issue
    activity, reaction, feedback, agreed = task
    context = {'focus':focus, 'constraint_lower':constraint[0].lower()+constraint[1:]}
    groups=[]
    openings=[]
    if stage == 1:
        openings += [rng.choice(INTRO)]
        openings += [
          ('You are in control of which details you share. Shall we focus on the school issue today?', 'Yes. I would rather not get into everything at home.'),
          ('What support would feel useful rather than judgmental?', 'Something practical that could help me keep up with school.'),
        ]
        history = [
          ('What is the main problem you wanted to talk about?', account),
          ('Could you describe something that actually happened?', concrete),
          ('What part of the situation is still uncertain?', constraint),
          ('What is your main hope for these meetings?', goal+'.'),
          ('Has anyone checked a school record or support eligibility yet?', 'Not that I know of. I do not want to say it has been confirmed.'),
        ]
    else:
        openings += [rng.choice(FOLLOW_OPEN)]
        openings += [
          ('Is it all right to revisit the plan from the previous appointment?', 'Yes, that is what I wanted to discuss.'),
          ('Has the main concern changed since we last spoke?', rng.choice(['Not completely. It is still affecting some school days.','A little, but it is not consistently better.','It has been uneven; one day went better and another did not.'])),
        ]
        fp = FOLLOWUP[prior_status]
        history = [
          (f'Last time we agreed that you would {prior_plan}. Were you able to do that?', fp[0]),
          (fp[1],fp[2]),
          ('What does that tell us, without assuming the issue is fully solved?', rng.choice(['The difficulty is still present on some days.','There might be a useful small step, but we need more information.','I need a plan that works even when things are difficult.'])),
          ('Did anything happen between sessions that we should check?', rng.choice(['There was one difficult school day, but I did not record the date.','I had a better lesson, but I cannot say it changed every day.','I heard an option might exist, but I have not confirmed the details.'])),
          ('Do you want to correct anything from our earlier summary?', rng.choice(['Please keep the issue as something I reported, not a confirmed fact about every day.','The problem is worse some days than others.','I want the earlier plan recorded as an attempt, not a guaranteed success.'])),
        ]
    groups.append(openings)
    groups.append(history)
    exploration = [
       ('When you think about this school difficulty, what has been hardest to manage?', 'The uncertainty makes it hard to plan ahead.'),
       ('Is there any part that is manageable at the moment?', rng.choice(['Some days it is easier when I know the plan early.','It is easier when I get a clear instruction rather than guessing.','I can usually manage one small task at a time.'])),
       ('Could other school or home circumstances also be involved?', 'Yes. I do not think there is only one reason.'),
       ('What should we avoid assuming from this account?', 'That I am unwilling to come to school or that everything is already fixed.'),
    ]
    groups.append(exploration)
    practical = [
       (f'For today’s {cfg["title"].lower()} work, could we {activity}?', 'Yes, that sounds like a reasonable thing to try here.'),
       ('Take your time. What do you notice as you try it?', reaction),
       ('Let me reflect what we saw in this meeting.', feedback),
       ('Which part of that exercise was useful?', rng.choice(['Having an example made the first step clearer.','Seeing the options side by side helped.','Writing down a small step was less confusing than a long plan.'])),
       ('What part remains difficult after that activity?', rng.choice(['I am unsure whether I can repeat it alone.','The school process still has to be confirmed.','The wider barrier has not disappeared.'])),
       ('Do we need to change the pace or the kind of help?', rng.choice(['Slowing down would help.','I would prefer a school-based next step.','We should keep it short and check how it goes.'])),
       ('Can we distinguish what happened in this room from what might happen next week?', 'We did the activity together today; what happens after today still needs checking.'),
    ]
    groups.append(practical)
    safeguards = [
       ('Before we arrange another step, is there a practical constraint we should respect?', constraint),
       ('Should we involve someone else or check a school policy before promising support?', 'We should check the right contact first. I would like to know what will be shared.'),
       ('Is there anything in the notes that would sound more certain than it really is?', 'Please do not write that the whole problem is resolved.'),
    ]
    groups.append(safeguards)
    planning = [
       (f'A possible between-session step is to {agreed}. Does that feel realistic?', rng.choice(['I can try that, provided it fits my schedule.','Yes, but I may need help if I get stuck.','I can try a smaller version first.'])),
       ('What could stop that step from happening?', rng.choice(['The school office might not be available.','I could run out of time after school.','I might need a teacher to explain the procedure.'])),
       ('If it cannot happen, what would you tell me at the next meeting?', 'I would say it was not done and explain what got in the way.'),
       ('How will we know what actually happened?', rng.choice(['I could note the date and what I tried.','I could bring the worksheet or written reply if I receive one.','We can ask for a record rather than guessing.'])),
    ]
    groups.append(planning)
    closing = [
       ('What would you like me to remember from today?', rng.choice(['The problem is real for me, but the details are not all confirmed.','I want a workable next step, not another warning.','I appreciate being able to say when a plan is too difficult.'])),
       ('I will record this as a completed mentoring meeting, not proof of a successful outside referral. Is that accurate?', 'Yes. We talked and practiced, but extra help has not automatically been delivered.'),
       ('If your concern becomes urgent before another appointment, can you approach the designated school adult?', 'Yes. I would not have to wait for the next mentoring session.'),
       ('Thank you for being open today. Is there anything I should correct before we finish?', rng.choice(['No, that sounds fair.','Just note that I was not sure about the dates.','Please keep the private family details out of the summary.'])),
    ]
    if stage == 5:
        closing[-1] = ('This is our fifth planned session. Does that mean every concern is solved?', 'No. We have a continuing plan, and I may still need school support later.')
    groups.append(closing)
    return groups,context


def render_one(student_code, cfg_key, issue, tasks, session_num, total, date, start_minutes, duration, prev_plan, progress_status, rng):
    cfg=CONFIG[cfg_key]
    task=tasks[session_num-1]
    # When an earlier planned task was incomplete, do not invent successful use of its output.
    if session_num>1 and progress_status in ('partial','blocked','uncertain'):
        activity,reaction,feedback,agreed=task
        if progress_status=='partial':
            reaction='I can work through part of this in our meeting, but I still lack some of the real-world information.'
        else:
            reaction='I can practise that here using an example, but I have not verified what happens outside this appointment.'
        feedback='Today we practised the step together; that does not establish the earlier task was completed.'
        task=(activity,reaction,feedback,agreed)
    groups,ctx=sections_for_session(cfg,issue,task,session_num,prev_plan,progress_status,rng,session_num==total)
    mandatory=sum(len(g) for g in groups)
    assert mandatory==30, mandatory
    extras_needed=duration-mandatory
    assert 0<=extras_needed<=len(PROMPTS)
    additions=rng.sample(PROMPTS, extras_needed)
    # Mix optional discussions before the conclusion, while preserving core chronological structure.
    counts=[0]*6
    for p in additions:
        counts[rng.choices([0,1,2,3,4,5], weights=[1,3,3,4,2,2])[0]]+=1
    all_pairs=[]; k=0
    for gi,g in enumerate(groups):
        all_pairs+=g
        if gi<6:
            for _ in range(counts[gi]):
                q,a=additions[k]; k+=1
                all_pairs.append((q.format(**ctx),a.format(**ctx)))
    assert len(all_pairs)==duration and k==len(additions)
    start=dt.datetime.combine(date,dt.time())+dt.timedelta(minutes=start_minutes)
    end=start+dt.timedelta(minutes=duration)
    label='Initial session' if session_num==1 else ('Fifth scheduled session' if session_num==5 else 'Follow-up session')
    # Statement of reported progress is never converted to verified outcome.
    lines=['# Student','',f'**Intervention type:** {cfg["title"]}',f'**Intervention student:** {student_code}',
           f'**Session number:** {session_num}',f'**Stage:** {label}',
           f'**Date:** {date.isoformat()}',f'**Start:** {start:%H:%M}',f'**End:** {end:%H:%M}',
           f'**Duration:** {duration} minutes',
           '**Provenance:** Fictional longitudinal case; reported claims and intervention events are simulated.',
           '', '## Minute-by-minute conversation','']
    for n,(q,a) in enumerate(all_pairs):
        stamp=start+dt.timedelta(minutes=n)
        lines.extend([f'### {stamp:%H:%M}','',f'**Mentor:** {q}','',f'**Student:** {a}',''])
    lines+=['## Session record', '',
            f'- **Main concern (student-reported):** {issue[0]}.',
            f'- **Intervention activity completed in this appointment:** {task[0]}.',
            '- **Attendance at this appointment:** Attended.',
            '- **External support approval/delivery:** Not established by this dialogue; do not infer an award or service from discussion.',
            f'- **Between-session action agreed:** {task[3]}.',
            '- **Dropout/retention outcome:** Not observed or determined in this conversation.',
            '- **Record standard:** Student statements remain reported unless independently verified.',
           ]
    if session_num>1:
        lines.insert(lines.index('## Session record')+2, f'- **Prior action report:** {progress_status} (student-reported; not independently checked).')
    txt='\n'.join(lines)+'\n'
    return txt, end.strftime('%H:%M'), task[3]


def main():
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    profiles=[]; sessions=[]
    statuses_by_support=Counter()
    for si,key in enumerate(SUPPORT_ORDER,1):
        cfg=CONFIG[key]; folder=OUT / f'{si:02d}_{key}'
        folder.mkdir()
        # Exactly two student histories each of length 1, 2, 3, 4, 5.
        lengths=[1,1,2,2,3,3,4,4,5,5]
        R.shuffle(lengths)
        for j in range(1,11):
            sid=f'{si:02d}-{j:03d}'
            n_sessions=lengths[j-1]
            student_dir=folder / f'intervention_student_{j:03d}'
            student_dir.mkdir()
            # Five different case starts repeated twice for diversity; activity varies by session.
            issue=cfg['issues'][(j-1+si)%5]
            plans=cfg['activities']
            start_date=dt.date(2026,9,7)+dt.timedelta(days=R.randint(0,33))
            date=start_date
            first_date=str(start_date)
            last_date=None
            prev_plan=None
            status=None
            steps=[]
            for t in range(1,n_sessions+1):
                if t>1:
                    date += dt.timedelta(days=R.choice([7,7,8,13,14,15]))
                    # Prefer some stalls and missed actions over monotonic improvement.
                    status=R.choices(list(FOLLOWUP), weights=[38,34,21,7])[0]
                duration=R.randint(30,60)
                start_m=R.randint(9*60,15*60+10)
                start_m=5*round(start_m/5)
                txt,end_time,next_action=render_one(sid,key,issue,plans,t,n_sessions,date,start_m,duration,prev_plan,status,R)
                prev_plan=next_action
                name=f'session_{t:02d}_{"initial" if t==1 else "followup"}.md'
                path=student_dir/name
                path.write_text(txt,encoding='utf8')
                last_date=str(date)
                digest=hashlib.sha256(txt.encode()).hexdigest()
                sessions.append(dict(student_id=sid,intervention_type=key,student_folder=str(student_dir.relative_to(OUT)),
                                     session_number=t,session_id=f'{sid}-S{t:02d}',attended='yes',
                                     date=str(date),duration_minutes=duration,start_time=f'{start_m//60:02d}:{start_m%60:02d}',end_time=end_time,
                                     stage='initial' if t==1 else ('fifth_scheduled' if t==5 else 'followup'),
                                     concern=issue[0],prior_action_progress='not_applicable' if t==1 else status,
                                     between_session_action=next_action,sha256=digest,relative_path=str(path.relative_to(OUT))))
                steps.append(str(t))
            if n_sessions==5:
                disposition='five_appointments_attended; support needs may remain'
            else:
                # Only attendance history is stated; later appointments have no transcript.
                disposition=R.choice(ENDINGS)
            profiles.append(dict(student_id=sid,intervention_type=key,intervention_name=cfg['title'],
                                 focus_concern=issue[0],total_sessions_attended=n_sessions,
                                 first_session_date=first_date,last_session_date=last_date,
                                 series_end_status=disposition,
                                 intervention_path=str(student_dir.relative_to(OUT)),
                                 notes='Only attended sessions have files; no later dropout outcome asserted.'))
            statuses_by_support[(key,n_sessions)]+=1
    def write_csv(filename,rows,fields=None):
        with (OUT/filename).open('w',encoding='utf8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
    write_csv('student_profiles.csv',profiles)
    write_csv('session_manifest.csv',sessions)
    summary=[]
    for s in SUPPORT_ORDER:
        group=[p for p in profiles if p['intervention_type']==s]
        counts=Counter(p['total_sessions_attended'] for p in group)
        summary.append(dict(intervention_type=s,students=len(group),sessions=sum(p['total_sessions_attended'] for p in group),
                            students_with_1=counts[1],students_with_2=counts[2],students_with_3=counts[3],
                            students_with_4=counts[4],students_with_5=counts[5]))
    write_csv('intervention_summary.csv',summary)
    readme=f'''# Student–Mentor Longitudinal Intervention Histories

**Fully synthetic** study material; generated reproducibly with seed `{SEED}`.

## Contents

- **13** original intervention/support types.
- **130** fictional student histories (**10** per support type).
- **390** attended mentoring sessions (Markdown files), one file for each attended session.
- Each intervention student folder has **1–5** files. Exactly two students per type have each attendance count 1, 2, 3, 4 and 5.
- Every conversation is **30–60 minutes**, with a minute-by-minute timestamp and a Mentor/Student exchange at each minute.
- The top heading of every transcript is exactly `# Student`; no student names are used.
- The follow-up session explicitly references the preceding appointment's *exact agreed action*, with a report that it was tried, partly tried, not tried or uncertain. Follow-up activities build on earlier planning.
- A session file indicates **attended**, not simply scheduled. Missing/discontinued sessions have no Markdown file.

## Folder example

```text
02_tutoring/
  intervention_student_001/
    session_01_initial.md
    session_02_followup.md
  intervention_student_002/
    session_01_initial.md
    session_02_followup.md
    session_03_followup.md
    session_04_followup.md
    session_05_followup.md
```

The exact IDs and lengths vary; see `student_profiles.csv` rather than assuming the example lengths apply.

## Files

- `student_profiles.csv`: one row per student history, intervention type, attended count, session dates and retrospective series-end metadata.
- `session_manifest.csv`: one row per attended session, dates, duration, concern, linked prior-action status, proposed next step and relative path, plus SHA-256.
- `intervention_summary.csv`: counts by intervention type and number of attended sessions.
- `validation_report.json`: automated checks and exact counts.
- `generate_intervention_sequences.py`: generator, included for reproducibility.

## Research validity and responsible use

The dialogues, school activities and reported changes are **fictional and template-generated**. They are *not* records of real children, real mentors or measured treatment effects; even a completed five-session block does not establish that a support barrier was resolved or that dropout was prevented. Every transcript distinguishes in-session mentoring activity from unverified external support referrals. Attendance at a mentoring appointment is separate from overall school attendance. A student history ending after one session means **only one attendance is recorded**; it must not automatically be interpreted as school dropout or refusal. `series_end_status` is synthetic administrative metadata recorded separately from what was known at the time of each meeting.

This collection is useful for early *longitudinal continuity*, *information extraction*, *negation / uncertainty*, and *provenance* testing. However, it has intentionally repeated generator language, and category tags/CSV metadata are known labels: **do not give these indexes to an extraction model at evaluation time**. The same student history must never be split between training and testing. For robust scientific claims, independently author or review a held-out test set and validate the dialogue style against practitioner advice. Synthetic session progress must not be used as calibrated causal intervention effects.
'''
    (OUT/'README.md').write_text(readme,encoding='utf8')
    # Validation: coverage, correct progression and minute-level times.
    per_id=defaultdict(list)
    for s in sessions: per_id[s['student_id']].append(s)
    bad=[]; durations=[]; all_minutes=0
    for p in profiles:
        sid=p['student_id']; series=per_id[sid]
        if len(series)!=p['total_sessions_attended']: bad.append(f'{sid}:count')
        if [x['session_number'] for x in series]!=list(range(1,len(series)+1)):bad.append(f'{sid}:sequence')
        for ii,s in enumerate(series):
            text=(OUT/s['relative_path']).read_text(encoding='utf8')
            stamp=re.findall(r'^### (\d{2}:\d{2})$',text,re.M)
            if len(stamp)!=s['duration_minutes']:bad.append(s['session_id']+':timestamps')
            st=dt.datetime.strptime(s['start_time'],'%H:%M')
            expected=[(st+dt.timedelta(minutes=k)).strftime('%H:%M') for k in range(s['duration_minutes'])]
            if stamp!=expected:bad.append(s['session_id']+':time_sequence')
            if text.count('**Mentor:**')!=len(stamp) or text.count('**Student:**')!=len(stamp):bad.append(s['session_id']+':speakers')
            if not text.startswith('# Student\n'):bad.append(s['session_id']+':title')
            if ii>0 and series[ii-1]['between_session_action'] not in text:bad.append(s['session_id']+':previous_action_not_referenced')
            if not 30<=s['duration_minutes']<=60:bad.append(s['session_id']+':length')
            if hashlib.sha256(text.encode()).hexdigest()!=s['sha256']:bad.append(s['session_id']+':hash')
            durations.append(s['duration_minutes']);all_minutes+=s['duration_minutes']
    if len(profiles)!=130 or len(sessions)!=390:bad.append('overall_counts')
    if len(SUPPORT_ORDER)!=13:bad.append('support_types')
    if any(statuses_by_support[(k,i)]!=2 for k in SUPPORT_ORDER for i in range(1,6)):bad.append('coverage')
    report=dict(seed=SEED,intervention_types=len(SUPPORT_ORDER),students=len(profiles),
                attended_session_files=len(sessions),total_timestamped_minutes=all_minutes,
                min_minutes=min(durations),max_minutes=max(durations),average_minutes=round(sum(durations)/len(durations),2),
                student_histories_by_length={str(i):sum(p['total_sessions_attended']==i for p in profiles) for i in range(1,6)},
                validation_passed=not bad,issues=bad)
    (OUT/'validation_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    if bad:raise RuntimeError('Validation failed '+repr(bad[:15]))
    # Generator is a standalone root-level research artifact, not part of any student's folder.
    generator_src=Path(__file__)
    if generator_src.resolve()!=(OUT/'generate_intervention_sequences.py').resolve():
        shutil.copy2(generator_src,OUT/'generate_intervention_sequences.py')
    with zipfile.ZipFile(ZIP,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file(): z.write(p,p.relative_to(OUT).as_posix())
    print(json.dumps(report,indent=2))
    print('Archive:', ZIP, 'bytes:',ZIP.stat().st_size,'entries:',len(zipfile.ZipFile(ZIP).namelist()))

if __name__=='__main__':main()
