Feature: pubhost site check reads a built site as robots and other sites do
  A public site's pages name their language, title and description, and
  carry an Open Graph card whose image is large enough for LinkedIn's large
  preview, unless they ask not to be indexed. robots.txt lets the link-preview bots in, even where it keeps
  search engines out. deploy-static runs the check before every deploy.
  Each rule has an ID, and pubrules.json can declare an exception to it.

  Background:
    Given a scratch directory
    And the program under test is "pubhost"
    And a file "_site/index.html" holding:
      """
      <!doctype html>
      <html lang="en">
      <head>
      <meta charset="utf-8">
      <title>Example</title>
      <meta name="description" content="An example site.">
      <meta property="og:type" content="website">
      <meta property="og:title" content="Example">
      <meta property="og:description" content="An example site.">
      <meta property="og:url" content="https://example.eu/">
      <meta property="og:image" content="https://example.eu/card.png">
      <meta property="og:image:width" content="1200">
      <meta property="og:image:height" content="630">
      <meta name="twitter:card" content="summary_large_image">
      </head>
      <body><h1>Example</h1></body>
      </html>
      """
    And the site's card is a 1200×630 PNG

  Scenario: A complete site passes
    When I run "pubhost site check _site --url https://example.eu"
    Then it succeeds
    And it prints "1 page(s) meet the 6 site rules"

  Scenario: Without --url the pages are checked, and the images are not looked for
    Given the file "_site/card.png" is removed
    When I run "pubhost site check _site"
    Then it succeeds
    And it prints "give --url to check the og:image files too"

  Scenario: A page with no language, description or card fails, naming each rule
    Given a file "_site/about/index.html" holding "<!doctype html><html><head><title>About</title></head><body></body></html>"
    When I run "pubhost site check _site --url https://example.eu"
    Then it fails
    And stderr mentions "WEB-PAGE-01 about/index.html: no <html lang>"
    And stderr mentions "WEB-PAGE-02 about/index.html: no <meta name="
    And stderr mentions "WEB-OG-01 about/index.html: no og:title, og:description, og:type, og:url, og:image"
    And stderr mentions "WEB-OG-03 about/index.html"
    And stderr does not mention "WEB-PAGE-02 index.html"

  Scenario: An og:image smaller than LinkedIn's large card fails
    Given the site's card is a 640×480 JPEG
    When I run "pubhost site check _site --url https://example.eu"
    Then it fails
    And stderr mentions "og:image https://example.eu/card.png is 640×480; make it at least 1200×627"
    And stderr mentions "og:image:width says 1200, but https://example.eu/card.png is 640"

  Scenario: An og:image that is not a PNG or JPEG fails
    Given the site's card is a WebP
    When I run "pubhost site check _site --url https://example.eu"
    Then it fails
    And stderr mentions "is not a PNG or JPEG, which LinkedIn needs"

  Scenario: An og:image missing from the site fails
    Given the file "_site/card.png" is removed
    When I run "pubhost site check _site --url https://example.eu"
    Then it fails
    And stderr mentions "WEB-OG-02 index.html: og:image https://example.eu/card.png is not in the site"

  Scenario: A robots.txt that keeps everyone out hides the card
    Given a file "_site/robots.txt" holding:
      """
      User-agent: *
      Disallow: /
      """
    When I run "pubhost site check _site --url https://example.eu"
    Then it fails
    And stderr mentions "WEB-ROBOTS-01 robots.txt keeps LinkedInBot from https://example.eu/, https://example.eu/card.png"
    And stderr mentions "robots.txt keeps facebookexternalhit from"

  Scenario: A robots.txt that keeps search engines out but lets preview bots in passes
    Given a file "_site/robots.txt" holding:
      """
      User-agent: LinkedInBot
      User-agent: facebookexternalhit
      User-agent: Twitterbot
      User-agent: Slackbot
      Allow: /

      User-agent: *
      Disallow: /
      """
    When I run "pubhost site check _site --url https://example.eu"
    Then it succeeds

  Scenario: Redirects and the 404 page are not checked
    Given a file "_site/old/index.html" holding "<meta http-equiv="refresh" content="0; url=/">"
    And a file "_site/404.html" holding "<title>Not found</title>"
    When I run "pubhost site check _site --url https://example.eu"
    Then it succeeds
    And it prints "1 page(s) meet"

  Scenario Outline: A page that asks not to be indexed needs no description or card
    Given a file "_site/status/index.html" holding:
      """
      <!doctype html><html lang="en"><head><title>Storage</title><meta name="robots"
      content="<robots>"></head><body></body></html>
      """
    When I run "pubhost site check _site --url https://example.eu"
    Then it succeeds
    And it prints "2 page(s) meet"

    Examples:
      | robots            |
      | noindex           |
      | NOINDEX, NOFOLLOW |
      | nofollow,noindex  |
      | none              |

  Scenario: A page that asks not to be indexed still names its language and title
    Given a file "_site/status/index.html" holding "<!doctype html><html><head><title>Storage</title><meta name="robots" content="noindex"></head><body></body></html>"
    And a file "_site/robots.txt" holding:
      """
      User-agent: *
      Disallow: /status/
      """
    When I run "pubhost site check _site --url https://example.eu"
    Then it fails
    And stderr mentions "WEB-PAGE-01 status/index.html: no <html lang>"
    And stderr does not mention "WEB-PAGE-02 status/index.html"
    And stderr does not mention "WEB-OG-01 status/index.html"
    And stderr does not mention "WEB-OG-03 status/index.html"
    And stderr does not mention "WEB-ROBOTS-01"

  Scenario: nofollow alone still asks for the card
    Given a file "_site/status/index.html" holding "<!doctype html><html lang="en"><head><title>Storage</title><meta name="robots" content="nofollow"></head><body></body></html>"
    When I run "pubhost site check _site --url https://example.eu"
    Then it fails
    And stderr mentions "WEB-PAGE-02 status/index.html: no <meta name="
    And stderr mentions "WEB-OG-01 status/index.html"

  Scenario: A declared exception waives its rule and is listed as open
    Given a file "_site/about/index.html" holding "<!doctype html><html><head><title>About</title></head><body></body></html>"
    And a file "pubrules.json" holding:
      """
      {
        "kind": "service",
        "exceptions": [
          {
            "rule": "WEB-PAGE-01",
            "reason": "the card is coming",
            "until": "2099-01-01"
          },
          {
            "rule": "WEB-PAGE-02",
            "reason": "the card is coming",
            "until": "2099-01-01"
          },
          {
            "rule": "WEB-OG-01",
            "reason": "the card is coming",
            "until": "2099-01-01"
          },
          {
            "rule": "WEB-OG-03",
            "reason": "the card is coming",
            "until": "2099-01-01"
          }
        ]
      }
      """
    And the environment sets "PUBHOST_TODAY" to "2026-10-28"
    When I run "pubhost site check _site --url https://example.eu"
    Then it succeeds
    And it prints "open exception: WEB-OG-01 until 2099-01-01"
    And it prints "2 page(s) meet the 2 site rules"

  Scenario: An expired exception fails
    Given a file "pubrules.json" holding:
      """
      {
        "kind": "service",
        "exceptions": [
          {
            "rule": "WEB-OG-03",
            "reason": "the card is coming",
            "until": "2020-01-01"
          }
        ]
      }
      """
    And the environment sets "PUBHOST_TODAY" to "2026-10-28"
    When I run "pubhost site check _site --url https://example.eu"
    Then it fails
    And stderr mentions "WEB-OG-03: the exception expired on 2020-01-01"

  Scenario: A directory with no pages fails
    When I run "pubhost site check _site/about-nothing --url https://example.eu"
    Then it fails
    And stderr mentions "is not a directory; build the site first"
