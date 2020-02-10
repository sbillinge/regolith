"""Builder for publication lists."""
import os
import datetime as dt
from copy import copy
from typing import List, Any, Tuple
import openpyxl
from dateutil.relativedelta import relativedelta

try:
    from bibtexparser.bwriter import BibTexWriter
    from bibtexparser.bibdatabase import BibDatabase

    HAVE_BIBTEX_PARSER = True
except ImportError:
    HAVE_BIBTEX_PARSER = False

from regolith.tools import all_docs_from_collection, filter_publications, \
    is_since, fuzzy_retrieval
from regolith.sorters import doc_date_key, ene_date_key, position_key
from regolith.builders.basebuilder import LatexBuilderBase, BuilderBase, latex_safe

# specifying border and font style
from openpyxl.styles import Font, Border, Side
font = Font(bold=False, italic=False)
border = Border(left=Side(border_style='thin', color='00000000'),
                right=Side(border_style='thin', color='00000000'),
                top=Side(border_style='thin', color='00000000'),
                bottom=Side(border_style='thin', color='FF000000'))

COAUTHOR_TABLE_OFFFSET = 50
NUM_MONTHS = 48
ID = "sbillinge"
LATEX_OPTS = ["-halt-on-error", "-file-line-error"]

class RecentCollabsBuilder(LatexBuilderBase):
    btype = "recent-collabs"

    def construct_global_ctx(self):
        super().construct_global_ctx()
        gtx = self.gtx
        rc = self.rc

        gtx["people"] = sorted(
            all_docs_from_collection(rc.client, "people"),
            key=position_key,
            reverse=True,
        )
        gtx["contacts"] = sorted(
            all_docs_from_collection(rc.client, "contacts"),
            key=position_key,
            reverse=True,
        )
        gtx["institutions"] = all_docs_from_collection(rc.client,
                                                       "institutions")
        gtx["citations"] = all_docs_from_collection(rc.client, "citations")
        gtx["all_docs_from_collection"] = all_docs_from_collection

    def get_ppl_inst_info(self, id, months):
        """
        return a list of tuples, (c/a, people, institution) who has collaborated with
        the person with the given id within the given number months from today
        Parameters
        ----------
        id : str
            the id of the person for whom the collaborator list is being built (i.e. "sbillinge")
        months : int
            the number of months from today to go back in time when searching for jointly authored papers
        Returns
        -------
        ppl : list of tuples
            each tuple is of the form (c/a, people, institution)
            - c/a : str
                categories, either collaborator ('C') or co-author ('A'). here data is pulled
                from publications so assuming that all are authors ('A'). Refer to the excel template
                'coa_template.xlsx' for more information
            - people : str
                name
            - institution : str
                institution
        """
        rc = self.rc
        since_date = dt.date.today() - relativedelta(months=months)
        for p in self.gtx["people"]:
            if p["_id"] == id:
                my_names = frozenset(p.get("aka", []) + [p["name"]])
                pubs = filter_publications(self.gtx["citations"], my_names,
                                           reverse=True, bold=False)
                my_collabs = []
                for pub in pubs:
                    if is_since(pub.get("year"), since_date.year,
                                pub.get("month", 1), since_date.month):
                        if not pub.get("month"):
                            print("WARNING: {} is missing month".format(
                                pub["_id"]))
                        my_collabs.extend([collabs for collabs in
                                           [names for names in
                                            pub.get('author', [])]])
                people, institutions = [], []
                my_collabs_set = set(my_collabs)
                for collab in my_collabs_set:
                    person = fuzzy_retrieval(all_docs_from_collection(
                        rc.client, "people"),
                        ["name", "aka", "_id"],
                        collab)
                    if not person:
                        person = fuzzy_retrieval(all_docs_from_collection(
                            rc.client, "contacts"),
                            ["name", "aka", "_id"], collab)
                        if not person:
                            print(
                                "WARNING: {} not found in contacts. Check aka".format(
                                    collab))
                        else:
                            people.append(person)
                            inst = fuzzy_retrieval(all_docs_from_collection(
                                rc.client, "institutions"),
                                ["name", "aka", "_id"],
                                person["institution"])
                            if inst:
                                institutions.append(inst["name"])
                            else:
                                institutions.append(
                                    person.get("institution", "missing"))
                                print(
                                    "WARNING: {} missing from institutions".format(
                                        person["institution"]))
                    else:
                        people.append(person)
                        pinst = person.get("employment",
                                           [{"organization": "missing"}])[
                            0]["organization"]
                        inst = fuzzy_retrieval(all_docs_from_collection(
                            rc.client, "institutions"), ["name", "aka", "_id"],
                            pinst)
                        if inst:
                            institutions.append(inst["name"])
                        else:
                            institutions.append(pinst)
                            print(
                                "WARNING: {} missing from institutions".format(
                                    pinst))
                ppl = [('A', person["name"], i, '', '') for
                             person, i in zip(people, institutions) if
                             person]
                emp = p.get("employment", [{"organization": "missing",
                                            "begin_year": 2019}])
                emp.sort(key=ene_date_key, reverse=True)
        return ppl

    def make_excel(self, ppl):
        """
        function to fill in the 'coa_template.xlsx' with the people and institutions
        information, output from self.get_ppl_inst_info(id, months)
        Parameters
        ----------
        ppl : list of tuples
            the collaborator information for the rows in the csv and excel files
        Returns
        -------
        None
        """
        # fill in excel
        coa_excel_file = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                      "templates", "coa_template.xlsx")
        # loading excel file
        wb = openpyxl.load_workbook(coa_excel_file)
        ws = wb.worksheets[0]
        num_rows = len(ppl)  # number of rows to be added to the excel
        num_colns = len(ppl[0])  # number of columns
        # add empty rows below the header
        ws.insert_rows(COAUTHOR_TABLE_OFFFSET + 1, num_rows)
        # openpyxl index column and row from 1 instead
        # filling in the info
        for row_idx in range(1, num_rows + 1):
            for col_idx in range(1, num_colns + 1):
                cell = ws.cell(row=row_idx + COAUTHOR_TABLE_OFFFSET, column=col_idx)
                cell.value = ppl[row_idx-1][col_idx - 1]
                cell.font = font
                cell.border = border
        wb.save(os.path.join(self.bldir, "coa_table.xlsx"))

    def latex(self):
        """
        function that calls the get_ppl_inst_info and make_csv_and_excel methods
        to produce a .csv and a .xlsx file with information about collaborators who
        worked with ID in the past NUM_MONTHS months. ID and NUM_MONTHS declared at the top
        of the code.
        Returns
        -------
        None
        """
        rc = self.rc
        ppl = self.get_ppl_inst_info(ID, NUM_MONTHS)
        self.make_excel(ppl)

    def make_bibtex_file(self, pubs, pid, person_dir="."):
        if not HAVE_BIBTEX_PARSER:
            return None
        skip_keys = set(["ID", "ENTRYTYPE", "author"])
        self.bibdb.entries = ents = []
        for pub in pubs:
            ent = dict(pub)
            ent["ID"] = ent.pop("_id")
            ent["ENTRYTYPE"] = ent.pop("entrytype")
            ent["author"] = " and ".join(ent["author"])
            for key in ent.keys():
                if key in skip_keys:
                    continue
            ents.append(ent)
        fname = os.path.join(person_dir, pid) + ".bib"
        with open(fname, "w", encoding='utf-8') as f:
            f.write(self.bibwriter.write(self.bibdb))
        return fname
