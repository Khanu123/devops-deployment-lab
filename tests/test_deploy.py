import copy
import unittest

from scripts.deploy import prepare_task, validate_rollout

IMAGE = "123456789012.dkr.ecr.eu-west-2.amazonaws.com/devops-lab@sha256:" + "a" * 64
VERSION = "b" * 40


class DeployTests(unittest.TestCase):
    def setUp(self):
        self.task = {"family": "devops-lab", "taskDefinitionArn": "old", "revision": 2, "status": "ACTIVE",
                     "containerDefinitions": [{"name": "dashboard", "image": "old", "readonlyRootFilesystem": True,
                                               "environment": [{"name": "APP_VERSION", "value": "old"}, {"name": "APP_FAIL_READINESS", "value": "true"}]}]}

    def test_release_update_preserves_security_and_removes_aws_read_only_fields(self):
        before = copy.deepcopy(self.task)
        new = prepare_task(self.task, IMAGE, VERSION)
        self.assertNotIn("revision", new)
        self.assertNotIn("taskDefinitionArn", new)
        self.assertTrue(new["containerDefinitions"][0]["readonlyRootFilesystem"])
        self.assertEqual(new["containerDefinitions"][0]["environment"], [{"name": "APP_VERSION", "value": VERSION}])
        self.assertEqual(self.task, before)

    def test_mutable_tag_and_other_family_are_rejected(self):
        with self.assertRaises(ValueError):
            prepare_task(self.task, IMAGE.split("@")[0] + ":latest", VERSION)
        self.task["family"] = "other"
        with self.assertRaises(ValueError):
            prepare_task(self.task, IMAGE, VERSION)

    def test_stable_automatic_rollback_is_not_success(self):
        service = {"runningCount": 1, "deployments": [{"status": "PRIMARY", "taskDefinition": "old", "rolloutState": "COMPLETED"}]}
        with self.assertRaises(RuntimeError):
            validate_rollout(service, "new")

    def test_exact_completed_release_is_success(self):
        validate_rollout({"runningCount": 1, "deployments": [{"status": "PRIMARY", "taskDefinition": "new", "rolloutState": "COMPLETED"}]}, "new")

    def test_in_progress_or_zero_running_tasks_are_rejected(self):
        for state, count in [("IN_PROGRESS", 1), ("COMPLETED", 0)]:
            with self.assertRaises(RuntimeError):
                validate_rollout({"runningCount": count, "deployments": [{"status": "PRIMARY", "taskDefinition": "new", "rolloutState": state}]}, "new")
