
import csv as _csv
import os as _os
import io as _io
import zipfile as _zipfile

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

    return collapsed

def map_sheets(sheets, questions):
    q_names = {question.split(':')[0]: question for question in questions}

    try:
        sheet_map = {sheet: q_names[sheet.split('_')[0]] for sheet in sheets}
    except KeyError:
        raise FileNotFoundError("Evaluations contains extraneous questions")

    if len(sheet_map) != len(sheets):
        raise FileNotFoundError("Not all questions found in evaluations")

    return sheet_map

def read_eval_row(row):
    keys = list(row.keys())
    rubric_items = keys[7:-4]

    new_row = {
        'score': row['Score'],
        'adjustment': row['Adjustment'],
        'comment': row['Comments'],
        'rubric_items': {item: (row[item] == 'true') for item in rubric_items}
    }

    return new_row