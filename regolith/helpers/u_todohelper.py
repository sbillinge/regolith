"""Helper for updating a task in todos of people collection.
"""

import datetime as dt
import dateutil.parser as date_parser
from dateutil.relativedelta import relativedelta
import math
import sys

from regolith.helpers.basehelper import DbHelperBase
from regolith.fsclient import _id_key
from regolith.tools import (
    all_docs_from_collection,
    get_pi_id,
    document_by_value,
    print_task
)

TARGET_COLL = "people"
ALLOWED_IMPORTANCE = [0, 1, 2]
ALLOWED_STATUS = ["started", "finished", "cancelled"]


def subparser(subpi):
    subpi.add_argument("-i", "--index",
                       help="Enter the running_index of a certain task in the enumerated list to update that task.",
                       type=int)
    subpi.add_argument("--all", action="store_true",
                       help="List both finished and unfinished tasks. Without this flag, the helper will only display "
                            "unfinished tasks. "
                       )
    subpi.add_argument("-r", "--running_index", action="store_true",
                       help="Reorder and update the indices."
                       )
    subpi.add_argument("-d", "--description",
                       help=" Change the description of the to_do task. If the description has more than one "
                            "word, please enclose it in quotation marks."
                       )
    subpi.add_argument("-due", "--due_date",
                       help="Change the due date of the task. Either enter a date in format YYYY-MM-DD or an "
                            "integer. Integer 5 means 5 days from the begin_date. "
                       )
    subpi.add_argument("-e", "--estimated_duration",
                       help="Change the estimated duration the task will take in minutes. ",
                       type=float
                       )
    subpi.add_argument("-im", "--importance",
                       help=f"Change the importance of the task from {ALLOWED_IMPORTANCE}.",
                       type=int
                       )
    subpi.add_argument("-s", "--status",
                       help=f"Change the status of the task from {ALLOWED_STATUS}."
                       )
    subpi.add_argument("-n", "--notes", nargs="+", help="Change the notes for this task. Each note should be enclosed "
                                                        "in quotation marks.")
    subpi.add_argument("-b", "--begin_date",
                       help="Change the begin date of the task in format YYYY-MM-DD."
                       )
    subpi.add_argument("-end", "--end_date",
                       help="Change the end date of the task in format YYYY-MM-DD."
                       )
    subpi.add_argument("-a", "--assigned_to",
                       help="ID of the member to whom the task is assigned. Default id is saved in user.json. ")
    subpi.add_argument("-c", "--certain_date",
                       help="Enter a certain date so that the helper can calculate how many days are left from that date to the deadline. Default is today.")

    return subpi


