/**
 * Google Apps Script: CvSU-Imus 50-Respondent ISO/IEC 25010 Evaluation Form Builder & In-Place Updater
 * Project: AI-Driven Enrollment Scheduler for Irregular Students (CvSU - Imus Campus)
 *
 * TWO FUNCTIONS INCLUDED:
 *   1. updateExistingCvsuForm()  -> RECOMMENDED IF YOU ALREADY CREATED THE FORM!
 *      Safely adds the missing Chapter 1 & Chapter 3 items (Gender, Prior Experience,
 *      SOP 7.5 Scheduling & Conflict-Resolution Effectiveness, Time Spent, and Modified SUS)
 *      directly into your existing Google Form WITHOUT changing your form URL or Google Sheet.
 *
 *   2. createCvsuEvaluationForm() -> Creates a brand-new complete form + linked Sheet from scratch.
 */

var EXISTING_FORM_ID = '14cPyav_nEkysjM40lQCzbFZhR_0C1fK064VgjunC36E';

var LIKERT_COLUMNS = [
  '1 - Strongly Disagree',
  '2 - Disagree',
  '3 - Neutral',
  '4 - Agree',
  '5 - Strongly Agree'
];

/**
 * Safely upgrades your existing Google Form IN-PLACE (keeps the exact same link, QR code,
 * section branching, and linked Google Sheet). Idempotent: safe to run once or re-run.
 */
function updateExistingCvsuForm() {
  var form = FormApp.openById(EXISTING_FORM_ID);

  function hasItemTitled(titlePrefix) {
    var items = form.getItems();
    for (var i = 0; i < items.length; i++) {
      if (items[i].getTitle().indexOf(titlePrefix) === 0) {
        return true;
      }
    }
    return false;
  }

  function findItemIndexByTitle(titlePrefix) {
    var items = form.getItems();
    for (var i = 0; i < items.length; i++) {
      if (items[i].getTitle().indexOf(titlePrefix) === 0) {
        return items[i].getIndex();
      }
    }
    return -1;
  }

  // -------------------------------------------------------------------------
  // 1. Add missing Chapter 3 (p. 12) Demographic items into Section 2
  // -------------------------------------------------------------------------
  if (!hasItemTitled('Gender / Sex')) {
    var ageIdx = findItemIndexByTitle('Age Group');
    var genderItem = form.addListItem()
      .setTitle('Gender / Sex')
      .setChoiceValues(['Male', 'Female', 'Prefer not to say'])
      .setRequired(true);
    if (ageIdx !== -1) {
      form.moveItem(genderItem.getIndex(), ageIdx + 1);
    }
  }

  if (!hasItemTitled('Prior Experience with Manual Course Plotting')) {
    var yrIdx = findItemIndexByTitle('Year Level / Professional Standing');
    var expItem = form.addListItem()
      .setTitle('Prior Experience with Manual Course Plotting / Registration Portals')
      .setHelpText('Select the option that best describes your prior experience with irregular course scheduling.')
      .setChoiceValues([
        'No prior irregular scheduling experience',
        '1 - 2 semesters of manual schedule plotting',
        '3 or more semesters of manual schedule plotting',
        'Academic / registration advising experience',
        'IT / software system evaluation background'
      ])
      .setRequired(true);
    if (yrIdx !== -1) {
      form.moveItem(expItem.getIndex(), yrIdx + 1);
    }
  }

  // -------------------------------------------------------------------------
  // 2. Add SOP 7.5 Dedicated Grid + Experience/Time Spent + Modified SUS
  //    right before the "Technical Evaluation Checkpoint" item in Section 3
  // -------------------------------------------------------------------------
  if (!hasItemTitled('3G. Scheduling and Conflict-Resolution Effectiveness')) {
    var cpIdx1 = findItemIndexByTitle('Technical Evaluation Checkpoint');
    var sop75Grid = form.addGridItem()
      .setTitle('3G. Scheduling and Conflict-Resolution Effectiveness (SOP 7.5)')
      .setHelpText('Evaluates overall effectiveness in automating prerequisite checking, resolving conflicts, and generating usable schedules.')
      .setRows([
        '1. The system significantly reduces the time and effort needed to formulate a valid semester schedule compared to manual plotting.',
        '2. The Automated Prerequisite Validation reliably prevents enrollment in subjects with unmet prerequisite chains.',
        '3. The CSP solver and Dynamic Section-Swapping Engine effectively resolve overlapping lecture/laboratory schedules and closed sections.',
        '4. The generated Master Schedule layout clearly presents all required enrollment details (subject codes, sections, units, rooms, and meeting times) for adviser sign-off.'
      ])
      .setColumns(LIKERT_COLUMNS)
      .setRequired(true);
    if (cpIdx1 !== -1) {
      form.moveItem(sop75Grid.getIndex(), cpIdx1);
    }
  }

  if (!hasItemTitled('Estimated Time Spent Configuring Availability')) {
    var cpIdx2 = findItemIndexByTitle('Technical Evaluation Checkpoint');
    var timeItem = form.addMultipleChoiceItem()
      .setTitle('Estimated Time Spent Configuring Availability and Generating a Conflict-Free Schedule')
      .setHelpText('Approximate time it took you to complete Steps 1 to 3 during testing.')
      .setChoiceValues([
        'Less than 1 minute',
        '1 to 2 minutes',
        '3 to 5 minutes',
        'More than 5 minutes'
      ])
      .setRequired(true);
    if (cpIdx2 !== -1) {
      form.moveItem(timeItem.getIndex(), cpIdx2);
    }
  }

  if (!hasItemTitled('3H. Perceived Usability and Adoption (Modified SUS)')) {
    var cpIdx3 = findItemIndexByTitle('Technical Evaluation Checkpoint');
    var susGrid = form.addGridItem()
      .setTitle('3H. Perceived Usability and Adoption (Modified SUS)')
      .setHelpText('Modified System Usability Scale (SUS) items measuring confidence and willingness to adopt the system.')
      .setRows([
        '1. I would want to use this AI-Driven Enrollment Scheduler regularly during semesterly enrollment.',
        '2. I felt confident using the scheduler and Monday-Saturday toggle matrix without needing technical assistance.',
        '3. Overall, the system is noticeably more convenient and accurate than manual irregular schedule plotting.'
      ])
      .setColumns(LIKERT_COLUMNS)
      .setRequired(true);
    if (cpIdx3 !== -1) {
      form.moveItem(susGrid.getIndex(), cpIdx3);
    }
  }

  Logger.log('==================================================================');
  Logger.log('SUCCESS! Existing Form Updated In-Place (Same URL & Linked Sheet!)');
  Logger.log('Form Edit URL:      ' + form.getEditUrl());
  Logger.log('Form Responder URL: ' + form.getPublishedUrl());
  Logger.log('==================================================================');
}


