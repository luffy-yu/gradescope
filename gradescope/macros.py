import collections as _collections
import csv as _csv
import json
import os as _os
import re
import tempfile as _tempfile
import typing as _typing
from datetime import datetime

import bs4 as _bs4
import pytz

import gradescope.api
import gradescope.raw_util
import gradescope.util
from gradescope.raw_util import robust_float

us_est_timezone = pytz.timezone('US/Eastern')

ASSIGNMENT_URL_PATTERN = r"/courses/([0-9]*)/assignments/([0-9]*)$"


class GradescopeRole(gradescope.raw_util.DocEnum):
    # <option value="0">Student</option>
    # <option selected="selected" value="1">Instructor</option>
    # <option value="2">TA</option>
    # <option value="3">Reader</option>

    STUDENT = 0, "Student user"
    INSTRUCTOR = 1, "Instructor user"
    TA = 2, "TA user"
    READER = 3, "Reader user"


def get_assignment_grades(course_id, assignment_id, simplified=False, **kwargs):
    # Fetch the grades
    # https://www.gradescope.com/courses/702597/assignments/4023169/grade
    response = gradescope.api.request(
        endpoint=f'courses/{course_id}/assignments/{assignment_id}/grade'
    )

    soup = _bs4.BeautifulSoup(response.content, features="html.parser")

    # Parse the CSV format
    grades = gradescope.util.parse_csv(response.content)

    # Summarize it if necessary by removing question-level data
    if simplified:
        shortened_grades = list(map(gradescope.util.shortened_grade_record, grades))
        return shortened_grades

    # Collapse assignment grades into dictionary key
    grades = gradescope.util.collapse_grades(grades)
    gradescope.util.to_numeric(grades, ('Total Score', 'Max Points', 'View Count'))

    return grades


def get_assignment_evaluations(course_id, assignment_id, **kwargs):
    response = gradescope.api.request(
        endpoint="courses/{}/assignments/{}/export_evaluations".format(course_id,
                                                                       assignment_id)
    )

    # Fetch assignment grades for scaffolding
    grades = get_assignment_grades(course_id, assignment_id)

    if len(grades) == 0:
        return []

    subid_grades = {person['Submission ID']: person for person in grades}

    # Open temp directory for extraction
    with _tempfile.TemporaryDirectory() as td:
        file_path = gradescope.util.extract_evaluations(td, response.content)

        # Find question name for each sheet
        sheets = [i for i in _os.listdir(file_path) if '.csv' in i]
        sheet_map = gradescope.util.map_sheets(sheets, grades[0]['questions'].keys())

        # Read questions from each sheet
        for sheet in sheets:
            q_name = sheet_map[sheet]
            with open(_os.path.join(file_path, sheet)) as csvfile:
                reader = _csv.DictReader(
                    csvfile,
                    quotechar='"',
                    delimiter=',',
                    quoting=_csv.QUOTE_ALL,
                    skipinitialspace=True)
                # Match rows to students
                for row in reader:
                    if row['Assignment Submission ID'] not in subid_grades:
                        continue

                    subid = row['Assignment Submission ID']

                    new_row = gradescope.util.read_eval_row(row)

                    if new_row['score'] != subid_grades[subid]['questions'][q_name]:
                        raise ValueError('Mismatched scores!')

                    subid_grades[subid]['questions'][q_name] = new_row

    return list(subid_grades.values())


def get_course_roster(course_id, **kwargs):
    # Fetch the grades
    response = gradescope.api.request(
        endpoint="courses/{}/memberships.csv".format(course_id)
    )

    # Parse the CSV format
    roster = gradescope.util.parse_csv(response.content)

    return roster


def invite_many(course_id, role, users, **kwargs):
    # type: (int, GradescopeRole, _typing.List[_typing.Tuple[str, str]], dict) -> bool

    # Built payload
    payload = _collections.OrderedDict()
    counter = 0
    for (email, name) in users:
        payload["students[{}][name]".format(counter)] = name
        payload["students[{}][email]".format(counter)] = email
        counter += 1
    payload["role"] = role

    # Fetch the grades
    response = gradescope.api.request(
        endpoint="courses/{}/memberships/many".format(course_id),
        data=payload,
    )

    return response.status_code == 200


def get_courses(by_name=False):
    response = gradescope.api.request(endpoint="account")
    soup = _bs4.BeautifulSoup(response.content, features="html.parser")
    hrefs = list(filter(lambda s: s, map(
        lambda anchor: anchor.get("href"),
        soup.find_all("a", {"class": "courseBox"})
    )))
    course_ids = list(map(lambda href: href.split("/")[-1], hrefs))

    if by_name:
        return list(map(get_course_name, course_ids))

    return course_ids


def get_course_name(course_id):
    result = gradescope.api.request(endpoint="courses/{}".format(course_id))
    soup = _bs4.BeautifulSoup(result.content.decode(), features="html.parser")
    header_element = soup.find("header", {"class": "courseHeader"})
    if header_element:
        course_name = header_element.find("h1").text.replace(" ", "")

        course_term = header_element.find("div", {"class": "courseHeader--term"}).text
        course_term = course_term.replace("Fall ", "F")
        course_term = course_term.replace("Spring ", "S")
        return {"name": course_name, "term": course_term, "id": course_id}


