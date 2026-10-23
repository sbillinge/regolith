import warnings

import pytest

from regolith.schemas import SCHEMAS, _update_dict_target, insert_alloweds, load_exemplars, validate


def test_update_dict_target():
    doc = {
        "email": {
            "description": "contact email for the author.",
            "required": True,
            "deeper": {"eallowed": "TEST"},
        },
        "_id": {
            "description": "Unique identifier for submission. "
            "This generally includes the author name and part of the title.",
            "required": True,
            "type": "string",
        },
        "coauthors": {"description": "names of coauthors", "required": False, "eallowed": "TEST2"},
        "test_repeated": {"description": "names of coauthors", "required": False, "eallowed": "TEST2"},
    }
    expected = {
        "_id": {
            "description": "Unique identifier for submission. "
            "This generally includes the author name and part of the title.",
            "required": True,
            "type": "string",
        },
        "coauthors": {"description": "names of coauthors", "required": False, "eallowed": "string"},
        "test_repeated": {"description": "names of coauthors", "required": False, "eallowed": "string"},
        "email": {
            "description": "contact email for the author.",
            "required": True,
            "deeper": {"eallowed": ["string", "float"]},
        },
    }
    first_cut = _update_dict_target(doc, {"eallowed": "TEST"}, ["string", "float"])
    actual = _update_dict_target(first_cut, {"eallowed": "TEST2"}, "string")
    assert actual == expected


@pytest.mark.parametrize(
    "status, expected_warning",
    [
        # C1: grant with status accepted, expect no warning about the status
        ("accepted", False),
        # C2: grant with status finished, expect no warning about the status
        ("finished", False),
        # C3: grant with a status that is not allowed, expect a warning about the status
        ("not-a-status", True),
    ],
)
def test_grant_status_values(status, expected_warning):
    # Test that a grant status outside GRANT_STATI is flagged and one inside it is not
    grant = dict(load_exemplars()["grants"][0], status=status)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        validate("grants", grant, SCHEMAS)
    actual_warning = any("not in the preferred entries" in str(w.message) for w in caught)
    assert actual_warning is expected_warning


def test_insert_alloweds():
    alloweds = {"TEST": ["string", "float"], "TEST2": "string"}
    doc = {
        "email": {
            "description": "contact email for the author.",
            "required": True,
            "deeper": {"eallowed": "TEST"},
        },
        "_id": {
            "description": "Unique identifier for submission. "
            "This generally includes the author name and part of the title.",
            "required": True,
            "type": "string",
        },
        "coauthors": {"description": "names of coauthors", "required": False, "eallowed": "TEST2"},
        "test_repeated": {"description": "names of coauthors", "required": False, "eallowed": "TEST2"},
    }
    expected = {
        "_id": {
            "description": "Unique identifier for submission. "
            "This generally includes the author name and part of the title.",
            "required": True,
            "type": "string",
        },
        "coauthors": {"description": "names of coauthors", "required": False, "eallowed": "string"},
        "test_repeated": {"description": "names of coauthors", "required": False, "eallowed": "string"},
        "email": {
            "description": "contact email for the author.",
            "required": True,
            "deeper": {"eallowed": ["string", "float"]},
        },
    }
    actual = insert_alloweds(doc, alloweds, "eallowed")
    assert actual == expected
