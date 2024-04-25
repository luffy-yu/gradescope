"""
Author: Liuchuan Yu
Email: lyu20@gmu.edu
Github: https://github.com/luffy-yu/gradescope/tree/refactor
"""
from datetime import datetime
from gradescope.macros import *
import pandas as pd

# format to date only
FUNC = lambda x: datetime.strptime(datetime.strptime(x, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d'), '%Y-%m-%d')


def calculate_days(due_date, submission):
    """
    due_date = '2024-02-04 23:59:59'
    submission = '2024-02-06 23:59:59'
    calculate_days(due_date, submission)
    """
    d1 = FUNC(due_date)
    d2 = FUNC(submission)
    days_gap = (d1 - d2).days
    return days_gap


project_name = 'Project 4'
due_date = '2024-04-21 23:59:59'
question_name = 'Violations'

for course_id, course_name in {
    '702597': 'CS310 001-002-003',
    '709120': 'CS310 004-006'
}.items():
    submissions = get_course_assignment_submissions_by_name(course_id, project_name)
    print(f'Number of submission in {course_name}: {len(submissions)}')

    questions = get_course_assignment_question_submissions_by_name(course_id, project_name, question_name,
                                                                   wrap_url=True)

    # update submission data
    for i in range(len(submissions)):
        sub = submissions[i]
        # update days
        sub['days'] = calculate_days(due_date, sub['time'])
        submissions[i] = sub

    df_submission = pd.DataFrame(submissions)
    df_questions = pd.DataFrame(questions)

    # join on name
    df = pd.merge(df_submission, df_questions, on='name', how='inner')

    # to hyperlink
    df['url'] = df['url'].apply(lambda x: f'=HYPERLINK("{x}")')

    # write to file
    excel_name = df.to_excel(f'{project_name} {question_name} {course_name}.xlsx', index=False, header=True,
                             engine='openpyxl')
    print(f'Finished {course_name}')
