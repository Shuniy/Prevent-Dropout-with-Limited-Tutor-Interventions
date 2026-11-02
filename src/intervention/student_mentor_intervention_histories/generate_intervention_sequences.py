#!/usr/bin/env python3
"""Create fictional linked student-mentor intervention-series transcripts.
All content is synthetic; no intervention response or dropout outcome is inferred.
"""
from __future__ import annotations
import csv, datetime as dt, hashlib, io, json, random, re, shutil, zipfile
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path('/mnt/data/student_mentor_intervention_histories_130_students')
ZIP = Path('/mnt/data/student_mentor_intervention_histories_130_students.zip')
SEED = 20261102
R = random.Random(SEED)

# Issue rows: (short concern, student account, example, secondary constraint, what student wants)
# Activity rows: (mentor's in-session exercise/action, student's reaction, mentor's feedback, next agreed action)
CONFIG = {
 'transport_assessment': {
  'title': 'Transport Assessment',
  'issues': [
   ('bus fare uncertainty','I sometimes have the fare for school and sometimes do not.','Last Thursday I walked because I did not have bus money.','The price of a weekly pass is not confirmed.','A way to arrive without worrying each morning'),
   ('unreliable morning bus','The bus does not always arrive when the timetable says.','Two mornings this month I waited and then reached the gate late.','I have not kept exact arrival times.','A more dependable journey plan'),
   ('long walking route','Walking to school leaves me tired before my first lesson.','The walk took nearly an hour on one rainy morning.','My family cannot always accompany me.','A journey that is manageable in bad weather'),
   ('unsafe crossing','The route involves a crossing that makes me nervous.','I waited for a long gap in traffic last Tuesday.','I do not know whether an approved alternative route exists.','A safer route rather than just a faster one'),
   ('bus timetable change','My usual bus changed its route and I am confused about the stops.','I went to the old stop one morning and missed registration.','I am not sure whether the change is permanent.','To know which stop and departure time to use'),
  ],
  'activities': [
   ('write down the usual route and the points where it becomes difficult','The route starts at the main road, and the hardest part is the connection.','We have a reported route, not a verified transport entitlement.','record two actual journey times before the next meeting'),
   ('compare the recorded journey times with the posted timetable','One journey was close to the timetable and another was much later.','We can document the difference without saying every bus is unreliable.','check an alternative departure and write down whether it is practical'),
   ('list available school transport-assistance or route-advice contacts','I would like to know the rules before anyone applies on my behalf.','We can request eligibility information without promising funding.','ask the support office what evidence an assessment would require'),
   ('make a bad-weather and missed-bus backup plan','I can identify a safe place to wait and a number to call the school.','The backup needs to be safe and realistically available.','try the backup communication step if a bus is delayed'),
   ('review what is confirmed, still pending, and outside our control','I can explain the two routes, but I still need clarity about financial help.','A route plan is not proof that the barrier has been removed.','keep the route log and request another assessment if travel remains difficult'),
  ],
 },
 'tutoring': {
  'title':'Tutoring',
  'issues': [
   ('fractions and decimals','I lost track of fractions when I missed two lessons.','I mixed up denominators on the last worksheet.','I am embarrassed about asking questions in class.','To understand the steps rather than copy answers'),
   ('algebra basics','I struggle to keep equations balanced.','I moved a number across the equals sign without changing it correctly.','The next class is already doing longer problems.','To solve a simple equation alone'),
   ('reading comprehension','I can read the words but struggle to explain what a paragraph means.','I answered a question without finding the evidence in the text.','I read more slowly when other people are waiting.','To explain an answer using a sentence from the text'),
   ('science explanations','I remember science terms but not how to use them in an explanation.','I wrote definitions instead of explaining a process in a test.','I missed one practical lesson.','To write a short scientific explanation'),
   ('written paragraphs','I can talk about an idea but my written paragraph gets muddled.','My teacher underlined places where I had no examples.','I run out of time when I rewrite everything.','To build one clear paragraph'),
  ],
  'activities': [
   ('work through one small example aloud, pausing after each step','I got the first step right once we slowed it down.','That shows what happened in this exercise, not your overall attainment.','try two similar examples and mark where I get stuck'),
   ('ask the student to teach one of the steps back to the mentor','I could describe the step but needed a hint for the next one.','A hint is useful information; we can target that exact gap.','write one worked example in my own words'),
   ('practice a problem with different numbers and no worked answer visible','I finished part of it independently and checked one error.','We should record the part done independently and the part needing support.','bring one attempt from class for us to review'),
   ('compare two possible answers and explain why one is better supported','I changed my answer after checking the evidence rather than guessing.','That is a useful strategy to practice in class.','use the evidence-checking step on the next class task'),
   ('do a short mixed review and identify the next learning gap','I remembered some steps but still mixed up one of the rules.','A fifth tutoring session does not prove the learning gap is closed.','continue the short practice routine and ask the teacher for the next topic'),
  ],
 },
 'homework_support': {
  'title':'Homework Support',
  'issues': [
   ('unfinished assignments','I start homework but rarely finish everything.','Three tasks were due on the same day last week.','I do not know which teacher will accept a late submission.','To hand in a manageable amount of work'),
   ('unclear instructions','I am unsure what some homework instructions mean.','I completed the wrong questions for one worksheet.','I do not always feel able to ask in class.','To understand the task before leaving school'),
   ('little quiet study time','It is difficult to find a quiet place to work after school.','I tried doing homework while family members used the same room.','The library is not open every evening.','To find a realistic place and time for homework'),
   ('poor task prioritisation','I spend too long on one assignment and forget another.','I revised one subject and missed a written task.','Deadlines change between lessons.','A weekly plan that I can actually follow'),
   ('work not submitted','Sometimes I do the work but forget to submit it.','My finished worksheet stayed in my bag for three days.','I am not sure whether online and paper deadlines match.','A reliable checking routine'),
  ],
  'activities': [
   ('put current tasks and due dates into one simple list','The list shows two urgent tasks and one that can wait.','We have organised reported deadlines; the actual portal may need checking.','check two deadlines and bring the confirmed dates'),
   ('break the most urgent task into three small steps','The first step feels possible in fifteen minutes.','A smaller task is an experiment, not a guarantee of completion.','attempt the first two steps at the agreed time'),
   ('rehearse how to ask a teacher to clarify an instruction','I can ask which pages and examples are required.','Clarification can prevent unnecessary work.','ask one teacher for clarification and note the reply'),
   ('test a short homework checklist and submission reminder','The checklist reminds me to put work in the correct place.','We can test whether it fits your school routine.','use the checklist on the next piece of work'),
   ('review completed, missed, and still-unconfirmed tasks','One task is finished and another is still not handed in.','We should not count unsubmitted work as completed.','keep a short task list and request support if it grows again'),
  ],
 },
 'attendance_planning': {
  'title':'Attendance Planning',
  'issues': [
   ('frequent late arrival','I am often late even on days I attend.','I missed registration twice last week.','The attendance office might have marked one late arrival as absent.','To get to the first lesson more consistently'),
   ('morning responsibilities','I help at home before leaving for school.','I sometimes wait until my younger sibling is collected.','The timing changes with family shifts.','A morning routine that does not ignore home responsibilities'),
   ('irregular weekly attendance','Some weeks I come most days and some weeks I miss two or three.','I was absent Monday but attended all my later lessons.','My recorded attendance percentage may be out of date.','To understand and reduce the pattern of missed days'),
   ('school avoidance after missed work','After being absent, it feels hard to go back to lessons.','I worried about returning after missing a test.','I do not always know how to request catch-up work.','A less stressful return after an absence'),
   ('confusing timetable','I sometimes go to the wrong classroom and arrive late.','The room change was not on my printed timetable.','I am not sure who updates the displayed timetable.','A clear plan for the first part of the day'),
  ],
  'activities': [
   ('make a day-by-day timeline of attendance and lateness','I can remember three days clearly but not the exact dates for all absences.','We should check the register rather than treat memory as official attendance.','compare my recollection with the attendance office record'),
   ('identify one realistic morning adjustment','Packing my bag earlier might help, but home duties could still delay me.','The plan must respect constraints rather than blame the student.','try the morning adjustment on two school days'),
   ('draft a message for the school when arrival is disrupted','I could use the attendance contact rather than just arriving without explanation.','We need to confirm the school contact process before relying on it.','confirm the correct contact and practice using it'),
   ('review which late days had different causes','One day was travel and another was catching up after an absence.','Different causes may require different supports.','keep a short record of the next two arrival times'),
   ('make a continued-attendance plan with an escalation contact','I know whom to approach if the same problem happens again.','We have a plan; subsequent attendance is still to be observed.','continue the arrival log and request review if absences persist'),
  ],
 },
 'device_access': {
  'title':'Device Access',
  'issues': [
   ('shared family phone','I share a phone at home and cannot always use it for homework.','My sister needed the phone when my assignment was due.','I have not checked the school device-loan rules.','Reliable access for assignments'),
   ('broken computer','The computer at home stopped working properly.','It shut down while I was writing a report.','We do not know whether it can be repaired.','A way to submit work even without that computer'),
   ('limited mobile data','I run out of mobile data before all tasks are submitted.','A video lesson would not load yesterday.','I cannot assume there is free data available.','To use smaller files or another access point'),
   ('school portal difficulties','I cannot always log in to the homework portal.','The password reset did not reach the device I used.','The account status needs to be checked by IT.','To access assignments independently'),
   ('no printer access','Some activities expect printed worksheets that I cannot print.','I copied questions by hand instead of doing the exercise.','I do not know if paper copies can be requested.','A way to complete tasks without a printer'),
  ],
  'activities': [
   ('list the devices, connections and school resources the student can actually use','I can use a phone sometimes, but not at every homework time.','We are mapping access, not assuming a loan device exists.','check when the school computer room is available'),
   ('test a low-bandwidth or paper-based version of one task','The smaller file opens, but typing a long answer is still awkward.','An alternative format may remove one obstacle while others remain.','ask whether the next assignment has an offline option'),
   ('prepare an inquiry to the authorised school IT or device-support contact','I would prefer to ask about the rules before sharing personal information.','We can check eligibility without claiming a device has been issued.','request the current device-support procedure'),
   ('plan a backup submission method for a device failure','I could save a draft at school and tell my teacher if the device fails.','The backup must be approved by the teacher.','confirm the acceptable backup submission method'),
   ('check what access improved and what remains unavailable','I managed one task at school, but home access is still limited.','One successful submission does not mean the access barrier is resolved.','continue using the agreed backup while any application is pending'),
  ],
 },
 'family_finances': {
  'title':'Family Finances',
  'issues': [
   ('school supply costs','I am worried about buying the materials requested in class.','I borrowed paper because I did not have the workbook.','I do not know which school materials may be provided.','To keep participating without unexpected costs'),
   ('uniform replacement','My uniform is worn out and I feel uncomfortable coming to school.','I avoided an activity because I was worried about how it looked.','I do not know whether uniform assistance exists.','To feel comfortable attending'),
   ('transport expense pressure','The travel cost adds to other household expenses.','I had to choose walking over paying for the bus last week.','I do not know the household budget details.','To find out what support might be available'),
   ('missed fee-related activities','I have skipped activities because I thought they might cost money.','I did not join a workshop because the note mentioned a fee.','I have not confirmed whether the fee is required.','To know which activities are affordable'),
   ('household money worries','Money problems at home make it difficult to focus in lessons.','I worried about a bill while studying yesterday.','I do not know exactly what the family owes.','To understand what help the school can discuss with my family'),
  ],
  'activities': [
   ('separate school-related costs the student knows from unverified household details','I can name the materials and travel issues but not the family income.','We should not infer income or eligibility from this account.','list the specific school costs to ask the support office about'),
   ('identify a trusted adult and plan a consent-sensitive contact','I want the conversation explained to me before anyone calls home.','We can respect that preference subject to safeguarding requirements.','agree with a trusted adult how a support inquiry should be made'),
   ('review publicly described assistance routes without promising eligibility','I understand an application might need information I do not have.','An inquiry is not approval or delivery of assistance.','ask the school office for written eligibility guidance'),
   ('practice requesting a no-cost alternative for a school activity','I could ask whether materials are supplied or the activity has an alternative.','A practical question can avoid making assumptions about fees.','ask the teacher which costs are compulsory'),
   ('record confirmed answers and unresolved financial barriers','One question has an answer but other costs are still uncertain.','We cannot claim financial circumstances have improved from this conversation.','keep the support contact details and request another review if needed'),
  ],
 },
 'family_liaison': {
  'title':'Family Liaison',
  'issues': [
   ('parent-school contact difficulty','The school and my guardian keep missing each other on the phone.','A teacher called while my guardian was working.','I have not checked the best time for a call.','To make communication easier'),
   ('changing home schedule','Changes in shifts at home affect school routines.','The pickup plan changed unexpectedly on Wednesday.','I am not sure what next week will look like.','A plan that both home and school understand'),
   ('confusion about school notices','Some notices reach home late or are hard to understand.','We missed a meeting date on a paper letter.','I do not know whether there is another contact format.','To make notices clearer'),
   ('care responsibilities','I sometimes help care for a younger family member.','I arrived late after helping with childcare.','The details are private and I do not want to share everything.','To find practical support without blaming my family'),
   ('different expectations','My family and teachers have different ideas about how much homework I can do.','I was told to attend a club when I was expected at home.','The adults have not discussed a common schedule.','A realistic agreement between home and school'),
  ],
  'activities': [
   ('map which school communication channels have been tried','I think we missed a voicemail, but I have not checked the phone log.','We should label this as reported, not a confirmed failed contact.','ask my guardian which contact time works best'),
   ('rehearse a short explanation of the student’s school need','I can explain the school issue without speaking for every family member.','The student can have a voice in the contact plan.','agree what can be shared with the school contact'),
   ('prepare a contact request for the appropriate staff member','I would like to be told when the request is sent.','Drafting a request does not mean a call occurred.','ask the liaison office to confirm whether contact was made'),
   ('compare the student and family timetable needs','I can suggest one day that may work for home and school.','Availability still has to be confirmed by the family and staff.','check whether the proposed meeting time is acceptable'),
   ('summarise verified contact and remaining misunderstandings','We have a clearer question, though not every issue is agreed.','We should record what was heard and what remains unconfirmed.','keep a contact plan and revisit if home and school need another meeting'),
  ],
 },
 'language_support': {
  'title':'Language Support',
  'issues': [
   ('complex classroom vocabulary','I understand some lessons but not the longer instructions.','I missed what the word compare meant in a question.','I am still learning school-specific vocabulary.','To understand what teachers are asking me to do'),
   ('explaining answers in English','I know the idea but cannot always explain it in English.','I used one-word answers in a science discussion.','I feel rushed when speaking in front of others.','To make longer explanations with confidence'),
   ('reading school notices','School letters take me a long time to read.','I missed a deadline written in a long notice.','Some terms are not clear even when translated.','To find important dates and actions'),
   ('writing in lessons','I understand the topic but struggle to write complete sentences.','My paragraph was missing linking words.','I am not sure when to use formal language.','To write a few clear sentences'),
   ('speaking in groups','I hesitate to contribute when classmates speak quickly.','I thought of an answer only after the discussion ended.','The problem is not the same in every class.','To join classroom discussions more often'),
  ],
  'activities': [
   ('choose three common classroom instruction words and explain them in plain language','I can explain one of them easily and need examples for the others.','We will practice meaning rather than just memorise definitions.','write down two instruction words that appear in class'),
   ('practice answering a question in two linked sentences','I could say the first sentence but paused before the reason.','We can keep the language task manageable.','try the two-sentence frame in one lesson'),
   ('read a short notice and find its date, task and contact','I found the date after highlighting the important line.','That strategy may help with other school messages.','highlight the action and date in the next notice'),
   ('rehearse a respectful clarification question for class','I can say: Could you explain what that instruction means?','Asking for clarity is a useful learning strategy.','use one clarification question when it is needed'),
   ('review a new passage and note remaining language needs','I can explain the main idea but still need help with some phrases.','Improvement on one passage is not a general proficiency test.','continue the phrase notebook and ask about unfamiliar instructions'),
  ],
 },
 'learning_access': {
  'title':'Learning Access',
  'issues': [
   ('noisy classroom','I lose track of instructions when the room is loud.','I missed a demonstration because nearby people were talking.','The room layout changes between subjects.','To hear instructions more clearly'),
   ('hard-to-read materials','Some worksheets are difficult for me to follow in the given format.','I lost my place while reading a crowded page.','I have not had a formal access assessment.','To use a clearer learning format'),
   ('seating difficulties','I cannot always see the board from where I sit.','I copied the wrong number from the far side of the board.','I have not asked whether seats can be changed.','A place where I can follow the lesson'),
   ('fast lesson pace','I need more time to process examples before moving on.','The teacher moved to the next step while I was still writing.','I do not know which adjustment is practical in every class.','To keep up without rushing everything'),
   ('unclear visual instructions','Diagrams in class sometimes lack a clear explanation.','I was unsure which arrow belonged to the first step.','The issue affects some topics more than others.','To understand diagrams and task sequence'),
  ],
  'activities': [
   ('describe one specific learning-access obstacle without diagnosing its cause','I can explain which room and activity made it difficult.','We can request a practical adjustment without guessing a diagnosis.','note one lesson where the same obstacle occurs'),
   ('compare a standard worksheet with a clearer layout','The spaced version is easier to follow, at least for this example.','A short trial does not establish a formal accommodation entitlement.','ask whether a clearer copy can be provided in one class'),
   ('practice a way to request clarification or an appropriate seat','I can ask calmly before the lesson rather than interrupting midway.','Staff must confirm what is possible for that room.','ask the relevant teacher what adjustments are feasible'),
   ('evaluate the attempted adjustment and remaining obstacles','It helped in one lesson but another room was still difficult.','We should record where it helped and where it did not.','keep a short record of conditions that support learning'),
   ('agree when and how to revisit access needs','I know which teacher or support lead I can ask next.','We are not declaring the learning barrier permanently resolved.','keep using workable adjustments and seek review if the problem persists'),
  ],
 },
 'peer_support': {
  'title':'Peer Support',
  'issues': [
   ('isolated break times','I often spend breaks alone.','I ate lunch by myself three days last week.','I do not know whether joining a group would feel comfortable.','To feel less isolated at school'),
   ('group-work conflict','I find it hard when group members disagree or ignore my ideas.','During a project, I was given no clear role.','I do not know whether anyone meant to exclude me.','A fair way to participate in group tasks'),
   ('rumours among classmates','People have been repeating things about me and I feel embarrassed.','I heard a comment in the corridor last week.','I have not confirmed where the rumour started.','To feel safe and respected at school'),
   ('friendship change','My closest friend moved classes and I feel left out.','I had no one to sit with in one lesson.','I do not know how permanent the timetable change is.','To rebuild some social connections'),
   ('anxiety about clubs','I want to join an activity but worry about arriving alone.','I walked past a club meeting without entering.','I am unsure whether the club is currently open.','To try a group activity without pressure'),
  ],
  'activities': [
   ('map which school spaces and peer interactions feel comfortable','One classroom feels easier than the crowded lunch area.','We should not force a friendship or confrontation.','notice one setting where I feel included'),
   ('rehearse a low-pressure introduction or group-work request','I could ask whether there is a task I can take responsibility for.','The choice to approach peers remains yours.','try one small group interaction if it feels safe'),
   ('identify a trusted adult for escalation if peer behaviour becomes harmful','I would rather speak privately than confront the group.','We can follow school safety procedures without guessing anyone’s motives.','check how to contact the school pastoral lead'),
   ('review what happened during a chosen social activity','I stayed for part of it, but I was still uncomfortable at first.','We can acknowledge both participation and discomfort.','choose whether to repeat that activity or try another'),
   ('create an ongoing peer-support and safety plan','I know one adult to approach if a problem returns.','An improved interaction does not prove bullying or isolation ended.','maintain the chosen contact and report further incidents promptly'),
  ],
 },
 'reentry_support': {
  'title':'Re-entry Support',
  'issues': [
   ('return after prolonged absence','I have missed several weeks and feel nervous coming back.','I did not know which lesson to attend on my first morning.','I am uncertain which missed assessments can be retaken.','To return without being overwhelmed'),
   ('transfer to a new school','I am still learning how this school works.','I went to the wrong room on my second day.','Some prior records have not arrived.','To settle into a predictable routine'),
   ('return after family disruption','I was away because things changed at home.','I missed a unit while I was absent.','I do not want to share all the private family details.','To catch up with work at a manageable pace'),
   ('rebuilding study habits','My routine changed while I was out of school.','I struggled to start homework after returning.','I do not yet know my current academic level.','To build confidence with short tasks'),
   ('worry about returning to friends','I am nervous about what classmates might say after my absence.','I stayed quiet during my first break back.','I do not know whether the concern will persist.','To feel comfortable being back at school'),
  ],
  'activities': [
   ('draw a first-week timetable with a named school contact','I can identify the first lesson and where to go if a room changes.','This is a proposed routine, not yet a verified attendance outcome.','check the timetable with the school office'),
   ('sort missed work into urgent, useful and later categories','I can see that not everything needs doing in the same week.','The teachers need to confirm the actual catch-up priorities.','ask one subject teacher which work should come first'),
   ('rehearse asking for help after an absence','I can explain that I missed the starting lesson without giving private details.','The student can decide what personal information to share.','use the agreed help request in one class'),
   ('review one successful and one difficult return-to-class moment','One lesson felt manageable and another still felt confusing.','The return may be uneven and we should document that.','keep a short diary of access and workload needs'),
   ('agree an ongoing return-to-school contact and support option','I know where to ask for a review if the timetable becomes too much.','Attending these meetings is not itself proof of retention.','keep the agreed school contact and review attendance records later'),
  ],
 },
 'school_meals': {
  'title':'School Meals',
  'issues': [
   ('skipping lunch','I sometimes do not eat at school.','I went through the afternoon without lunch on Monday.','I have not checked what meal options are available.','To be able to eat during the school day'),
   ('meal card confusion','I am unsure how the school lunch card works.','The card was not accepted once at the till.','I do not know whether that was a balance or technical issue.','To understand how to access the meal service'),
   ('long lunch queue','The queue takes so long I sometimes leave without food.','I missed the start of a lunchtime activity while waiting.','I do not know the quieter collection times.','A practical way to use the lunch break'),
   ('worry about meal costs','I sometimes avoid buying lunch because of the cost.','I brought nothing on a day when I expected to buy food.','I do not know whether any meal assistance would apply.','To check available support without embarrassment'),
   ('uncertain meal choices','I am not sure what food I can get at school.','I could not find a suitable option on one day.','I have not asked the catering staff about choices.','To know what options exist'),
  ],
  'activities': [
   ('identify what happened at lunch on specific recent days','I remember one missed meal but not every day in the week.','We should not invent a count from an uncertain memory.','note which days lunch access is difficult'),
   ('review the school lunch service process with the student','I know where the meal point is but I am unsure about the card.','We need to confirm actual service and eligibility rules.','ask catering staff about the correct access procedure'),
   ('prepare a discreet support or eligibility inquiry','I would prefer a private answer rather than discussing money in the queue.','Making an inquiry does not mean free meals were approved.','check with the designated office what documents or steps are needed'),
   ('plan a manageable lunch-time routine and alternative contact','I can try arriving earlier if the schedule allows.','A time change should not cost you a required lesson.','test the agreed lunch routine on one school day'),
   ('summarise confirmed access steps and any remaining need','One part of the process is clearer but I am unsure about longer-term help.','We cannot equate this discussion with sustained meal access.','keep the contact details and report another missed meal promptly'),
  ],
 },
 'wellbeing_checkin': {
  'title':'Wellbeing Check-in',
  'issues': [
   ('exam pressure','I get overwhelmed thinking about upcoming tests.','I struggled to concentrate the evening before a quiz.','I have not tracked how often this happens.','To feel more able to prepare for assessments'),
   ('feeling disconnected','I have felt less interested in activities I usually enjoy.','I stayed quiet through lunch a few days ago.','I am not sure whether this is temporary.','To find ways to feel more connected at school'),
   ('low confidence','I tell myself I will fail before I try.','I avoided answering a question I probably knew.','I do not know how often I hold back.','To try tasks without expecting immediate failure'),
   ('overwhelming schedule','School and other responsibilities feel difficult to balance.','I felt exhausted after a day with several deadlines.','I do not know which part of the routine can change yet.','To find a smaller, manageable weekly plan'),
   ('worry about asking for help','I keep concerns to myself because I do not want to bother anyone.','I left class without clarifying something I did not understand.','I am unsure whom I could approach privately.','To know where to ask for help'),
  ],
  'activities': [
   ('identify situations that make the school day feel more or less manageable','A quiet activity feels easier than thinking about every task at once.','We are discussing experiences, not diagnosing a condition.','notice one manageable moment and one difficult moment this week'),
   ('practice a brief grounding or pause routine the student chooses','Slowing down for a moment made the exercise feel less rushed.','A coping practice is optional and does not replace specialist support.','try the chosen pause during one stressful school moment'),
   ('name one trusted school adult and rehearse a help request','I can ask for a private conversation without explaining everything in class.','We can discuss the limits of confidentiality and safety responsibilities.','check when the trusted adult is available'),
   ('review which coping steps helped and which did not','One strategy helped briefly but the busy afternoon was still difficult.','A partial improvement should not be called full recovery.','keep the manageable step and reconsider one that did not help'),
   ('make an ongoing support and escalation plan','I know how to ask for another check-in if things get harder.','This session does not establish any clinical outcome or dropout change.','use the agreed school support contact if concerns continue'),
  ],
 },
}

