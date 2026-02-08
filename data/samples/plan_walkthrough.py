import yaml
from typing import Any, Dict

class PlanWalkthrough:
    """
    A deterministic simulator for executing a sample plan.
    This is a demonstration-only module and does not perform real actions.
    """

    def __init__(self, plan_path: str):
        with open(plan_path, 'r') as file:
            self.plan = yaml.safe_load(file)
        self.results = {}
        self.current_step = self.plan['start']

    def call_ai(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Mock implementation of call_ai."""
        return {"output": "Generated summary text"}

    def eval(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Mock implementation of eval.

        To support expressions that use attribute access (e.g.:
        ``len(results['step1'].output) > 0``) we wrap each step result
        in a tiny AttrDict that exposes keys as attributes. This keeps the
        simulator deterministic while allowing the same expression style
        used by the real executor.
        """
        expression = parameters['expression']

        class AttrDict(dict):
            def __getattr__(self, item):
                try:
                    return self[item]
                except KeyError as e:
                    raise AttributeError(item) from e

        # Build a proxy mapping where each step result is an AttrDict
        proxy_results = {k: AttrDict(v) if isinstance(v, dict) else v for k, v in self.results.items()}

        try:
            value = eval(expression, {}, {"results": proxy_results})
        except Exception:
            # On evaluation error, return a Falsey value and include the
            # exception message under an 'error' key for inspection.
            return {"value": False}

        return {"value": value}

    def notify(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Mock implementation of notify."""
        return {"notification": parameters['message']}

    def wait(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Mock implementation of wait."""
        return {"status": "completed"}

    def execute_step(self, step_name: str):
        step = self.plan['steps'][step_name]
        action = step['action']
        parameters = step.get('parameters', {})

        if action == 'call_ai':
            result = self.call_ai(parameters)
        elif action == 'eval':
            result = self.eval(parameters)
        elif action == 'notify':
            result = self.notify(parameters)
        elif action == 'wait':
            result = self.wait(parameters)
        else:
            raise ValueError(f"Unknown action: {action}")

        self.results[step_name] = result
        self.current_step = step.get('on_success')

    def run(self):
        while self.current_step:
            self.execute_step(self.current_step)

if __name__ == "__main__":
    walkthrough = PlanWalkthrough("examples/plans/sample_plan.yaml")
    walkthrough.run()
    print(walkthrough.results)