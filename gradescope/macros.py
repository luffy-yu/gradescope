
import collections as _collections
import re as _re
import typing as _typing
import tempfile as _tempfile
import os as _os
import csv as _csv

import bs4 as _bs4

import gradescope.raw_util

import gradescope.api
import gradescope.util

from gradescope.raw_util import robust_float


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
    response = gradescope.api.request(
        endpoint="courses/{}/assignments/{}/scores.csv".format(course_id, assignment_id)
    )

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

    assignment_table = soup.find("table", {"class": "table-assignments"})
    assignment_rows = assignment_table.findChildren("tr",
                      {"class": "js-assignmentTableAssignmentRow"})
    
    assignments = []
    for row in assignment_rows:
        anchors = row.find_all("a")

        assignment = None
        for anchor in anchors:
            url = anchor.get("href")
            if url is None or url == "":
                continue
            match = _re.match(ASSIGNMENT_URL_PATTERN, url)
            if match is None:
                continue

            assignment = {
                "id": match.group(2),
                "name": anchor.text
            }
        
        if assignment == None:
            continue

        assignment["published"] = len(row.findAll("i",
            {"class": "workflowCheck-complete"})) > 0

        assignments.append(assignment)

    return assignments


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


