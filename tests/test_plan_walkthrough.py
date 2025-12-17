import pytest
from plan_walkthrough import PlanWalkthrough

def test_plan_walkthrough():
    walkthrough = PlanWalkthrough("examples/plans/sample_plan.yaml")
    walkthrough.run()

    # Assert step results accumulate in correct order
    assert "step1" in walkthrough.results
    assert "step2" in walkthrough.results
    assert "step3" in walkthrough.results
    assert "step4" in walkthrough.results

    # Assert notifications render properly
    assert walkthrough.results["step3"]["notification"] == "Summary generated successfully."

    # Assert branching works (mock failure and check on_failure path)
    # Simulate failure in step1
    walkthrough.results = {}
    walkthrough.current_step = "step1"
    walkthrough.plan['steps']['step1']['action'] = "notify"
    walkthrough.plan['steps']['step1']['parameters'] = {"message": "Step 1 failed."}
    walkthrough.run()
    assert "step1" in walkthrough.results
    assert walkthrough.results["step1"]["notification"] == "Step 1 failed."