/**
 * Creates a brand-new complete ISO/IEC 25010 + Chapter 1/3 Evaluation Form + Linked Sheet.
 */
function createCvsuEvaluationForm() {
  var form = FormApp.create(
    'System Evaluation Survey: AI-Driven Enrollment Scheduler for Irregular Students (CvSU-Imus)'
  );
  form.setDescription(
    'Cavite State University - Imus Campus | Department of Computer Studies (BSCS)\n\n' +
    'Thank you for participating in the evaluation of the AI-Driven Enrollment Scheduler for Irregular Students. ' +
    'This instrument adapts the ISO/IEC 25010 Software Product Quality Model, modified System Usability Scale (SUS) items, ' +
    'and Scheduling & Conflict-Resolution Effectiveness criteria.\n\n' +
    'Estimated completion time: 3 to 5 minutes.'
  );
  form.setProgressBar(true);
  form.setShowLinkToRespondAgain(false);
  form.setConfirmationMessage(
    'Thank you for completing the evaluation! Your feedback directly contributes to improving ' +
    'irregular student enrollment and advising at Cavite State University - Imus Campus.'
  );

  var ss = SpreadsheetApp.create(
    'CvSU-Imus AI Enrollment Scheduler - Evaluation Responses (50 Respondents)'
  );
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  // =========================================================================
  // SECTION 1: Informed Consent (RA 10173 - Data Privacy Act of 2012)
  // =========================================================================
  form.addSectionHeaderItem()
    .setTitle('Section 1: Informed Consent (Republic Act No. 10173)')
    .setHelpText(
      'In compliance with the Data Privacy Act of 2012 (RA 10173), all information gathered through ' +
      'this survey will remain strictly confidential and will be used exclusively for academic research ' +
      'and statistical evaluation by the BSCS researchers of Cavite State University - Imus Campus. ' +
      'Participation is completely voluntary.'
    );

  var consentItem = form.addCheckboxItem();
  consentItem.setTitle('Informed Consent');
  consentItem.setChoiceValues([
    'I confirm that I have tested the AI-Driven Enrollment Scheduler prototype and voluntarily consent to participate in this study.'
  ]);
  consentItem.setRequired(true);

  // =========================================================================
  // SECTION 2: Demographic Profile & Respondent Role Dropdown
  // =========================================================================
  form.addPageBreakItem()
    .setTitle('Section 2: Respondent Profile')
    .setHelpText('Please select your role and provide basic demographic information for quota sampling analysis (N = 50).');

  var roleDropdown = form.addListItem()
    .setTitle('Respondent Role')
    .setHelpText('Select the stakeholder group you represent in this evaluation.')
    .setRequired(true);

  form.addTextItem()
    .setTitle('Name or Initials (Optional)')
    .setHelpText('Optional — used only to verify quota counts during campus testing.')
    .setRequired(false);

  form.addListItem()
    .setTitle('Age Group')
    .setChoiceValues(['18 - 20', '21 - 23', '24 - 29', '30 and above'])
    .setRequired(true);

  form.addListItem()
    .setTitle('Gender / Sex')
    .setChoiceValues(['Male', 'Female', 'Prefer not to say'])
    .setRequired(true);

  form.addListItem()
    .setTitle('Program / Affiliation')
    .setChoiceValues([
      'BS Computer Science (BSCS)',
      'BS Information Technology (BSIT)',
      'Other CvSU-Imus Program / Department',
      'External IT Industry / Practitioner'
    ])
    .setRequired(true);

  form.addListItem()
    .setTitle('Year Level / Professional Standing')
    .setChoiceValues([
      '2nd Year Student',
      '3rd Year Student',
      '4th Year / Extended Student',
      'Faculty / Academic or Registration Adviser',
      'IT Professional / Software Practitioner'
    ])
    .setRequired(true);

  form.addListItem()
    .setTitle('Prior Experience with Manual Course Plotting / Registration Portals')
    .setHelpText('Select the option that best describes your prior experience with irregular course scheduling.')
    .setChoiceValues([
      'No prior irregular scheduling experience',
      '1 - 2 semesters of manual schedule plotting',
      '3 or more semesters of manual schedule plotting',
      'Academic / registration advising experience',
      'IT / software system evaluation background'
    ])
    .setRequired(true);

  // =========================================================================
  // SECTION 2A: Prior Manual Enrollment Difficulties (Students - SOP #1)
  // =========================================================================
  var sec2aStudent = form.addPageBreakItem()
    .setTitle('Section 2A: Current Manual Scheduling Difficulties (Students)')
    .setHelpText(
      'Before evaluating the AI-Driven Enrollment Scheduler, please rate the difficulties you ' +
      'currently experience when manually plotting your semester schedule (1 = Strongly Disagree, 5 = Strongly Agree).'
    );

  form.addGridItem()
    .setTitle('Manual Enrollment Challenges Encountered (SOP #1)')
    .setRows([
      '1. I find it difficult to manually map my personal time availability against fragmented section offerings across multiple year levels.',
      '2. I experience confusion or errors when manually checking subject eligibility and prerequisite chains from the curriculum checklist.',
      '3. I spend excessive time detecting lecture/laboratory schedule overlaps and manually resolving conflicting sections.',
      '4. I struggle to find viable alternative sections when my preferred classes conflict or reach maximum room capacity.'
    ])
    .setColumns(LIKERT_COLUMNS)
    .setRequired(true);

  // =========================================================================
  // SECTION 2B: Prior Advising Bottlenecks (Advisers - SOP #2)
  // =========================================================================
  var sec2bAdviser = form.addPageBreakItem()
    .setTitle('Section 2B: Current Advising Challenges (Academic / Registration Advisers)')
    .setHelpText(
      'Before evaluating the AI-Driven Enrollment Scheduler, please rate the challenges encountered ' +
      'when manually advising irregular students during enrollment (1 = Strongly Disagree, 5 = Strongly Agree).'
    );

  form.addGridItem()
    .setTitle('Manual Advising Bottlenecks Encountered (SOP #2)')
    .setRows([
      '1. Manually validating irregular students\' transcript records against curriculum prerequisite rules is time-consuming during peak enrollment.',
      '2. Manually inspecting plotted irregular schedules for lecture/laboratory timetable clashes and room overlaps is prone to oversight.',
      '3. Assisting irregular students in finding conflict-free alternative section combinations creates advising queues during peak registration periods.'
    ])
    .setColumns(LIKERT_COLUMNS)
    .setRequired(true);

  // =========================================================================
  // SECTION 3: ISO/IEC 25010 Core Quality + SOP 7.5 + Modified SUS (All 50)
  // =========================================================================
  var sec3Core = form.addPageBreakItem()
    .setTitle('Section 3: ISO/IEC 25010 System Quality Evaluation')
    .setHelpText(
      'Based on your hands-on testing of the AI-Driven Enrollment Scheduler inside the CvSU-Imus Student Portal, ' +
      'please rate each statement using the 5-point scale (1 = Strongly Disagree to 5 = Strongly Agree).'
    );

  // 3A. Functional Suitability (SOP 7.1)
  form.addGridItem()
    .setTitle('3A. Functional Suitability (Completeness, Correctness, and Appropriateness)')
    .setHelpText('Evaluates whether the system provides all required features accurately and solves irregular scheduling needs.')
    .setRows([
      '1. (Completeness) The system provides all essential functions needed for irregular enrollment: prerequisite validation, weekly availability matrix, conflict detection, dynamic section swapping, master schedule generation, and PDF export.',
      '2. (Correctness - Prerequisites) The Automated Prerequisite Validation accurately distinguishes eligible, retake, and prerequisite-locked BSCS subjects based on academic standing.',
      '3. (Correctness - Zero Overlaps) The CSP solver consistently generates conflict-free schedules with zero lecture/laboratory overlaps while strictly honoring blocked availability slots.',
      '4. (Correctness - Conflict & Swap Resolution) When section overlaps or closed classes occur, the Conflict Report Log clearly explains the clash and the Dynamic Section-Swapping Engine recommends valid conflict-free alternatives.',
      '5. (Appropriateness) The 3-step Pre-Registration workflow (Select Subjects -> Weekly Availability -> Master Schedule & Advising) is practical and well-suited for irregular student enrollment at CvSU-Imus.'
    ])
    .setColumns(LIKERT_COLUMNS)
    .setRequired(true);

  // 3B. Performance Efficiency (SOP 7.3)
  form.addGridItem()
    .setTitle('3B. Performance Efficiency (Time Behaviour, Resource Utilization, and Capacity)')
    .setHelpText('Evaluates system speed, responsiveness, and capacity under full semester loads.')
    .setRows([
      '1. (Time Behaviour) The CSP scheduler computes conflict-free schedule options quickly (within seconds) without noticeable delay.',
      '2. (Time Behaviour) Navigating portal pages, filtering Subjects Offered, and toggling slots on the Monday-Saturday availability grid respond smoothly.',
      '3. (Resource Utilization) The web application runs smoothly on a standard desktop or mobile browser without freezing or slowing down the device.',
      '4. (Capacity) The system effectively handles full irregular course loads (up to 24 units across multiple year levels) and produces multiple ranked schedule options.'
    ])
    .setColumns(LIKERT_COLUMNS)
    .setRequired(true);

  // 3C. Usability (SOP 7.2)
  form.addGridItem()
    .setTitle('3C. Usability (Recognizability, Learnability, Operability, Error Protection, Aesthetics, Accessibility)')
    .setHelpText('Evaluates portal familiarity, ease of learning, visual design, and error prevention.')
    .setRows([
      '1. (Recognizability) Because the interface faithfully mirrors the official CvSU-Imus Student Portal, I immediately understood how to navigate the dashboard, grades, checklist, and pre-registration pages.',
      '2. (Learnability) The 3-step Pre-Registration workflow and Monday-Saturday (7:00 AM - 8:00 PM) toggle matrix are intuitive and easy to learn without lengthy instructions.',
      '3. (Operability) Selecting subjects, applying availability presets, comparing timetable options, and exporting PDF schedules are straightforward and easy to control.',
      '4. (User Error Protection) The system prevents common enrollment mistakes (disabling locked prerequisites, enforcing unit limits, confirming before submitting to an adviser, and preventing duplicate submissions).',
      '5. (UI Aesthetics) The layout, typography, status badges, weekly timetable grid, and Light/Dark themes are clean, uncluttered, and easy on the eyes.',
      '6. (Accessibility) Text labels, contrast, tables, and buttons remain legible and usable across different screen sizes.'
    ])
    .setColumns(LIKERT_COLUMNS)
    .setRequired(true);

  // 3D. Reliability (SOP 7.4)
  form.addGridItem()
    .setTitle('3D. Reliability (Maturity, Availability, Fault Tolerance, and Recoverability)')
    .setHelpText('Evaluates stability, error handling, and data consistency.')
    .setRows([
      '1. (Maturity) The system operates smoothly across all portal and scheduler workflows without crashes, broken layouts, or unexpected errors.',
      '2. (Availability) All portal pages, solver actions, advising tools, and PDF exports worked consistently throughout testing.',
      '3. (Fault Tolerance) When conflicting section pins or blocked-hour deadlocks occur, the system responds gracefully with clear conflict diagnostics and slot-relaxation suggestions.',
      '4. (Recoverability) Saved availability settings, submitted master schedules, and adviser approvals remain intact across page refreshes and re-logins.'
    ])
    .setColumns(LIKERT_COLUMNS)
    .setRequired(true);

  // 3E. Compatibility
  form.addGridItem()
    .setTitle('3E. Compatibility (Co-existence and Interoperability)')
    .setHelpText('Evaluates smooth integration with the student portal environment and standard document formats.')
    .setRows([
      '1. (Co-existence) The AI Enrollment Scheduler blends naturally into the CvSU-Imus Student Portal Pre-Registration module without disrupting existing portal features.',
      '2. (Interoperability) Exported Master Schedule and Registration Form PDF documents open and display accurately in standard PDF viewers.'
    ])
    .setColumns(LIKERT_COLUMNS)
    .setRequired(true);

  // 3F. Security
  form.addGridItem()
    .setTitle('3F. Security (Access Control, Data Integrity, and Confidentiality)')
    .setHelpText('Evaluates role separation, read-only academic standing, and privacy compliance.')
    .setRows([
      '1. (Access Control) Authentication and role separation appropriately restrict Student vs. Academic Adviser actions (e.g., only advisers can grant manual prerequisite overrides and approve schedules).',
      '2. (Data Integrity) Students cannot modify their official transcript grades or bypass prerequisite rules during normal pre-registration.',
      '3. (Confidentiality) The portal provides a clear RA 10173 Data Privacy notice and handles account sign-in and sign-out securely.'
    ])
    .setColumns(LIKERT_COLUMNS)
    .setRequired(true);

  // 3G. Scheduling & Conflict-Resolution Effectiveness (SOP 7.5)
  form.addGridItem()
    .setTitle('3G. Scheduling and Conflict-Resolution Effectiveness (SOP 7.5)')
    .setHelpText('Evaluates overall effectiveness in automating prerequisite checking, resolving conflicts, and generating usable schedules.')
    .setRows([
      '1. The system significantly reduces the time and effort needed to formulate a valid semester schedule compared to manual plotting.',
      '2. The Automated Prerequisite Validation reliably prevents enrollment in subjects with unmet prerequisite chains.',
      '3. The CSP solver and Dynamic Section-Swapping Engine effectively resolve overlapping lecture/laboratory schedules and closed sections.',
      '4. The generated Master Schedule layout clearly presents all required enrollment details (subject codes, sections, units, rooms, and meeting times) for adviser sign-off.'
    ])
    .setColumns(LIKERT_COLUMNS)
    .setRequired(true);

  // Time Spent & Modified SUS (Ch. 3 p. 11 & p. 13)
  form.addMultipleChoiceItem()
    .setTitle('Estimated Time Spent Configuring Availability and Generating a Conflict-Free Schedule')
    .setHelpText('Approximate time it took you to complete Steps 1 to 3 during testing.')
    .setChoiceValues([
      'Less than 1 minute',
      '1 to 2 minutes',
      '3 to 5 minutes',
      'More than 5 minutes'
    ])
    .setRequired(true);

  form.addGridItem()
    .setTitle('3H. Perceived Usability and Adoption (Modified SUS)')
    .setHelpText('Modified System Usability Scale (SUS) items measuring confidence and willingness to adopt the system.')
    .setRows([
      '1. I would want to use this AI-Driven Enrollment Scheduler regularly during semesterly enrollment.',
      '2. I felt confident using the scheduler and Monday-Saturday toggle matrix without needing technical assistance.',
      '3. Overall, the system is noticeably more convenient and accurate than manual irregular schedule plotting.'
    ])
    .setColumns(LIKERT_COLUMNS)
    .setRequired(true);

  var techBranchDropdown = form.addListItem()
    .setTitle('Technical Evaluation Checkpoint: Are you evaluating as an IT Professional?')
    .setHelpText('IT Professionals proceed to Maintainability & Portability; Students and Advisers proceed directly to Open-Ended Feedback.')
    .setRequired(true);

  // =========================================================================
  // SECTION 4: Technical ISO/IEC 25010 Evaluation (IT Professionals Only)
  // =========================================================================
  var sec4Technical = form.addPageBreakItem()
    .setTitle('Section 4: Technical Quality Evaluation (IT Professionals Only)')
    .setHelpText('Evaluates software architecture, maintainability, and portability under ISO/IEC 25010.');

  form.addGridItem()
    .setTitle('4A. Maintainability (Modularity, Modifiability, Analyzability, and Testability)')
    .setRows([
      '1. (Modularity) Separating the web portal UI, Prerequisite DAG validator, OR-Tools CP-SAT solver, Dynamic Swap engine, and ORM database models promotes clean modular architecture.',
      '2. (Modifiability) Storing BSCS curricula and semester offerings in structured JSON snapshots allows administrators to update courses and schedules each term without rewriting solver code.',
      '3. (Analyzability & Testability) Automated pytest verification suites and structured conflict diagnostic logs make verifying solver accuracy and diagnosing faults straightforward.'
    ])
    .setColumns(LIKERT_COLUMNS)
    .setRequired(true);

  form.addGridItem()
    .setTitle('4B. Portability (Adaptability and Installability)')
    .setRows([
      '1. (Cross-Platform Adaptability) The FastAPI + responsive Bootstrap web architecture runs reliably across modern operating systems and web browsers (Chrome, Edge, Firefox).',
      '2. (Institutional Scalability) The curriculum DAG and JSON snapshot design can be extended to other degree programs at CvSU-Imus beyond BSCS.',
      '3. (Installability) Using Python and SQLAlchemy ORM enables smooth local testing with SQLite and straightforward migration to MySQL/PostgreSQL for institutional cloud deployment.'
    ])
    .setColumns(LIKERT_COLUMNS)
    .setRequired(true);

  // =========================================================================
  // SECTION 5: Open-Ended Qualitative Feedback (All 50 Respondents)
  // =========================================================================
  var sec5OpenEnded = form.addPageBreakItem()
    .setTitle('Section 5: Open-Ended Feedback')
    .setHelpText('Your qualitative insights will help us refine the system and enrich Chapter 4 discussion.');

  form.addParagraphTextItem()
    .setTitle('1. Which feature of the AI-Driven Enrollment Scheduler did you find most helpful compared to manual scheduling?')
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('2. Did you encounter any bugs, confusing labels, or usability issues during testing? (Optional)')
    .setRequired(false);

  form.addParagraphTextItem()
    .setTitle('3. What additional features or improvements would you suggest before full deployment at CvSU-Imus? (Optional)')
    .setRequired(false);

  // Wire up Section Branching
  roleDropdown.setChoices([
    roleDropdown.createChoice('Student', sec2aStudent),
    roleDropdown.createChoice('Adviser', sec2bAdviser),
    roleDropdown.createChoice('IT Professional', sec3Core)
  ]);
  sec2aStudent.setGoToPage(sec3Core);
  sec2bAdviser.setGoToPage(sec3Core);

  techBranchDropdown.setChoices([
    techBranchDropdown.createChoice(
      'Yes - IT Professional (Proceed to Maintainability & Portability)',
      sec4Technical
    ),
    techBranchDropdown.createChoice(
      'No - Student or Adviser (Proceed to Open-Ended Feedback)',
      sec5OpenEnded
    )
  ]);
  sec4Technical.setGoToPage(sec5OpenEnded);

  // Build "Chapter 4 Summary" Sheet
  var summarySheet = ss.insertSheet('Chapter 4 Summary');
  summarySheet.getRange('A1:E1').setValues([[
    'CvSU-Imus AI Enrollment Scheduler - Live Evaluation Tracker (N = 50)', '', '', '', ''
  ]]).setFontWeight('bold').setFontSize(12);

  summarySheet.getRange('A3:E7').setValues([
    ['Respondent Group', 'Target Quota', 'Collected', 'Remaining', 'Share (%)'],
    ['Student', 35, '=COUNTIF(\'Form Responses 1\'!C:C,"Student")', '=B4-C4', '=IF($C$7=0,0,C4/$C$7)'],
    ['Adviser', 10, '=COUNTIF(\'Form Responses 1\'!C:C,"Adviser")', '=B5-C5', '=IF($C$7=0,0,C5/$C$7)'],
    ['IT Professional', 5, '=COUNTIF(\'Form Responses 1\'!C:C,"IT Professional")', '=B6-C6', '=IF($C$7=0,0,C6/$C$7)'],
    ['Total', '=SUM(B4:B6)', '=SUM(C4:C6)', '=SUM(D4:D6)', '=SUM(E4:E6)']
  ]);
  summarySheet.getRange('A3:E3').setFontWeight('bold').setBackground('#00a15d').setFontColor('#ffffff');
  summarySheet.getRange('A7:E7').setFontWeight('bold').setBackground('#f3f6f9');
  summarySheet.getRange('E4:E7').setNumberFormat('0.00%');

  summarySheet.getRange('A9:D15').setValues([
    ['Chapter 3 Table 3 - Weighted Mean Verbal Interpretation Reference', '', '', ''],
    ['Range of Weighted Mean', 'Equivalent', 'Rating', 'Description'],
    ['4.51 - 5.00', 'Excellent', 5, 'The system is acceptable and exceeds expectations.'],
    ['3.51 - 4.50', 'Very Good', 4, 'The system meets all expectations.'],
    ['2.51 - 3.50', 'Good', 3, 'The system meets most of its expectations.'],
    ['1.51 - 2.50', 'Fair', 2, 'The system barely meets its expectations.'],
    ['1.50 and below', 'Poor', 1, 'The system did not meet the expectation.']
  ]);
  summarySheet.getRange('A9').setFontWeight('bold');
  summarySheet.getRange('A10:D10').setFontWeight('bold').setBackground('#00a15d').setFontColor('#ffffff');

  summarySheet.getRange('A17:B19').setValues([
    ['Formula Tip (Extract Numeric Score 1-5 from Likert Text):', '=ARRAYFORMULA(IF(K2:K="","",VALUE(LEFT(K2:K,1))))'],
    ['Formula Tip (Weighted Mean of Numeric Column):', '=AVERAGE(colRange)'],
    ['Formula Tip (Auto Verbal Interpretation from Mean in B2):', '=IF(B2>=4.51,"Excellent",IF(B2>=3.51,"Very Good",IF(B2>=2.51,"Good",IF(B2>=1.51,"Fair","Poor"))))']
  ]);
  summarySheet.getRange('A17:A19').setFontWeight('bold');
  summarySheet.autoResizeColumns(1, 5);

  Logger.log('==================================================================');
  Logger.log('SUCCESS! CvSU-Imus ISO/IEC 25010 Evaluation Form Created!');
  Logger.log('Form Edit URL:       ' + form.getEditUrl());
  Logger.log('Form Responder URL:  ' + form.getPublishedUrl());
  Logger.log('Linked Sheet URL:    ' + ss.getUrl());
  Logger.log('==================================================================');
}
