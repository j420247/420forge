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

  Scenario: AcForge index.html presents an "upgrade" option
     Given acforge is set up
     When i browse to the acforge index
      Then i see an option to upgrade

  Scenario: AcForge index.html presents an "clone" option
     Given acforge is set up
     When i browse to the acforge index
      Then i see an option to clone

  Scenario: AcForge index.html presents an "restart" option
     Given acforge is set up
     When i browse to the acforge index
      Then i see an option to restart

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