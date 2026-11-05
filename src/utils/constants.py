"""Shared configuration, paths, schemas, and scenario constants."""

from pathlib import Path

from .enums import SupportType

import numpy as np

# Default seed for independently owned simulation streams.
SEED = 42
SEEDS = [SEED, 123, 456, 789, 101112]


def create_rng(seed: int = SEED) -> np.random.Generator:
    """Create an independent seeded stream for a reproducible simulation run."""
    return np.random.default_rng(seed)


# default simulation parameters
DEFAULT_NUMBER_OF_STUDENTS = 1000
DEFAULT_NUMBER_OF_MENTORS = 10
DEFAULT_NUMBER_OF_MONTHS = 12
DEFAULT_BUDGET = 10000
DEFAULT_MENTOR_COST_PER_SESSION = 1.0
DEFAULT_NUMBER_OF_SESSIONS_PER_STUDENT = 5
DEFAULT_NUMBER_OF_STUDENTS_PER_MENTOR = 10


ALL_SUPPORT_TYPES: tuple[SupportType, ...] = (
    "attendance_planning",
    "device_access",
    "family_finances",
    "family_liaison",
    "homework_support",
    "language_support",
    "learning_access",
    "peer_support",
    "reentry_support",
    "school_meals",
    "transport_assessment",
    "tutoring",
    "wellbeing_checkin",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_STUDENT_DATA_PATH = (
    PROJECT_ROOT / "data/synthetic/populations/synthetic_student_population.csv"
)

BOOLEAN_FIELDS = (
    "rural_residence",
    "family_size_gt3",
    "parents_apart",
    "school_support_existing",
    "family_support_existing",
    "paid_classes_existing",
    "extracurricular",
    "nursery_attended",
    "higher_education_aspiration",
    "internet_at_home",
)

INTEGER_FIELDS = (
    "age_years",
    "mother_education_code",
    "father_education_code",
    "travel_time_category",
    "study_time_category",
    "past_failures_count",
    "family_relationship_rating",
    "health_self_rating",
    "anchor_grade1_0_20",
    "weeks_since_offer",
    "support_sessions_completed",
)

HISTORIES = PROJECT_ROOT / "src/intervention/student_mentor_intervention_histories"

RAG_RESULTS = Path(__file__).resolve().parents[2] / "results" / "intervention_rag"

SIMULATION_RESULTS = PROJECT_ROOT / "results/intervention_simulation"
EXAMPLE_SEED = 5726455


# Synthetic transcript scenario ingredients.
HISTORY_OUT = Path('/mnt/data/student_mentor_intervention_histories_130_students')

HISTORY_ZIP = Path('/mnt/data/student_mentor_intervention_histories_130_students.zip')

HISTORY_SEED = 20261102

HISTORY_CONFIG = {
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

HISTORY_SUPPORT_ORDER = list(HISTORY_CONFIG)

HISTORY_FOLLOWUP = {
 'done': ('Yes, I completed the specific step we agreed and made a note of what happened.', 'That is a reported completed step. What did it tell you?', 'I did that step, but the wider school problem is not automatically solved.'),
 'partial': ('I started it but did not finish the whole step.', 'Which part worked, and where did it stop?', 'I tried the small beginning; the rest was difficult because of my schedule.'),
 'blocked': ('No, I could not do the step we agreed.', 'What got in the way? We can change the plan rather than treat that as failure.', 'The situation at home and school made the timing difficult.'),
 'uncertain': ('I am not sure whether I did it exactly as planned.', 'That is fine. We can record it as unclear rather than tick it off.', 'I remember part of it, but I did not write down what happened.'),
}

HISTORY_INTRO = [
 ('Thanks for coming today. What would make this meeting useful to you?', 'I would like a practical step that fits what is going on.'),
 ('Before we begin, this is a support conversation. What is on your mind?', 'I am worried the problem is starting to affect school.'),
 ('We can look at what is known and what still needs checking. Is that okay?', 'Yes. I do not want anyone guessing about my situation.'),
]

HISTORY_FOLLOW_OPEN = [
 ('Welcome back. How have things been since our last appointment?', 'Some things were similar, although there was a change this week.'),
 ('Good to see you again. We can continue from our last agreed step.', 'Yes. I remember what we talked about last time.'),
 ('Today is a follow-up, so we will start with what actually happened.', 'Okay. I can tell you what I tried, but not every detail.'),
]

HISTORY_PROMPTS = [
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

HISTORY_ENDINGS = ['no_further_attendance_recorded', 'next_meeting_not_attended', 'further_support_declined', 'contact_not_confirmed']


# Synthetic transcript scenario ingredients.
DIALOGUE_SEED=20261103

DIALOGUE_N=400

DIALOGUE_TOPICS={
 'transport_cost': dict(
    overview='The bus fare has become difficult to cover on some mornings.',
    timeline='It became harder around the middle of last month, but I cannot remember the exact week.',
    pattern='It is usually worse near the end of the week when we have already spent money on other things.',
    example='Last Thursday I waited at the stop, then went home because I had no fare.',
    impact='When I arrive late or miss a day, I struggle to follow the next lesson.',
    attempt='I have walked a few times, but it takes a long time and I arrive tired.',
    constraint='I do not know whether our route is covered by any school scheme.',
    misconception='I do not skip school just because I dislike lessons.',
    uncertainty='I am not sure how many days the fare itself was the problem.',
    aspiration='I would like a reliable way of getting here without worrying every morning.',
    priority='Please find out whether transport help can even be considered.',
    actions=['transport_assessment','family_finances','attendance_planning']),
 'unreliable_bus': dict(
    overview='The morning bus sometimes does not show up on time.',
    timeline='It started happening more often after the route changed.',
    pattern='Some mornings it comes normally, and other mornings we wait a long time.',
    example='On Tuesday I reached the gate after the first lesson had finished.',
    impact='The late mark makes me anxious about going into class.',
    attempt='I tried leaving earlier, but there is no earlier bus I can use every day.',
    constraint='I cannot tell when the service will be delayed.',
    misconception='Being late does not always mean I got up late.',
    uncertainty='I have not kept all the bus times, so I cannot prove every delay.',
    aspiration='I want a predictable morning and to stop missing the first class.',
    priority='Could someone review my lateness separately from absences?',
    actions=['transport_assessment','attendance_planning']),
 'household_finances': dict(
    overview='Money is tight at home and I sometimes lack what classes require.',
    timeline='It got more noticeable after my parent lost some working hours.',
    pattern='Not every week is the same; sometimes we manage and sometimes we cannot.',
    example='I did not bring the requested materials for a project last week.',
    impact='I feel embarrassed and spend time worrying instead of concentrating.',
    attempt='I borrowed supplies once but I cannot keep borrowing everything.',
    constraint='I do not know exactly what support our household would qualify for.',
    misconception='A missing item does not mean my family is not interested in school.',
    uncertainty='I do not know our household income and would rather not guess.',
    aspiration='I would like to attend without feeling that I am constantly behind on costs.',
    priority='Please explain the available support and what information it requires.',
    actions=['family_finances','family_liaison','school_meals']),
 'caregiving': dict(
    overview='I sometimes help care for someone at home before school.',
    timeline='The morning routine changed when the usual caregiver started a new shift.',
    pattern='It happens on certain days, not every morning.',
    example='Last Monday I had to wait for an adult to come home before I could leave.',
    impact='I missed registration and spent the day worried about catching up.',
    attempt='I asked whether the routine could change, but no one has sorted it yet.',
    constraint='I do not control the adults’ schedules.',
    misconception='I am not saying I have to stay home every day.',
    uncertainty='I do not know the schedule for the next few weeks.',
    aspiration='I want to help at home and still be able to attend consistently.',
    priority='Can we plan around the difficult mornings without blaming my family?',
    actions=['family_liaison','attendance_planning']),
 'housing_changes': dict(
    overview='We have been staying in different places and my school routine keeps changing.',
    timeline='We moved temporarily several weeks ago.',
    pattern='Some weeks are settled; other weeks we do not know where we will be staying.',
    example='I left my workbook at another address and could not finish the assignment.',
    impact='It is hard to sleep, plan travel, and remember everything I need.',
    attempt='I keep my important books in one bag now, which helps a little.',
    constraint='I cannot promise when our address will stop changing.',
    misconception='I am not changing schools by choice.',
    uncertainty='We do not have a confirmed longer-term address yet.',
    aspiration='I want a stable place to do work and a way to keep coming to the same school.',
    priority='Could someone help me work out whom to contact about school arrangements?',
    actions=['family_liaison','transport_assessment','attendance_planning']),
 'food_access': dict(
    overview='Some mornings I come to school without having eaten enough.',
    timeline='It has happened more often in the last few weeks.',
    pattern='Not every day. It depends on what is available at home.',
    example='On Friday I felt hungry halfway through the first lesson.',
    impact='I found it difficult to pay attention, particularly before lunch.',
    attempt='I have brought something small when possible, but that is not always possible.',
    constraint='I do not know what help the school currently provides.',
    misconception='Being distracted in class does not mean I am trying to be rude.',
    uncertainty='I am not sure whether we meet the rules for any meal programme.',
    aspiration='I want to be able to focus instead of thinking about food.',
    priority='I would like to hear what meal support is available.',
    actions=['school_meals','family_finances','family_liaison']),
 'math_gap': dict(
    overview='I missed part of the maths course and now the new work does not make sense.',
    timeline='It started after I was absent during the fractions lessons.',
    pattern='It is especially difficult during algebra; other topics are better.',
    example='I could not do the equation on the board even after copying the example.',
    impact='My confidence drops and I leave questions blank.',
    attempt='I watched a short video, but I got stuck halfway through.',
    constraint='I need help with the basics before the class moves further ahead.',
    misconception='I am struggling with one part of maths, not refusing to learn everything.',
    uncertainty='I am not sure exactly which earlier step I misunderstood.',
    aspiration='I want to solve questions without always copying the answer.',
    priority='Can someone find the first concept I need to practise?',
    actions=['tutoring','homework_support','learning_access']),
 'reading_gap': dict(
    overview='Long reading assignments take me much longer than they seem to take others.',
    timeline='I have found longer texts difficult for quite a while.',
    pattern='Short passages are okay; unfamiliar words slow me down.',
    example='I spent the whole evening on two pages and did not finish the questions.',
    impact='I often understand less of the lesson because I am still reading the instructions.',
    attempt='I tried reading aloud and making notes, which sometimes helps.',
    constraint='I do not want the whole class to listen to me struggle.',
    misconception='I can read; I am not saying that I cannot read at all.',
    uncertainty='I have not had any assessment, and I do not know what is causing it.',
    aspiration='I would like strategies that let me keep up without feeling exposed.',
    priority='Could we look at an accessible way to practise reading?',
    actions=['tutoring','learning_access','homework_support']),
 'device_access': dict(
    overview='Several assignments need internet access, and I cannot always get online.',
    timeline='It became a problem when more homework moved to the online platform.',
    pattern='I can sometimes use a shared phone, but it is not always available.',
    example='I wrote my answers on paper because the upload page would not load.',
    impact='Some of my work is showing as missing even though I attempted it.',
    attempt='I used the library computer once, but its opening time did not always fit.',
    constraint='I cannot rely on having a personal laptop or steady connection.',
    misconception='A missing online upload does not always mean the homework was not done.',
    uncertainty='I do not know whether teachers will accept an offline version for each task.',
    aspiration='I want a reliable way to hand in the work I complete.',
    priority='Could we check whether I can use school equipment or submit differently?',
    actions=['device_access','homework_support','family_liaison']),
 'language_learning': dict(
    overview='I understand many lessons, but I sometimes miss important instructions in English.',
    timeline='This became more noticeable with the new subject vocabulary this term.',
    pattern='I can follow spoken examples better than long written explanations.',
    example='I understood the calculation but did not understand what the question was asking.',
    impact='I spend extra time translating words and sometimes finish late.',
    attempt='I keep a vocabulary list in my notebook.',
    constraint='I do not want teachers to assume I understand nothing.',
    misconception='I know the subject content in some lessons; the wording can be the problem.',
    uncertainty='I do not know which language-support sessions the school currently runs.',
    aspiration='I want to follow new topics without having to guess at instructions.',
    priority='Could we try a vocabulary or instruction-checking approach?',
    actions=['language_support','tutoring','learning_access']),
 'peer_bullying': dict(
    overview='A few students have been making comments that make school uncomfortable.',
    timeline='It began a few weeks ago and has happened on more than one day.',
    pattern='It happens mainly around breaks, not in every lesson.',
    example='Someone mocked my answer when I was walking out of class.',
    impact='I sometimes stay away from shared spaces and feel tense during the day.',
    attempt='I moved away from them, but that did not settle the situation.',
    constraint='I worry that a public confrontation could make things worse.',
    misconception='I am not saying everyone in my class is involved.',
    uncertainty='I do not know whether a staff member witnessed the incidents.',
    aspiration='I want to feel safe enough to concentrate on lessons.',
    priority='Can we discuss a safe way to tell the right staff without making it public?',
    actions=['wellbeing_checkin','family_liaison','peer_support']),
 'friendship_conflict': dict(
    overview='I had a disagreement with friends and now group work feels awkward.',
    timeline='It happened after a group project two weeks ago.',
    pattern='It is mainly difficult when we have to work together.',
    example='Last week no one answered when I asked which section I should do.',
    impact='I have stopped contributing as much in that class.',
    attempt='I tried sending a message to clear things up, but it did not resolve much.',
    constraint='I do not want a forced meeting if the others are not willing.',
    misconception='I am not asking the school to decide that one person is entirely wrong.',
    uncertainty='I do not know what the others think about discussing it.',
    aspiration='I want group work to be manageable even if we are not close friends.',
    priority='Could we discuss options without requiring everyone to meet?',
    actions=['peer_support','wellbeing_checkin','attendance_planning']),
 'exam_pressure': dict(
    overview='I get very worried before tests, and then I cannot show what I know.',
    timeline='The worry grew after two disappointing marks.',
    pattern='It is worse before timed assessments than during ordinary classwork.',
    example='I revised the night before but froze when I saw the first question.',
    impact='I sometimes avoid revision because it reminds me of the test.',
    attempt='I tried making a timetable but it had too much in it.',
    constraint='I need a plan small enough to follow.',
    misconception='I do want to sit the tests; I am not trying to get out of them.',
    uncertainty='I do not know whether my test marks reflect what I actually understand.',
    aspiration='I would like a calmer way to prepare and start questions.',
    priority='Could we practise a manageable revision routine?',
    actions=['tutoring','wellbeing_checkin','homework_support']),
 'learning_access': dict(
    overview='I have trouble following lessons when instructions come all at once.',
    timeline='I have noticed it more since the timetable became busier.',
    pattern='One step at a time is easier for me than several spoken directions.',
    example='I completed the first part but forgot what the next two tasks were.',
    impact='I lose time and sometimes look like I am not paying attention.',
    attempt='I write short reminders, but I do not always catch every instruction.',
    constraint='I would rather explore practical adjustments before making assumptions about why this happens.',
    misconception='This does not mean I have a diagnosis or that I cannot do the work.',
    uncertainty='I do not know what adjustments a teacher can reasonably offer.',
    aspiration='I would like to know the steps clearly and finish more tasks.',
    priority='Could we try a written checklist or smaller steps?',
    actions=['learning_access','tutoring','homework_support']),
 'health_appointments': dict(
    overview='I have been absent for appointments and then I struggle to catch up.',
    timeline='The appointments became more frequent this term.',
    pattern='They are not on a fixed school day.',
    example='I missed a practical lesson when an appointment ran late.',
    impact='I return with missing notes and do not know what to prioritise.',
    attempt='I have asked classmates for notes, but they do not cover everything.',
    constraint='I prefer not to discuss private medical details in this meeting.',
    misconception='I am not saying I am unable to attend school most days.',
    uncertainty='I do not know the dates of all future appointments.',
    aspiration='I want a way to catch up that does not require explaining personal health details.',
    priority='Can we agree how work will be shared after authorised absences?',
    actions=['attendance_planning','homework_support','wellbeing_checkin']),
 'low_motivation': dict(
    overview='I feel disconnected from some lessons and have stopped trying as much.',
    timeline='The feeling has built up over the last couple of months.',
    pattern='I am more interested in practical activities than long written tasks.',
    example='I left a worksheet unfinished even though I had enough time.',
    impact='My marks are slipping and teachers have noticed I am quieter.',
    attempt='I tried setting a study goal, but it felt too big to keep going.',
    constraint='Being told to just try harder does not give me a starting point.',
    misconception='I do have interests and goals outside this difficult subject.',
    uncertainty='I am not sure whether the problem is boredom, confusion or both.',
    aspiration='I want to find a reason to keep up with the parts of school that matter.',
    priority='Could we work out one achievable goal for the next week?',
    actions=['wellbeing_checkin','tutoring','homework_support']),
 'school_transfer': dict(
    overview='I changed schools and the topics do not line up with what I studied before.',
    timeline='I joined this school earlier in the term.',
    pattern='Some subjects match, while others use books I have not seen.',
    example='The class referred to a project that started before I arrived.',
    impact='I feel as if I am behind even in subjects I used to enjoy.',
    attempt='I asked for the notes but received only part of the material.',
    constraint='I cannot immediately redo every lesson from the previous term.',
    misconception='Changing schools does not mean I am a new learner in every subject.',
    uncertainty='I do not know which earlier modules are essential to catch up on.',
    aspiration='I want to understand the new school routine and keep my subjects on track.',
    priority='Could someone map the missing topics and help me settle in?',
    actions=['reentry_support','tutoring','attendance_planning']),
 'attendance_dispute': dict(
    overview='Some attendance marks look wrong, and I think this is affecting how teachers see me.',
    timeline='I first noticed the issue when I saw the attendance summary last week.',
    pattern='I am not disputing every absence, just a couple of entries.',
    example='On one morning I arrived late, but the record appears to show a full absence.',
    impact='I feel unfairly judged and less comfortable asking for help.',
    attempt='I mentioned it to a teacher but do not know whether it was checked.',
    constraint='I do not have written proof for every late arrival.',
    misconception='Some of the other absences are real; I am not denying those.',
    uncertainty='The register needs checking before anyone knows the correct count.',
    aspiration='I would like the record reviewed and then a fair discussion about attendance.',
    priority='Please check the disputed dates instead of changing them just on my word.',
    actions=['attendance_planning','family_liaison']),
 'classroom_noise': dict(
    overview='It is hard for me to focus when the classroom is noisy.',
    timeline='It became more difficult after we moved rooms.',
    pattern='Quiet independent work is easier than crowded group activities.',
    example='I missed part of a demonstration because people were talking nearby.',
    impact='I ask for things to be repeated and sometimes fall behind.',
    attempt='I moved closer to the front once and could follow better.',
    constraint='I cannot choose a quiet place in every classroom.',
    misconception='I am not saying other students are always causing trouble.',
    uncertainty='I do not know which seating changes are possible.',
    aspiration='I want to hear instructions clearly and finish classwork.',
    priority='Could we ask about a quieter working spot or written directions?',
    actions=['learning_access','tutoring','wellbeing_checkin']),
 'missed_coursework': dict(
    overview='I have several unfinished assignments and do not know which to start with.',
    timeline='The backlog grew over a few weeks after I missed deadlines.',
    pattern='I can start small tasks, but bigger assignments make me stop.',
    example='I opened the project brief and could not decide what the first step was.',
    impact='I avoid checking the platform because the list makes me anxious.',
    attempt='I wrote down the deadlines, but I did not rank them.',
    constraint='I cannot realistically finish everything tonight.',
    misconception='A late assignment does not mean I did no work at all.',
    uncertainty='I do not know which deadlines can still be negotiated.',
    aspiration='I want a realistic order for finishing the most important work.',
    priority='Could we break the backlog into a short, agreed plan?',
    actions=['homework_support','tutoring','attendance_planning']),
 'part_time_work': dict(
    overview='I sometimes help with paid work outside school and feel exhausted afterward.',
    timeline='The work hours increased recently because the household needed help.',
    pattern='Some evenings are much later than others.',
    example='After a late shift I struggled to stay awake during morning revision.',
    impact='Homework takes longer and I occasionally arrive late.',
    attempt='I tried doing homework earlier, but the hours change unexpectedly.',
    constraint='I do not want to make commitments about work hours I cannot control.',
    misconception='I am not asking to leave education; I want a workable balance.',
    uncertainty='I cannot confirm what the next month of work will look like.',
    aspiration='I want enough rest and time to complete schoolwork.',
    priority='Can we talk about support with the timetable and family pressures?',
    actions=['family_liaison','family_finances','attendance_planning']),
 'safety_route': dict(
    overview='I feel uncomfortable on part of the route to school.',
    timeline='It has been concerning me since an incident near the crossing last month.',
    pattern='It is worse when I have to travel alone at an early time.',
    example='I waited for other people instead of using the crossing on my own.',
    impact='I can arrive late and feel distracted once I reach school.',
    attempt='I tried another path, but it takes substantially longer.',
    constraint='I do not want to give details in front of other students.',
    misconception='This is about feeling safe on the route, not about disliking school.',
    uncertainty='I am not sure if the council or school has already reviewed that location.',
    aspiration='I want a route that feels safe enough to use consistently.',
    priority='Could an appropriate adult help assess options without making assumptions?',
    actions=['transport_assessment','wellbeing_checkin','family_liaison']),
}

DIALOGUE_SUPPORTS={
 'tutoring': [
    ('If tutoring were available, what topic would you want to start with?', 'The first topic I stopped understanding, not the hardest chapter.'),
    ('Would short practice with feedback help more than another lecture?', 'Yes, I would like to try a few problems and see where I go wrong.'),
    ('How long could you concentrate on one practice block?', 'About twenty minutes, with a short break if I need it.'),
    ('Is it easier to ask questions alone or in a small group?', 'A small group might be okay, but one-to-one would feel safer at first.'),
    ('What would tell you that practice was useful?', 'If I can explain a step without reading the answer.'),
    ('Could we begin with one worked example rather than assuming you know the earlier steps?', 'Yes, starting slowly would help.'),
    ('Would you rather take home a short practice sheet or use an online exercise?', 'A short paper sheet would be more reliable for me.'),
    ('How should we respond if the first tutoring approach does not work?', 'Try a different explanation rather than just giving more of the same.'),
    ('Would a trial session be okay before committing to several sessions?', 'Yes, I would like to try it first.'),
 ],
 'family_liaison': [
    ('Would a conversation with a family liaison worker be helpful?', 'Maybe, if I understand what would be discussed first.'),
    ('What would you feel comfortable sharing with a family member?', 'The school difficulties, but not every personal thing I said today.'),
    ('Is there a trusted adult you would prefer us to contact?', 'There is someone at home, but I would like to speak with them first.'),
    ('Would a phone call or a meeting be easier for the family?', 'A phone call may fit better, depending on work hours.'),
    ('Do you want to help decide the wording of the first message?', 'Yes, I do not want it to sound as if I am being reported.'),
    ('What questions should a liaison worker avoid assuming answers to?', 'They should not assume the adults at home do not care.'),
    ('Should we check whether an interpreter or another communication option is needed?', 'We can ask rather than assuming.'),
    ('What would a useful family-school conversation achieve?', 'A realistic agreement on what each person can manage.'),
    ('If there is disagreement about the situation, what would help?', 'Hear both sides and check the records instead of picking a side.'),
 ],
 'transport_assessment': [
    ('Can we map the journey you usually take to school?', 'I normally use the bus and walk the last part.'),
    ('Would you be able to tell the support office which route you use?', 'Yes, although I might need to check the route number.'),
    ('Are the costs, reliability, or safety of the journey your main concern?', 'The problem is not the same every day; I would like someone to ask about each part.'),
    ('Would you be willing to keep a short record of travel difficulties?', 'I could write down the date and what happened.'),
    ('Do you know whether a pass or travel programme already exists?', 'No, I have not been given that information.'),
    ('Should the office check eligibility before asking your family for documents?', 'Yes, I would prefer to know what is required.'),
    ('Would a change in arrival arrangements help while the route is reviewed?', 'It might, but the teacher would need to agree.'),
    ('What would you do if transport help were not available?', 'I would still need to discuss an alternative plan.'),
    ('What information should remain marked as uncertain?', 'The number of days affected and whether any programme covers my journey.'),
 ],
 'family_finances': [
    ('Would you like information about school-related financial support?', 'Yes, but I do not want to promise that we qualify.'),
    ('Which school expense feels most urgent to discuss?', 'The expense that has been stopping me from taking part.'),
    ('Would you prefer to review general options before involving home?', 'Yes, I would like to understand them first.'),
    ('Do you have confirmed information about household income?', 'No, I do not know the exact amount.'),
    ('Is there a trusted adult who could review application requirements?', 'Probably, if the information is clear.'),
    ('How would you feel about an eligibility assessment?', 'I would consider it if someone explains what is recorded.'),
    ('What should we avoid promising today?', 'That money or a fee waiver is guaranteed.'),
    ('Would help with materials be useful even if other financial support is unavailable?', 'Yes, that could remove one practical difficulty.'),
    ('What kind of update would help you feel informed?', 'A simple answer about what has been checked and what has not.'),
 ],
 'attendance_planning': [
    ('Would it help to separate recorded attendance from the reasons behind it?', 'Yes, some marks and some reasons need checking.'),
    ('Can we identify the hardest point in the school morning?', 'Usually the first part, before I reach the classroom.'),
    ('Would an agreed way to report a delay be useful?', 'Yes, then staff would know what happened.'),
    ('Do you want to check the register together for specific dates?', 'Yes, but I may not remember every date precisely.'),
    ('Would an attendance goal for next week feel manageable?', 'A small goal would be better than asking for perfect attendance overnight.'),
    ('How should school respond if an agreed plan does not work?', 'Ask what happened instead of assuming I gave up.'),
    ('Could a teacher provide missed work in a predictable way?', 'That would make returning easier.'),
    ('Do you need a way to explain late arrival privately?', 'Yes, I do not want to explain it to the whole class.'),
    ('Would you be okay reviewing the plan after one week?', 'Yes, one week is enough to see whether it is practical.'),
 ],
 'wellbeing_checkin': [
    ('Would you feel comfortable having a regular private check-in at school?', 'Maybe. I would like to know who I would speak with.'),
    ('What makes it easier for you to talk when something is difficult?', 'Having time and not being interrupted.'),
    ('Do you prefer practical problem-solving or space to talk first?', 'Talking first, then we can think about a plan.'),
    ('Are there places at school where you currently feel comfortable?', 'There are a couple of rooms where it is quieter.'),
    ('Would you like me to explain which concerns staff may need to share for safety?', 'Yes, I want to know how that works.'),
    ('How would you recognise a helpful check-in?', 'I would feel heard and know what to do next.'),
    ('Would it help to identify an adult you can approach between appointments?', 'Yes, especially on difficult days.'),
    ('Can we avoid deciding today what is causing every feeling?', 'Yes, I am still figuring it out.'),
    ('Would you prefer a written reminder of the next contact?', 'A small note would help me remember.'),
 ],
 'homework_support': [
    ('Would you like to sort unfinished tasks by priority rather than by age?', 'Yes, the oldest task is not always the most urgent.'),
    ('Could you show me how you currently track assignments?', 'I have a list but it is mixed up.'),
    ('What size of homework task feels possible on a normal evening?', 'Something I can finish in twenty or thirty minutes.'),
    ('Would checking with teachers about which deadlines remain active help?', 'Yes, I do not know which tasks still count.'),
    ('Would you prefer a paper planner or the school platform?', 'A paper planner would be easier to see every day.'),
    ('What usually interrupts your homework time?', 'Sometimes other responsibilities or just not knowing how to begin.'),
    ('Could we break one assignment into a first action and a next action?', 'Yes, that sounds less overwhelming.'),
    ('How would you know when to ask for help instead of getting stuck?', 'If I cannot make progress after trying a few minutes.'),
    ('Would a short check-in on completed steps be useful?', 'Yes, as long as it is not another stressful deadline.'),
 ],
 'learning_access': [
    ('Would written instructions alongside spoken ones make tasks easier?', 'I think so. I can check them again if I lose my place.'),
    ('Do you want to try breaking instructions into numbered steps?', 'Yes, that would be clearer.'),
    ('Are there seating or classroom arrangements you want to discuss?', 'Possibly, if they are not too noticeable.'),
    ('What kind of example is easiest for you to follow?', 'One worked through slowly, with the steps shown.'),
    ('Would you be comfortable with a short learning-support discussion?', 'Yes, as long as no one decides I have a condition from one conversation.'),
    ('Should we ask teachers which adjustments they can actually provide?', 'Yes, I would rather have a realistic arrangement.'),
    ('What if one change helps in maths but not in another subject?', 'Then we should review subjects separately.'),
    ('Would an informal trial of a checklist be acceptable?', 'That would be okay.'),
    ('How should your feedback be collected after trying a change?', 'Just ask whether I followed the instructions more easily.'),
 ],
 'device_access': [
    ('What equipment do assignments require most often?', 'Mostly a browser and a way to upload files.'),
    ('Would school computer access help if a slot were available?', 'Yes, but I would need to know the opening times.'),
    ('Do you know whether the school has any loan devices?', 'No, I have never asked.'),
    ('Can you work offline and upload later for some assignments?', 'Sometimes, but it depends on what the teacher allows.'),
    ('Would checking teacher-approved paper alternatives be useful?', 'Yes, that could prevent missing-work marks.'),
    ('Is shared-device access predictable from one week to another?', 'Not always, and I cannot use it whenever I need.'),
    ('Would a device-assessment referral require a family conversation?', 'I would like to hear the rules before contacting home.'),
    ('What is the most important online task to make possible?', 'Submitting my own work on time.'),
    ('What if equipment is not available immediately?', 'I would want a temporary way to submit work.'),
 ],
 'school_meals': [
    ('Would you like to learn what meal or breakfast arrangements the school offers?', 'Yes, I do not know all the options.'),
    ('Would a quiet conversation about eligibility be preferable?', 'Yes, I would rather not discuss it in front of classmates.'),
    ('Do you know which forms or permissions might be required?', 'No, that would have to be checked.'),
    ('Would information about today’s provision be useful separately from longer-term aid?', 'Yes, especially if it is already available to students.'),
    ('Should the support office check the current criteria?', 'Yes, I do not want someone to assume I am eligible.'),
    ('What would make a school meal option practical for you?', 'Knowing when and where it is offered.'),
    ('Would you want a family member involved in a formal application?', 'If needed, but please explain it to me first.'),
    ('What would you like staff to understand about concentration in morning lessons?', 'Sometimes I am distracted by being hungry, not the subject.'),
    ('How would you like a decision about meal support communicated?', 'Privately and clearly.'),
 ],
 'language_support': [
    ('Would reviewing important subject words before a lesson be useful?', 'Yes, I could understand the instructions faster.'),
    ('Do you prefer hearing an example or seeing a written one?', 'Usually both together.'),
    ('Could you show a question that was difficult because of its wording?', 'Yes, I have one in my notebook.'),
    ('Would a small vocabulary list each week be manageable?', 'Yes, if it is not too long.'),
    ('Do you want extra time to ask about unfamiliar instructions?', 'Yes, without holding up the whole class.'),
    ('Should we avoid making assumptions about which languages you speak?', 'Please ask me rather than guessing.'),
    ('Would you like the teacher to check understanding of instructions privately?', 'That could help.'),
    ('What would show the support is useful?', 'I would answer more of the question instead of guessing what it means.'),
    ('If the extra vocabulary list is not enough, what next?', 'We could try another explanation or more practice.'),
 ],
 'peer_support': [
    ('Would speaking with a trusted peer or staff-facilitated group be helpful?', 'Maybe, but I do not want to be forced into a conversation.'),
    ('How much contact would feel comfortable right now?', 'A small amount, and only with people I trust.'),
    ('Would you prefer a staff member to help with group arrangements?', 'Yes, especially at the beginning.'),
    ('What should staff avoid doing?', 'Do not announce my situation to the whole class.'),
    ('Would an alternative group-work arrangement help temporarily?', 'Yes, while we work out what is practical.'),
    ('Do you know a peer you already feel safe working with?', 'There may be one person, but I want to ask them first.'),
    ('What would make a meeting feel voluntary?', 'Knowing I can say no and still get help.'),
    ('Should we separate an immediate safety concern from an ordinary disagreement?', 'Yes, those are not the same thing.'),
    ('How would you like feedback about any arrangement?', 'Privately and without blaming anyone beforehand.'),
 ],
 'reentry_support': [
    ('Could we map the topics covered before and after your school change?', 'Yes, then I could see what I actually missed.'),
    ('Are there routines here that still feel unfamiliar?', 'The assignment platform and some of the lesson times.'),
    ('Would a timetable guide or a buddy system be helpful?', 'A guide would be good. I am not sure about a buddy yet.'),
    ('Can we ask teachers for the essential earlier materials?', 'Yes, the main topics would be enough to begin.'),
    ('What do you already know well that we should not make you repeat?', 'Some of the basics from my previous school.'),
    ('Would one point of contact for questions help?', 'Yes, I get different answers from different people.'),
    ('How should we prioritise catching up?', 'The topics needed for next week’s lessons first.'),
    ('If a subject follows a different syllabus, what would help?', 'A short comparison of what changed.'),
    ('Could we review how settled you feel after another week?', 'Yes, I will probably know more by then.'),
 ],
}

DIALOGUE_SECONDARIES={
 'math_confidence': [
    ('How is your confidence in maths at the moment?', 'Lower than last term, especially when the teacher moves quickly.'),
    ('Would looking at one missing prerequisite be manageable?', 'Yes, I do not want another huge pile of work.'),
    ('Have you told your maths teacher where you get stuck?', 'Not yet; I find it awkward to interrupt.'),
    ('Should we keep the maths concern separate from the original attendance issue?', 'Yes, both matter but they are not identical.'),
 ],
 'missed_notes': [
    ('What happens to class notes when you miss a lesson?', 'I usually receive only a photo of someone’s page.'),
    ('Does that give you enough context to understand the topic?', 'Not always; it misses what the teacher explained aloud.'),
    ('Would a short catch-up summary from staff be useful?', 'Yes, if it says which part to do first.'),
    ('Should we check what the teacher can realistically share?', 'Yes, I do not expect someone to rewrite every lesson.'),
 ],
 'quiet_place': [
    ('Do you have a place where you can usually concentrate after school?', 'Sometimes, but there can be a lot going on at home.'),
    ('Would school study space help if it fits your schedule?', 'Possibly, depending on the time.'),
    ('Does noise interfere every evening?', 'No, some evenings are easier.'),
    ('Should we treat that as a separate study-access concern?', 'Yes, it affects homework rather than getting to school.'),
 ],
 'teacher_contact': [
    ('Is there a teacher you already feel comfortable approaching?', 'There is one, but I have not spoken about this.'),
    ('What would make that conversation easier?', 'Knowing what to say before I go.'),
    ('Would a short written question help you start?', 'Yes, I could show it if I get nervous.'),
    ('Should we ask before sharing your details with that teacher?', 'Please do.'),
 ],
 'exam_worry': [
    ('Have upcoming tests added pressure?', 'Yes, I worry about catching up before the next one.'),
    ('What happens when you try to revise?', 'I sometimes jump between topics without finishing one.'),
    ('Would a smaller revision target help?', 'Probably; one topic a day feels possible.'),
    ('Should we avoid interpreting that as not caring?', 'Yes, I do care about the result.'),
 ],
 'online_uploads': [
    ('Have online submissions been working reliably for you?', 'Not every time; I have had trouble with the platform.'),
    ('Is the problem finishing the work or sending it?', 'Sometimes the work is complete but not uploaded.'),
    ('Could we check one assignment status rather than guessing?', 'Yes, I can show the saved file.'),
    ('Should we confirm the teacher’s accepted submission method?', 'That would help.'),
 ],
 'morning_routine': [
    ('How predictable is your morning routine?', 'It changes on some days, so I cannot always plan well.'),
    ('Is the same reason behind every late arrival?', 'No, that would be too simple.'),
    ('Would writing down two or three mornings help us see a pattern?', 'Yes, I could try that.'),
    ('What should we avoid concluding before checking?', 'That I am always late because I chose to be.'),
 ],
 'belonging': [
    ('Do you feel connected to other people at school?', 'Some days, but I do not have a big group of friends.'),
    ('Is there an activity that makes school feel better?', 'I enjoy one practical class.'),
    ('Would joining another activity interest you?', 'Maybe, as long as it does not add too much pressure.'),
    ('Should we avoid assuming you are isolated all the time?', 'Yes, it is not like that every day.'),
 ],
 'deadline_confusion': [
    ('Are assignment deadlines clear to you?', 'Sometimes the platform and what I hear in class do not match.'),
    ('Could we verify one deadline together?', 'Yes, I brought the assignment list.'),
    ('Would a weekly task check be useful?', 'That would help me avoid guessing.'),
    ('Should we label any uncertain dates as needing confirmation?', 'Definitely.'),
 ],
 'fatigue': [
    ('Have you been feeling tired in lessons?', 'More than usual, but not every day.'),
    ('Have you noticed a particular pattern?', 'It can be worse after an unsettled evening.'),
    ('Would you like to talk about practical school supports without discussing private details?', 'Yes, that would be better.'),
    ('Should we avoid guessing at the cause of tiredness?', 'Yes, I do not know exactly why either.'),
 ],
 'attendance_record': [
    ('Do the dates in the attendance register match your memory?', 'One date looks wrong, but I am not sure about the others.'),
    ('Could you say which entry should be checked first?', 'The day I arrived late after the first class.'),
    ('Should the office verify the entry before changing it?', 'Yes, I understand it needs checking.'),
    ('Does a record correction by itself solve the original difficulty?', 'No, we still need to work on that.'),
 ],
}

DIALOGUE_INTRO=[
 ('Thanks for coming. Is it okay if we talk about how school has been going?', 'Yes, though I am not sure where to start.'),
 ('This is to understand what support might be useful, not to decide you have done something wrong. How does that sound?', 'That helps. I was worried I might be in trouble.'),
 ('We can distinguish things you know, things you think, and things we still need to check. Is that fair?', 'Yes, because I do not know every detail.'),
 ('What would you most like to get from today’s conversation?', 'I want a practical next step instead of just another warning.'),
 ('You can tell me when a question feels too personal. Are you comfortable continuing?', 'Yes. I might skip a few details.'),
 ('Is there something at school that is still going reasonably well?', 'There are lessons I enjoy, even though other things are difficult.'),
]

DIALOGUE_CORE_GENERAL=[
 ('What has a relatively good school day looked like recently?', 'I get here, know what I am doing, and can follow the first lesson.'),
 ('How does a more difficult day usually begin?', 'There is usually something unexpected before I can settle down.'),
 ('Has the problem affected every subject equally?', 'No, it is more noticeable in some lessons than others.'),
 ('How do you respond when you realise you have fallen behind?', 'Sometimes I try to catch up quietly, and sometimes I stop asking.'),
 ('Have you already explained part of this to another adult at school?', 'A little, but I did not explain the whole situation.'),
 ('What do you think a teacher notices from the outside?', 'They probably notice the missed work more than the reason for it.'),
 ('Is there anything we might be misunderstanding from the attendance or homework record?', 'Possibly. It would be better to check particular dates than guess.'),
 ('How certain are you about the timing of all this?', 'I remember some examples clearly but not every date.'),
 ('What has helped even briefly?', 'When I get a clear next step, I feel less stuck.'),
 ('What kind of response from school would make things harder?', 'Being called out in front of everyone would be difficult.'),
 ('Do you want your explanation written down as something you reported, rather than as a verified fact?', 'Yes, that is more accurate.'),
 ('Would it be fair to say there may be more than one reason for the difficulty?', 'Yes, I do not think one answer explains everything.'),
 ('Which part of the problem feels within your control?', 'I can try a plan, but I cannot control every circumstance.'),
 ('What would be unfair for us to assume about your family or motivation?', 'That people do not care just because something went wrong.'),
 ('If school records disagree with your recollection, how should we handle it?', 'Check the evidence first, and let me explain the date.'),
]

DIALOGUE_SECONDARY_GENERAL=[
 ('Apart from the main difficulty, is there another small thing affecting your school day?', 'There are a few smaller things, but I want to keep them separate.'),
 ('Which of those is most urgent for the next week?', 'The one that makes tomorrow’s lessons harder.'),
 ('Would dealing with everything at once be realistic?', 'No, I would rather start with one or two things.'),
 ('Have you noticed whether this changes between weekdays?', 'It does change, so one day might not describe the whole week.'),
 ('What information would help clarify this extra concern?', 'A specific date or a conversation with the teacher might help.'),
 ('Is that something you have directly seen, or something you have been told?', 'Some of it I saw myself; the rest needs checking.'),
 ('How would you prefer another staff member to hear about it?', 'A short accurate summary, not a dramatic story.'),
 ('Can we mark anything you are unsure about as unknown for now?', 'Yes. I do not want to make up an answer.'),
 ('Would a practical adjustment be more useful than a big promise?', 'Yes, I would rather start with something possible.'),
]

DIALOGUE_SUPPORT_GENERAL=[
 ('What would make an extra support session worth your time?', 'It would need to address a real obstacle, not just add another appointment.'),
 ('Is there a time in the school week when a short session could work?', 'Lunch or a planned break could work, depending on the day.'),
 ('Would you rather try one step and review it than commit indefinitely?', 'Yes, I would like to know whether it is useful first.'),
 ('Do you have any concerns about teachers or family members being contacted?', 'I would like to know what will be shared and why.'),
 ('If the first option is unavailable, would you want us to discuss alternatives?', 'Yes, but please be clear that alternatives are not guaranteed.'),
 ('How should we know whether a plan is practical for you?', 'Ask whether I can actually attend or use it, not just whether I agreed.'),
 ('Would it help to write down which parts are still waiting for confirmation?', 'Yes, then I will not mistake a possibility for a promise.'),
 ('Can we separate requesting help from actually receiving it?', 'Yes, I know those are different things.'),
 ('Do you want to be involved in deciding what information gets passed to support staff?', 'As much as possible, yes.'),
 ('If support is offered but you cannot take it up, what should happen?', 'I would like someone to ask about the timing or reason.'),
 ('Should we review what has been tried instead of assuming it worked?', 'Yes. Something being offered does not mean it helped.'),
 ('If there is a waiting list, what information would be useful?', 'Whether my request is on it and when it will be reviewed.'),
]

DIALOGUE_CLOSING=[
 ('Can I summarise what I heard and you tell me if I missed something?', 'Yes, I would like to check the wording.'),
 ('What should I record as your account rather than as a confirmed fact?', 'The examples I told you about that have not been checked.'),
 ('Which part of today’s discussion feels most useful?', 'Understanding what is possible and what still needs checking.'),
 ('Is there anything you want corrected in the summary?', 'Please do not make it sound as if we have checked facts that are still uncertain.'),
 ('Do you know who you can approach if the situation changes before the next meeting?', 'I can come back to you or ask the support office.'),
 ('Would a brief follow-up next week be reasonable?', 'Yes, unless the timetable needs changing.'),
 ('What should we check at that follow-up?', 'Whether anything has changed, and whether the approach still makes sense.'),
 ('Is there anything else you want to add before we finish?', 'Not right now. Thank you for listening.'),
]

DIALOGUE_STATUS={
 'inquiry_pending': (
   ('At this point I can only make an inquiry; I cannot say that the support has been approved. Is that clear?', 'Yes, an inquiry is not the same as receiving the support.'),
   ('I will record the request as pending a response from the relevant team.', 'Please let me know what they say, even if it is a no.'),
 ),
 'information_only': (
   ('Would you prefer information first rather than making a request today?', 'Yes, I want to understand the options before deciding.'),
   ('I will record that we discussed options but did not submit an application or arrange a service.', 'That matches what we agreed.'),
 ),
 'declined': (
   ('Do you want to take up the proposed extra support now?', 'Not at the moment. I would like time to think about it.'),
   ('I will record that you declined the offer today, not that the underlying concern is resolved.', 'Thank you. I might ask again later.'),
 ),
 'assessment_requested': (
   ('Would you like me to request an assessment of available support, without assuming the outcome?', 'Yes, an assessment would be useful.'),
   ('I will record your agreement to the assessment request. Eligibility and any service are still unconfirmed.', 'Okay. Please tell me what information is needed.'),
 ),
 'followup_planned': (
   ('Would you be willing to review the idea again after checking your timetable?', 'Yes, I can check and come back with an answer.'),
   ('I will mark a follow-up discussion as planned; no additional service has been booked.', 'That is accurate.'),
 ),
}

DIALOGUE_TOPIC_QUESTIONS=[
 ('What first made you notice the difficulty?', 'overview'),
 ('When did it become more noticeable?', 'timeline'),
 ('Does it affect every day in the same way?', 'pattern'),
 ('Can you describe one particular occasion without guessing at other days?', 'example'),
 ('What happens to learning or attendance afterward?', 'impact'),
 ('What have you already tried yourself?', 'attempt'),
 ('What is outside your control here?', 'constraint'),
 ('What would be a mistaken conclusion from that story?', 'misconception'),
 ('Which details are still unknown or need checking?', 'uncertainty'),
 ('If we look ahead a little, what would you like school to feel like?', 'aspiration'),
 ('What should be the first question we try to resolve?', 'priority'),
]
