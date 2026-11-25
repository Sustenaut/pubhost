Feature: terraform.yml gives Terraform the repository variables tf_vars names
  The reusable workflow's step "Give Terraform the repository variables tf_vars
  names" is run here as the runner runs it: bash, with NAMES as tf_vars and VARS as
  the calling repository's variables (toJSON(vars)), writing to a GITHUB_ENV file.
  Each named variable becomes TF_VAR_ and its name in lower case.

  Background:
    Given a scratch directory

  Scenario: The workflow takes tf_vars, empty by default
    When the workflow's input "tf_vars" is read
    Then the result is:
      """
      {"description": "The calling repository's variables Terraform gets, by name, separated by spaces or commas; each becomes TF_VAR_ and its name in lower case, so SLA is var.sla. None by default.",
       "type": "string", "default": ""}
      """

  Scenario: A variable of many lines reaches Terraform whole, as TF_VAR_ and its lower-case name
    When the tf_vars step runs with tf_vars "SLA" and the variables:
      """
      {"SLA": "{\n  \"uptime\": [],\n  \"senders\": []\n}", "OTHER": "x"}
      """
    Then it succeeds
    And it prints "tf_vars: SLA is TF_VAR_sla"
    And Terraform gets "TF_VAR_sla" as:
      """
      {
        "uptime": [],
        "senders": []
      }
      """
    And Terraform gets no "TF_VAR_other"

  Scenario: Names separated by commas or spaces each reach Terraform
    When the tf_vars step runs with tf_vars "SLA, REGION ZONE" and the variables:
      """
      {"SLA": "{}", "REGION": "europe-north1", "ZONE": "a"}
      """
    Then it succeeds
    And Terraform gets "TF_VAR_sla" as "{}"
    And Terraform gets "TF_VAR_region" as "europe-north1"
    And Terraform gets "TF_VAR_zone" as "a"

  Scenario: A variable the repository doesn't have is left out, and Terraform takes its default
    When the tf_vars step runs with tf_vars "SLA" and the variables:
      """
      {"OTHER": "x"}
      """
    Then it succeeds
    And it prints "the repository has no variable SLA, so Terraform takes its default"
    And Terraform gets no "TF_VAR_sla"

  Scenario: A name that isn't a variable's fails the run
    When the tf_vars step runs with tf_vars "SLA $(x)" and the variables:
      """
      {"SLA": "{}"}
      """
    Then it fails
    And it prints "tf_vars: $(x) is not a variable's name"

  Scenario: The step runs only when tf_vars names something
    When the tf_vars step's condition is read
    Then the result is "inputs.tf_vars != ''"
