# Plan Walkthrough

This document provides a step-by-step walkthrough of how the `ExecutionContext` evolves during the execution of the sample plan defined in `sample_plan.yaml`.

## Initial State
- **Variables**: None
- **Results**: {}
- **Current Step**: `step1`

## Step-by-Step Execution

### Step 1: `call_ai`
- **Action**: Generate a summary.
- **Mock Output**: `"Generated summary text"`
- **Results After Step**:
  ```json
  {
    "step1": {
      "output": "Generated summary text"
    }
  }
  ```
- **Next Step**: `step2`

### Step 2: `eval`
- **Action**: Evaluate the expression `len(results['step1'].output) > 0`.
- **Mock Output**: `true`
- **Results After Step**:
  ```json
  {
    "step1": {
      "output": "Generated summary text"
    },
    "step2": {
      "value": true
    }
  }
  ```
- **Next Step**: `step3`

### Step 3: `notify`
- **Action**: Notify with the message `"Summary generated successfully."`.
- **Results After Step**:
  ```json
  {
    "step1": {
      "output": "Generated summary text"
    },
    "step2": {
      "value": true
    },
    "step3": {
      "notification": "Summary generated successfully."
    }
  }
  ```
- **Next Step**: `step4`

### Step 4: `wait`
- **Action**: Wait for 5 seconds.
- **Results After Step**:
  ```json
  {
    "step1": {
      "output": "Generated summary text"
    },
    "step2": {
      "value": true
    },
    "step3": {
      "notification": "Summary generated successfully."
    },
    "step4": {
      "status": "completed"
    }
  }
  ```
- **Next Step**: None (Plan completed).

## Conditional Branching

### Failure in Step 1
- **Action**: Notify with the message `"Step 1 failed."`.
- **Results**:
  ```json
  {
    "step1": {
      "error": "Step 1 failed."
    }
  }
  ```

### Failure in Step 2
- **Action**: Notify with the message `"Step 2 evaluation failed."`.
- **Results**:
  ```json
  {
    "step1": {
      "output": "Generated summary text"
    },
    "step2": {
      "error": "Step 2 evaluation failed."
    }
  }
  ```

## Notification Templates
- **Success**: `"Summary generated successfully."`
- **Failure**: `"Step 1 failed."`, `"Step 2 evaluation failed."`

## Final Rendered Output
- **Success Path**:
  ```json
  {
    "step1": {
      "output": "Generated summary text"
    },
    "step2": {
      "value": true
    },
    "step3": {
      "notification": "Summary generated successfully."
    },
    "step4": {
      "status": "completed"
    }
  }
  ```
- **Failure Path**:
  See "Conditional Branching" section.