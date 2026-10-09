import unittest

from app.triage import (
    Alert,
    analyst_notes,
    case_summary,
    false_positive_handling,
    load_alerts,
    load_config,
    recommendation,
    triage,
)
from datetime import datetime


class SocTriageTests(unittest.TestCase):
    def test_critical_case_gets_top_priority(self):
        alerts = [
            Alert(datetime(2026, 7, 4, 9, 0), "fail", "high", "1.1.1.1", "web-01", "admin", "Credential Access"),
            Alert(datetime(2026, 7, 4, 9, 1), "success", "critical", "1.1.1.1", "web-01", "admin", "Initial Access"),
        ]

        cases = triage(alerts)

        self.assertEqual(cases[0]["source_ip"], "1.1.1.1")
        self.assertGreaterEqual(cases[0]["priority"], 90)

    def test_recommendation_escalates_highest_priority(self):
        self.assertIn("Escalate", recommendation(95))

    def test_case_contains_mitre_and_sla_context(self):
        alerts = [
            Alert(
                datetime(2026, 7, 4, 9, 0),
                "Successful login after failures",
                "critical",
                "1.1.1.1",
                "web-01",
                "admin",
                "Initial Access",
            )
        ]

        case = triage(alerts, load_config())[0]

        self.assertIn("T1078", case["mitre"])
        self.assertEqual(case["sla"], "Immediate escalation")
        self.assertIn("Priority", case_summary(case))

    def test_false_positive_guidance_is_preserved(self):
        alerts = [
            Alert(
                datetime(2026, 7, 4, 9, 0),
                "Known scanner",
                "low",
                "203.0.113.9",
                "portal-01",
                "-",
                "Reconnaissance",
                false_positive_hint="Confirm this is not an approved scanner.",
            )
        ]

        case = triage(alerts)[0]

        self.assertIn("approved scanner", case["false_positive_handling"])

    def test_sample_data_loads_and_creates_multiple_cases(self):
        alerts = load_alerts("sample_data/alerts.json")
        cases = triage(alerts)

        self.assertGreaterEqual(len(alerts), 8)
        self.assertGreaterEqual(len(cases), 4)
        self.assertIn("analyst_notes", cases[0])
        self.assertIn("false_positive_handling", cases[0])

    def test_default_notes_are_generated_when_missing(self):
        alerts = [
            Alert(datetime(2026, 7, 4, 9, 0), "Discovery", "medium", "10.0.0.5", "host-1", "alice", "Discovery")
        ]

        self.assertIn("alice", analyst_notes(alerts))
        self.assertIn("maintenance windows", false_positive_handling(alerts))


if __name__ == "__main__":
    unittest.main()