def get_course_id(course_name, course_term):
    courses = get_courses(by_name=True)
    for course in courses:
        if course["name"] == course_name and course["term"] == course_term:
            return course["id"]


def get_course_assignments(course_id):
    # NOTE: remove "/assignments" for only active assignments?
    result = gradescope.api.request(endpoint="courses/{}/assignments".format(course_id))
    soup = _bs4.BeautifulSoup(result.content.decode(), features="html.parser")

    assignment_table = soup.find('div', {'data-react-class': 'AssignmentsTable'})
    table_data = json.loads(assignment_table.attrs['data-react-props'])
    assignment_rows = table_data['table_data']

    assignments = []
    for row in assignment_rows:
        if 'is_published' in row:
            # id 'assignment_3922368'
            assignment = dict(id=row['id'].split('_')[1], name=row['title'], url=row['url'])
            assignments.append(assignment)

    return assignments


def get_course_assignment_by_name(course_id, assignment_name):
    assignments = get_course_assignments(course_id)
    for assignment in assignments:
        if assignment['name'] == assignment_name:
            return assignment
    return None


def format_time(src_time):
    # change to us est time
    time = datetime.strptime(src_time, '%Y-%m-%d %H:%M:%S %z').astimezone(us_est_timezone)
    time = datetime.strftime(time, '%Y-%m-%d %H:%M:%S')
    return time


def find_section_and_grader(row):
    spans = row.findAll('span', {'class': 'sectionsColumnCell--sectionSpan'})
    section, grader = '', ''
    for span in spans:
        if re.match('[a-zA-Z]+', span.text):
            grader = span.text
        elif re.match('\d', span.text):
            section = span.text

    return section, grader


def get_course_assignment_submissions_by_name(course_id, assignment_name):
    assignment = get_course_assignment_by_name(course_id, assignment_name)
    if assignment is None:
        return

    result = gradescope.api.request(endpoint=f'{assignment["url"]}/submissions')
    soup = _bs4.BeautifulSoup(result.content.decode(), features="html.parser")
    table_data = soup.find('table', {'class': 'js-programmingAssignmentSubmissionsTable'}).find('tbody').findChildren(
        'tr')
    result = []
    for row in table_data:
        name = row.find('a').text
        time = row.find('time').attrs['datetime']  # "2024-02-04 20:57:57 -0800"
        time = format_time(time)
        section, grader = find_section_and_grader(row)
        data = dict(name=name, time=time, grader=grader, section=section)
        result.append(data)
    return result


def get_course_assignment_grades_by_name(course_id, assignment_name):
    assignment = get_course_assignment_by_name(course_id, assignment_name)
    if assignment is None:
        return

    response = gradescope.api.request(
        endpoint=f'courses/{course_id}/assignments/{assignment["id"]}/grade'
    )

    soup = _bs4.BeautifulSoup(response.content.decode(), features="html.parser")

    grading_table = soup.find('div', {'data-react-class': 'GradingDashboard'})
    table_data = json.loads(grading_table.attrs['data-react-props'])

    questions = table_data['presenter']['assignments'][assignment['id']]['questions']

    result = []

    for q in questions:
        row = questions[q]
        data = dict(id=row['id'], name=row['title'], grade_url=row['link'], submissions_url=row['submissionsLink'])
        result.append(data)

    return result


def get_course_assignment_question_submissions_by_name(course_id, assignment_name, question_name):
    grades = get_course_assignment_grades_by_name(course_id, assignment_name)
    if not grades:
        return

    question = {}
    for grade in grades:
        if grade['name'] == question_name:
            question = grade

    if not question:
        return

    response = gradescope.api.request(endpoint=question['submissions_url'])

    soup = _bs4.BeautifulSoup(response.content.decode(), features="html.parser")

    table_data = soup.find('table').findAll('tr')[1:]

    result = []
    for row in table_data:
        a_data = row.find('a')
        url = a_data.attrs['href']
        submissions_id = url.split('/')[-2]
        name_email = a_data.text.split('(')
        name = name_email[0].strip()
        email = name_email[1][:-1]
        result.append(dict(name=name, email=email, submissions_id=submissions_id, url=url))

    return result


def get_course_grades(course_id, only_graded=True, use_email=True):
    # Dictionary mapping student emails to grades
    grades = {}

    gradescope_assignments = get_course_assignments(
        course_id=course_id)

    for assignment in gradescope_assignments:
        # {'id': '273671', 'name': 'Written Exam 1'}
        assignment_name = assignment["name"]
        assignment_grades = get_assignment_grades(
            course_id=course_id,
            assignment_id=assignment.get("id"),
            simplified=True)

        for record in assignment_grades:
            # {'name': 'Joe Student',
            #   'sid': 'jl27',
            #   'email': 'jl27@princeton.edu',
            #   'score': '17.75',
            #   'graded': True,
            #   'view_count': '4',
            #   'id': '22534979'}

            if only_graded and not record.get("graded", False):
                continue

            student_id = record["sid"]
            if use_email:
                student_id = record["email"]
            grade = robust_float(record.get("score"))

            # Add grade to student
            grades[student_id] = grades.get(student_id, dict())
            grades[student_id][assignment_name] = grade

    return grades