SUPPORT_ORDER = list(CONFIG)
assert len(SUPPORT_ORDER) == 13

# Distinct follow-up outcomes: status applies to the previous agreed between-session action.
FOLLOWUP = {
 'done': ('Yes, I completed the specific step we agreed and made a note of what happened.', 'That is a reported completed step. What did it tell you?', 'I did that step, but the wider school problem is not automatically solved.'),
 'partial': ('I started it but did not finish the whole step.', 'Which part worked, and where did it stop?', 'I tried the small beginning; the rest was difficult because of my schedule.'),
 'blocked': ('No, I could not do the step we agreed.', 'What got in the way? We can change the plan rather than treat that as failure.', 'The situation at home and school made the timing difficult.'),
 'uncertain': ('I am not sure whether I did it exactly as planned.', 'That is fine. We can record it as unclear rather than tick it off.', 'I remember part of it, but I did not write down what happened.'),
}

INTRO = [
 ('Thanks for coming today. What would make this meeting useful to you?', 'I would like a practical step that fits what is going on.'),
 ('Before we begin, this is a support conversation. What is on your mind?', 'I am worried the problem is starting to affect school.'),
 ('We can look at what is known and what still needs checking. Is that okay?', 'Yes. I do not want anyone guessing about my situation.'),
]
FOLLOW_OPEN = [
 ('Welcome back. How have things been since our last appointment?', 'Some things were similar, although there was a change this week.'),
 ('Good to see you again. We can continue from our last agreed step.', 'Yes. I remember what we talked about last time.'),
 ('Today is a follow-up, so we will start with what actually happened.', 'Okay. I can tell you what I tried, but not every detail.'),
]

