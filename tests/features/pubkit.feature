Feature: pubhost uses pubkit as a library, through the names its README lists
  pubhost reads pubkit.json's hosting block through pubkit's own check of it,
  so it imports pubkit rather than copying it. pubkit never imports pubhost,
  and names nothing of it. The names pubhost takes are listed here, and in
  the README, so a pubkit change that drops one fails this suite first.

  Scenario: pubhost imports from pubkit only the names its README lists
    When I read every import of pubkit in src/pubhost
    Then each is one the README lists under "What pubhost takes from pubkit"
    And the README lists none that pubhost does not import

  Scenario: Every name pubhost takes from pubkit is in the pubkit installed
    When I read every import of pubkit in src/pubhost
    Then the installed pubkit has each of them

  Scenario: pubhost says its version
    When I run pubhost "--version"
    Then it succeeds
    And it prints "pubhost "

  Scenario: The modules and pubkit's hosting check read the same hosting block
    The hosting block's shape is pubkit's, and the modules' variable types are
    pubhost's. Both read terraform/testdata/pubkit.json, which the modules'
    own tests use, so a setting one side accepts and the other drops shows.
    When pubkit's hosting check reads terraform/testdata/pubkit.json
    Then it accepts it
    And every setting it names is one the hosting module's config variable declares
