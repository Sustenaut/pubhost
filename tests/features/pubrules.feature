Feature: pubhost uses pubrules as a library, through the names its README lists
  pubhost reads pubrules.json's hosting block through pubrules' own check of it,
  so it imports pubrules rather than copying it. pubrules never imports pubhost,
  and names nothing of it. The names pubhost takes are listed here, and in
  the README, so a pubrules change that drops one fails this suite first.

  Scenario: pubhost imports from pubrules only the names its README lists
    When I read every import of pubrules in src/pubhost
    Then each is one the README lists under "What pubhost takes from pubrules"
    And the README lists none that pubhost does not import

  Scenario: Every name pubhost takes from pubrules is in the pubrules installed
    When I read every import of pubrules in src/pubhost
    Then the installed pubrules has each of them

  Scenario: pubhost says its version
    Given a scratch directory
    And the program under test is "pubhost"
    When I run "pubhost --version"
    Then it succeeds
    And it prints "pubhost "

  Scenario: The modules and pubrules' hosting check read the same hosting block
    The hosting block's shape is pubrules', and the modules' variable types are
    pubhost's. Both read terraform/testdata/pubrules.json, which the modules'
    own tests use, so a setting one side accepts and the other drops shows.
    When pubrules' hosting check reads terraform/testdata/pubrules.json
    Then it accepts it
    And every setting it names is one the hosting module's config variable declares
