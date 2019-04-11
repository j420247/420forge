Feature: As a service actor,
            I want to be be able to create or upgrade a DR or Staging service by UI

  Scenario: AcForge service index page returns expected status_code
   Given acforge is set up
   When i browse to the acforge index
    Then i should receive a 200

  Scenario: AcForge service index page returns expected title
     Given acforge is set up
     When i browse to the acforge index
      Then i see the "Atlassian Cloudformation Forge" title

  Scenario: AcForge index.html presents an environment of "Staging"
   Given acforge is set up
   When i browse to the acforge index
    Then i see an option of staging

  Scenario: AcForge index.html presents an environment of "Production"
   Given acforge is set up
   When i browse to the acforge index
    Then i see an option of production

  Scenario: AcForge index.html presents an "upgrade" option
     Given acforge is set up
     When i browse to the acforge index
      Then i see an option to upgrade

  Scenario: AcForge index.html presents a "fullrestart" option
     Given acforge is set up
     When i browse to the acforge index
      Then i see an option to fullrestart

  Scenario: AcForge index.html presents a "rollingrestart" option
   Given acforge is set up
   When i browse to the acforge index
    Then i see an option to rollingrestart

  Scenario: AcForge index.html for staging environment presents a "clone" option
     Given acforge is set up
     When i select staging on acforge index
      Then i see an option to clone

  Scenario: AcForge index.html for staging environment presents a "destroy" option
     Given acforge is set up
     When i select staging on acforge index
      Then i see an option to destroy

  Scenario: after environment is set and i chose an action, the "stack selection" form is presented
     Given environment has a value
     When i select an action on acforge index
      Then i see the stack_selection form

  Scenario: after action is set and i chose an environment, the "stack selection" form is presented
     Given action has a value
     When i select an environment on acforge index
      Then i see the stack_selection form

#  Scenario: Upgrade dash presented
#     Given acforge is setup
#      When i login with "admin" and "default"
#      Then i should see the alert "You were logged in"
#
#  Scenario: "Upgrade or Clone or Restart" option shown
#     Given acforge is setup
#      When i login with "monty" and "default"
#      Then i should see the alert "Invalid username"
#
#  Scenario: on "upgrade", List of existing stacks presented
#     Given acforge is setup
#      When i login with "admin" and "python"
#      Then  i should see the alert "Invalid password"
#
#  Scenario: on "rebuild", List of restore points presented
#     Given acforge is setup
#      When i login with "admin" and "python"
#      Then  i should see the alert "Invalid password"
#
#  Scenario: Aws Tags derived for charging
#     Given acforge is setup
#     and i login with "admin" and "default"
#      When i logout
#      Then  i should see the alert "You were logged out"
#
#  Scenario: Duo requested on upgrade/build
#     Given acforge is setup
#     and i login with "admin" and "default"
#      When i logout
#      Then  i should see the alert "You were logged out"
#
#  Scenario: progress bar presented based upon cfn events list
#     Given acforge is setup
#     and i login with "admin" and "default"
#      When i logout
#      Then  i should see the alert "You were logged out"
#
#  Scenario: bring up 1 cluster node then bring up required others in sequence
#     Given acforge is setup
#     and i login with "admin" and "default"
#      When i logout
#      Then  i should see the alert "You were logged out"steps here