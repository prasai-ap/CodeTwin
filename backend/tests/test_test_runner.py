from codetwin.test_runner import run_targeted_tests


def test_runner_reports_passing_and_failing_targeted_tests():
    files = {
        "tests/test_ok.py": "def test_ok():\n    assert 2 + 2 == 4\n",
        "tests/test_broken.py": "def test_broken():\n    assert 2 + 2 == 5\n",
    }

    passed = run_targeted_tests(files, ["tests/test_ok.py"])
    failed = run_targeted_tests(files, ["tests/test_broken.py"])

    assert passed["status"] == "passed"
    assert passed["passed"] is True
    assert failed["status"] == "failed"
    assert failed["passed"] is False


def test_runner_refuses_paths_outside_snapshot_and_reports_missing_test():
    assert run_targeted_tests({"app/main.py": "pass\n"}, [])["status"] == "no_tests"

    try:
        run_targeted_tests({"tests/test_ok.py": "def test_ok(): pass\n"}, ["../secret.py"])
    except ValueError as error:
        assert "relative" in str(error)
    else:
        raise AssertionError("path traversal should be rejected")