# The extra prompts are designed as additional dialogue rather than generic filler.
PROMPTS = [
 ('When was the most recent time that this issue affected your day?', 'I noticed it during a lesson this week, though I cannot remember the exact time.'),
 ('Was that the usual pattern or a particularly difficult day?', 'That day was worse than usual, so I would not call it typical.'),
 ('What was different about a day when the concern was less noticeable?', 'I had a little more time to prepare and felt less rushed.'),
 ('How did it affect the subject or activity you were doing?', 'I lost time and needed to catch up with instructions afterward.'),
 ('Which part would you most like to make easier first?', 'The part that affects whether I can take part in class.'),
 ('Is that based on something you checked, or mainly on your recollection?', 'Mostly my recollection. I have not checked a record.'),
 ('Could another explanation also fit what happened?', 'Possibly. I do not think I know the whole reason yet.'),
 ('What would be a fair way of checking before deciding?', 'We could ask the relevant school staff or check a dated record.'),
 ('What part of the situation can you choose, and what is outside your control?', 'I can choose one small step, but not the whole situation.'),
 ('Is there anything you have already tried that did not work?', 'I tried dealing with it alone, but that did not solve the difficulty.'),
 ('Which of your usual strengths might help with this?', 'I can stick to a small routine if it is clear and realistic.'),
 ('How would you notice a small improvement next week?', 'I would be able to complete more of the school activity without getting stuck.'),
 ('Can we describe one concrete example rather than a general feeling?', 'One recent lesson was harder, but I would need to check the date.'),
 ('What does your preferred outcome look like in a normal school week?', 'I want to feel able to join in and finish what I am meant to do.'),
 ('Does the concern happen in all classes?', 'No, it varies. I do not want it recorded as happening everywhere.'),
 ('Who at school would be most appropriate to confirm that information?', 'Probably the class teacher or the office that handles that issue.'),
 ('Would asking that person feel comfortable for you?', 'Maybe, if I know what we are going to ask first.'),
 ('What should we avoid sharing without a clear reason?', 'I would prefer not to share private details about home.'),
 ('Could we phrase the request without including private family information?', 'Yes, that would make it easier for me to agree.'),
 ('Would a written reminder be more helpful than trying to remember everything?', 'A short reminder would help, as long as it is not too complicated.'),
 ('Could you repeat the next step in your own words?', 'I should try one manageable thing and record what actually happened.'),
 ('How much time could you realistically give the next step?', 'A few minutes on one or two days, not every evening.'),
 ('Is there a particular school day when trying it makes sense?', 'A day without too many other tasks would probably work.'),
 ('What would you do if the planned time is unavailable?', 'I would ask to reschedule rather than say it was completed.'),
 ('Is anything still unclear about how this support works?', 'I still need to know which part is confirmed and which part is only proposed.'),
 ('Are we making an offer, or has any external support actually been delivered?', 'So far we are discussing and checking options; I have not received that extra support.'),
 ('What would you want recorded in the mentoring note?', 'Please say what I reported, not that every detail has been verified.'),
 ('What should remain marked as uncertain?', 'The exact dates and whether a service is available are still uncertain.'),
 ('If the first idea is not available, what kind of backup would be useful?', 'A smaller school-based step rather than something I cannot manage at home.'),
 ('Does this proposed next step interfere with lessons or travel?', 'We should check the timing before I agree to it.'),
 ('Would you prefer to make the request yourself or with support?', 'I would like to try with someone helping me phrase it.'),
 ('What would make you feel more comfortable returning for another discussion?', 'Knowing that a difficult week will not be treated as me refusing help.'),
 ('How did you feel when the problem showed up recently?', 'Frustrated at first, and then I stopped asking about it.'),
 ('What helped you get through that day?', 'I asked a classmate what I had missed, although that was only partly useful.'),
 ('Do you want to leave any detail out of the written record?', 'Please keep it focused on the school problem rather than every personal detail.'),
 ('What do you think the school knows about this already?', 'Probably the missed work or late arrival, but not why it happened.'),
 ('Does {constraint_lower} make that plan harder?', 'Yes, that is why I would prefer a small step we can adjust.'),
 ('What would be the first sign that our plan is too ambitious?', 'If I keep missing the step because it takes too much time.'),
 ('Can we choose a measure that does not depend only on memory?', 'I could mark a date or keep a very short note after it happens.'),
 ('How can we avoid confusing participation with the final outcome?', 'Coming to a meeting helps me plan, but the school problem may still be there.'),
 ('What should happen if the concern gets worse before another session?', 'I could speak to the designated school adult rather than wait.'),
 ('Is there something you disagree with in my summary?', 'I would change the part that sounds as though it happens every day.'),
 ('What do you want your teacher to understand about this?', 'That I am trying, but the practical difficulty is still getting in the way.'),
 ('Could the plan work even if outside help is delayed?', 'Part of it could, but I might need another option if the delay continues.'),
 ('Would you like a moment to think before choosing the next step?', 'Yes. I would rather choose something possible than agree too quickly.'),
 ('Can we compare what was reported with what is actually confirmed?', 'The experience is mine to report, but the office details still need checking.'),
]

# Administrative stopping patterns appear in the manifest ONLY, not retroactively in a session.
ENDINGS = ['no_further_attendance_recorded', 'next_meeting_not_attended', 'further_support_declined', 'contact_not_confirmed']


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