class TodoUpdaterHelper(DbHelperBase):
    """Helper for updating a task in todos of people collection.
    """
    # btype must be the same as helper target in helper.py
    btype = "u_todo"
    needed_dbs = [f'{TARGET_COLL}']

    def construct_global_ctx(self):
        """Constructs the global context"""
        super().construct_global_ctx()
        gtx = self.gtx
        rc = self.rc
        if "groups" in self.needed_dbs:
            rc.pi_id = get_pi_id(rc)

        rc.coll = f"{TARGET_COLL}"
        rc.database = rc.databases[0]["name"]
        gtx[rc.coll] = sorted(
            all_docs_from_collection(rc.client, rc.coll), key=_id_key
        )
        gtx["all_docs_from_collection"] = all_docs_from_collection
        gtx["float"] = float
        gtx["str"] = str
        gtx["zip"] = zip

    def db_updater(self):
        rc = self.rc
        if not rc.assigned_to:
            try:
                rc.assigned_to = rc.default_user_id
            except AttributeError:
                print(
                    "Please set default_user_id in '~/.config/regolith/user.json', or you need to enter your group id "
                    "in the command line")
                return
        filterid = {'_id': rc.assigned_to}
        if rc.running_index:
            index = 1
            index_finished = -1
            for i in range(0, len(rc.databases)):
                db_name = rc.databases[i]["name"]
                person_idx = rc.client.find_one(db_name, rc.coll, filterid)
                todolist_idx = person_idx.get("todos", [])
                if len(todolist_idx) == 0:
                    continue
                else:
                    for todo in todolist_idx:
                        if todo.get('status') == "started":
                            todo["running_index"] = index
                            index += 1
                        if todo.get('status') in ["finished", "cancelled"]:
                            todo["running_index"] = index_finished
                            index_finished += -1
        person = document_by_value(all_docs_from_collection(rc.client, "people"), "_id", rc.assigned_to)
        if not person:
            raise TypeError(f"Id {rc.assigned_to} can't be found in people collection")
        todolist = person.get("todos", [])
        if len(todolist) == 0:
            print(f"{rc.assigned_to} doesn't have todos in people collection.")
            return
        if not rc.index:
            if not rc.certain_date:
                today = dt.date.today()
            else:
                today = date_parser.parse(rc.certain_date).date()
            for todo in todolist:
                if not todo.get('importance'):
                    todo['importance'] = 1
                if type(todo["due_date"]) == str:
                    todo["due_date"] = date_parser.parse(todo["due_date"]).date()
                todo["days_to_due"] = (todo.get('due_date') - today).days
                todo["order"] = todo['importance'] + 1 / (1 + math.exp(abs(todo["days_to_due"])))
            todolist = sorted(todolist, key=lambda k: (-k['order'], k.get('duration', 10000), k['status']))
            index_match={}
            if rc.running_index:
                new_index = 1
                for todo in todolist:
                    if todo["status"] == 'started':
                        index_match[todo["running_index"]] = new_index
                        new_index += 1
                for i in range(0, len(rc.databases)):
                    db_name = rc.databases[i]["name"]
                    person_idx = rc.client.find_one(db_name, rc.coll, filterid)
                    todolist_idx = person_idx.get("todos", [])
                    if len(todolist_idx) != 0:
                        for todo in todolist_idx:
                            if todo.get('status') == "started":
                                index = index_match[todo["running_index"]]
                                todo["running_index"] = index
                        rc.client.update_one(db_name, rc.coll, {'_id': rc.assigned_to}, {"todos": todolist_idx},
                                             upsert=True)
                        print(f"Indices in {db_name} for {rc.assigned_to} have been updated.")
                return
            print("If the indices are far from being in numerical order, please reorder them by running regolith helper u_todo -r")
            print("Please choose from one of the following to update:")
            print("(index) action (days to due date|importance|expected duration (mins))")
            print("-" * 70)
            for todo in todolist:
                print_task(todo, status=['started'])
            if rc.all:
                print("finished/cancelled:")
                for todo in todolist:
                    print_task(todo, status=['finished', 'cancelled'])
            print("-" * 70)

        else:
            match_todo = [i for i in todolist if i.get("running_index") == rc.index]
            if len(match_todo) == 0:
                raise RuntimeError("Please enter a valid index.")
            else:
                todo = match_todo[0]
                if rc.description:
                    todo["description"] = rc.description
                if rc.due_date:
                    try:
                        relative_day = int(rc.due_date)
                        due_date = todo.get("begin_date") + relativedelta(days=relative_day)
                    except ValueError:
                        due_date = date_parser.parse(rc.due_date).date()
                    todo["due_date"] = due_date
                if rc.estimated_duration:
                    todo["duration"] = rc.estimated_duration
                if rc.importance:
                    if rc.importance in ALLOWED_IMPORTANCE:
                        todo["importance"] = rc.importance
                    else:
                        raise ValueError(f"Importance should be chosen from{ALLOWED_IMPORTANCE}.")
                if rc.status:
                    if rc.status in ALLOWED_STATUS:
                        todo["status"] = rc.status
                    else:
                        raise ValueError(f"Status should be chosen from{ALLOWED_STATUS}.")
                if rc.notes:
                    todo["notes"] = rc.notes
                if rc.begin_date:
                    todo["begin_date"] = date_parser.parse(rc.begin_date).date()
                if rc.end_date:
                    todo["end_date"] = date_parser.parse(rc.end_date).date()

                for i in range(0, len(rc.databases)):
                    db_name = rc.databases[i]["name"]
                    person_update = rc.client.find_one(db_name, rc.coll, filterid)
                    todolist_update = person_update.get("todos", [])
                    if len(todolist_update) != 0:
                        for i, todo_u in enumerate(todolist_update):
                            if rc.index == todo_u.get("running_index"):
                                todolist_update[i] = todo
                                rc.client.update_one(db_name, rc.coll, {'_id': rc.assigned_to},
                                                     {"todos": todolist_update}, upsert=True)
                                print(
                                    f"The task with running_index {todo_u['running_index']} in {db_name} for {rc.assigned_to} has been updated.")
                                return
        return
