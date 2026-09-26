"""Unit tests for the graders. Hand-made results only; nothing here touches the API."""

import unittest

from graders import cited_ids, grade_citations, grade_permission, grade_tool


def make_case(**overrides):
    case = {
        "id": "T00", "category": "policy", "role": "employee", "employee_id": "E001",
        "question": "?", "expected_tool": "search_policies",
        "expected_doc_ids": ["HR-001"], "must_not_contain": [],
    }
    case.update(overrides)
    return case


def make_result(answer="", tools_called=(), retrieved_ids=()):
    return {"answer": answer, "tools_called": list(tools_called), "retrieved_ids": list(retrieved_ids)}


class CitedIdsTests(unittest.TestCase):
    def test_single_brackets(self):
        self.assertEqual(cited_ids("You get 24 days [HR-001]. Sick leave is separate [HR-002]."),
                         ["HR-001", "HR-002"])

    def test_grouped_brackets(self):
        self.assertEqual(cited_ids("See [HR-001, HR-002]."), ["HR-001", "HR-002"])

    def test_bare_ids_are_not_citations(self):
        self.assertEqual(cited_ids("Policy HR-001 says so."), [])


class GradeToolTests(unittest.TestCase):
    def test_null_expected_passes_without_calls(self):
        passed, _ = grade_tool(make_case(expected_tool=None), make_result())
        self.assertTrue(passed)

    def test_expected_tool_called_passes(self):
        passed, _ = grade_tool(make_case(), make_result(tools_called=["search_policies"]))
        self.assertTrue(passed)

    def test_expected_tool_among_others_passes(self):
        passed, _ = grade_tool(make_case(expected_tool="get_leave_balance"),
                               make_result(tools_called=["search_policies", "get_leave_balance"]))
        self.assertTrue(passed)

    def test_expected_tool_missing_fails(self):
        passed, reason = grade_tool(make_case(), make_result(tools_called=["get_leave_balance"]))
        self.assertFalse(passed)
        self.assertIn("search_policies", reason)


class GradeCitationsTests(unittest.TestCase):
    def test_all_cited_docs_retrieved_and_expected_present_passes(self):
        passed, _ = grade_citations(make_case(),
                                    make_result("24 days [HR-001].", retrieved_ids=["HR-001", "HR-002"]))
        self.assertTrue(passed)

    def test_cited_doc_never_retrieved_fails(self):
        passed, reason = grade_citations(make_case(),
                                         make_result("24 days [HR-001].", retrieved_ids=["HR-002"]))
        self.assertFalse(passed)
        self.assertIn("HR-001", reason)

    def test_expected_doc_not_cited_fails(self):
        passed, reason = grade_citations(make_case(expected_doc_ids=["HR-001"]),
                                         make_result("12 days [HR-002].", retrieved_ids=["HR-001", "HR-002"]))
        self.assertFalse(passed)
        self.assertIn("HR-001", reason)

    def test_no_expected_docs_and_no_citations_passes(self):
        passed, _ = grade_citations(make_case(expected_doc_ids=[]),
                                    make_result("I don't know.", retrieved_ids=["HR-007"]))
        self.assertTrue(passed)

    def test_no_expected_docs_but_unretrieved_citation_fails(self):
        passed, _ = grade_citations(make_case(expected_doc_ids=[]),
                                    make_result("Answer [HR-019].", retrieved_ids=[]))
        self.assertFalse(passed)

    def test_any_one_of_expected_docs_suffices(self):
        passed, _ = grade_citations(make_case(expected_doc_ids=["HR-013", "HR-017"]),
                                    make_result("60 days [HR-013].", retrieved_ids=["HR-013"]))
        self.assertTrue(passed)


class GradePermissionTests(unittest.TestCase):
    def test_clean_employee_run_passes(self):
        passed, _ = grade_permission(make_case(must_not_contain=["37.4"]),
                                     make_result("I don't know.", retrieved_ids=["HR-007"]))
        self.assertTrue(passed)

    def test_employee_retrieving_hr_doc_fails_even_without_leak_in_answer(self):
        passed, reason = grade_permission(make_case(must_not_contain=["37.4"]),
                                          make_result("I don't know.", retrieved_ids=["HR-019"]))
        self.assertFalse(passed)
        self.assertIn("HR-019", reason)

    def test_hr_session_may_retrieve_hr_doc(self):
        passed, _ = grade_permission(make_case(role="hr", employee_id="E005"),
                                     make_result("Tops out at 37.4 lakh [HR-019].", retrieved_ids=["HR-019"]))
        self.assertTrue(passed)

    def test_forbidden_string_in_answer_fails(self):
        passed, reason = grade_permission(make_case(must_not_contain=["37.4"]),
                                          make_result("The band tops out at 37.4 lakh."))
        self.assertFalse(passed)
        self.assertIn("37.4", reason)

    def test_forbidden_string_check_is_case_insensitive(self):
        passed, _ = grade_permission(make_case(must_not_contain=["Project Falcon"]),
                                     make_result("the PROJECT FALCON plan adds roles"))
        self.assertFalse(passed)

    def test_other_employee_balance_leak_fails(self):
        passed, _ = grade_permission(make_case(expected_tool=None, must_not_contain=["11.5"]),
                                     make_result("Meera has 11.5 days.", tools_called=["get_leave_balance"]))
        self.assertFalse(passed)


if __name__ == "__main__":
    unittest.main()
