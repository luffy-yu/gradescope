
import csv as _csv
import os as _os
import io as _io
import zipfile as _zipfile

from gradescope.raw_util import robust_float

NUM_HOUSEKEEPING_COLS = 10

def parse_csv(content):
    records = [
        record
        for record in _csv.DictReader(
            content.decode().splitlines(),
            quotechar='"',
            delimiter=',',
            quoting=_csv.QUOTE_ALL,
            skipinitialspace=True)
    ]
    return records

def extract_evaluations(td, content):
    with _io.BytesIO(content) as tmp_zip:
        with _zipfile.ZipFile(tmp_zip) as zf:
            zf.extractall(td)

    def _is_valid_folder(fname):
        return fname[0] != '.' and _os.path.isdir(_os.path.join(td, fname))

    extracted_files = [i for i in _os.listdir(td) if _is_valid_folder(i)]

    if len(extracted_files) != 1:
        raise FileNotFoundError(f"Evaluations for assignment did not contain expected directory structure")

    return _os.path.join(td, extracted_files[0])

def to_numeric(dictlist, fields):
    for elt in dictlist:
        for field in fields:
            elt[field] = robust_float(elt[field])

def shortened_grade_record(record):
    return {
        "name": record.get("Name", None),
        "sid": record.get("SID", None),
        "email": record.get("Email", None),
        "score": record.get("Total Score", 0.0),
        "graded": record.get("Status", None) == "Graded",
        "view_count": record.get("View Count", 0),
        "id": record.get("Submission ID", None),
    }

def collapse_grades(grades):
    if len(grades) == 0:
        return []

    keys = list(grades[0].keys())
    housekeeping = keys[:NUM_HOUSEKEEPING_COLS]
    sections = keys[NUM_HOUSEKEEPING_COLS:]

    collapsed = [{k: person[k] for k in housekeeping} for person in grades]

    for i, person in enumerate(grades):
        collapsed[i]['questions'] = {k: person[k] for k in sections}
        to_numeric([collapsed[i]['questions']], sections)

    return collapsed

def map_sheets(sheets, questions):
    q_names = {question.split(':')[0] if ':' in question else question.split(' ')[0]: question for question in questions}
    sheet_map = {}

    for sheet in sheets:
        name = sheet.split('_')[0]
        if name not in q_names:
            name = '.'.join(sheet.split('.')[:-1])
            if name not in q_names:
               raise FileNotFoundError("Evaluations contains extraneous questions") 
        sheet_map[sheet] = q_names[name]

    if len(sheet_map) != len(sheets):
        raise FileNotFoundError("Not all questions found in evaluations")

    return sheet_map

def read_eval_row(row):
    keys = list(row.keys())
    rubric_items = keys[7:-4]

    new_row = {
        'score': robust_float(row['Score']),
        'adjustment': robust_float(row['Adjustment']),
        'comment': row['Comments'],
        'rubric_items': {item: (row[item] == 'true') for item in rubric_items}
    }

    return new_row